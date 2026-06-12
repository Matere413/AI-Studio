from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from src.features.generation.models import GenerateRequest, GenerateResponse
from src.features.generation.service import GenerationService
from src.shared.job_store import JobStore

router = APIRouter()

# Shared job store instance (MVP in-memory)
_job_store = JobStore()
_service = GenerationService(job_store=_job_store)


@router.post("/generate", status_code=202)
def generate(request: GenerateRequest) -> GenerateResponse:
    """POST /generate endpoint.

    Accepts a generation request, creates a job, and returns 202 Accepted.
    """
    job_id = _service.create_job(request.prompt)
    return GenerateResponse(job_id=job_id)


@router.websocket("/ws/generate/{job_id}")
async def websocket_generate(websocket: WebSocket, job_id: str):
    """WS /ws/generate/{job_id} endpoint.

    Streams the job lifecycle events to the client.
    """
    await websocket.accept()
    try:
        events = _service.get_job_events(job_id)
        for event in events:
            await websocket.send_json(event)
            # If terminal event, close the connection
            if event["event"] in ["completed", "error"]:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
