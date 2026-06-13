from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Literal, Optional


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    checkpoint_url: Optional[str] = Field(
        None, description="Optional custom .safetensors URL for the checkpoint."
    )
    lora_url: Optional[str] = Field(
        None, description="Optional custom LoRA URL."
    )
    workflow_name: Optional[str] = Field(
        "txt2img", description="Workflow template to use (e.g., txt2img, img2img)."
    )


class GenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., min_length=1)
    status: Literal["pending"] = "pending"


class JobEventError(BaseModel):
    code: Literal[
        "timeout",
        "model_not_allowed",
        "model_not_cached",
        "comfyui_execution_failed",
        "job_not_found",
    ] = Field(..., min_length=1)
    detail: str = Field(..., min_length=1)


class JobEventResult(BaseModel):
    image_path: str = Field(..., min_length=1)


class JobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal[
        "booting_server",
        "downloading_weights",
        "generating",
        "progress",
        "completed",
        "error",
    ]
    job_id: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)
    progress: Optional[int] = Field(None, ge=0, le=100)
    message: Optional[str] = None
    result: Optional[JobEventResult] = None
    error: Optional[JobEventError] = None

    @model_validator(mode="after")
    def validate_terminal_fields(self):
        if self.event == "completed" and self.result is None:
            raise ValueError("completed event must include result")
        if self.event == "error" and self.error is None:
            raise ValueError("error event must include error details")
        return self
