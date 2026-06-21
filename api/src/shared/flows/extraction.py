"""Extraction/isolation flow — BRIA RMBG background removal.

Input: source image (ImageArtifact)
Output: transparent RGBA PNG with extracted subject
GPU: L4, timeout: 300s
"""

from typing import Optional

from pydantic import Field

from src.shared.flows.base import BaseAtomicFlow, GPUProfile, ImageArtifact


class ExtractionRequest(BaseAtomicFlow):
    """Request model for the BRIA background extraction flow."""

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

    workflow_name: str = "extraction"
    gpu_profile: GPUProfile = GPUProfile.L4
    timeout_s: int = 300
