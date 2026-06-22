"""Base types for atomic flow contracts.

Defines GPUProfile enum, ImageArtifact with path traversal guard,
FlowOutput for flow results, and BaseAtomicFlow as the typed base model.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GPUProfile(str, Enum):
    """GPU hardware profile for Modal function dispatch."""

    T4 = "T4"
    L4 = "L4"
    A100 = "A100"


class ImageArtifact(BaseModel):
    """Typed image handle for flow input/output, validated for safe paths.

    The primary handoff path between flows is ``volume_path``.
    Supports ``image/png`` and ``image/jpeg`` media types only.
    Path traversal (``../``, absolute paths outside the volume root)
    is rejected during validation.
    """

    volume_path: str = Field(
        ...,
        min_length=1,
        description="Path within the shared image volume",
    )
    media_type: str = Field(
        default="image/png",
        description="MIME type — must be image/png or image/jpeg",
    )
    source_job_id: Optional[str] = Field(
        default=None,
        description="Job ID that produced this artifact, if chained",
    )
    owner_session_id: Optional[str] = Field(
        default=None,
        description="Session UUID that owns this artifact for input/ path validation",
    )
    width: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image width in pixels",
    )
    height: Optional[int] = Field(
        default=None,
        ge=1,
        description="Image height in pixels",
    )

    @model_validator(mode="after")
    def _validate_media_type(self) -> "ImageArtifact":
        """Reject unsupported media types."""
        allowed = {"image/png", "image/jpeg"}
        if self.media_type not in allowed:
            raise ValueError(
                f"invalid_media_type: '{self.media_type}' is not supported. "
                f"Must be one of: {', '.join(sorted(allowed))}"
            )
        return self

    @model_validator(mode="after")
    def _validate_path_traversal(self) -> "ImageArtifact":
        """Reject paths that attempt directory traversal outside the volume root."""
        normalized = self.volume_path.replace("\\", "/")
        parts = normalized.split("/")
        if ".." in parts:
            raise ValueError(
                f"invalid_artifact: Path traversal detected in volume_path '{self.volume_path}'"
            )
        return self

    @model_validator(mode="after")
    def _validate_not_absolute(self) -> "ImageArtifact":
        """Reject absolute paths that escape the artifact namespace.

        Only relative paths (e.g., ``output/job-1/result.png``) are allowed.
        Absolute paths like ``/etc/passwd`` or ``/root/ComfyUI/output/evil.png``
        are rejected to prevent path injection.
        """
        if self.volume_path.startswith("/"):
            raise ValueError(
                f"invalid_artifact: Absolute paths are not allowed in volume_path "
                f"'{self.volume_path}'"
            )
        return self


class FlowOutput(BaseModel):
    """Standard output contract for every successful atomic flow execution."""

    job_id: str = Field(..., min_length=1, description="Job ID that produced this output")
    artifacts: list[ImageArtifact] = Field(
        ...,
        min_length=1,
        description="At least one output artifact must be produced",
    )


def _validate_artifact_ownership(artifact: ImageArtifact, session_id: str) -> None:
    """Validate that an input artifact is owned by the request session.

    Artifacts with ``source_job_id`` (chained from a completed flow) are always
    accepted because ownership propagates from the source job.

    Input artifacts (``volume_path`` starting with ``'input/'``) that have
    ``owner_session_id`` set must match the provided ``session_id``. Artifacts
    without ``owner_session_id`` are accepted for backward compatibility until
    the SDD 3 upload migration is complete.

    Raises ``ValueError`` with ``invalid_artifact`` code on mismatch.
    """
    if artifact.source_job_id:
        return

    if artifact.owner_session_id is not None and artifact.owner_session_id != session_id:
        raise ValueError(
            f"invalid_artifact: Artifact owner session "
            f"'{artifact.owner_session_id}' does not match "
            f"request session '{session_id}'"
        )


class BaseAtomicFlow(BaseModel):
    """Base model for every atomic flow request.

    Concrete flows (e.g., ExtractionRequest) inherit from this and
    bind their own ``workflow_name``, ``gpu_profile``, and ``timeout_s``.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_name: str = Field(
        ...,
        min_length=1,
        description="Unique flow identifier used for workflow routing",
    )
    gpu_profile: GPUProfile = Field(
        ...,
        description="GPU hardware profile for Modal function dispatch",
    )
    timeout_s: int = Field(
        ...,
        gt=0,
        description="Maximum execution time in seconds",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Text prompt for generation",
    )
