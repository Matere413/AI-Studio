from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from src.features.generation.models import GenerateRequest, GenerateResponse
from src.features.generation.service import GenerationService, ModelNotAllowedError
from src.shared.job_store import JobStore

router = APIRouter()

# Shared job store instance (MVP in-memory)
_job_store = JobStore()
_service = GenerationService(job_store=_job_store)

# Polling interval for WebSocket state updates (seconds)
POLL_INTERVAL = 0.5


@router.post("/generate", status_code=202)
def generate(request: GenerateRequest) -> GenerateResponse:
    """POST /generate endpoint.

    Accepts a generation request, creates a job, resolves the workflow,
    and returns 202 Accepted.
    """
    job_id = _service.create_job(request.prompt)
    try:
        _service.enqueue_modal_work(
            job_id=job_id,
            prompt=request.prompt,
            workflow_name=request.workflow_name or "txt2img",
            checkpoint_url=request.checkpoint_url,
            lora_url=request.lora_url,
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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return GenerateResponse(job_id=job_id)


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
