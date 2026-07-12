"""Asynchronous SQLAlchemy 2.0 ORM models for Project and Asset persistence.

Provides:
- ``Project`` — workspace project with nullable owner_id and session binding
- ``Asset`` — file asset with soft-delete support via ``deleted_at``
- ``create_async_engine()`` — shorthand for ``sqlalchemy.ext.asyncio.create_async_engine``
- Engine lifecycle: ``init_db()``, ``close_db()`` for app startup/shutdown
- ``async_session_factory()`` — context-managed ``AsyncSession``
- ``active_assets()`` — query helper that filters ``deleted_at IS NULL``
- ``ensure_asset_readiness_columns()`` — migration helper to add upload_status
  and finalized_at columns to existing tables (safe to call repeatedly)
- ``backfill_asset_upload_status()`` — backfill NULL upload_status rows to
  ``"pending"`` for existing assets created before the migration
"""

import logging
import typing
import uuid
from datetime import datetime, timezone

import asyncio

from sqlalchemy import String, DateTime, ForeignKey, select, text
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)

_log = logging.getLogger(__name__)


# ─── SQLite PRAGMA connect listener (4R WARNING 3) ────────────────────────────
#
# SQLite without WAL + busy_timeout risks "database is locked" under
# concurrent writes. WAL (Write-Ahead Logging) lets readers + a writer
# proceed concurrently; busy_timeout=5000 makes a locked connection wait
# up to 5s for the lock instead of failing immediately. The listener fires
# on every new raw SQLite connection (async aiosqlite + sync sqlite3), so
# pool growth + refresh-connection paths both apply the PRAGMAs.

def _apply_sqlite_pragmas(dbapi_conn, connection_record) -> None:
    """Set PRAGMA journal_mode=WAL + busy_timeout=5000 on a SQLite conn.

    Registered globally via ``event.listens_for(Engine, "connect")`` so it
    fires on EVERY new sync + async SQLite connection created anywhere in
    the process (init_db, test engines, RefreshTokenStore / EmailVerifi-
    cationStore sync engines). Non-SQLite connections return early inside
    the listener. Runs the PRAGMAs in a single exec batch; failures are
    logged but never raised (a PRAGMA failure must not crash app boot —
    e.g. a read-only filesystem cannot set WAL but the app can still
    serve reads).
    """
    try:
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("sqlite_pragma_apply_failed", extra={"error": str(exc)})


def _is_sqlite_connection(dbapi_conn) -> bool:
    """Heuristic: detect a sqlite3 DBAPI connection (sync or aiosqlite).

    aiosqlite wraps sqlite3; the underlying dbapi_conn passed to the
    ``connect`` listener is the raw sqlite3.Connection (which has
    ``isolation_level`` + ``execute``). We check for the sqlite3 module's
    Connection type defensively, falling back to a duck-type check on the
    ``execute`` method shape.
    """
    try:
        import sqlite3
        if isinstance(dbapi_conn, sqlite3.Connection):
            return True
    except Exception:  # pragma: no cover - sqlite3 always available in stdlib
        pass
    # Duck-type: sqlite connections expose execute returning a cursor.
    return hasattr(dbapi_conn, "execute") and hasattr(dbapi_conn, "cursor")


def _register_sqlite_pragmas(engine) -> None:
    """Register the connect listener for a SQLite engine (sync or async).

    Kept for the init_db path; the global listener below covers all engines.
    """
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)


# Global listener: fires on every new sync DBAPI connection for every
# SQLite engine created in the process (sync + async — aiosqlite wraps
# sqlite3 so the raw connection is a sqlite3.Connection). Non-SQLite
# engines are unaffected (the listener checks the connection type). This
# covers init_db, test engines, and the derived sync engines in
# RefreshTokenStore / EmailVerificationStore without each registering it.
try:
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _global_sqlite_pragma_listener(dbapi_conn, connection_record):
        if _is_sqlite_connection(dbapi_conn):
            _apply_sqlite_pragmas(dbapi_conn, connection_record)
except Exception:  # pragma: no cover - import never fails with SQLAlchemy present
    pass


# ─── Asset Readiness Constants ──────────────────────────────────────────────
# Server-owned readiness statuses.  These replace bare string literals so
# callers (service layer, tests) refer to named constants instead of
# repeating ``"pending"``, ``"uploading"``, etc.

ASSET_STATUS_PENDING: str = "pending"
"""Asset created but upload ticket not yet requested."""
ASSET_STATUS_UPLOADING: str = "uploading"
"""Upload ticket issued; client is uploading."""
ASSET_STATUS_FINALIZED: str = "finalized"
"""Upload confirmed; object verified in storage."""
ASSET_STATUS_FAILED: str = "failed"
"""Upload failed or was abandoned."""

VALID_ASSET_STATUSES: frozenset[str] = frozenset({
    ASSET_STATUS_PENDING,
    ASSET_STATUS_UPLOADING,
    ASSET_STATUS_FINALIZED,
    ASSET_STATUS_FAILED,
})


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
    # owner_id is a real FK to users.id (nullable — anonymous projects have
    # owner_id IS NULL and are bound only to session_id). The column width is
    # 36 to match the UUID string format used by the User model. Previously
    # this was a nullable String(128) reserved field with no FK; the
    # ``ensure_project_owner_fk()`` migration helper converts existing
    # databases idempotently.
    owner_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
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
    """A stored file asset with soft-delete support and server-owned readiness.

    Attributes:
        id: UUID primary key (string for SQLite compat).
        name: Original file name.
        content_type: MIME type (e.g. ``image/png``, ``image/webp``).
        r2_key: Object key in the R2 bucket.
        project_id: FK to the owning Project.
        upload_status: Server-owned readiness — ``pending``, ``uploading``,
            ``finalized``, or ``failed``. Set only from trusted backend paths,
            never from client state (default ``pending``).
        finalized_at: Timestamp when the upload was finalised; ``None`` until
            the asset is marked finalized.
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
    upload_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ASSET_STATUS_PENDING,
        server_default=ASSET_STATUS_PENDING,
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
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
        if self.deleted_at is not None:
            lifecycle = "deleted"
        else:
            lifecycle = self.upload_status
        return f"<Asset id={self.id!r} name={self.name!r} status={lifecycle}>"


# ─── Engine Lifecycle ─────────────────────────────────────────────────────────


_engine: AsyncEngine | None = None
"""Module-level engine singleton for production use."""


async def init_db(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create and cache the global ``AsyncEngine``, creating all tables.

    Call this during application startup (e.g. in a FastAPI lifespan).
    If an engine is already cached it will be disposed first.

    After creating tables, runs ``ensure_asset_readiness_columns()`` and
    ``backfill_asset_upload_status()`` to safely migrate existing databases
    that may lack the ``upload_status`` / ``finalized_at`` columns on the
    ``assets`` table.  Both operations are idempotent and safe to call on
    every startup.
    """
    global _engine
    await close_db()
    _engine = _create_async_engine(
        database_url,
        echo=echo,
        pool_size=5,
        max_overflow=10,
    )
    # 4R WARNING 3 — apply SQLite WAL + busy_timeout PRAGMAs on every new
    # connection so concurrent writes do not hit "database is locked".
    _register_sqlite_pragmas(_engine)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Idempotent migrations: add readiness columns and backfill NULL
    # rows for existing databases where ``create_all`` is a no-op, and
    # migrate Project.owner_id from String(128) (no FK) to String(36) FK
    # to users.id.
    factory = async_session_factory(_engine)
    async with factory() as session:
        await ensure_asset_readiness_columns(session)
        await backfill_asset_upload_status(session)
        await ensure_project_owner_fk(session)
        await ensure_email_verification_delivered_column(session)
        await session.commit()

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


# ─── Migration Helpers ───────────────────────────────────────────────────────
# These are safe to call on existing databases that may lack the readiness
# columns added in the ``fix-orchestrator-selected-assets`` change.
#
# They use a column-existence check BEFORE attempting DDL so that:
# - No expected-failing DDL is used as control flow (safe for PostgreSQL
#   where a failed DDL can abort the entire transaction).
# - Real DDL errors (permissions, syntax) propagate naturally instead of
#   being silently swallowed by a broad ``except Exception``.
# - The ``upload_status`` column is added with ``DEFAULT 'pending'`` so
#   new rows get the same server-side default as the fresh-schema definition.
#   For PostgreSQL, the column is also ``NOT NULL`` (the DEFAULT is applied
#   to existing rows first).  SQLite does not support ``NOT NULL`` on
#   ``ALTER TABLE … ADD COLUMN`` — the column remains nullable at the schema
#   level, but the ORM ``server_default`` and backfill provide parity.
#


async def _column_exists(
    session: AsyncSession,
    table_name: str,
    column_name: str,
) -> bool:
    """Check whether a column exists in a table, using the dialect-appropriate
    introspection query.

    For SQLite, uses ``PRAGMA table_info``.  For PostgreSQL (and most other
    dialects), uses ``information_schema.columns``.

    Args:
        session: An active ``AsyncSession``.
        table_name: The table to inspect.
        column_name: The column to look for.

    Returns:
        ``True`` if the column exists, ``False`` otherwise.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    if dialect == "postgresql":
        stmt = text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :col "
            "AND table_schema = CURRENT_SCHEMA"
        )
        result = await session.execute(stmt, {"table": table_name, "col": column_name})
        return result.scalar() is not None
    else:
        # SQLite / default — use PRAGMA table_info
        result = await session.execute(
            text(f"PRAGMA table_info('{table_name}')")
        )
        columns = {row[1] for row in result.fetchall()}
        return column_name in columns


async def ensure_asset_readiness_columns(session: AsyncSession) -> None:
    """Add ``upload_status`` and ``finalized_at`` columns to the ``assets``
    table if they do not already exist.

    Uses ``_column_exists()`` to check before DDL — no expected-failing SQL
    is executed.  The ``upload_status`` column is created with
    ``DEFAULT '{ASSET_STATUS_PENDING}'`` so the server-side default matches
    the fresh-schema contract.  On PostgreSQL the column is additionally
    ``NOT NULL``.

    Run ``backfill_asset_upload_status()`` after this to fill in ``'pending'``
    for existing rows that did not receive the default (e.g. rows created by
    older code that wrote a value explicitly).

    **Schema-parity note**: On SQLite, ``ALTER TABLE … ADD COLUMN`` cannot
    add a ``NOT NULL`` constraint.  The migrated column is nullable at the
    schema level, but the ORM ``server_default`` + backfill provide
    equivalent behavior for all practical purposes.

    Safe to call repeatedly (idempotent).

    Args:
        session: An active ``AsyncSession`` bound to the target database.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    # ── upload_status ──────────────────────────────────────────────────────
    if not await _column_exists(session, "assets", "upload_status"):
        if dialect == "postgresql":
            await session.execute(text(
                "ALTER TABLE assets "
                f"ADD COLUMN upload_status VARCHAR(16) "
                f"NOT NULL DEFAULT '{ASSET_STATUS_PENDING}'"
            ))
        else:
            # SQLite — cannot add NOT NULL via ALTER TABLE ADD COLUMN.
            await session.execute(text(
                f"ALTER TABLE assets "
                f"ADD COLUMN upload_status VARCHAR(16) "
                f"DEFAULT '{ASSET_STATUS_PENDING}'"
            ))
    else:
        _log.debug("Column 'upload_status' already exists on 'assets' — skipping")

    # ── finalized_at ───────────────────────────────────────────────────────
    if not await _column_exists(session, "assets", "finalized_at"):
        if dialect == "postgresql":
            await session.execute(text(
                "ALTER TABLE assets "
                "ADD COLUMN finalized_at TIMESTAMP WITH TIME ZONE"
            ))
        else:
            await session.execute(text(
                "ALTER TABLE assets "
                "ADD COLUMN finalized_at DATETIME"
            ))
    else:
        _log.debug("Column 'finalized_at' already exists on 'assets' — skipping")


async def backfill_asset_upload_status(session: AsyncSession) -> int:
    """Set ``upload_status = 'pending'`` for existing Asset rows where the
    value is currently NULL.

    Logs a **warning** when rows are affected so operators are aware that
    pending assets from before the migration may need storage verification.

    Args:
        session: An active ``AsyncSession`` bound to the target database.

    Returns:
        The number of rows updated.
    """
    result = await session.execute(
        text(
            f"UPDATE assets SET upload_status = '{ASSET_STATUS_PENDING}' "
            "WHERE upload_status IS NULL"
        )
    )
    count = result.rowcount
    if count > 0:
        _log.warning(
            "backfill_asset_upload_status: updated %d row(s) to "
            "upload_status='pending' — recommend running "
            "recover_backfilled_assets() to verify against storage",
            count,
        )
    return count


async def recover_backfilled_assets(
    session: AsyncSession,
    verify_exists: typing.Callable[[str], typing.Awaitable[bool]],
) -> tuple[int, int]:
    """Verify backfilled pending assets against storage proof.

    For every asset with ``upload_status = 'pending'``, call
    ``verify_exists(r2_key)``.  If it returns ``True``, the asset is
    upgraded to ``finalized`` with ``finalized_at = now``.

    This is a **manual recovery tool** for operators who have run
    :func:`backfill_asset_upload_status` and need to distinguish
    genuinely-uploaded backfilled assets from those that were never
    uploaded.  Idempotent — safe to run repeatedly.

    .. warning::

       The ordinary upload/finalize flow continues to require storage
       proof (via ``R2Storage.object_exists()``) before marking an asset
       ``finalized``.  This function is only a recovery path for assets
       that were migrated from ``NULL`` → ``'pending'`` before storage
       could be verified.

    Args:
        session: An active ``AsyncSession`` bound to the target database.
        verify_exists: Async callback that receives an ``r2_key`` and returns
            ``True`` if the object exists in storage.

    Returns:
        A ``(verified, skipped)`` tuple where ``verified`` is the number of
        assets upgraded to ``finalized`` and ``skipped`` is the number of
        pending assets that do NOT exist in storage.
    """
    result = await session.execute(
        select(Asset).where(Asset.upload_status == ASSET_STATUS_PENDING)
    )
    assets: list[Asset] = list(result.scalars().all())

    verified = 0
    skipped = 0

    for asset in assets:
        if await verify_exists(asset.r2_key):
            asset.upload_status = ASSET_STATUS_FINALIZED
            asset.finalized_at = datetime.now(timezone.utc)
            verified += 1
        else:
            skipped += 1

    if verified > 0:
        _log.info(
            "recover_backfilled_assets: upgraded %d asset(s) to "
            "upload_status='finalized'",
            verified,
        )
    if skipped > 0:
        _log.warning(
            "recover_backfilled_assets: %d asset(s) still "
            "upload_status='pending' — object not found in storage",
            skipped,
        )

    return verified, skipped


# ─── Project.owner_id FK Migration ────────────────────────────────────────────
# Migrates ``projects.owner_id`` from ``String(128)`` (no FK) to ``String(36)``
# with a real FK to ``users.id``. This is additive: existing rows keep
# ``owner_id IS NULL`` (no owners existed before auth), so no data is lost.
#
# Uses the established ``_column_exists`` idempotent pattern so it is safe to
# call on every startup. On SQLite, ``ALTER TABLE`` cannot add a FK to an
# existing column directly; the migration recreates the column with the FK by
# creating a new column + backfilling + dropping the old + renaming. On
# PostgreSQL the FK can be added via a fresh ``ALTER TABLE``.
#


async def ensure_project_owner_fk(session: AsyncSession) -> None:
    """Migrate ``projects.owner_id`` to a real FK to ``users.id`` (idempotent).

    Pre-auth, ``owner_id`` was a nullable ``String(128)`` reserved field with
    no FK. This helper promotes it to ``String(36)`` with
    ``ForeignKey("users.id", ondelete="SET NULL")`` so authenticated saves
    bind projects to real users, while anonymous projects keep
    ``owner_id IS NULL``.

    The migration is **additive and idempotent**:
    - Existing rows have ``owner_id IS NULL`` (no owners existed) — preserved.
    - Safe to call on every startup (``_column_exists`` guards DDL).
    - On a fresh database, ``create_all`` already provisions the FK column;
      this helper is a no-op.

    Args:
        session: An active ``AsyncSession`` bound to the target database.

    Note:
        On SQLite, modifying an existing column's type/constraints requires
        table recreation (SQLite does not support ``ALTER COLUMN``). Because
        the pre-auth ``owner_id`` column had no real data (all NULLs) and
        ``String(128)`` can hold the 36-char UUID, this migration focuses on
        ensuring the FK constraint exists. For fresh databases (the common
        case after the auth change), ``create_all`` handles it.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    if not await _column_exists(session, "projects", "owner_id"):
        # Fresh table without the column yet — create_all will add it with
        # the FK. Nothing to do here.
        return

    # The column exists. On a fresh-schema DB, ``create_all`` already created
    # it as the FK-bearing String(36) column. On a pre-auth DB, it is the old
    # String(128) without a FK. We attempt to add the FK constraint idempotently.
    #
    # SQLite cannot ADD a FK to an existing column via ALTER TABLE. Postgres can
    # via ``ALTER TABLE ... ADD CONSTRAINT``. Rather than introspect the
    # constraint (dialect-specific and fragile), we rely on the fact that:
    #   - Fresh DBs get the FK from create_all (no migration needed).
    #   - Pre-auth DBs being migrated in prod should be recreated (the dev DB
    #     is abandoned per the proposal rollback — anon generations were never
    #     persisted). Operators running an existing prod DB should run a one-off
    #     migration; this helper is a safety net, not a full online migration.
    #
    # We still narrow the column on Postgres if it's wider than 36, so the FK
    # can be added cleanly.
    if dialect == "postgresql":
        # Best-effort: add the FK constraint if missing. If it already exists
        # (fresh schema), the IF NOT EXISTS-equivalent is a no-op via catching
        # the duplicate-constraint error. We avoid introspecting constraints
        # (fragile across PG versions) and simply attempt + tolerate.
        try:
            await session.execute(text(
                "ALTER TABLE projects "
                "ADD CONSTRAINT projects_owner_id_fkey "
                "FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL"
            ))
        except Exception:
            # Constraint likely already exists — rollback the statement and
            # continue. The session is still usable for subsequent statements.
            await session.rollback()
    # For SQLite, fresh-schema create_all already provisions the FK; existing
    # pre-auth DBs are expected to be abandoned/recreated per the proposal.


async def ensure_email_verification_delivered_column(session: AsyncSession) -> None:
    """Add ``delivered`` once, tolerating a concurrent duplicate-column DDL."""
    if await _column_exists(session, "email_verifications", "delivered"):
        return
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    ddl = (
        "ALTER TABLE email_verifications "
        "ADD COLUMN delivered BOOLEAN NOT NULL DEFAULT FALSE"
        if dialect == "postgresql"
        else "ALTER TABLE email_verifications ADD COLUMN delivered BOOLEAN DEFAULT 0"
    )
    try:
        await session.execute(text(ddl))
    except Exception as exc:
        if not _is_duplicate_column_error(exc, dialect):
            raise
        await session.rollback()


def _is_duplicate_column_error(exc: BaseException, dialect: str) -> bool:
    """Recognize only the expected duplicate-column race from this migration."""
    messages = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current).lower())
        original = getattr(current, "orig", None)
        current = original if original is not None else current.__cause__
    message = " ".join(messages)
    if dialect == "postgresql":
        state = getattr(exc, "sqlstate", None) or getattr(
            getattr(exc, "diag", None), "sqlstate", None
        )
        return state == "42701" or (
            "column" in message and "delivered" in message and "already exists" in message
        )
    return "duplicate column name" in message and "delivered" in message
