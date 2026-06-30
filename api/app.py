import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager

import modal
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.features.assets.router import init_assets, get_service as get_assets_service, router as assets_router
from src.features.assets.service import AssetsService
from src.features.generation.router import router as generation_router, set_resolve_asset_url
from src.shared.errors import register_app_error_handlers
from src.shared.logging import get_logger
from src.shared.modal_config import modal_app, comfy_image, model_volume, image_volume, r2_secret, planner_secret, app_config_secret
from src.shared.models.persistence import async_session_factory, close_db, init_db

# Import the Modal tasks so they are registered with the app BEFORE serving
import src.features.generation.modal_tasks  # noqa
import src.shared.workflows.cache  # noqa


# ── resolve_asset_url wiring ───────────────────────────────────────────────────


def _wire_asset_resolver() -> None:
    """Create and register the ``resolve_asset_url`` callback.

    The callback bridges the synchronous ``dispatch_flow`` to the async
    ``AssetsService.get_active_asset`` and ``R2Storage.presigned_get``
    via ``asyncio.run()``.

    When the assets service or its storage is not available, the callback
    is set to ``None`` (asset_id resolution disabled — backward compatible).
    """
    try:
        svc = get_assets_service()
    except RuntimeError:
        _log.warning("asset_resolver_not_wired", _reason="AssetsService not initialised")
        set_resolve_asset_url(None)
        return

    if svc._storage is None:
        _log.warning("asset_resolver_not_wired", _reason="R2Storage not configured")
        set_resolve_asset_url(None)
        return

    async def _resolve_async(asset_id: str, session_id: str) -> str:
        asset = await svc.get_active_asset(asset_id, session_id)
        url = await svc._storage.presigned_get(asset["r2_key"])
        return url

    def _resolve_sync(asset_id: str, session_id: str) -> str:
        return asyncio.run(_resolve_async(asset_id, session_id))

    set_resolve_asset_url(_resolve_sync)
    _log.info("asset_resolver_wired")


# ── Assets Service ────────────────────────────────────────────────────────────


def _init_assets_service() -> None:
    """Create and register the ``AssetsService`` with the module-level router.

    Reads R2 configuration from environment variables.  When any variable is
    missing, the service is created without a storage backend — the
    ``upload-ticket`` endpoint will raise a clear ``RuntimeError`` in that
    case, guiding operators to set the required env vars.
    """
    r2_endpoint = os.environ.get("R2_ENDPOINT")
    r2_access_key = os.environ.get("R2_ACCESS_KEY")
    r2_secret_key = os.environ.get("R2_SECRET_KEY")
    r2_bucket = os.environ.get("R2_BUCKET")

    storage = None
    if r2_endpoint and r2_access_key and r2_secret_key and r2_bucket:
        from src.shared.storage import R2Storage

        storage = R2Storage(
            endpoint_url=r2_endpoint,
            access_key=r2_access_key,
            secret_key=r2_secret_key,
            bucket=r2_bucket,
        )
        _log.info("assets_storage_configured", bucket=r2_bucket)
    else:
        _log.warning(
            "assets_storage_not_configured",
            _reason="R2 env vars not fully set",
        )

    factory = async_session_factory()
    service = AssetsService(session_factory=factory, storage=storage)
    init_assets(service)


# ── Database Lifespan ─────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize the async DB engine on startup and dispose on shutdown.

    Uses ``asyncio.wait_for`` to guard against startup hangs and a
    ``try…finally`` block to ensure the engine is always disposed —
    even when the application crashes during ``yield``.
    """
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:////root/ComfyUI/output/dev.db")
    _log.info("db_startup", url=database_url.split("://")[0] + "://...")
    await asyncio.wait_for(init_db(database_url, echo=False), timeout=10.0)

    # Initialise the Assets service (R2Storage is optional — upload-ticket will
    # raise a clear error when not configured).
    _init_assets_service()

    # Wire the resolve_asset_url callback so generation endpoints can resolve
    # asset_id references to presigned GET URLs for the LoadImageFromUrl node.
    # This bridges the sync dispatch_flow to async AssetsService + R2Storage.
    _wire_asset_resolver()
    try:
        yield
    finally:
        _log.info("db_shutdown")
        await close_db()


# FastAPI ASGI application
fastapi_app = FastAPI(lifespan=lifespan)

# ── Observability ────────────────────────────────────────────────────────────

_log = get_logger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Generate a correlation_id per request, bind it to structlog, and log
    a structured summary after each request completes."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        _log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            correlation_id=correlation_id,
        )

        response.headers["X-Correlation-ID"] = correlation_id
        return response


# Register request-id / request-logging middleware first so it wraps everything.
fastapi_app.add_middleware(RequestLogMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow-list from env (default localhost:3000 for Next.js dev server).
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sentry (gated) ───────────────────────────────────────────────────────────
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration()],
    )
    _log.info("sentry_initialized", dsn_prefix=_sentry_dsn[:20])

# Register global error handlers so custom exceptions produce
# structured JSON responses rather than raw tracebacks.
register_app_error_handlers(fastapi_app)

fastapi_app.include_router(generation_router)
fastapi_app.include_router(assets_router)

# Modal ASGI endpoint to serve the FastAPI application
app = modal_app  # Expose the app instance for 'modal serve' command

@app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
    },
    # Use explicit Modal secrets instead of from_dotenv() which
    # injects ALL local .env variables into the Modal runtime, potentially
    # leaking development secrets.  Create the planner-secret via:
    #   modal secret create planner-secret PLANNER_API_URL=... PLANNER_API_KEY=... PLANNER_MODEL=...
    # Other env vars (DATABASE_URL, CORS_ORIGINS, SENTRY_DSN) are typically
    # production values set via Modal dashboard or CI secrets.
    secrets=[r2_secret] + ([planner_secret] if planner_secret else []) + ([app_config_secret] if app_config_secret else []),
    gpu="T4",
)
@modal.asgi_app()
def asgi_app():
    """Serve the FastAPI application via Modal's ASGI app wrapper."""
    return fastapi_app
