"""FastAPI router for workspace Project and Asset management endpoints.

Provides RESTful endpoints for:

- **Create Project** — ``POST /projects``
- **List Projects** — ``GET /projects`` (scoped to ``X-Session-ID``)
- **Upload Ticket** — ``POST /projects/{id}/upload-ticket``
- **Finalize Asset** — ``PATCH /assets/{id}/finalize``
- **Soft-Delete Asset** — ``DELETE /assets/{id}``

All endpoints require the ``X-Session-ID`` header for ownership scoping.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import RedirectResponse

from src.features.assets.exceptions import (
    AssetNotFoundError,
    ProjectNotFoundError,
    ProjectOwnershipError,
    StorageNotConfiguredError,
    StorageOperationError,
)
from src.features.assets.models import (
    AssetResponse,
    ProjectCreate,
    ProjectResponse,
    UploadTicketRequest,
    UploadTicketResponse,
)
from src.features.assets.service import AssetsService
from src.shared.errors import AppError
from src.shared.storage import StorageError

_log = logging.getLogger(__name__)

router = APIRouter(tags=["assets"])

# Module-level service instance (lazy-initialised, wired in ``init_assets``).
_service: AssetsService | None = None


def get_service() -> AssetsService:
    """Return the module-level ``AssetsService`` instance.

    Raises:
        RuntimeError: If the service has not been initialised via
            ``init_assets()``.
    """
    if _service is None:
        raise RuntimeError(
            "AssetsService not initialised. Call init_assets() during app startup."
        )
    return _service


def init_assets(
    service: AssetsService,
) -> None:
    """Initialise the module-level ``AssetsService``.

    Must be called during application startup (e.g. inside the FastAPI
    lifespan) **before** any assets endpoint receives a request.

    Args:
        service: A fully configured ``AssetsService`` instance.
    """
    global _service
    _service = service
    _log.info("assets_service_initialised")


# ── Session validation ────────────────────────────────────────────────────────


def _require_session(x_session_id: str = Header(default="", alias="X-Session-ID")) -> str:
    """Validate and return the caller's session ID.

    Raises:
        HTTPException(422): If the header is missing or empty.
    """
    session_id = x_session_id.strip()
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Session-ID header is required",
        )
    return session_id


# ── Service error mapping ─────────────────────────────────────────────────────


@contextmanager
def _map_service_errors():
    """Catch domain exceptions from the service layer and raise appropriate
    ``AppError`` exceptions.

    Maps:
    - ``ProjectNotFoundError`` / ``AssetNotFoundError`` → 404
    - ``ProjectOwnershipError`` → 403
    - ``StorageNotConfiguredError`` → 503
    - ``StorageOperationError`` → 502

    Usage::

        with _map_service_errors():
            result = await _service.some_method(...)
    """
    try:
        yield
    except HTTPException:
        raise
    except (ProjectNotFoundError, AssetNotFoundError) as exc:
        code = "project_not_found" if isinstance(exc, ProjectNotFoundError) else "asset_not_found"
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            user_message=str(exc),
        )
    except ProjectOwnershipError as exc:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="session_mismatch",
            user_message=str(exc),
        )
    except StorageNotConfiguredError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="storage_not_configured",
            user_message="Storage is not configured",
        )
    except StorageOperationError as exc:
        _log.exception("storage_operation_failed")
        raise AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="storage_error",
            user_message="Unable to generate asset redirect",
        )


# ==============================================================================
# Endpoints
# ==============================================================================


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    body: ProjectCreate,
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
) -> ProjectResponse:
    """Create a workspace project bound to the caller's session.

    The project is created with the given ``name`` and the caller's
    ``session_id``.  The response includes the full project data with
    an empty ``assets`` list.
    """
    with _map_service_errors():
        project = await service.create_project(
            name=body.name,
            session_id=session_id,
        )
        return ProjectResponse.model_validate(project, from_attributes=True)


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    summary="List projects for the caller's session",
)
async def list_projects(
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
) -> list[ProjectResponse]:
    """Return all projects owned by the caller's session.

    Projects are ordered newest-first.  Each project includes its active
    (non-deleted) assets via eager-loading.
    """
    projects = await service.list_projects(session_id=session_id)
    return [
        ProjectResponse.model_validate(p, from_attributes=True)
        for p in projects
    ]


@router.post(
    "/projects/{project_id}/upload-ticket",
    response_model=UploadTicketResponse,
    summary="Request a presigned upload URL",
)
async def request_upload_ticket(
    project_id: str,
    body: UploadTicketRequest,
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
) -> UploadTicketResponse:
    """Request a presigned PUT URL for direct browser-to-R2 upload.

    Creates an Asset row and returns:
    - ``asset_id`` — the new Asset UUID
    - ``presigned_url`` — a time-limited PUT URL (5 min TTL)
    - ``r2_key`` — the object key to PUT to

    Requires project ownership via ``X-Session-ID``.
    """
    with _map_service_errors():
        result = await service.request_upload_ticket(
            project_id=project_id,
            asset_name=body.asset_name,
            session_id=session_id,
            content_type=body.content_type,
        )
        return UploadTicketResponse(**result)


@router.patch(
    "/assets/{asset_id}/finalize",
    response_model=AssetResponse,
    summary="Confirm an upload completed",
)
async def finalize_asset(
    asset_id: str,
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
) -> AssetResponse:
    """Confirm that an upload completed successfully.

    Validates that the asset exists and is owned by the caller's session.
    Returns the asset data so clients can display it immediately.
    """
    with _map_service_errors():
        asset = await service.finalize_asset(
            asset_id=asset_id,
            session_id=session_id,
        )
        return AssetResponse.model_validate(asset, from_attributes=True)


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an asset",
)
async def delete_asset(
    asset_id: str,
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
) -> None:
    """Soft-delete an asset by setting ``deleted_at``.

    The asset is excluded from default queries after deletion.  The
    backing R2 object will be hard-purged by the bucket lifecycle rule
    (≥30 days).
    """
    with _map_service_errors():
        await service.soft_delete_asset(
            asset_id=asset_id,
            session_id=session_id,
        )


@router.get(
    "/r2/{r2_key:path}",
    summary="Resolve an asset R2 key to a presigned GET redirect",
)
async def get_r2_asset(
    r2_key: str,
    session_id: str = Depends(_require_session),
    service: AssetsService = Depends(get_service),
):
    """Resolve an owned active asset key to a short-lived R2 redirect."""
    with _map_service_errors():
        asset = await service.get_asset_by_r2_key(r2_key=r2_key, session_id=session_id)

        storage = getattr(service, "_storage", None)
        if storage is None:
            raise StorageNotConfiguredError("R2Storage not configured")

        try:
            location = await storage.presigned_get(asset["r2_key"])
        except StorageError as exc:
            _log.exception("r2_presign_failed", extra={"r2_key": r2_key})
            raise StorageOperationError("Unable to generate presigned asset URL") from exc

        return RedirectResponse(
            url=location,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
