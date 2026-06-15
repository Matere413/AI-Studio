import mimetypes
import os

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone
from src.features.generation.models import GenerateRequest, GenerateResponse
from src.features.generation.service import GenerationService, ModelNotAllowedError
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
    normalized_workflow = request.workflow or request.workflow_name or "txt2img"
    try:
        _service.enqueue_modal_work(
            job_id=job_id,
            prompt=request.prompt,
            workflow_name=normalized_workflow,
            format=request.format,
            checkpoint_url=request.checkpoint_url,
            lora_url=request.lora_url,
            age=request.age,
            gender=request.gender,
            ethnicity=request.ethnicity,
            wardrobe=request.wardrobe,
            expression=request.expression,
            background=request.background,
            output_type=request.output_type,
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
        raise HTTPException(status_code=422, detail=message)
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
