import mimetypes
import os
from contextlib import contextmanager

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from datetime import datetime, timezone
from src.features.generation.models import GenerateRequest, GenerateResponse
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


@router.post("/generate", status_code=202)
def generate(
    request: GenerateRequest,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate endpoint.

    Accepts a generation request, creates a job, validates that any requested
    models are whitelisted, resolves the workflow, and returns 202 Accepted.

    V1 boundary: models must be pre-cached in the Modal Volume; no runtime
    downloads are performed.
    """
    session_id = x_session_id.strip()
    job_id = _service.create_job(request.prompt, session_id=session_id)
    normalized_workflow = request.workflow or request.workflow_name or "flux2_txt2img"
    with _handle_service_errors():
        _service.enqueue_modal_work(
            job_id=job_id,
            prompt=request.prompt,
            workflow_name=normalized_workflow,
            use_turbo=request.use_turbo,
            image_base64=request.image_base64,
        )
    return GenerateResponse(job_id=job_id)


@router.post("/generate/extraction", status_code=202)
def generate_extraction(
    request: ExtractionFlow,
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> GenerateResponse:
    """POST /generate/extraction endpoint.

    Accepts a typed extraction request with an input image artifact,
    creates a job, resolves the BRIA RMBG workflow, and returns 202 Accepted.
    """
    session_id = x_session_id.strip()
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
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
    session_id = x_session_id.strip()
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
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
    session_id = x_session_id.strip()
    job_id = _service.create_job(request.prompt, session_id=session_id)
    with _handle_service_errors():
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
            session_id=session_id,
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
    job = _service.get_job(job_id)
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
