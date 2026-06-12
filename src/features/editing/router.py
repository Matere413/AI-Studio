from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from src.features.generation.models import GenerateResponse
from src.features.generation.service import GenerationService
from src.shared.job_store import JobStore

router = APIRouter()

_job_store = JobStore()
_service = GenerationService(job_store=_job_store)


class EditRequest(BaseModel):
    """Request schema for img2img editing workflow."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    image_url: str = Field(..., description="URL of the input image to edit.")
    checkpoint_url: Optional[str] = Field(
        None, description="Optional custom .safetensors URL for the checkpoint."
    )
    lora_url: Optional[str] = Field(
        None, description="Optional custom LoRA URL."
    )
    denoise: float = Field(0.75, ge=0.0, le=1.0, description="Denoising strength for img2img.")
    workflow_name: Optional[str] = Field(
        "img2img", description="Workflow template to use."
    )


@router.post("/edit", status_code=202)
def edit(request: EditRequest) -> GenerateResponse:
    """POST /edit endpoint for image-to-image editing.

    Accepts an editing request, creates a job, and returns 202 Accepted.
    """
    job_id = _service.create_job(request.prompt)
    _service.enqueue_modal_work(
        job_id=job_id,
        prompt=request.prompt,
        workflow_name=request.workflow_name or "img2img",
        checkpoint_url=request.checkpoint_url,
        lora_url=request.lora_url,
    )
    return GenerateResponse(job_id=job_id)
