from typing import Callable

import mimetypes
import os
from contextlib import contextmanager

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse
from src.features.generation.models import GenerateRequest, GenerateResponse, OrchestrateRequest, OrchestrateResponse
from src.features.generation.planner import PlannerClient
from src.features.generation.service import GenerationService, ModelNotAllowedError
from src.shared.errors import (
    AppError,
    ModelNotAllowedError as AppModelNotAllowedError,
    ModelNotCachedError as AppModelNotCachedError,
    SessionMismatchError,
    UnsupportedWorkflowError,
)
from src.shared.flows.composition import CompositionFlow
from src.shared.flows.extraction import ExtractionFlow
from src.shared.flows.identity import IdentityFlow
from src.shared.job_store import JobStore
from src.shared.workflows.cache import ModelNotCachedError
from src.shared.modal_config import image_volume

router = APIRouter()

# Shared job store instance (MVP in-memory)
_job_store = JobStore()
_service = GenerationService(job_store=_job_store)

# resolve_asset_url callback — set during app lifespan by init_asset_resolver()
# When provided, it is forwarded to dispatch_flow so asset_id fields in
# ImageArtifact are resolved to presigned GET URLs for LoadImageFromUrl.
_resolve_asset_url_cb: Callable[[str, str], str] | None = None
_planner_client: PlannerClient | None = None


def set_resolve_asset_url(callback: Callable[[str, str], str] | None) -> None:
    """Set the resolve_asset_url callback for asset_id → presigned GET URL.

    Must be called during application startup (e.g. inside the FastAPI
    lifespan) **after** the AssetsService is initialised.

    The callback signature is ``(asset_id, session_id) -> str`` and must:
    - Validate that the caller's ``session_id`` owns the asset
    - Return a fresh presigned GET URL for the asset's R2 object
    - Raise ``ValueError`` with ``invalid_artifact`` on disallowed access

    Args:
        callback: A sync callable, or ``None`` to disable.
    """
    global _resolve_asset_url_cb
    _resolve_asset_url_cb = callback


def set_planner_client(client: PlannerClient | None) -> None:
    """Set an injectable planner client for orchestration tests or runtime wiring."""
    global _planner_client
    _planner_client = client

# Polling interval for WebSocket state updates (seconds)
POLL_INTERVAL = 0.5


@contextmanager
def _handle_service_errors():
    """Catch known service exceptions and convert to ``AppError``.

    This is the single error-mapping point for all router endpoints.
    The converted ``AppError`` propagates to the global handler
    registered in ``app.py``, which produces a structured JSON response.

    Usage::

        with _handle_service_errors():
            _service.enqueue_modal_work(...)

    """
    try:
        yield
    except AppError:
        # Already an AppError — let it propagate to the global handler
        raise
    except ModelNotAllowedError as exc:
        raise AppModelNotAllowedError(exc.model_id) from exc
    except ModelNotCachedError as exc:
        raise AppModelNotCachedError(exc.filename) from exc
    except ValueError as exc:
        message = str(exc)
        if message.startswith("unsupported_workflow"):
            detail = message.split(": ", 1)[1] if ": " in message else message
            raise UnsupportedWorkflowError(detail) from exc
        if message.startswith("model_not_allowed"):
            detail = message.split(": ", 1)[1] if ": " in message else message
            raise AppModelNotAllowedError(detail) from exc
        # Other value errors (e.g., missing params) become generic 422
        raise HTTPException(status_code=422, detail=message)
    except Exception as exc:
        # Infrastructure errors (StorageError, RuntimeError from Modal spawn,
        # etc.) that reach here have already been logged and the job marked
        # terminal by the service layer. Convert to 500 so the test harness
        # receives a proper response instead of an unhandled exception.
        raise AppError(
            status_code=500,
            code="generation_dispatch_failed",
            user_message="Generation dispatch failed",
        ) from exc


def _validate_session(session_id: str) -> str:
    """Validate that the session_id is non-empty and return it.

    Raises:
        HTTPException(401): If session_id is empty or only whitespace.
    """
    session_id = session_id.strip()
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Session-ID header is required",
        )
    return session_id


@router.post("/generate", status_code=202)
def generate(
    request: GenerateRequest,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate endpoint.

    Accepts a generation request, resolves assets, creates a job, validates
    that any requested models are whitelisted, resolves the workflow, and
    returns 202 Accepted.

    Job creation is deferred until after asset resolution so that a failed
    download does not leave orphaned pending jobs in the database.

    V1 boundary: models must be pre-cached in the Modal Volume; no runtime
    downloads are performed.
    """
    session_id = _validate_session(x_session_id)
    normalized_workflow = request.workflow or request.workflow_name or "flux2_txt2img"

    # Resolve asset_id to base64 when provided (R2 pipeline bridge).
    # This downloads the asset from R2 and converts it to base64 so the
    # legacy ComfyUI editing workflow can use it without changes.
    # NOTE: job creation happens AFTER this block so asset resolution
    # failures never orphan a pending job in the database.
    resolved_base64 = request.image_base64
    if request.image_asset_id and normalized_workflow == "flux2_editing":
        if not _resolve_asset_url_cb:
            raise AppError(
                status_code=500,
                code="asset_resolution_unavailable",
                user_message="Asset resolution callback is not configured",
            )

        import urllib.request
        import base64

        try:
            presigned_url = _resolve_asset_url_cb(request.image_asset_id, session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise AppError(
                status_code=500,
                code="asset_resolution_failed",
                user_message="Asset resolution failed",
            ) from exc
        try:
            with urllib.request.urlopen(presigned_url, timeout=30) as resp:
                resolved_base64 = base64.b64encode(resp.read()).decode("ascii")
        except Exception as exc:
            raise AppError(
                status_code=500,
                code="asset_download_failed",
                user_message="Asset download failed",
            ) from exc

    job_id = _service.create_job(request.prompt, session_id=session_id)

    with _handle_service_errors():
        _service.enqueue_modal_work(
            job_id=job_id,
            prompt=request.prompt,
            workflow_name=normalized_workflow,
            use_turbo=request.use_turbo,
            image_base64=resolved_base64,
        )
    return GenerateResponse(job_id=job_id)


@router.post("/generate/orchestrate")
def generate_orchestrate(
    request: OrchestrateRequest,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> OrchestrateResponse:
    """POST /generate/orchestrate prompt-first orchestration endpoint."""
    session_id = _validate_session(x_session_id)
    with _handle_service_errors():
        response = _service.orchestrate(
            request=request,
            session_id=session_id,
            planner=_planner_client,
            resolve_asset_url=_resolve_asset_url_cb,
        )
    if response.outcome == "job_started":
        return JSONResponse(status_code=202, content=response.model_dump(exclude_none=True))
    if response.outcome == "error":
        status_code = 503 if response.error_code in {
            "planner_provider_unavailable",
            "planner_unconfigured",
        } else 422
        return JSONResponse(status_code=status_code, content=response.model_dump(exclude_none=True))
    return response


@router.post("/generate/extraction", status_code=202)
def generate_extraction(
    request: ExtractionFlow,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate/extraction endpoint.

    Accepts a typed extraction request with an input image artifact,
    creates a job, resolves the BRIA RMBG workflow, and returns 202 Accepted.
    """
    session_id = _validate_session(x_session_id)
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
            resolve_asset_url=_resolve_asset_url_cb,
        )
    return GenerateResponse(job_id=job_id)


@router.post("/generate/composition", status_code=202)
def generate_composition(
    request: CompositionFlow,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate/composition endpoint.

    Accepts a typed composition request with background and foreground images,
    a control mode (depth or canny), and optional control_strength/seed.
    Creates a job, resolves the FLUX + ControlNet workflow, and returns 202.
    """
    session_id = _validate_session(x_session_id)
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
            resolve_asset_url=_resolve_asset_url_cb,
        )
    return GenerateResponse(job_id=job_id)


@router.post("/generate/identity", status_code=202)
def generate_identity(
    request: IdentityFlow,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate/identity endpoint.

    Accepts a typed identity request with a reference face image,
    creates a job, resolves the PuLID + FLUX identity workflow,
    and returns 202 Accepted. Runs on A100 GPU.
    """
    session_id = _validate_session(x_session_id)
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
            resolve_asset_url=_resolve_asset_url_cb,
        )
    return GenerateResponse(job_id=job_id)


@router.get("/images/{job_id}")
def get_image(
    job_id: str,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
):
    """GET /images/{job_id} endpoint.

    Serves the generated image for a completed job. Verifies that the
    requesting session owns the job when the job has a stored session_id.
    Returns a 404 with a structured error code when the job or image is
    missing, or 403 on session mismatch.
    """
    job = _service.get_job(job_id)
    if job is None:
        raise AppError(
            status_code=404,
            code="job_not_found",
            user_message="Job does not exist",
        )

    # Session ownership check: if the job was created with a session_id,
    # the requesting session must match.
    job_session = job.get("session_id", "")
    request_session = x_session_id.strip()
    if job_session and job_session != request_session:
        raise SessionMismatchError(request_session, job_session)

    image_path = job.get("image_path")
    if not image_path:
        raise AppError(
            status_code=404,
            code="image_not_found",
            user_message="No image path assigned to this job",
        )

    # If the job has an R2 presigned URL, redirect to it instead of
    # serving from the local volume.  This is preferred when available
    # because the R2 object persists independently of the Modal volume.
    r2_url = job.get("r2_url")
    if r2_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=r2_url)

    # IMPORTANTE: Forzar la lectura de los últimos cambios del volumen distribuido
    try:
        image_volume.reload()
    except Exception:
        pass

    if not os.path.exists(image_path):
        raise AppError(
            status_code=404,
            code="image_not_found",
            user_message="No image found on disk for this job",
        )

    media_type, _ = mimetypes.guess_type(image_path)
    return FileResponse(image_path, media_type=media_type)


@router.websocket("/ws/generate/{job_id}")
async def websocket_generate(
    websocket: WebSocket,
    job_id: str,
    session_id: str = Query(""),
):
    """WS /ws/generate/{job_id} endpoint.

    Streams the job lifecycle events to the client with polling/resume semantics.
    Requires a matching session_id (as query param) when the job has a stored
    session_id, to prevent cross-session WebSocket access.
    """
    await websocket.accept()

    # Session ownership check: reject if the job has a session_id and the
    # client did not provide a matching one via query parameter.
    job = await _service.aget_job(job_id)
    if job is not None:
        job_session = job.get("session_id", "")
        if job_session and session_id != job_session:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    try:
        async for event in _service.poll_job_events(job_id, interval=POLL_INTERVAL):
            await websocket.send_json(event)
            # If terminal event, close the connection
            if event["event"] in ["completed", "error"]:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
