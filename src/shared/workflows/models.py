"""Pydantic models for ComfyUI Studio workflow manifests and engine contracts."""

from typing import Dict, Optional

from pydantic import BaseModel, Field, ConfigDict


class NodeMapping(BaseModel):
    """Maps a semantic input name to a ComfyUI node ID and field."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)


class ManifestSchema(BaseModel):
    """Top-level manifest schema defining the inputs a workflow accepts."""

    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, NodeMapping]


class WorkflowRequest(BaseModel):
    """Base request schema for workflow execution with dynamic inputs."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000, description="The main text prompt.")
    checkpoint_url: Optional[str] = Field(None, description="Optional custom .safetensors URL.")
    lora_url: Optional[str] = Field(None, description="Optional custom LoRA URL.")
