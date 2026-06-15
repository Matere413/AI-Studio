"""Pydantic models for ComfyUI Studio workflow manifests and engine contracts."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeMapping(BaseModel):
    """Maps a semantic input name to a ComfyUI node ID and field."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)


class FormatDimensions(BaseModel):
    """Resolution metadata for a workflow format."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class ManifestSchema(BaseModel):
    """Top-level manifest schema defining the inputs a workflow accepts."""

    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, NodeMapping]
    default_checkpoint: Optional[str] = Field(None, min_length=1)
    default_format: Optional[str] = Field(None, min_length=1)
    formats: Dict[str, FormatDimensions] = Field(default_factory=dict)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    prompt_templates: Dict[str, str] = Field(
        default_factory=dict,
        alias="prompt-templates",
    )
    persona_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        alias="persona-metadata",
    )

    @model_validator(mode="after")
    def _validate_format_contract(self) -> "ManifestSchema":
        """Ensure format metadata is internally consistent when declared."""
        if self.formats and not self.default_format:
            raise ValueError("default_format is required when formats are declared")
        if self.default_format and self.default_format not in self.formats:
            raise ValueError(
                f"default_format '{self.default_format}' must match a declared format"
            )
        return self


class WorkflowRequest(BaseModel):
    """Base request schema for workflow execution with dynamic inputs."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000, description="The main text prompt.")
    checkpoint_url: Optional[str] = Field(None, description="Optional custom .safetensors URL.")
    lora_url: Optional[str] = Field(None, description="Optional custom LoRA URL.")
    checkpoint: Optional[str] = Field(None, description="Checkpoint filename for whitelist validation.")
    lora: Optional[str] = Field(None, description="LoRA filename for whitelist validation.")
