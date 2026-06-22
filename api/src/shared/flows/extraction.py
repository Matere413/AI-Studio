"""Extraction/isolation flow — BRIA RMBG background removal.

Input: source image (ImageArtifact)
Output: transparent RGBA PNG with extracted subject
GPU: L4, timeout: 300s
"""

from typing import Optional

from pydantic import ConfigDict, Field, model_validator

from src.shared.flows.base import BaseAtomicFlow, GPUProfile, ImageArtifact


class ExtractionRequest(BaseAtomicFlow):
    """Request model for the BRIA background extraction flow."""

    model_config = ConfigDict(extra="forbid")

    input_image: ImageArtifact = Field(
        ...,
        description="Source image containing the subject to extract",
    )
    mask_margin: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Optional pixel margin around the detected mask",
    )


class ExtractionFlow(ExtractionRequest):
    """Concrete extraction flow binding workflow_name, GPU profile, and timeout."""

    model_config = ConfigDict(extra="forbid")

    workflow_name: str = "extraction"
    gpu_profile: GPUProfile = GPUProfile.L4
    timeout_s: int = 300

    @model_validator(mode="before")
    @classmethod
    def _reject_fixed_field_override(cls, data):
        """Reject client attempts to override fixed workflow defaults."""
        if not isinstance(data, dict):
            return data
        fixed = {
            "workflow_name": ("extraction", str),
            "gpu_profile": (GPUProfile.L4, (GPUProfile, str)),
            "timeout_s": (300, int),
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
