"""Business-logic layer for workspace Project and Asset management.

Provides ``AssetsService`` with methods for:

- **Project** CRUD — create, list (scoped to ``session_id``)
- **Upload ticket** — create an Asset row and generate a presigned PUT URL
- **Finalize** — confirm an upload completed (validates ownership)
- **Soft-delete** — set ``deleted_at`` to exclude from default queries

All public methods are async and expect a pre-existing ``async_sessionmaker``
for database access and an optional ``R2Storage`` instance for presigned URL
generation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from src.shared.models.persistence import Asset, Project
from src.shared.storage import R2Storage


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


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
                but ``request_upload_ticket`` will raise ``ValueError``.
        """
        self._session_factory = session_factory
        self._storage = storage

    # ── Project operations ─────────────────────────────────────────────────

    async def create_project(
        self,
        name: str,
        session_id: str,
        owner_id: str | None = None,
    ) -> Project:
        """Create a new Project.

        Args:
            name: Project name (1–128 chars, validated upstream).
            session_id: The caller's session identifier.
            owner_id: Optional owner reference for multi-tenant use.

        Returns:
            The persisted ``Project`` ORM instance.

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
            await session.refresh(project)
            return project

    async def list_projects(self, session_id: str) -> list[Project]:
        """Return all projects for the given session (newest first).

        Each project includes its active (non-deleted) assets via
        ``selectinload`` to avoid N+1 queries.

        Args:
            session_id: The caller's session identifier.

        Returns:
            A list of ``Project`` instances, newest first.
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
            return list(result.scalars().all())

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

        Args:
            project_id: The owning Project's UUID.
            asset_name: The original file name.
            session_id: The caller's session (validated against the project).
            content_type: MIME type for the upload (default ``image/webp``).

        Returns:
            A dict with ``asset_id``, ``presigned_url``, and ``r2_key``.

        Raises:
            ValueError: With ``project_not_found`` or ``session_mismatch``
                when the project does not exist or is not owned by the session.
        """
        if self._storage is None:
            raise RuntimeError("R2Storage not configured — cannot generate upload tickets")

        async with self._session_factory() as session:
            # Validate project ownership
            stmt = select(Project).where(Project.id == project_id)
            project = await session.scalar(stmt)

            if project is None:
                raise ValueError("project_not_found")

            if project.session_id != session_id:
                raise ValueError("session_mismatch")

            # Create the asset row
            r2_key = f"projects/{project_id}/{asset_name}"
            asset = Asset(
                name=asset_name,
                content_type=content_type,
                r2_key=r2_key,
                project_id=project_id,
            )
            session.add(asset)
            await session.commit()
            await session.refresh(asset)

        # Generate presigned PUT URL
        presigned_url = await self._storage.presigned_put(r2_key)

        return {
            "asset_id": asset.id,
            "presigned_url": presigned_url,
            "r2_key": r2_key,
        }

    # ── Asset finalize ─────────────────────────────────────────────────────

    async def finalize_asset(
        self,
        asset_id: str,
        session_id: str,
    ) -> Asset:
        """Confirm an upload completed successfully.

        Validates that the asset exists and is owned by the caller's session
        (via the project chain).  Returns the asset data so clients can
        display it immediately.

        Args:
            asset_id: The Asset UUID.
            session_id: The caller's session identifier.

        Returns:
            The ``Asset`` ORM instance.

        Raises:
            ValueError: With ``asset_not_found`` or ``session_mismatch``.
        """
        async with self._session_factory() as session:
            stmt = select(Asset).where(Asset.id == asset_id)
            asset = await session.scalar(stmt)

            if asset is None:
                raise ValueError("asset_not_found")

            # Validate ownership via project session
            project_stmt = select(Project).where(Project.id == asset.project_id)
            project = await session.scalar(project_stmt)

            if project is None or project.session_id != session_id:
                raise ValueError("session_mismatch")

            return asset

    # ── Soft-delete ────────────────────────────────────────────────────────

    async def soft_delete_asset(
        self,
        asset_id: str,
        session_id: str,
    ) -> None:
        """Soft-delete an asset by setting ``deleted_at``.

        The asset is excluded from default queries after deletion.  The
        backing R2 object will be hard-purged by the bucket lifecycle rule
        (``deleted/`` prefix, ≥30 days).

        Args:
            asset_id: The Asset UUID.
            session_id: The caller's session identifier.

        Raises:
            ValueError: With ``asset_not_found`` or ``session_mismatch``.
        """
        async with self._session_factory() as session:
            stmt = select(Asset).where(Asset.id == asset_id)
            asset = await session.scalar(stmt)

            if asset is None:
                raise ValueError("asset_not_found")

            # Validate ownership via project session
            project_stmt = select(Project).where(Project.id == asset.project_id)
            project = await session.scalar(project_stmt)

            if project is None or project.session_id != session_id:
                raise ValueError("session_mismatch")

            asset.deleted_at = _now()
            await session.commit()
