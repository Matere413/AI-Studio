from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal, Optional
from src.shared.workflows.models import validate_dimensions


WorkflowName = Literal["flux2_txt2img", "flux2_editing", "identidad_gguf"]
FLUX2_WORKFLOWS = {"flux2_txt2img", "flux2_editing"}
SUPPORTED_WORKFLOWS = {"flux2_txt2img", "flux2_editing", "identidad_gguf"}


def is_supported_reference_image_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    workflow: Optional[WorkflowName] = Field(
        None, description="Optional workflow alias for routing."
    )
    workflow_name: WorkflowName = Field(
        "flux2_txt2img", description="Workflow template to use."
    )
    use_turbo: bool = Field(True, strict=True, description="Flux 2 turbo LoRA switch.")
    image_base64: Optional[str] = Field(None, description="Flux 2 editing image input.")
    image_url: Optional[str] = Field(
        None,
        description="Reference face image URL or data URI for identidad_gguf.",
    )
    width: Optional[int] = Field(None, description="Identity GGUF output width in pixels.")
    height: Optional[int] = Field(None, description="Identity GGUF output height in pixels.")
    seed: Optional[int] = Field(None, description="Identity GGUF seed; -1 requests a random seed.")

    @model_validator(mode="before")
    @classmethod
    def reject_unsupported_workflow_with_code(cls, data):
        if not isinstance(data, dict):
            return data
        for field_name in ("workflow", "workflow_name"):
            workflow_value = data.get(field_name)
            if workflow_value is not None and workflow_value not in SUPPORTED_WORKFLOWS:
                raise ValueError(
                    f"unsupported_workflow: Workflow '{workflow_value}' is not supported"
                )
        return data

    @model_validator(mode="after")
    def validate_workflow_scoped_fields(self):
        resolved_workflow = self.workflow or self.workflow_name or "flux2_txt2img"
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

        if "use_turbo" in self.model_fields_set and resolved_workflow not in FLUX2_WORKFLOWS:
            raise ValueError("use_turbo is only supported for Flux 2 workflows")
        if resolved_workflow == "flux2_editing" and not self.image_base64:
            raise ValueError("image_base64 is required for the flux2_editing workflow")
        if self.image_base64 is not None and resolved_workflow != "flux2_editing":
            raise ValueError("image_base64 is only supported for the flux2_editing workflow")
        if (
            "image_url" in self.model_fields_set
            and resolved_workflow != "identidad_gguf"
        ):
            raise ValueError(
                "image_url is only supported for the identidad_gguf workflow"
            )
        if resolved_workflow == "identidad_gguf" and not self.image_url:
            raise ValueError("image_url is required for the identidad_gguf workflow")
        if self.image_url is not None and not is_supported_reference_image_url(self.image_url):
            raise ValueError("image_url must be an http(s) URL or data URI")
        dimension_fields = {"width", "height"}.intersection(self.model_fields_set)
        if resolved_workflow != "identidad_gguf" and dimension_fields:
            fields = ", ".join(sorted(dimension_fields))
            raise ValueError(f"{fields} are only supported for the identidad_gguf workflow")
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
