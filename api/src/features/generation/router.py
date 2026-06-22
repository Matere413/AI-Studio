import mimetypes
import os

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone
from src.features.generation.models import GenerateRequest, GenerateResponse
from src.features.generation.service import GenerationService, ModelNotAllowedError
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


@router.post("/generate", status_code=202)
def generate(request: GenerateRequest) -> GenerateResponse:
    """POST /generate endpoint.

    Accepts a generation request, creates a job, validates that any requested
    models are whitelisted, resolves the workflow, and returns 202 Accepted.

    V1 boundary: models must be pre-cached in the Modal Volume; no runtime
    downloads are performed.
    """
    job_id = _service.create_job(request.prompt)
    normalized_workflow = request.workflow or request.workflow_name or "flux2_txt2img"
    try:
        _service.enqueue_modal_work(
            job_id=job_id,
            prompt=request.prompt,
            workflow_name=normalized_workflow,
            use_turbo=request.use_turbo,
            image_base64=request.image_base64,
        )
    except ModelNotAllowedError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "model_not_allowed",
                    "detail": f"Model '{exc.model_id}' is not in the allowed whitelist.",
                }
            },
        )
    except ModelNotCachedError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "model_not_cached",
                    "detail": f"Model '{exc.filename}' is not cached.",
                }
            },
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("model_not_allowed"):
            detail = message.split(": ", 1)[1] if ": " in message else message
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "model_not_allowed",
                        "detail": detail,
                    }
                },
            )
        if message.startswith("unsupported_workflow"):
            detail = message.split(": ", 1)[1] if ": " in message else message
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "type": "value_error",
                            "loc": ["body", "workflow"],
                            "msg": f"Value error, {message}",
                            "input": normalized_workflow,
                            "ctx": {"error": detail},
                        }
                    ]
                },
            )
        raise HTTPException(status_code=422, detail=message)
    return GenerateResponse(job_id=job_id)


@router.post("/generate/extraction", status_code=202)
def generate_extraction(request: ExtractionFlow) -> GenerateResponse:
    """POST /generate/extraction endpoint.

    Accepts a typed extraction request with an input image artifact,
    creates a job, resolves the BRIA RMBG workflow, and returns 202 Accepted.
    """
    job_id = _service.create_job(request.prompt)
    try:
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
        )
    except ModelNotAllowedError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "model_not_allowed",
                    "detail": f"Model '{exc.model_id}' is not in the allowed whitelist.",
                }
            },
        )
    except ModelNotCachedError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "model_not_cached",
                    "detail": f"Model '{exc.filename}' is not cached.",
                }
            },
        )
    except ValueError as exc:
        if str(exc).startswith("unsupported_workflow"):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "type": "value_error",
                            "loc": ["body", "workflow"],
                            "msg": f"Value error, {exc}",
                            "input": request.workflow_name,
                            "ctx": {"error": str(exc).split(": ", 1)[1] if ": " in str(exc) else str(exc)},
                        }
                    ]
                },
            )
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    return GenerateResponse(job_id=job_id)


@router.post("/generate/composition", status_code=202)
def generate_composition(request: CompositionFlow) -> GenerateResponse:
    """POST /generate/composition endpoint.

    Accepts a typed composition request with background and foreground images,
    a control mode (depth or canny), and optional control_strength/seed.
    Creates a job, resolves the FLUX + ControlNet workflow, and returns 202.
    """
    job_id = _service.create_job(request.prompt)
    try:
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
        )
    except ModelNotAllowedError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "model_not_allowed",
                    "detail": f"Model '{exc.model_id}' is not in the allowed whitelist.",
                }
            },
        )
    except ModelNotCachedError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "model_not_cached",
                    "detail": f"Model '{exc.filename}' is not cached.",
                }
            },
        )
    except ValueError as exc:
        if str(exc).startswith("unsupported_workflow"):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "type": "value_error",
                            "loc": ["body", "workflow"],
                            "msg": f"Value error, {exc}",
                            "input": request.workflow_name,
                            "ctx": {"error": str(exc).split(": ", 1)[1] if ": " in str(exc) else str(exc)},
                        }
                    ]
                },
            )
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    return GenerateResponse(job_id=job_id)


@router.post("/generate/identity", status_code=202)
def generate_identity(request: IdentityFlow) -> GenerateResponse:
    """POST /generate/identity endpoint.

    Accepts a typed identity request with a reference face image,
    creates a job, resolves the PuLID + FLUX identity workflow,
    and returns 202 Accepted. Runs on A100 GPU.
    """
    job_id = _service.create_job(request.prompt)
    try:
        _service.dispatch_flow(
            job_id=job_id,
            flow_request=request,
        )
    except ModelNotAllowedError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "model_not_allowed",
                    "detail": f"Model '{exc.model_id}' is not in the allowed whitelist.",
                }
            },
        )
    except ModelNotCachedError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "model_not_cached",
                    "detail": f"Model '{exc.filename}' is not cached.",
                }
            },
        )
    except ValueError as exc:
        if str(exc).startswith("unsupported_workflow"):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "type": "value_error",
                            "loc": ["body", "workflow"],
                            "msg": f"Value error, {exc}",
                            "input": request.workflow_name,
                            "ctx": {"error": str(exc).split(": ", 1)[1] if ": " in str(exc) else str(exc)},
                        }
                    ]
                },
            )
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    return GenerateResponse(job_id=job_id)


@router.get("/images/{job_id}")
def get_image(job_id: str):
    """GET /images/{job_id} endpoint.

    Serves the generated image for a completed job. Returns a 404 with a
    structured error code when the job or image is missing.
    """
    job = _service.get_job(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "job_not_found",
                    "detail": "Job does not exist",
                }
            },
        )

    image_path = job.get("image_path")
    if not image_path:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "image_not_found",
                    "detail": "No image path assigned to this job",
                }
            },
        )
        
    # IMPORTANTE: Forzar la lectura de los últimos cambios del volumen distribuido
    try:
        image_volume.reload()
    except Exception:
        pass

    if not os.path.exists(image_path):
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "image_not_found",
                    "detail": "No image found on disk for this job",
                }
            },
        )

    media_type, _ = mimetypes.guess_type(image_path)
    return FileResponse(image_path, media_type=media_type)


@router.websocket("/ws/generate/{job_id}")
async def websocket_generate(websocket: WebSocket, job_id: str):
    """WS /ws/generate/{job_id} endpoint.

    Streams the job lifecycle events to the client with polling/resume semantics.
    """
    await websocket.accept()
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
