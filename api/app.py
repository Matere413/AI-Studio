import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager

import modal
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.features.generation.router import router as generation_router
from src.shared.errors import register_app_error_handlers
from src.shared.logging import get_logger
from src.shared.modal_config import modal_app, comfy_image, model_volume, image_volume
from src.shared.models.persistence import close_db, init_db

# Import the Modal tasks so they are registered with the app BEFORE serving
import src.features.generation.modal_tasks  # noqa
import src.shared.workflows.cache  # noqa


# ── Database Lifespan ─────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize the async DB engine on startup and dispose on shutdown.

    Uses ``asyncio.wait_for`` to guard against startup hangs and a
    ``try…finally`` block to ensure the engine is always disposed —
    even when the application crashes during ``yield``.
    """
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    _log.info("db_startup", url=database_url.split("://")[0] + "://...")
    await asyncio.wait_for(init_db(database_url, echo=False), timeout=10.0)
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

# Modal ASGI endpoint to serve the FastAPI application
app = modal_app  # Expose the app instance for 'modal serve' command

@app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
    },
    gpu="T4",
)
@modal.asgi_app()
def asgi_app():
    """Serve the FastAPI application via Modal's ASGI app wrapper."""
    return fastapi_app
