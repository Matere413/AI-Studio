"""Unit tests for Project and Asset ORM models.

Covers model creation, field validation, async session lifecycle,
the active_assets() soft-delete filter, and surgical fixes from
4R reviews (pooling, lifespan safety, PRAGMA, cross-session scoping).
"""

from datetime import datetime, timezone, timedelta
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
    """Create and return a sample project bound to a test session."""
    project = Project(
        name="Campaign A",
        owner_id="user-abc",
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
        """
        project = Project(
            name="Campaign A",
            owner_id="user-abc",
            session_id="session-abc",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        assert project.id is not None
        assert project.name == "Campaign A"
        assert project.owner_id == "user-abc"
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

        with patch("app.close_db", mock_close), patch("app.init_db", mock_init):
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

        with patch.object(
            persistence_module, "_create_async_engine", return_value=mock_engine
        ) as mock_create:
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
