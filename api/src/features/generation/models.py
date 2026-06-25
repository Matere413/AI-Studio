from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal, Optional


WorkflowName = Literal["flux2_txt2img", "flux2_editing"]
FLUX2_WORKFLOWS = {"flux2_txt2img", "flux2_editing"}
SUPPORTED_WORKFLOWS = {"flux2_txt2img", "flux2_editing"}

# NOTE: identidad_gguf has been fully removed in Phase 3.
# Identity preservation now uses the typed IdentityFlow (PuLID + FLUX on A100).
# Legacy fields: image_url, width, height, seed are removed from GenerateRequest.


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
    image_base64: Optional[str] = Field(None, description="Flux 2 editing image input (legacy).")
    image_asset_id: Optional[str] = Field(
        None,
        description="Asset ID for R2-backed editing reference image. "
        "When set, the asset is resolved to a presigned URL via "
        "resolve_asset_url instead of using image_base64.",
    )

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
        if resolved_workflow == "flux2_editing" and not self.image_base64 and not self.image_asset_id:
            raise ValueError(
                "image_base64 or image_asset_id is required for the flux2_editing workflow"
            )
        if self.image_base64 is not None and resolved_workflow != "flux2_editing":
            raise ValueError("image_base64 is only supported for the flux2_editing workflow")
        if self.image_asset_id is not None and resolved_workflow != "flux2_editing":
            raise ValueError("image_asset_id is only supported for the flux2_editing workflow")
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
        "node_missing",
        "gpu_oom",
        "no_face_detected",
    ] = Field(..., min_length=1)
    detail: str = Field(..., min_length=1)


class JobEventResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_path: Optional[str] = Field(
        default=None,
        description="Deprecated: clients should use GET /images/{job_id} instead",
    )


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
        # result is now optional for completed events — clients use GET /images/{job_id}
        if self.event == "error" and self.error is None:
            raise ValueError("error event must include error details")
        return self
