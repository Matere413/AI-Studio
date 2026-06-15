from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Literal, Optional


WorkflowName = Literal["txt2img", "img2img", "controlnet", "product_premium"]
ProductFormat = Literal["square", "vertical"]


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    workflow: Optional[WorkflowName] = Field(
        None, description="Optional workflow alias for backward-compatible routing."
    )
    workflow_name: WorkflowName = Field(
        "txt2img", description="Workflow template to use (e.g., txt2img, img2img)."
    )
    format: ProductFormat = Field(
        "square", description="Product premium output format (square or vertical)."
    )
    checkpoint_url: Optional[str] = Field(
        None, description="Optional custom .safetensors URL for the checkpoint."
    )
    lora_url: Optional[str] = Field(
        None, description="Optional custom LoRA URL."
    )

    @model_validator(mode="after")
    def validate_format_scope(self):
        resolved_workflow = self.workflow or self.workflow_name or "txt2img"
        if (
            "workflow" in self.model_fields_set
            and "workflow_name" in self.model_fields_set
            and self.workflow is not None
            and self.workflow_name is not None
            and self.workflow != self.workflow_name
        ):
            raise ValueError(
                "workflow and workflow_name must match when both are provided"
            )
        if resolved_workflow != "product_premium" and self.format != "square":
            raise ValueError("format is only supported for the product_premium workflow")
        return self


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
