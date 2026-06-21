"""Pydantic models for ComfyUI Studio workflow manifests and engine contracts."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

MIN_DIMENSION = 256
MAX_DIMENSION = 2048
DIMENSION_MULTIPLE = 64
MAX_PIXELS = 4_194_304


def validate_dimensions(width: int, height: int) -> None:
    """Raise ValueError when dimensions are unsafe for ComfyUI generation."""
    if width * height > MAX_PIXELS:
        raise ValueError("invalid_dimensions: total pixels exceed 4,194,304")
    if not (MIN_DIMENSION <= width <= MAX_DIMENSION) or not (
        MIN_DIMENSION <= height <= MAX_DIMENSION
    ):
        raise ValueError("invalid_dimensions: width and height must be between 256 and 2048")
    if width % DIMENSION_MULTIPLE != 0 or height % DIMENSION_MULTIPLE != 0:
        raise ValueError("invalid_dimensions: width and height must be multiples of 64")


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
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Output artifact declarations (e.g., artifacts list)",
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
