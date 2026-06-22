"""Identity flow — PuLID + FLUX identity-preserving generation on A100.

Input: reference face image (ImageArtifact) + prompt
Output: identity-preserved portrait with face detail enhancement
GPU: A100, timeout: 1200s
"""

from typing import Optional

from pydantic import ConfigDict, Field, model_validator

from src.shared.flows.base import BaseAtomicFlow, GPUProfile, ImageArtifact


class IdentityRequest(BaseAtomicFlow):
    """Request model for the PuLID + FLUX identity preservation flow."""

    model_config = ConfigDict(extra="forbid")

    reference_face: ImageArtifact = Field(
        ...,
        description="Reference face image for identity preservation",
    )
    width: int = Field(
        default=1024,
        ge=64,
        le=2048,
        description="Output image width (must be multiple of 64, max 2048 for VRAM safety)",
    )
    height: int = Field(
        default=1024,
        ge=64,
        le=2048,
        description="Output image height (must be multiple of 64, max 2048 for VRAM safety)",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=-1,
        description="Optional random seed for reproducible generation; -1 requests random",
    )

    @model_validator(mode="after")
    def _validate_dimensions_multiple_of_64(self) -> "IdentityRequest":
        """Reject dimensions that are not multiples of 64."""
        if self.width % 64 != 0:
            raise ValueError(
                f"width must be a multiple of 64, got {self.width}"
            )
        if self.height % 64 != 0:
            raise ValueError(
                f"height must be a multiple of 64, got {self.height}"
            )
        return self


class IdentityFlow(IdentityRequest):
    """Concrete identity flow binding workflow_name, GPU profile, and timeout."""

    model_config = ConfigDict(extra="forbid")

    workflow_name: str = "identity"
    gpu_profile: GPUProfile = GPUProfile.A100
    timeout_s: int = 1200

    @model_validator(mode="before")
    @classmethod
    def _reject_fixed_field_override(cls, data):
        """Reject client attempts to override fixed workflow defaults."""
        if not isinstance(data, dict):
            return data
        fixed = {
            "workflow_name": ("identity", str),
            "gpu_profile": (GPUProfile.A100, (GPUProfile, str)),
            "timeout_s": (1200, int),
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
