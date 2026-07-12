"""Unit tests for Project and Asset ORM models.

Covers model creation, field validation, async session lifecycle,
the active_assets() soft-delete filter, and surgical fixes from
4R reviews (pooling, lifespan safety, PRAGMA, cross-session scoping).
"""

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.orm import selectinload

from src.shared.models.persistence import (
    Asset,
    Base,
    Project,
    active_assets,
    async_session_factory,
    close_db,
    init_db,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_session():
    """Create an isolated in-memory SQLite session for each test.

    Creates all tables before the test and drops them after.
    Enables ``PRAGMA foreign_keys=ON`` so that FK violations raise
    ``IntegrityError`` rather than silently succeeding.
    """
    engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
        await conn.run_sync(Project.metadata.create_all)

    factory = async_session_factory(engine)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Project.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def sample_project(db_session):
    """Create and return a sample project bound to a test session.

    ``owner_id`` is ``None`` (anonymous project) so the FK to ``users.id``
    added in the add-auth change is not violated. Tests that need a real
    owner create a ``User`` first.
    """
    project = Project(
        name="Campaign A",
        owner_id=None,
        session_id="session-abc",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def sample_asset(db_session, sample_project):
    """Create and return a sample asset belonging to sample_project."""
    asset = Asset(
        name="face.png",
        content_type="image/png",
        r2_key="projects/abc-123/face.png",
        project_id=sample_project.id,
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)
    return asset


# ─── Project Model ────────────────────────────────────────────────────────────


class TestProjectModel:
    """Unit tests for Project ORM creation and field constraints."""

    async def test_create_project_with_all_fields(self, db_session):
        """GIVEN a Project with name, owner_id, and session_id
        WHEN persisted
        THEN all fields are stored correctly.

        Since the add-auth change, ``owner_id`` is a real FK to ``users.id``;
        the test creates a real ``User`` first so the FK is satisfied.
        """
        from src.features.auth.infrastructure.models import User

        user = User(email="owner@test.io", password_hash="$argon2id$h")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        project = Project(
            name="Campaign A",
            owner_id=user.id,
            session_id="session-abc",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        assert project.id is not None
        assert project.name == "Campaign A"
        assert project.owner_id == user.id
        assert project.session_id == "session-abc"
        assert isinstance(project.created_at, datetime)

    async def test_create_project_with_nullable_owner_id(self, db_session):
        """GIVEN a Project without owner_id
        WHEN persisted
        THEN owner_id is NULL.
        """
        project = Project(name="Anonymous Project", session_id="session-xyz")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        assert project.owner_id is None
        assert project.name == "Anonymous Project"

    async def test_project_created_at_defaults_to_now(self, db_session):
        """GIVEN a newly created Project
        WHEN inspected
        THEN created_at is within the last 5 seconds.
        """
        before = datetime.now(timezone.utc)
        project = Project(name="Timely", session_id="session-ts")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        created = project.created_at.replace(tzinfo=timezone.utc)
        assert before.timestamp() - 5 <= created.timestamp() <= before.timestamp() + 5


# ─── Asset Model ──────────────────────────────────────────────────────────────


class TestAssetModel:
    """Unit tests for Asset ORM creation and field constraints."""

    async def test_create_asset_with_all_fields(self, db_session, sample_project):
        """GIVEN an Asset with name, content_type, r2_key, and project_id
        WHEN persisted
        THEN all fields are stored correctly.
        """
        asset = Asset(
            name="face.png",
            content_type="image/png",
            r2_key="projects/abc-123/face.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.id is not None
        assert asset.name == "face.png"
        assert asset.content_type == "image/png"
        assert asset.r2_key == "projects/abc-123/face.png"
        assert asset.project_id == sample_project.id
        assert asset.deleted_at is None
        assert isinstance(asset.created_at, datetime)

    async def test_asset_default_deleted_at_is_none(self, db_session, sample_project):
        """GIVEN a newly created Asset
        WHEN persisted without deleted_at
        THEN deleted_at is NULL.
        """
        asset = Asset(
            name="active.png",
            content_type="image/png",
            r2_key="projects/abc/active.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.deleted_at is None

    async def test_asset_can_be_soft_deleted(self, db_session, sample_project):
        """GIVEN an existing Asset
        WHEN deleted_at is set
        THEN the field is populated.
        """
        asset = Asset(
            name="delete-me.png",
            content_type="image/png",
            r2_key="projects/abc/delete-me.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        delete_time = datetime.now(timezone.utc)
        asset.deleted_at = delete_time
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.deleted_at is not None
        assert abs((asset.deleted_at.replace(tzinfo=timezone.utc) - delete_time).total_seconds()) < 2

    async def test_asset_project_relationship(self, db_session, sample_project):
        """GIVEN an Asset linked to a Project
        WHEN accessing asset.project
        THEN the related project is returned.
        """
        asset = Asset(
            name="linked.png",
            content_type="image/png",
            r2_key="projects/abc/linked.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()

        fetched = await db_session.get(Asset, asset.id)
        assert fetched is not None
        assert fetched.project.name == "Campaign A"

    # ── Trusted Readiness Fields ──────────────────────────────────────────

    async def test_asset_default_upload_status_is_pending(self, db_session, sample_project):
        """GIVEN a newly created Asset
        WHEN persisted without explicit upload_status
        THEN upload_status defaults to "pending".
        """
        asset = Asset(
            name="new.png",
            content_type="image/png",
            r2_key="projects/abc/new.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.upload_status == "pending"

    async def test_asset_upload_status_can_be_set_explicitly(self, db_session, sample_project):
        """GIVEN an Asset
        WHEN upload_status is set to "uploading"
        THEN the field is persisted.
        """
        asset = Asset(
            name="uploading.png",
            content_type="image/png",
            r2_key="projects/abc/uploading.png",
            project_id=sample_project.id,
            upload_status="uploading",
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.upload_status == "uploading"

    async def test_asset_upload_status_can_be_finalized(self, db_session, sample_project):
        """GIVEN an Asset with upload_status="finalized"
        WHEN persisted
        THEN the finalized status is stored.
        """
        asset = Asset(
            name="done.png",
            content_type="image/png",
            r2_key="projects/abc/done.png",
            project_id=sample_project.id,
            upload_status="finalized",
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.upload_status == "finalized"

    async def test_asset_upload_status_can_be_failed(self, db_session, sample_project):
        """GIVEN an Asset with upload_status="failed"
        WHEN persisted
        THEN the failed status is stored.
        """
        asset = Asset(
            name="failed.png",
            content_type="image/png",
            r2_key="projects/abc/failed.png",
            project_id=sample_project.id,
            upload_status="failed",
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.upload_status == "failed"

    async def test_asset_default_finalized_at_is_none(self, db_session, sample_project):
        """GIVEN a newly created Asset
        WHEN persisted without finalized_at
        THEN finalized_at is NULL.
        """
        asset = Asset(
            name="not-finalized.png",
            content_type="image/png",
            r2_key="projects/abc/not-finalized.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.finalized_at is None

    async def test_asset_finalized_at_can_be_set(self, db_session, sample_project):
        """GIVEN an Asset
        WHEN finalized_at is set to a timestamp
        THEN the field is persisted.
        """
        now = datetime.now(timezone.utc)
        asset = Asset(
            name="finalized.png",
            content_type="image/png",
            r2_key="projects/abc/finalized.png",
            project_id=sample_project.id,
            upload_status="finalized",
            finalized_at=now,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.finalized_at is not None
        assert abs((asset.finalized_at.replace(tzinfo=timezone.utc) - now).total_seconds()) < 2


# ─── active_assets() Helper ───────────────────────────────────────────────────


class TestActiveAssetsHelper:
    """Unit tests for the active_assets() soft-delete filter."""

    async def test_active_assets_excludes_soft_deleted(self, db_session, sample_project):
        """GIVEN one active and one soft-deleted Asset in the same project
        WHEN active_assets() is called
        THEN only the active asset is returned.
        """
        active = Asset(
            name="active.png",
            content_type="image/png",
            r2_key="projects/abc/active.png",
            project_id=sample_project.id,
        )
        deleted = Asset(
            name="deleted.png",
            content_type="image/png",
            r2_key="projects/abc/deleted.png",
            project_id=sample_project.id,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add_all([active, deleted])
        await db_session.commit()

        result = await active_assets(db_session, project_id=sample_project.id)
        asset_names = [a.name for a in result]

        assert "active.png" in asset_names
        assert "deleted.png" not in asset_names
        assert len(result) == 1

    async def test_active_returns_empty_when_no_assets(self, db_session, sample_project):
        """GIVEN a project with zero assets
        WHEN active_assets() is called
        THEN an empty list is returned.
        """
        result = await active_assets(db_session, project_id=sample_project.id)
        assert result == []

    async def test_all_deleted_returns_empty(self, db_session, sample_project):
        """GIVEN a project where all assets are soft-deleted
        WHEN active_assets() is called
        THEN an empty list is returned.
        """
        now = datetime.now(timezone.utc)
        assets = [
            Asset(
                name=f"gone-{i}.png",
                content_type="image/png",
                r2_key=f"projects/abc/gone-{i}.png",
                project_id=sample_project.id,
                deleted_at=now,
            )
            for i in range(3)
        ]
        db_session.add_all(assets)
        await db_session.commit()

        result = await active_assets(db_session, project_id=sample_project.id)
        assert result == []


# ─── Async Session Factory ────────────────────────────────────────────────────


class TestAsyncSession:
    """Unit tests for the async engine and session factory."""

    async def test_async_session_can_create_and_query(self):
        """GIVEN an in-memory SQLite engine with tables
        WHEN using async_session_factory
        THEN Project rows can be inserted and queried asynchronously.
        """
        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Project.metadata.create_all)

        factory = async_session_factory(engine)
        async with factory() as session:
            project = Project(name="Async Test", session_id="session-async")
            session.add(project)
            await session.commit()

            result = await session.get(Project, project.id)
            assert result is not None
            assert result.name == "Async Test"

        await engine.dispose()

    async def test_multiple_concurrent_sessions(self):
        """GIVEN two separate async sessions on the same engine
        WHEN each inserts a Project
        THEN both commits succeed and both rows are visible.
        """
        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Project.metadata.create_all)

        factory = async_session_factory(engine)
        async with factory() as session1:
            session1.add(Project(name="S1 Project", session_id="s1"))
            await session1.commit()

        async with factory() as session2:
            session2.add(Project(name="S2 Project", session_id="s2"))
            await session2.commit()

        # Verify both rows exist
        from sqlalchemy import select

        async with factory() as check:
            stmt = select(Project).order_by(Project.name)
            rows = (await check.execute(stmt)).scalars().all()
            assert len(rows) == 2
            assert rows[0].name == "S1 Project"

        await engine.dispose()


# ─── Fix 1: Soft-Delete Leakage (primaryjoin) ──────────────────────────────
# RED: Project.assets relationship does NOT exclude soft-deleted assets yet.


class TestProjectSoftDelete:
    """Project.assets relationship MUST filter out soft-deleted rows."""

    async def _reload_project_with_assets(self, db_session, project):
        """Re-load a Project with eager-loaded assets (async-safe)."""
        stmt = (
            select(Project)
            .where(Project.id == project.id)
            .options(selectinload(Project.assets))
        )
        result = await db_session.execute(stmt)
        return result.scalar_one()

    async def test_relationship_excludes_soft_deleted(self, db_session, sample_project):
        """GIVEN one active and one soft-deleted Asset
        WHEN accessing ``project.assets``
        THEN only the active asset is returned.
        """
        active = Asset(
            name="active.png",
            content_type="image/png",
            r2_key="projects/abc/active.png",
            project_id=sample_project.id,
        )
        deleted = Asset(
            name="deleted.png",
            content_type="image/png",
            r2_key="projects/abc/deleted.png",
            project_id=sample_project.id,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add_all([active, deleted])
        await db_session.commit()

        project = await self._reload_project_with_assets(db_session, sample_project)
        assert len(project.assets) == 1
        assert project.assets[0].name == "active.png"

    async def test_relationship_returns_empty_when_all_deleted(self, db_session, sample_project):
        """GIVEN a Project where all Assets are soft-deleted
        WHEN accessing ``project.assets``
        THEN an empty list is returned.
        """
        now = datetime.now(timezone.utc)
        deleted = Asset(
            name="gone.png",
            content_type="image/png",
            r2_key="projects/abc/gone.png",
            project_id=sample_project.id,
            deleted_at=now,
        )
        db_session.add(deleted)
        await db_session.commit()

        project = await self._reload_project_with_assets(db_session, sample_project)
        assert project.assets == []


# ─── Fix 2: FastAPI Lifespan — try…finally on yield ────────────────────────
# RED: The lifespan currently has an unprotected ``yield``.
# If the application crashes during yield, close_db() is never called.


class TestLifespan:
    """The FastAPI lifespan MUST call close_db() even when the app crashes."""

    async def test_lifespan_calls_close_db_on_exception(self):
        """GIVEN the lifespan context manager
        WHEN an exception occurs during yield
        THEN close_db() is still called.
        """
        mock_close = AsyncMock()
        mock_init = AsyncMock()

        with (
            patch("app.close_db", mock_close),
            patch("app.init_db", mock_init),
            patch("app._init_assets_service"),
            patch("app._init_auth_service"),
            patch("app._wire_asset_resolver"),
        ):
            from app import lifespan

            with pytest.raises(RuntimeError, match="crash"):
                async with lifespan(None):
                    raise RuntimeError("crash")

        mock_init.assert_awaited_once()
        mock_close.assert_awaited_once()


# ─── Fix 3: Connection Pooling & Timeouts ──────────────────────────────────
# RED: init_db() does not pass pool_size / max_overflow to the engine.


class TestEngineConfig:
    """Async engine MUST be created with pool_size and max_overflow."""

    async def test_init_db_passes_pool_settings(self):
        """GIVEN init_db is called
        THEN ``_create_async_engine`` receives pool_size=5 and max_overflow=10.
        """
        import contextlib

        from src.shared.models import persistence as persistence_module

        mock_engine = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock(return_value=None)

        # Wrap begin() return value in an actual async context manager
        @contextlib.asynccontextmanager
        async def mock_begin():
            yield mock_conn

        mock_engine.begin = mock_begin

        # Mock the session+ migration helpers added in the corrective fix.
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        @contextlib.asynccontextmanager
        async def mock_session_cm(*a, **kw):
            yield mock_session

        with (
            patch.object(
                persistence_module, "_create_async_engine", return_value=mock_engine
            ) as mock_create,
            patch.object(
                persistence_module,
                "async_session_factory",
                return_value=lambda: mock_session_cm(),
            ),
            patch.object(
                persistence_module,
                "ensure_asset_readiness_columns",
                AsyncMock(),
            ),
            patch.object(
                persistence_module,
                "backfill_asset_upload_status",
                AsyncMock(return_value=0),
            ),
            patch.object(
                persistence_module,
                "ensure_project_owner_fk",
                AsyncMock(),
            ),
            patch.object(
                persistence_module,
                "ensure_email_verification_delivered_column",
                AsyncMock(),
            ),
        ):
            persistence_module._engine = None
            await persistence_module.init_db("sqlite+aiosqlite://", echo=False)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert "pool_size" in call_kwargs, "pool_size kwarg missing from engine creation"
        assert call_kwargs["pool_size"] == 5
        assert "max_overflow" in call_kwargs, "max_overflow kwarg missing from engine creation"
        assert call_kwargs["max_overflow"] == 10


# ─── Fix 4: SQLite PRAGMA foreign_keys + cross-project isolation + ordering ─
# RED: In-memory SQLite DOES NOT enforce foreign keys by default.


class TestPragmaForeignKeys:
    """SQLite in-memory DB MUST enable PRAGMA foreign_keys=ON."""

    async def test_foreign_key_violation_raises_on_sqlite(self, db_session):
        """GIVEN PRAGMA foreign_keys=ON
        WHEN inserting an Asset with a non-existent project_id
        THEN IntegrityError is raised.
        """
        orphan = Asset(
            name="orphan.png",
            content_type="image/png",
            r2_key="orphan.png",
            project_id="00000000-0000-0000-0000-000000000000",
        )
        db_session.add(orphan)
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestCrossProjectIsolation:
    """active_assets() MUST NOT leak assets across projects."""

    async def test_active_assets_isolated_per_project(self, db_session):
        """GIVEN two projects each with their own assets
        WHEN active_assets() is called for each project
        THEN assets from different projects are not mixed.
        """
        proj_a = Project(name="Project A", session_id="session-a")
        proj_b = Project(name="Project B", session_id="session-b")
        db_session.add_all([proj_a, proj_b])
        await db_session.commit()

        asset_a = Asset(
            name="a-asset.png",
            content_type="image/png",
            r2_key="a-key",
            project_id=proj_a.id,
        )
        asset_b = Asset(
            name="b-asset.png",
            content_type="image/png",
            r2_key="b-key",
            project_id=proj_b.id,
        )
        db_session.add_all([asset_a, asset_b])
        await db_session.commit()

        result_a = await active_assets(db_session, project_id=proj_a.id)
        result_b = await active_assets(db_session, project_id=proj_b.id)

        assert len(result_a) == 1
        assert result_a[0].name == "a-asset.png"
        assert len(result_b) == 1
        assert result_b[0].name == "b-asset.png"


class TestAssetOrdering:
    """active_assets() MUST return assets newest-first."""

    async def test_active_assets_returns_newest_first(self, db_session, sample_project):
        """GIVEN assets created at different times
        WHEN active_assets() is called
        THEN assets are ordered by created_at descending.
        """
        now = datetime.now(timezone.utc)
        oldest = Asset(
            name="oldest.png",
            content_type="image/png",
            r2_key="oldest",
            project_id=sample_project.id,
            created_at=now - timedelta(hours=2),
        )
        middle = Asset(
            name="middle.png",
            content_type="image/png",
            r2_key="middle",
            project_id=sample_project.id,
            created_at=now - timedelta(hours=1),
        )
        newest = Asset(
            name="newest.png",
            content_type="image/png",
            r2_key="newest",
            project_id=sample_project.id,
            created_at=now,
        )
        db_session.add_all([oldest, middle, newest])
        await db_session.commit()

        result = await active_assets(db_session, project_id=sample_project.id)

        assert len(result) == 3
        assert result[0].name == "newest.png"
        assert result[1].name == "middle.png"
        assert result[2].name == "oldest.png"


# ─── Fix (PR fix-orchestrator-selected-assets): Server_default on upload_status ─
# RED: upload_status has only Python-side default, not server_default.
# This test proves the column definition change works at the DB level.


class TestServerDefaultUploadStatus:
    """``upload_status`` MUST have a ``server_default`` so the DB provides
    ``pending`` even when the Python-side default is bypassed (e.g. on
    existing tables where ``create_all`` does nothing)."""

    async def test_server_default_provides_pending_without_python_default(self):
        """GIVEN the assets table with server_default='pending' on upload_status
        WHEN inserting an Asset WITHOUT specifying upload_status (bypassing
        the Python ORM default via raw SQL)
        THEN the DB provides "pending" as the column value.
        """
        import textwrap

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Asset.metadata.create_all)

        factory = async_session_factory(engine)
        async with factory() as session:
            # Create project first (FK constraint)
            project = Project(name="Migrate Test", session_id="session-mig")
            session.add(project)
            await session.commit()

            project_id = project.id

        # Insert Asset row via raw SQL, bypassing Python ORM defaults.
        # created_at is included to satisfy the NOT NULL constraint.
        async with factory() as session:
            import uuid
            asset_id = str(uuid.uuid4())
            raw_sql = text("""
                INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at)
                VALUES (:id, :name, :ct, :r2k, :pid, datetime('now'))
            """)
            await session.execute(raw_sql, {
                "id": asset_id,
                "name": "server-default.png",
                "ct": "image/png",
                "r2k": "projects/mig/test.png",
                "pid": project_id,
            })
            await session.commit()

        # Read back via raw SQL to confirm DB-level default
        async with factory() as session:
            result = await session.execute(
                text("SELECT upload_status FROM assets WHERE id = :id"),
                {"id": asset_id},
            )
            row = result.one()
            assert row[0] == "pending", (
                f"Expected DB-level default 'pending', got {row[0]!r}"
            )

        await engine.dispose()

    async def test_orm_create_still_uses_python_default_when_server_default_present(self, db_session, sample_project):
        """GIVEN server_default='pending' on upload_status
        WHEN creating an Asset via the ORM without upload_status
        THEN ORM default and server_default both yield "pending".
        """
        asset = Asset(
            name="orm-default.png",
            content_type="image/png",
            r2_key="projects/abc/orm-default.png",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.upload_status == "pending"


# ===============================================================================
# Fix (Second 4R Blocker 4): _column_exists MUST be schema-scoped and tested
# for both SQLite and PostgreSQL dialect paths without requiring live PG.
# ===============================================================================


class TestColumnExists:
    """``_column_exists`` must correctly detect column existence for both
    SQLite and PostgreSQL dialects."""

    async def test_returns_true_when_column_exists_sqlite(self, db_session, sample_project):
        """GIVEN an assets table that has a 'name' column
        WHEN _column_exists is called with SQLite dialect (default)
        THEN True is returned.
        """
        from src.shared.models.persistence import _column_exists

        result = await _column_exists(db_session, "assets", "name")
        assert result is True

    async def test_returns_false_when_column_missing_sqlite(self, db_session, sample_project):
        """GIVEN an assets table WITHOUT a 'nonexistent' column
        WHEN _column_exists is called with SQLite dialect (default)
        THEN False is returned.
        """
        from src.shared.models.persistence import _column_exists

        result = await _column_exists(db_session, "assets", "nonexistent_column_xyz")
        assert result is False

    async def test_returns_false_for_unknown_table(self, db_session, sample_project):
        """GIVEN a table that does not exist
        WHEN _column_exists is called
        THEN False is returned (PRAGMA returns no rows for unknown tables).
        """
        from src.shared.models.persistence import _column_exists

        result = await _column_exists(db_session, "nonexistent_table", "id")
        assert result is False

    async def test_pg_dialect_queries_information_schema(self):
        """GIVEN a session whose dialect is 'postgresql'
        WHEN _column_exists is called
        THEN the SQL query targets information_schema.columns.
        """
        from src.shared.models.persistence import _column_exists
        from unittest.mock import AsyncMock, MagicMock, PropertyMock

        mock_session = AsyncMock()
        mock_bind = AsyncMock()
        type(mock_bind).dialect = PropertyMock(return_value=SimpleNamespace(name="postgresql"))
        mock_session.bind = mock_bind
        # _column_exists uses sync .scalar() (no await) on the execute result,
        # so we need a sync mock for the result, not AsyncMock.
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        await _column_exists(mock_session, "assets", "upload_status")

        # Verify the query targets information_schema
        call_text = mock_session.execute.call_args[0][0].text
        assert "information_schema.columns" in call_text
        assert "table_name" in call_text
        assert "column_name" in call_text

    async def test_pg_dialect_filters_by_table_schema(self):
        """GIVEN a session whose dialect is 'postgresql'
        WHEN _column_exists is called
        THEN the query MUST filter by table_schema = CURRENT_SCHEMA
        to avoid false positives when the same table name exists in
        multiple schemas.
        """
        from src.shared.models.persistence import _column_exists
        from unittest.mock import AsyncMock, MagicMock, PropertyMock

        mock_session = AsyncMock()
        mock_bind = AsyncMock()
        type(mock_bind).dialect = PropertyMock(return_value=SimpleNamespace(name="postgresql"))
        mock_session.bind = mock_bind
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        await _column_exists(mock_session, "assets", "upload_status")

        call_text = mock_session.execute.call_args[0][0].text
        assert "table_schema" in call_text, (
            f"PostgreSQL query MUST filter by table_schema to avoid "
            f"cross-schema false positives. Query text: {call_text}"
        )
        assert "CURRENT_SCHEMA" in call_text, (
            f"PostgreSQL query MUST use CURRENT_SCHEMA for the schema filter. "
            f"Query text: {call_text}"
        )

    async def test_sqlite_dialect_uses_pragma(self):
        """GIVEN a session whose dialect is 'sqlite'
        WHEN _column_exists is called
        THEN the SQL query uses PRAGMA table_info.
        """
        from src.shared.models.persistence import _column_exists
        from unittest.mock import AsyncMock, MagicMock, PropertyMock

        mock_session = AsyncMock()
        mock_bind = AsyncMock()
        type(mock_bind).dialect = PropertyMock(return_value=SimpleNamespace(name="sqlite"))
        mock_session.bind = mock_bind
        # _column_exists uses sync .fetchall() (no await) on the execute result,
        # so we need a sync mock for the result, not AsyncMock.
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(0, "upload_status", "VARCHAR", 0, None, 1)]
        mock_session.execute.return_value = mock_result

        await _column_exists(mock_session, "assets", "upload_status")

        # Verify PRAGMA is used
        call_text = mock_session.execute.call_args[0][0].text
        assert "PRAGMA table_info" in call_text


class TestEnsureAssetColumns:
    """``ensure_asset_readiness_columns()`` MUST safely add upload_status and
    finalized_at columns to an existing table that lacks them."""

    async def test_adds_upload_status_column_to_existing_table(self):
        """GIVEN an assets table WITHOUT upload_status column
        WHEN ensure_asset_readiness_columns is called
        THEN the upload_status column is added with server_default 'pending'.
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        # Create assets table WITHOUT upload_status column by building a
        # minimal schema using only the pre-readiness Asset columns.
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        # Manually create assets table WITHOUT upload_status/finalized_at
        async with factory() as session:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            await session.commit()

        # Call the migration helper
        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # Verify columns exist by inspecting table info
        async with factory() as session:
            result = await session.execute(text("PRAGMA table_info('assets')"))
            columns = {row[1] for row in result.fetchall()}

        assert "upload_status" in columns, "upload_status column was not added"
        assert "finalized_at" in columns, "finalized_at column was not added"

        await engine.dispose()

    async def test_idempotent_when_columns_already_exist(self):
        """GIVEN an assets table that ALREADY has upload_status and finalized_at
        WHEN ensure_asset_readiness_columns is called
        THEN no error is raised (idempotent).
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Asset.metadata.create_all)

        async with factory() as session:
            # First call should succeed (columns already exist from create_all)
            await ensure_asset_readiness_columns(session)
            await session.commit()

        async with factory() as session:
            # Second call should also succeed (idempotent)
            await ensure_asset_readiness_columns(session)
            await session.commit()

        await engine.dispose()


class TestMigrationColumnDefault:
    """The migration helper MUST add ``upload_status`` with a ``DEFAULT
    'pending'`` clause so that new rows inserted after the migration get
    the correct server-side default — matching the fresh-schema contract
    parity required by the 4R review (Finding 3).

    This is separate from ``test_server_default_provides_pending_without_python_default``
    because that test uses ``Asset.metadata.create_all`` (fresh schema).
    Here we verify the *migration* path: column added via ALTER TABLE by
    ``ensure_asset_readiness_columns``.
    """

    async def test_migrated_column_has_default_for_new_rows(self):
        """GIVEN a pre-migration assets table WITHOUT upload_status
        WHEN ``ensure_asset_readiness_columns`` adds the column
        AND a new row is inserted via raw SQL (bypassing ORM defaults)
        THEN the DB default ``'pending'`` is applied.
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        # Create a pre-migration table (no upload_status / finalized_at)
        async with factory() as session:
            await session.execute(text("DROP TABLE IF EXISTS assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            project = Project(name="Migration Default", session_id="s-def")
            session.add(project)
            await session.commit()
            pid = project.id

        # Add columns via migration helper
        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # Insert a NEW row via raw SQL, OMITTING upload_status to test
        # whether the DB-layer DEFAULT provides 'pending'.
        async with factory() as session:
            import uuid
            aid = str(uuid.uuid4())
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at) "
                "VALUES (:id, 'default-test.png', 'image/png', :k, :pid, :now)"
            ), {
                "id": aid, "k": f"projects/{pid}/default-test.png",
                "pid": pid, "now": now_str,
            })
            await session.commit()

        # Read back via raw SQL to confirm the DB default fired
        async with factory() as session:
            result = await session.execute(
                text("SELECT upload_status FROM assets WHERE id = :id"),
                {"id": aid},
            )
            row = result.one()
            assert row[0] == "pending", (
                f"Expected DB default 'pending' after migration, "
                f"got {row[0]!r}"
            )

        await engine.dispose()

    async def test_migrated_column_default_applies_to_orm_inserts(self):
        """GIVEN a migrated table
        WHEN an Asset is created via the ORM without upload_status
        THEN the ORM default AND server_default both yield 'pending'.
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        # Pre-migration table
        async with factory() as session:
            await session.execute(text("DROP TABLE IF EXISTS assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            project = Project(name="ORM Default", session_id="s-orm")
            session.add(project)
            await session.commit()
            pid = project.id

        # Migrate
        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # Create Asset via ORM (no explicit upload_status)
        async with factory() as session:
            asset = Asset(
                name="orm-migrated.png",
                content_type="image/png",
                r2_key=f"projects/{pid}/orm-migrated.png",
                project_id=pid,
            )
            session.add(asset)
            await session.commit()
            await session.refresh(asset)
            assert asset.upload_status == "pending", (
                f"Expected 'pending' from ORM after migration, "
                f"got {asset.upload_status!r}"
            )

        await engine.dispose()


class TestBackfillAssetUploadStatus:
    """``backfill_asset_upload_status()`` MUST set ``upload_status='pending'``
    for existing rows where upload_status is NULL."""

    async def test_backfills_null_upload_status_to_pending(self):
        """GIVEN existing assets with NULL upload_status
        WHEN backfill_asset_upload_status is called
        THEN NULL rows are set to "pending".
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns, backfill_asset_upload_status

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        # Drop and recreate assets table WITHOUT upload_status to simulate
        # a pre-migration schema.  ``Project.metadata.create_all`` also
        # creates the full assets table (shared Base.metadata), so we
        # replace it with a minimal version.
        async with factory() as session:
            await session.execute(text("DROP TABLE assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            # Create a project
            project = Project(name="Backfill Test", session_id="session-bf")
            session.add(project)
            await session.commit()
            pid = project.id

            # Insert two assets (no upload_status column yet).
            # created_at must be included to satisfy NOT NULL constraint.
            import uuid
            aid1 = str(uuid.uuid4())
            aid2 = str(uuid.uuid4())
            from datetime import datetime, timezone
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at) "
                "VALUES (:id1, 'a.png', 'image/png', :k1, :pid, :now), "
                "(:id2, 'b.png', 'image/png', :k2, :pid, :now)"
            ), {
                "id1": aid1, "k1": f"projects/{pid}/a.png",
                "id2": aid2, "k2": f"projects/{pid}/b.png",
                "pid": pid, "now": now_str,
            })
            await session.commit()

        # Add columns via migration helper.
        # NOTE: Because ``ensure_asset_readiness_columns`` now adds
        # ``DEFAULT 'pending'`` (4R Finding 3 fix), SQLite applies the
        # default to EXISTING rows when the column is added.  The backfill
        # below is therefore a no-op for new migrations — it exists to
        # handle databases migrated *before* the DEFAULT clause was added.
        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # After the migration, upload_status is already 'pending' for all
        # existing rows because ``DEFAULT 'pending'`` fired during ALTER
        # TABLE on SQLite.
        async with factory() as session:
            result = await session.execute(text("SELECT upload_status FROM assets"))
            statuses = [r[0] for r in result.fetchall()]
            assert all(s == "pending" for s in statuses), (
                f"Expected all 'pending' from migration DEFAULT, got {statuses}"
            )

        # Run backfill — should be a no-op (nothing is NULL now that the
        # DEFAULT clause fills existing rows).
        async with factory() as session:
            count = await backfill_asset_upload_status(session)
            await session.commit()
            assert count == 0, (
                f"Expected 0 backfilled (DEFAULT already fired), got {count}"
            )

        # Verify all rows still have pending
        async with factory() as session:
            result = await session.execute(text("SELECT upload_status FROM assets"))
            statuses = [r[0] for r in result.fetchall()]
            assert all(s == "pending" for s in statuses), f"Expected all 'pending', got {statuses}"

        await engine.dispose()

    async def test_skips_already_filled_rows(self):
        """GIVEN assets where some already have upload_status set
        WHEN backfill_asset_upload_status is called
        THEN only NULL rows are updated, leaving non-NULL rows unchanged.
        """
        from src.shared.models.persistence import ensure_asset_readiness_columns, backfill_asset_upload_status

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        # Drop and recreate minimal assets table (see previous test for why).
        async with factory() as session:
            await session.execute(text("DROP TABLE assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            project = Project(name="Skip Test", session_id="session-sk")
            session.add(project)
            await session.commit()
            pid = project.id

            import uuid
            aid1 = str(uuid.uuid4())
            aid2 = str(uuid.uuid4())
            from datetime import datetime, timezone
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at) "
                "VALUES (:id1, 'a.png', 'image/png', :k1, :pid, :now), "
                "(:id2, 'b.png', 'image/png', :k2, :pid, :now)"
            ), {
                "id1": aid1, "k1": f"projects/{pid}/a.png",
                "id2": aid2, "k2": f"projects/{pid}/b.png",
                "pid": pid, "now": now_str,
            })
            await session.commit()

        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # The DEFAULT 'pending' fired during ALTER TABLE, so both rows
        # now have 'pending'.  Override one to 'finalized' to test that
        # backfill does not touch non-NULL rows.
        async with factory() as session:
            await session.execute(
                text("UPDATE assets SET upload_status = 'finalized' WHERE id = :id"),
                {"id": aid2},
            )
            await session.commit()

        # Backfill should be a no-op — no NULL rows exist (DEFAULT already
        # filled both rows during migration).
        async with factory() as session:
            count = await backfill_asset_upload_status(session)
            await session.commit()
            assert count == 0, (
                f"Expected 0 backfilled (DEFAULT already fired), got {count}"
            )

        # Verify aid1 is still 'pending' and aid2 is still 'finalized'
        async with factory() as session:
            result = await session.execute(
                text("SELECT id, upload_status FROM assets ORDER BY id")
            )
            rows = {r[0]: r[1] for r in result.fetchall()}
            assert rows[aid1] == "pending", f"aid1 should be 'pending', got {rows[aid1]}"
            assert rows[aid2] == "finalized", f"aid2 should still be 'finalized', got {rows[aid2]}"

        await engine.dispose()


class TestBackfillObservability:
    """``backfill_asset_upload_status()`` MUST log a warning when it affects
    any existing rows (observability for operator awareness)."""

    async def test_logs_warning_when_rows_are_backfilled(self, caplog):
        """GIVEN assets with NULL upload_status
        WHEN backfill_asset_upload_status updates them
        THEN a warning is logged with the count.
        """
        import logging

        from src.shared.models.persistence import (
            ASSET_STATUS_PENDING,
            ensure_asset_readiness_columns,
            backfill_asset_upload_status,
        )

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        async with factory() as session:
            await session.execute(text("DROP TABLE assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            project = Project(name="Log Test", session_id="session-log")
            session.add(project)
            await session.commit()
            pid = project.id

            import uuid
            from datetime import datetime, timezone
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at) "
                "VALUES (:id, 'a.png', 'image/png', :k, :pid, :now)"
            ), {
                "id": str(uuid.uuid4()),
                "k": f"projects/{pid}/a.png",
                "pid": pid,
                "now": now_str,
            })
            await session.commit()

        # Add columns (DEFAULT 'pending' will fire on SQLite)
        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        # Force some rows back to NULL so backfill actually runs
        async with factory() as session:
            await session.execute(text("UPDATE assets SET upload_status = NULL"))
            await session.commit()

        caplog.set_level(logging.WARNING)
        async with factory() as session:
            count = await backfill_asset_upload_status(session)
            await session.commit()

        assert count > 0, "Expected at least 1 backfilled row"
        assert any(
            "backfill" in record.message.lower() and str(count) in record.message
            for record in caplog.records
        ), f"No warning log found with backfill count={count} in {[r.message for r in caplog.records]}"

        await engine.dispose()

    async def test_no_warning_when_no_rows_to_backfill(self, caplog):
        """GIVEN no assets with NULL upload_status
        WHEN backfill is called
        THEN no warning is logged.
        """
        import logging

        from src.shared.models.persistence import (
            ASSET_STATUS_PENDING,
            ensure_asset_readiness_columns,
            backfill_asset_upload_status,
        )

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        async with factory() as session:
            await session.execute(text("DROP TABLE assets"))
            await session.execute(text("""
                CREATE TABLE assets (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(256) NOT NULL,
                    content_type VARCHAR(64) NOT NULL,
                    r2_key VARCHAR(512) NOT NULL,
                    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """))
            project = Project(name="No Log Test", session_id="session-nolog")
            session.add(project)
            await session.commit()
            pid = project.id

            import uuid
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at) "
                "VALUES (:id, 'a.png', 'image/png', :k, :pid, :now)"
            ), {
                "id": str(uuid.uuid4()),
                "k": f"projects/{pid}/a.png",
                "pid": pid,
                "now": now_str,
            })
            await session.commit()

        async with factory() as session:
            await ensure_asset_readiness_columns(session)
            await session.commit()

        caplog.set_level(logging.WARNING)
        async with factory() as session:
            count = await backfill_asset_upload_status(session)
            await session.commit()

        # All rows already have pending from DEFAULT → backfill is a no-op
        assert count == 0
        backfill_logs = [
            r for r in caplog.records
            if "backfill" in r.message.lower()
        ]
        assert len(backfill_logs) == 0, (
            f"No warning expected for 0-row backfill, got: {backfill_logs}"
        )

        await engine.dispose()


class TestRecoverBackfilledAssets:
    """``recover_backfilled_assets()`` verifies pending backfilled assets
    against storage proof and upgrades verified ones to "finalized"."""

    async def test_recover_upgrades_verified_pending_assets_to_finalized(self):
        """GIVEN assets with upload_status='pending' (backfilled)
        WHEN recover_backfilled_assets is called with a verify callback
        THEN assets that pass verification are set to 'finalized'.
        """
        from src.shared.models.persistence import (
            ASSET_STATUS_FINALIZED,
            ASSET_STATUS_PENDING,
            recover_backfilled_assets,
        )

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        async with factory() as session:
            project = Project(name="Recovery Test", session_id="session-rec")
            session.add(project)
            await session.commit()
            pid = project.id

            import uuid
            aid1 = str(uuid.uuid4())
            aid2 = str(uuid.uuid4())
            now_str = datetime.now(timezone.utc).isoformat()
            await session.execute(text(
                "INSERT INTO assets (id, name, content_type, r2_key, project_id, created_at, upload_status) "
                "VALUES (:id1, 'exists.png', 'image/png', :k1, :pid, :now, :st1), "
                "(:id2, 'missing.png', 'image/png', :k2, :pid, :now, :st2)"
            ), {
                "id1": aid1, "k1": f"projects/{pid}/exists_object.png",
                "id2": aid2, "k2": f"projects/{pid}/missing_object.png",
                "pid": pid, "now": now_str,
                "st1": ASSET_STATUS_PENDING,
                "st2": ASSET_STATUS_PENDING,
            })
            await session.commit()

        async def verify_exists(r2_key: str) -> bool:
            return "exists_object" in r2_key

        async with factory() as session:
            verified, skipped = await recover_backfilled_assets(
                session, verify_exists
            )
            await session.commit()

            assert verified == 1, f"Expected 1 verified, got {verified}"
            assert skipped == 1, f"Expected 1 skipped, got {skipped}"

            # Check the verified asset
            result = await session.execute(
                text("SELECT upload_status, finalized_at FROM assets WHERE id = :id"),
                {"id": aid1},
            )
            row = result.fetchone()
            assert row[0] == ASSET_STATUS_FINALIZED
            assert row[1] is not None, "finalized_at should be set"

            # Check the skipped asset
            result = await session.execute(
                text("SELECT upload_status FROM assets WHERE id = :id"),
                {"id": aid2},
            )
            assert result.scalar() == ASSET_STATUS_PENDING

        await engine.dispose()

    async def test_recover_returns_zeroes_when_no_pending_assets(self):
        """GIVEN no assets with upload_status='pending'
        WHEN recover_backfilled_assets is called
        THEN verified=0, skipped=0.
        """
        from src.shared.models.persistence import (
            ASSET_STATUS_FINALIZED,
            recover_backfilled_assets,
        )

        engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
        factory = async_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(lambda sc: sc.execute(text("PRAGMA foreign_keys=ON")))
            await conn.run_sync(Project.metadata.create_all)

        async with factory() as session:
            project = Project(name="Empty Recovery", session_id="session-emp")
            session.add(project)
            await session.commit()

        async def verify_exists(r2_key: str) -> bool:
            return True

        async with factory() as session:
            verified, skipped = await recover_backfilled_assets(
                session, verify_exists
            )
            assert verified == 0, f"Expected 0 verified, got {verified}"
            assert skipped == 0, f"Expected 0 skipped, got {skipped}"

        await engine.dispose()


# ─── Fix 5: Cross-Session Access ───────────────────────────────────────────
# RED: active_assets() does NOT currently accept a session_id parameter.


class TestSessionScopedAssets:
    """active_assets() MUST enforce the caller's session_id boundary."""

    async def test_active_assets_filters_by_session_id(self, db_session, sample_project):
        """GIVEN an asset in a session-scoped project
        WHEN active_assets() is called with a matching session_id
        THEN the asset is returned.
        WHEN called with a non-matching session_id
        THEN no assets are returned.
        """
        asset = Asset(
            name="my-asset.png",
            content_type="image/png",
            r2_key="my-asset",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()

        # Correct session → asset visible
        result = await active_assets(
            db_session,
            project_id=sample_project.id,
            session_id="session-abc",
        )
        assert len(result) == 1
        assert result[0].name == "my-asset.png"

        # Wrong session → no assets
        result = await active_assets(
            db_session,
            project_id=sample_project.id,
            session_id="session-wrong",
        )
        assert len(result) == 0

    async def test_active_assets_backward_compatible_without_session(self, db_session, sample_project):
        """GIVEN active_assets() is called without session_id
        THEN it still works (backward compatibility when session_id is None).
        """
        asset = Asset(
            name="compat.png",
            content_type="image/png",
            r2_key="compat",
            project_id=sample_project.id,
        )
        db_session.add(asset)
        await db_session.commit()

        result = await active_assets(db_session, project_id=sample_project.id)
        assert len(result) == 1
        assert result[0].name == "compat.png"


# ─── Fix (PR fix-orchestrator-selected-assets corrective): init_db migration wiring ─
# RED: init_db() does NOT call ensure_asset_readiness_columns or
# backfill_asset_upload_status, so existing databases never get the
# readiness columns.  This test PROVES the gap exists by verifying
# that after init_db() the columns ARE present (the fix makes it pass).


class TestInitDbMigration:
    """``init_db()`` MUST run readiness migration on existing tables."""

    async def test_init_db_adds_readiness_columns_to_existing_table(self):
        """GIVEN an existing database with an assets table that LACKS
        upload_status and finalized_at columns
        WHEN init_db() is called (simulating a production restart)
        THEN the readiness columns exist and NULL rows are backfilled
        to 'pending'.
        """
        import tempfile
        import os

        from src.shared.models.persistence import (
            init_db,
            close_db,
            async_session_factory,
            Project,
        )

        # Create a persistent temp file so we can close and re-open the DB.
        db_path = os.path.join(
            tempfile.mkdtemp(), "test_init_db_migration.db"
        )
        db_url = f"sqlite+aiosqlite:///{db_path}"

        try:
            # ── Phase 1: Set up a PRE-MIGRATION schema ────────────────────
            engine1 = _create_async_engine(db_url, echo=False)
            async with engine1.begin() as conn:
                await conn.run_sync(lambda sc: sc.execute(
                    text("PRAGMA foreign_keys=ON")
                ))
                await conn.run_sync(Project.metadata.create_all)

                # Drop the full assets table and recreate it without
                # upload_status / finalized_at (pre-migration state).
                await conn.run_sync(lambda sc: sc.execute(
                    text("DROP TABLE IF EXISTS assets")
                ))
                await conn.run_sync(lambda sc: sc.execute(text("""
                    CREATE TABLE assets (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(256) NOT NULL,
                        content_type VARCHAR(64) NOT NULL,
                        r2_key VARCHAR(512) NOT NULL,
                        project_id VARCHAR(36) NOT NULL
                            REFERENCES projects(id) ON DELETE CASCADE,
                        deleted_at DATETIME,
                        created_at DATETIME NOT NULL
                            DEFAULT (datetime('now'))
                    )
                """)))
            await engine1.dispose()

            # Insert a project + asset to verify backfill later.
            async with async_session_factory(engine1)() as session:
                proj = Project(name="Migrate Me", session_id="s-mig")
                session.add(proj)
                await session.commit()
                pid = proj.id

                import uuid
                await session.execute(text(
                    "INSERT INTO assets "
                    "(id, name, content_type, r2_key, project_id, created_at) "
                    "VALUES (:id, 'old.png', 'image/png', :k, :pid, "
                    "datetime('now'))"
                ), {
                    "id": str(uuid.uuid4()),
                    "k": f"projects/{pid}/old.png",
                    "pid": pid,
                })
                await session.commit()
            await engine1.dispose()

            # ── RED ASSERTION (before fix): table info has NO new columns ─
            engine_check = _create_async_engine(db_url, echo=False)
            async with engine_check.begin() as conn:
                result = await conn.run_sync(
                    lambda sc: sc.execute(
                        text("PRAGMA table_info('assets')")
                    ).fetchall()
                )
            column_names = {row[1] for row in result}
            assert "upload_status" not in column_names, (
                "Pre-condition failed: upload_status column already exists"
            )
            assert "finalized_at" not in column_names, (
                "Pre-condition failed: finalized_at column already exists"
            )
            await engine_check.dispose()

            # ── Phase 2: Call init_db — the function under test ───────────
            await init_db(db_url, echo=False)

            # ── Phase 3: Verify migration ran ─────────────────────────────
            factory = async_session_factory()
            async with factory() as session:
                # Columns exist
                result = await session.execute(
                    text("PRAGMA table_info('assets')")
                )
                columns = {row[1] for row in result.fetchall()}
                assert "upload_status" in columns, (
                    "upload_status column was NOT added by init_db"
                )
                assert "finalized_at" in columns, (
                    "finalized_at column was NOT added by init_db"
                )

                # Existing rows were backfilled to 'pending'
                rows = await session.execute(
                    text("SELECT upload_status FROM assets")
                )
                statuses = [r[0] for r in rows.fetchall()]
                assert all(s == "pending" for s in statuses), (
                    f"Expected all 'pending', got {statuses}"
                )

            await close_db()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            parent = os.path.dirname(db_path)
            if os.path.exists(parent):
                os.rmdir(parent)

    async def test_init_db_fresh_database_and_idempotent(self):
        """GIVEN a fresh database (no pre-existing assets table)
        WHEN init_db() is called
        THEN readiness columns exist from create_all
        AND a second call to init_db() is safe (idempotent).
        """
        import tempfile
        import os

        from src.shared.models.persistence import (
            init_db,
            close_db,
            async_session_factory,
        )

        db_path = os.path.join(
            tempfile.mkdtemp(), "test_init_db_fresh.db"
        )
        db_url = f"sqlite+aiosqlite:///{db_path}"

        try:
            # ── First call: fresh database ────────────────────────────
            await init_db(db_url, echo=False)

            factory = async_session_factory()
            async with factory() as session:
                result = await session.execute(
                    text("PRAGMA table_info('assets')")
                )
                columns = {row[1] for row in result.fetchall()}
                assert "upload_status" in columns, (
                    "upload_status column missing on fresh DB"
                )
                assert "finalized_at" in columns, (
                    "finalized_at column missing on fresh DB"
                )

            await close_db()

            # ── Second call: already-migrated table (idempotent) ──────
            await init_db(db_url, echo=False)
            # No assertion needed — proving no exception is raised.

            await close_db()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            parent = os.path.dirname(db_path)
            if os.path.exists(parent):
                os.rmdir(parent)
