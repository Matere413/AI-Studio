"""Composition flow — FLUX + ControlNet image composition.

Input: background image + foreground image + control_mode (depth/canny)
Output: composed image with foreground placed onto generated background
GPU: L4, timeout: 600s
"""

from typing import Literal, Optional

from pydantic import ConfigDict, Field, model_validator

from src.shared.flows.base import BaseAtomicFlow, GPUProfile, ImageArtifact


class CompositionRequest(BaseAtomicFlow):
    """Request model for the FLUX + ControlNet composition flow."""

    model_config = ConfigDict(extra="forbid")

    background_image: ImageArtifact = Field(
        ...,
        description="Background image used for depth/canny conditioning",
    )
    foreground_image: ImageArtifact = Field(
        ...,
        description="Foreground subject image to compose onto background",
    )
    control_mode: Literal["depth", "canny"] = Field(
        ...,
        description="ControlNet preprocessor mode — depth or canny edge detection",
    )
    control_strength: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="ControlNet conditioning strength (0.0–2.0)",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=-1,
        description="Optional random seed for reproducible generation; omitted (None) or -1 request random",
    )


class CompositionFlow(CompositionRequest):
    """Concrete composition flow binding workflow_name, GPU profile, and timeout."""

    model_config = ConfigDict(extra="forbid")

    workflow_name: str = "composition"
    gpu_profile: GPUProfile = GPUProfile.L4
    timeout_s: int = 600

    @model_validator(mode="before")
    @classmethod
    def _reject_fixed_field_override(cls, data):
        """Reject client attempts to override fixed workflow defaults."""
        if not isinstance(data, dict):
            return data
        fixed = {
            "workflow_name": ("composition", str),
            "gpu_profile": (GPUProfile.L4, (GPUProfile, str)),
            "timeout_s": (600, int),
        }
        for field, (expected, expected_type) in fixed.items():
            if field in data:
                value = data[field]
                if value != expected:
                    raise ValueError(
                        f"Cannot override fixed field '{field}': "
                        f"'{value}' != '{expected}'"
                    )
        return data
