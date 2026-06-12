from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from src.features.generation.models import GenerateResponse
from src.features.generation.service import GenerationService
from src.shared.job_store import JobStore

router = APIRouter()

_job_store = JobStore()
_service = GenerationService(job_store=_job_store)


class ControlNetRequest(BaseModel):
    """Request schema for ControlNet workflow."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    control_image_url: str = Field(..., description="URL of the control image.")
    checkpoint_url: Optional[str] = Field(
        None, description="Optional custom .safetensors URL for the checkpoint."
    )
    lora_url: Optional[str] = Field(
        None, description="Optional custom LoRA URL."
    )
    control_strength: float = Field(1.0, ge=0.0, le=2.0, description="ControlNet conditioning strength.")
    workflow_name: Optional[str] = Field(
        "controlnet", description="Workflow template to use."
    )


@router.post("/controlnet", status_code=202)
def controlnet(request: ControlNetRequest) -> GenerateResponse:
    """POST /controlnet endpoint for ControlNet generation.

    Accepts a ControlNet request, creates a job, and returns 202 Accepted.
    """
    job_id = _service.create_job(request.prompt)
    _service.enqueue_modal_work(
        job_id=job_id,
        prompt=request.prompt,
        workflow_name=request.workflow_name or "controlnet",
        checkpoint_url=request.checkpoint_url,
        lora_url=request.lora_url,
        control_image_url=request.control_image_url,
        control_strength=request.control_strength,
    )
    return GenerateResponse(job_id=job_id)
