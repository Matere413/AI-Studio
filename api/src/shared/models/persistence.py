"""Asynchronous SQLAlchemy 2.0 ORM models for Project and Asset persistence.

Provides:
- ``Project`` — workspace project with nullable owner_id and session binding
- ``Asset`` — file asset with soft-delete support via ``deleted_at``
- ``create_async_engine()`` — shorthand for ``sqlalchemy.ext.asyncio.create_async_engine``
- Engine lifecycle: ``init_db()``, ``close_db()`` for app startup/shutdown
- ``async_session_factory()`` — context-managed ``AsyncSession``
- ``active_assets()`` — query helper that filters ``deleted_at IS NULL``
"""

import uuid
from datetime import datetime, timezone

import asyncio

from sqlalchemy import String, DateTime, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _uuid_column(**kwargs):
    """Return a UUID primary key column compatible with both SQLite and PostgreSQL.

    SQLite stores UUIDs as strings; PostgreSQL uses the native UUID type.
    """
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        **kwargs,
    )


class Project(Base):
    """A workspace project that groups assets.

    Attributes:
        id: UUID primary key (string for SQLite compat).
        name: Human-readable project name (1–128 chars).
        owner_id: Optional owner reference for future multi-tenant use.
        session_id: Session that created this project.
        created_at: Auto-set creation timestamp.
        assets: ORM relationship to linked Asset rows.
    """

    __tablename__ = "projects"

    id: Mapped[str] = _uuid_column()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="project",
        cascade="all, delete-orphan",
        foreign_keys="Asset.project_id",
        primaryjoin="and_(Asset.project_id == Project.id, Asset.deleted_at.is_(None))",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id!r} name={self.name!r}>"


class Asset(Base):
    """A stored file asset with soft-delete support.

    Attributes:
        id: UUID primary key (string for SQLite compat).
        name: Original file name.
        content_type: MIME type (e.g. ``image/png``, ``image/webp``).
        r2_key: Object key in the R2 bucket.
        project_id: FK to the owning Project.
        deleted_at: Soft-delete timestamp; ``None`` when active.
        created_at: Auto-set creation timestamp.
        project: ORM relationship to the parent Project.
    """

    __tablename__ = "assets"

    id: Mapped[str] = _uuid_column()
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="assets",
        foreign_keys=[project_id],
    )

    def __repr__(self) -> str:
        status = "active" if self.deleted_at is None else "deleted"
        return f"<Asset id={self.id!r} name={self.name!r} status={status}>"


# ─── Engine Lifecycle ─────────────────────────────────────────────────────────


_engine: AsyncEngine | None = None
"""Module-level engine singleton for production use."""


async def init_db(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create and cache the global ``AsyncEngine``, creating all tables.

    Call this during application startup (e.g. in a FastAPI lifespan).
    If an engine is already cached it will be disposed first.
    """
    global _engine
    await close_db()
    _engine = _create_async_engine(
        database_url,
        echo=echo,
        pool_size=5,
        max_overflow=10,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return _engine


async def close_db() -> None:
    """Dispose the global ``AsyncEngine``.

    Call this during application shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    """Return the module-level cached ``AsyncEngine``.

    Raises:
        RuntimeError: If ``init_db()`` has not been called yet.
    """
    if _engine is None:
        raise RuntimeError(
            "AsyncEngine not initialised. Call init_db(database_url) during app startup."
        )
    return _engine


def async_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return an ``async_sessionmaker`` bound to the given or cached engine."""
    return async_sessionmaker(
        engine or get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ─── Query Helpers ────────────────────────────────────────────────────────────


async def active_assets(
    session: AsyncSession,
    project_id: str,
    session_id: str | None = None,
) -> list[Asset]:
    """Return all non-deleted (``deleted_at IS NULL``) assets for a project.

    When ``session_id`` is provided, additionally joins with the owning
    ``Project`` and filters by ``Project.session_id`` to enforce the
    caller's session boundary.

    Args:
        session: An active ``AsyncSession``.
        project_id: The project to filter by.
        session_id: Optional — enforces the caller's session boundary
                    when provided.

    Returns:
        A list of ``Asset`` rows with ``deleted_at`` set to ``None``, ordered
        by ``created_at`` descending (newest first).
    """
    stmt = (
        select(Asset)
        .join(Asset.project)
        .where(Asset.project_id == project_id, Asset.deleted_at.is_(None))
        .order_by(Asset.created_at.desc())
    )
    if session_id is not None:
        stmt = stmt.where(Project.session_id == session_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
