"""Pydantic v2 schemas for the Assets API.

Provides request/response models for Project and Asset endpoints:

- ``ProjectCreate`` — input for creating a workspace project
- ``ProjectResponse`` — full project representation with embedded assets
- ``AssetResponse`` — asset representation returned to clients
- ``UploadTicketRequest`` — request body for requesting a presigned PUT URL
- ``UploadTicketResponse`` — presigned upload ticket returned to clients
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Schema for creating a new project.

    Attributes:
        name: Human-readable project name (1–128 characters).
    """

    name: str = Field(min_length=1, max_length=128)


class ProjectUpdate(BaseModel):
    """Schema for updating a project (slice 2).

    Binding: only ``name`` is updatable on Project. The ``Project`` model
    has only ``id, name, owner_id, session_id, created_at`` — no
    ``description``. ``name`` is optional here; when ``None`` the service
    skips the update (so an empty body is a no-op 200).
    """

    name: str | None = Field(default=None, min_length=1, max_length=128)


class AssetResponse(BaseModel):
    """Schema for a stored file asset returned to clients.

    Attributes:
        id: UUID primary key.
        name: Original file name.
        content_type: MIME type (e.g. ``image/webp``, ``image/png``).
        r2_key: Object key in the R2 bucket.
        project_id: FK to the owning Project.
        upload_status: Server-owned readiness — ``pending``, ``uploading``,
            ``finalized``, or ``failed``.
        finalized_at: Timestamp when the asset was finalised; ``None`` until
            the upload is confirmed.
        created_at: Auto-set creation timestamp.
    """

    id: str
    name: str
    content_type: str
    r2_key: str
    project_id: str
    upload_status: str = "pending"
    finalized_at: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    """Schema for a project returned to clients.

    Attributes:
        id: UUID primary key.
        name: Human-readable project name.
        owner_id: Optional owner reference (nullable).
        session_id: Session that created the project.
        created_at: Auto-set creation timestamp.
        assets: List of active (non-deleted) assets in this project.
    """

    id: str
    name: str
    owner_id: str | None = None
    session_id: str
    created_at: datetime
    assets: list[AssetResponse] = []

    model_config = {"from_attributes": True}


class UploadTicketRequest(BaseModel):
    """Schema for requesting a presigned upload URL.

    Attributes:
        asset_name: Original file name (1–256 characters).
        content_type: MIME type of the upload (default ``image/webp``).
    """

    asset_name: str = Field(min_length=1, max_length=256)
    content_type: str = "image/webp"


class UploadTicketResponse(BaseModel):
    """Schema for the presigned upload ticket.

    Attributes:
        asset_id: The newly created Asset UUID.
        presigned_url: The presigned PUT URL (expires in 300s).
        r2_key: The object key the client should PUT to.
    """

    asset_id: str
    presigned_url: str
    r2_key: str
