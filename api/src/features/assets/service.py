"""Business-logic layer for workspace Project and Asset management.

Provides ``AssetsService`` with methods for:

- **Project** CRUD — create, list (scoped to ``session_id``)
- **Upload ticket** — create an Asset row and generate a presigned PUT URL
- **Finalize** — confirm an upload completed (validates ownership)
- **Soft-delete** — set ``deleted_at`` to exclude from default queries

All public methods are async and expect a pre-existing ``async_sessionmaker``
for database access and an optional ``R2Storage`` instance for presigned URL
generation.

Fix notes (4R Review):
- ``r2_key`` is generated server-side via ``uuid.uuid4().hex`` to prevent
  path traversal / overwrites via user-provided ``asset_name``.
- Presigned URLs are generated *before* the DB commit to prevent ghost assets.
- All public methods return plain dicts, not ORM instances, to avoid
  ``DetachedInstanceError`` when the caller serialises the result after the
  session closes.
- Domain errors use typed exception classes (see ``exceptions.py``) instead of
  stringly-typed ``ValueError`` codes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from src.features.assets.exceptions import (
    AssetNotFoundError,
    ProjectNotFoundError,
    ProjectOwnershipError,
    StorageNotConfiguredError,
    StorageOperationError,
)
from src.shared.models.persistence import Asset, Project
from src.shared.storage import R2Storage, StorageError


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def _project_to_dict(project: Project) -> dict:
    """Convert a Project ORM instance to a plain dict suitable for
    Pydantic validation.

    Includes eager-loaded ``assets`` when available, otherwise returns
    an empty list (safe for detached instances).
    """
    from sqlalchemy import inspect as sa_inspect

    try:
        insp = sa_inspect(project)
        # ``unloaded`` is the set of attributes NOT yet loaded.
        # If "assets" is NOT in that set, it was loaded (e.g. via selectinload).
        assets_loaded = insp is not None and "assets" not in insp.unloaded
    except Exception:
        assets_loaded = False

    if assets_loaded:
        assets_list = [
            {
                "id": a.id,
                "name": a.name,
                "content_type": a.content_type,
                "r2_key": a.r2_key,
                "project_id": a.project_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in project.assets
        ]
    else:
        assets_list = []

    return {
        "id": project.id,
        "name": project.name,
        "owner_id": project.owner_id,
        "session_id": project.session_id,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "assets": assets_list,
    }


def _asset_to_dict(asset: Asset) -> dict:
    """Convert an Asset ORM instance to a plain dict."""
    return {
        "id": asset.id,
        "name": asset.name,
        "content_type": asset.content_type,
        "r2_key": asset.r2_key,
        "project_id": asset.project_id,
        "created_at": asset.created_at.isoformat(),
    }


class AssetsService:
    """Encapsulates business logic for Project and Asset operations.

    Usage::

        service = AssetsService(session_factory, storage)
        project = await service.create_project(name="Campaign A", session_id="sess-1")
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        storage: R2Storage | None = None,
    ) -> None:
        """Initialise the service.

        Args:
            session_factory: An ``async_sessionmaker`` bound to the
                application's ``AsyncEngine``.
            storage: An ``R2Storage`` instance for presigned URL generation.
                When ``None``, the service can still perform DB-only operations
                but ``request_upload_ticket`` will raise
                ``StorageNotConfiguredError``.
        """
        self._session_factory = session_factory
        self._storage = storage

    # ── Project operations ─────────────────────────────────────────────────

    async def create_project(
        self,
        name: str,
        session_id: str,
        owner_id: str | None = None,
    ) -> dict:
        """Create a new Project.

        Args:
            name: Project name (1–128 chars, validated upstream).
            session_id: The caller's session identifier.
            owner_id: Optional owner reference for multi-tenant use.

        Returns:
            A dict with the persisted project data (including an empty
            ``assets`` list).

        Raises:
            ValueError: If ``name`` or ``session_id`` is empty.
        """
        if not name or not session_id:
            raise ValueError("name and session_id are required")

        async with self._session_factory() as session:
            project = Project(
                name=name,
                session_id=session_id,
                owner_id=owner_id,
            )
            session.add(project)
            await session.commit()
            # Re-fetch with eager-loaded assets so the dict conversion works
            # even after the session closes (no detached-instance errors).
            stmt = (
                select(Project)
                .where(Project.id == project.id)
                .options(selectinload(Project.assets))
            )
            loaded = await session.scalar(stmt)
            return _project_to_dict(loaded)

    async def list_projects(self, session_id: str) -> list[dict]:
        """Return all projects for the given session (newest first).

        Each project includes its active (non-deleted) assets via
        ``selectinload`` to avoid N+1 queries.

        Args:
            session_id: The caller's session identifier.

        Returns:
            A list of project dicts, newest first.
        """
        if not session_id:
            return []

        async with self._session_factory() as session:
            stmt = (
                select(Project)
                .where(Project.session_id == session_id)
                .options(selectinload(Project.assets))
                .order_by(Project.created_at.desc())
            )
            result = await session.execute(stmt)
            return [_project_to_dict(p) for p in result.scalars().all()]

    # ── Upload ticket ──────────────────────────────────────────────────────

    async def request_upload_ticket(
        self,
        project_id: str,
        asset_name: str,
        session_id: str,
        content_type: str = "image/webp",
    ) -> dict:
        """Create an Asset row and return a presigned PUT URL.

        The asset is created in a ``pending`` state (no ``deleted_at``).
        The presigned URL allows the client to upload directly to R2.

        **Security**: ``r2_key`` is a server-side ``uuid.uuid4().hex``,
        NOT the user-provided ``asset_name``. This prevents path-traversal
        overwrites of existing objects.  The original ``asset_name`` is
        stored in the ``name`` column for display only.

        **Resilience**: The presigned URL is generated *before* the DB
        commit.  If URL generation fails, no Asset row is persisted,
        preventing ghost assets.

        Args:
            project_id: The owning Project's UUID.
            asset_name: The original file name (stored in DB for display).
            session_id: The caller's session (validated against the project).
            content_type: MIME type for the upload (default ``image/webp``).

        Returns:
            A dict with ``asset_id``, ``presigned_url``, and ``r2_key``.

        Raises:
            ProjectNotFoundError: If no project matches ``project_id``.
            ProjectOwnershipError: If the caller's session does not own the
                project.
            StorageNotConfiguredError: If no R2Storage backend is available.
            StorageOperationError: If the R2 presigned URL generation fails.
        """
        if self._storage is None:
            raise StorageNotConfiguredError(
                "R2Storage not configured — cannot generate upload tickets"
            )

        # Generate a server-side r2_key (uuid4 hex) to prevent path traversal
        # and object overwrites via user-provided asset_name.
        file_id = uuid.uuid4().hex
        r2_key = f"projects/{project_id}/{file_id}"

        # Generate presigned URL BEFORE any DB write — if this fails no ghost
        # asset is created.
        try:
            presigned_url = await self._storage.presigned_put(r2_key, content_type=content_type)
        except StorageError as exc:
            raise StorageOperationError(str(exc)) from exc

        async with self._session_factory() as session:
            # Validate project ownership
            stmt = select(Project).where(Project.id == project_id)
            project = await session.scalar(stmt)

            if project is None:
                raise ProjectNotFoundError(f"Project {project_id} not found")

            if project.session_id != session_id:
                raise ProjectOwnershipError(
                    f"Session {session_id} does not own project {project_id}"
                )

            # Create the asset row
            asset = Asset(
                name=asset_name,
                content_type=content_type,
                r2_key=r2_key,
                project_id=project_id,
            )
            session.add(asset)
            await session.commit()
            await session.refresh(asset)

            return {
                "asset_id": asset.id,
                "presigned_url": presigned_url,
                "r2_key": r2_key,
            }

    # ── Active asset lookup ────────────────────────────────────────────────

    async def get_active_asset(self, asset_id: str, session_id: str) -> dict:
        """Get an active (non-deleted) asset with ownership validation.

        Validates that the asset exists, has not been soft-deleted, and is
        owned by the caller's session (via the project chain).  Returns the
        asset dict including ``r2_key`` for generating presigned GET URLs.

        Args:
            asset_id: The Asset UUID.
            session_id: The caller's session identifier.

        Returns:
            A dict with the asset data (includes ``r2_key``).

        Raises:
            AssetNotFoundError: If no active asset matches ``asset_id``.
            ProjectOwnershipError: If the caller's session does not own the
                asset's project.
        """
        async with self._session_factory() as session:
            stmt = select(Asset).where(
                Asset.id == asset_id,
                Asset.deleted_at.is_(None),
            )
            asset = await session.scalar(stmt)

            if asset is None:
                raise AssetNotFoundError(
                    f"Asset {asset_id} not found or deleted"
                )

            # Validate ownership via project session
            project_stmt = select(Project).where(
                Project.id == asset.project_id
            )
            project = await session.scalar(project_stmt)

            if project is None or project.session_id != session_id:
                raise ProjectOwnershipError(
                    f"Session {session_id} does not own asset {asset_id}"
                )

            return _asset_to_dict(asset)

    # ── Asset finalize ─────────────────────────────────────────────────────

    async def finalize_asset(
        self,
        asset_id: str,
        session_id: str,
    ) -> dict:
        """Confirm an upload completed successfully.

        Validates that the asset exists and is owned by the caller's session
        (via the project chain).  Returns the asset data so clients can
        display it immediately.

        Args:
            asset_id: The Asset UUID.
            session_id: The caller's session identifier.

        Returns:
            A dict with the asset data.

        Raises:
            AssetNotFoundError: If no asset matches ``asset_id``.
            ProjectOwnershipError: If the caller's session does not own the
                asset's project.
        """
        async with self._session_factory() as session:
            stmt = select(Asset).where(Asset.id == asset_id)
            asset = await session.scalar(stmt)

            if asset is None:
                raise AssetNotFoundError(f"Asset {asset_id} not found")

            # Validate ownership via project session
            project_stmt = select(Project).where(Project.id == asset.project_id)
            project = await session.scalar(project_stmt)

            if project is None or project.session_id != session_id:
                raise ProjectOwnershipError(
                    f"Session {session_id} does not own asset {asset_id}"
                )

            return _asset_to_dict(asset)

    # ── Soft-delete ────────────────────────────────────────────────────────

    async def soft_delete_asset(
        self,
        asset_id: str,
        session_id: str,
    ) -> None:
        """Soft-delete an asset by setting ``deleted_at`` and moving its
        backing R2 object to the ``deleted/`` prefix for lifecycle cleanup.

        The asset is excluded from default queries after deletion.  The
        backing R2 object is copied to the ``deleted/`` prefix (then the
        original is removed) so the bucket lifecycle rule (≥30 days) can
        hard-purge it later.

        **Transactional integrity**: ``mark_deleted`` is called *before*
        the DB commit.  If the storage operation fails the DB session is
        rolled back, so ``deleted_at`` is NOT persisted — the asset
        remains active and visible in queries.

        Args:
            asset_id: The Asset UUID.
            session_id: The caller's session identifier.

        Raises:
            AssetNotFoundError: If no asset matches ``asset_id``.
            ProjectOwnershipError: If the caller's session does not own the
                asset's project.
            StorageNotConfiguredError: If no R2Storage backend is available.
            StorageOperationError: If the R2 mark_deleted operation fails.
        """
        if self._storage is None:
            raise StorageNotConfiguredError(
                "R2Storage not configured — cannot delete asset backing object"
            )

        async with self._session_factory() as session:
            stmt = select(Asset).where(Asset.id == asset_id)
            asset = await session.scalar(stmt)

            if asset is None:
                raise AssetNotFoundError(f"Asset {asset_id} not found")

            # Validate ownership via project session
            project_stmt = select(Project).where(Project.id == asset.project_id)
            project = await session.scalar(project_stmt)

            if project is None or project.session_id != session_id:
                raise ProjectOwnershipError(
                    f"Session {session_id} does not own asset {asset_id}"
                )

            r2_key = asset.r2_key
            asset.deleted_at = _now()

            # Call mark_deleted BEFORE the DB commit so that a storage
            # failure triggers a rollback — the asset stays active.
            try:
                await self._storage.mark_deleted(r2_key)
            except StorageError as exc:
                await session.rollback()
                raise StorageOperationError(str(exc)) from exc

            await session.commit()
