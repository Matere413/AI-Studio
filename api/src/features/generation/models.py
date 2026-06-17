from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Literal, Optional
from src.shared.workflows.models import validate_dimensions


WorkflowName = Literal["txt2img", "img2img", "controlnet", "product_premium", "realistic_persona", "qwen_txt2img", "identidad_gguf"]
ProductFormat = Literal["square", "vertical"]
PersonaOutputType = Literal["portrait", "full-body", "lifestyle", "editorial"]
QualityMode = Literal["fast", "high"]


PERSONA_FIELD_NAMES = {
    "age",
    "gender",
    "ethnicity",
    "wardrobe",
    "expression",
    "background",
    "output_type",
    "image_url",
}


def is_supported_reference_image_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


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
    age: Optional[int] = Field(None, ge=18, le=100, description="Persona age range.")
    gender: Optional[str] = Field(None, min_length=1, description="Persona gender descriptor.")
    ethnicity: Optional[str] = Field(None, min_length=1, description="Persona ethnicity descriptor.")
    wardrobe: Optional[str] = Field(None, min_length=1, description="Persona wardrobe descriptor.")
    expression: Optional[str] = Field(None, min_length=1, description="Persona expression descriptor.")
    background: Optional[str] = Field(None, min_length=1, description="Persona background descriptor.")
    output_type: Optional[PersonaOutputType] = Field(
        None, description="Persona composition type."
    )
    image_url: Optional[str] = Field(
        None,
        description="Optional reference face image URL or base64 data URI for identity preservation.",
    )
    width: Optional[int] = Field(None, description="Qwen output width in pixels.")
    height: Optional[int] = Field(None, description="Qwen output height in pixels.")
    quality_mode: QualityMode = Field(
        "high", description="Qwen speed/quality mode: fast or high."
    )
    seed: Optional[int] = Field(None, description="Identity GGUF seed; -1 requests a random seed.")

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
        provided_persona_fields = (PERSONA_FIELD_NAMES - {"image_url"}).intersection(self.model_fields_set)
        if resolved_workflow != "realistic_persona" and provided_persona_fields:
            fields = ", ".join(sorted(provided_persona_fields))
            raise ValueError(
                f"{fields} are only supported for the realistic_persona workflow"
            )
        if (
            "image_url" in self.model_fields_set
            and resolved_workflow not in {"realistic_persona", "identidad_gguf"}
        ):
            raise ValueError(
                "image_url is only supported for the realistic_persona and identidad_gguf workflows"
            )
        if resolved_workflow == "identidad_gguf" and not self.image_url:
            raise ValueError("image_url is required for the identidad_gguf workflow")
        if self.image_url is not None and not is_supported_reference_image_url(self.image_url):
            raise ValueError("image_url must be an http(s) URL or data URI")
        dimension_fields = {"width", "height"}.intersection(self.model_fields_set)
        if resolved_workflow not in {"qwen_txt2img", "identidad_gguf"} and dimension_fields:
            fields = ", ".join(sorted(dimension_fields))
            raise ValueError(f"{fields} are only supported for the qwen_txt2img and identidad_gguf workflows")
        quality_fields = {"quality_mode"}.intersection(self.model_fields_set)
        if resolved_workflow != "qwen_txt2img" and quality_fields:
            fields = ", ".join(sorted(quality_fields))
            raise ValueError(f"{fields} are only supported for the qwen_txt2img workflow")
        if resolved_workflow == "qwen_txt2img" and self.width is not None and self.height is not None:
            validate_dimensions(self.width, self.height)
        if resolved_workflow == "identidad_gguf" and (self.width is not None or self.height is not None):
            validate_dimensions(self.width or 1024, self.height or 1024)
        if "seed" in self.model_fields_set and resolved_workflow != "identidad_gguf":
            raise ValueError("seed is only supported for the identidad_gguf workflow")
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
