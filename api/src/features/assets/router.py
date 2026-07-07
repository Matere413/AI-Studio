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
    AssetNotReadyError,
    ProjectNotFoundError,
    ProjectOwnershipError,
    StorageNotConfiguredError,
    StorageOperationError,
)
from src.features.assets.models import (
    AssetResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    UploadTicketRequest,
    UploadTicketResponse,
)
from src.features.assets.service import AssetsService
from src.features.auth.presentation.dependencies import (
    CurrentUser,
    get_optional_user,
    require_verified_user,
)
from src.shared.errors import AppError
from src.shared.errors_auth import NotOwnerError
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


def _optional_session(
    x_session_id: str = Header(default="", alias="X-Session-ID"),
) -> str:
    """Return the caller's session ID or an empty string (no 422).

    Used by endpoints that accept EITHER an authenticated user OR an
    anonymous X-Session-ID (slice 2 save-blocking). The route handler
    decides which path to take.
    """
    return x_session_id.strip()


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
    except AssetNotReadyError as exc:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="asset_not_ready",
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
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
) -> ProjectResponse:
    """Create a workspace project.

    Slice 2 save-blocking (binding — anonymous generation stays):
    - Authenticated user present → require email_verified; the project is
      created with ``owner_id = user.id``. Unverified → ``403
      email_not_verified``.
    - Anonymous (no auth cookie) → requires ``X-Session-ID``; the project
      is created with ``owner_id IS NULL`` bound to that session. Missing
      ``X-Session-ID`` → ``422``.

    The response includes the full project data with an empty ``assets``
    list.
    """
    from src.shared.errors_auth import EmailNotVerifiedError

    if user is not None:
        # Authenticated path: gate on email_verified.
        if not user.email_verified:
            raise EmailNotVerifiedError()
        owner_id = user.id
        session_id_for_project = session_id or user.id  # authenticated users may omit X-Session-ID
    else:
        # Anonymous path: X-Session-ID is required.
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="X-Session-ID header is required",
            )
        owner_id = None
        session_id_for_project = session_id
    with _map_service_errors():
        project = await service.create_project(
            name=body.name,
            session_id=session_id_for_project,
            owner_id=owner_id,
        )
        return ProjectResponse.model_validate(project, from_attributes=True)


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    summary="List projects for the caller (owner_id or session_id)",
)
async def list_projects(
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
) -> list[ProjectResponse]:
    """Return the caller's projects, newest first.

    Slice 2 owner_id filtering (binding — anonymous coexistence stays):
    - Authenticated user present → ``list_projects(owner_id=user.id)``.
      The ``X-Session-ID`` header is ignored on this path so an
      anonymous project sharing the session_id is NOT leaked into an
      authenticated user's listing.
    - Anonymous (no auth cookie) → requires ``X-Session-ID``;
      ``list_projects(session_id=...)`` (existing behavior). Missing
      ``X-Session-ID`` → ``422``.

    Each project includes its active (non-deleted) assets via
    eager-loading.
    """
    if user is not None:
        # Authenticated path: filter by owner_id.
        projects = await service.list_projects(owner_id=user.id)
    else:
        # Anonymous path: X-Session-ID is required.
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="X-Session-ID header is required",
            )
        projects = await service.list_projects(session_id=session_id)
    return [
        ProjectResponse.model_validate(p, from_attributes=True)
        for p in projects
    ]


@router.put(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project (owner only)",
)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: CurrentUser = Depends(require_verified_user),
    service: AssetsService = Depends(get_service),
) -> ProjectResponse:
    """Update a project's ``name`` (slice 2 — NEW endpoint).

    Requires an authenticated, verified user (``require_verified_user``).
    Additionally requires ownership: ``project.owner_id == user.id``,
    otherwise ``403 not_owner``. Unknown project id → ``404``. Only
    ``name`` is updatable (per binding).
    """
    with _map_service_errors():
        try:
            project = await service.update_project(
                project_id=project_id,
                owner_id=user.id,
                name=body.name,
            )
        except NotOwnerError as exc:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="not_owner",
                user_message=str(exc),
            ) from exc
        return ProjectResponse.model_validate(project, from_attributes=True)


@router.post(
    "/projects/{project_id}/upload-ticket",
    response_model=UploadTicketResponse,
    summary="Request a presigned upload URL",
)
async def request_upload_ticket(
    project_id: str,
    body: UploadTicketRequest,
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
) -> UploadTicketResponse:
    """Request a presigned PUT URL for direct browser-to-R2 upload.

    Creates an Asset row and returns:
    - ``asset_id`` — the new Asset UUID
    - ``presigned_url`` — a time-limited PUT URL (5 min TTL)
    - ``r2_key`` — the object key to PUT to

    Authorization (4R CRITICAL 1 fix):
    - Authenticated user → authorize by ``project.owner_id == user.id``
      (X-Session-ID ignored). Anonymous projects claimed on login become
      accessible.
    - Anonymous caller → requires ``X-Session-ID`` (422 on missing) and
      authorizes by ``project.session_id == session_id``.
    """
    if user is None and not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Session-ID header is required",
        )
    with _map_service_errors():
        result = await service.request_upload_ticket(
            project_id=project_id,
            asset_name=body.asset_name,
            session_id=session_id if user is None else None,
            content_type=body.content_type,
            owner_id=user.id if user is not None else None,
        )
        return UploadTicketResponse(**result)


@router.patch(
    "/assets/{asset_id}/finalize",
    response_model=AssetResponse,
    summary="Confirm an upload completed",
)
async def finalize_asset(
    asset_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
) -> AssetResponse:
    """Confirm that an upload completed successfully.

    Authorization (4R CRITICAL 1 fix):
    - Authenticated user → authorize by ``project.owner_id == user.id``.
    - Anonymous caller → requires ``X-Session-ID`` and authorizes by
      ``project.session_id == session_id``.

    Returns the asset data so clients can display it immediately.
    """
    if user is None and not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Session-ID header is required",
        )
    with _map_service_errors():
        asset = await service.finalize_asset(
            asset_id=asset_id,
            session_id=session_id if user is None else None,
            owner_id=user.id if user is not None else None,
        )
        return AssetResponse.model_validate(asset, from_attributes=True)


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an asset",
)
async def delete_asset(
    asset_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
) -> None:
    """Soft-delete an asset by setting ``deleted_at``.

    Authorization (4R CRITICAL 1 fix):
    - Authenticated user → authorize by ``project.owner_id == user.id``.
    - Anonymous caller → requires ``X-Session-ID`` and authorizes by
      ``project.session_id == session_id``.

    The asset is excluded from default queries after deletion.  The
    backing R2 object will be hard-purged by the bucket lifecycle rule
    (≥30 days).
    """
    if user is None and not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Session-ID header is required",
        )
    with _map_service_errors():
        await service.soft_delete_asset(
            asset_id=asset_id,
            session_id=session_id if user is None else None,
            owner_id=user.id if user is not None else None,
        )


@router.get(
    "/r2/{r2_key:path}",
    summary="Resolve an asset R2 key to a presigned GET redirect",
)
async def get_r2_asset(
    r2_key: str,
    user: CurrentUser | None = Depends(get_optional_user),
    session_id: str = Depends(_optional_session),
    service: AssetsService = Depends(get_service),
):
    """Resolve an owned active asset key to a short-lived R2 redirect.

    Authorization (4R CRITICAL 1 fix):
    - Authenticated user → authorize by ``project.owner_id == user.id``.
    - Anonymous caller → requires ``X-Session-ID`` and authorizes by
      ``project.session_id == session_id``.
    """
    if user is None and not session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Session-ID header is required",
        )
    with _map_service_errors():
        asset = await service.get_asset_by_r2_key(
            r2_key=r2_key,
            session_id=session_id if user is None else None,
            owner_id=user.id if user is not None else None,
        )

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
