"""Unit tests for Project and Asset ORM models.

Covers model creation, field validation, async session lifecycle,
and the active_assets() soft-delete filter.
"""

from datetime import datetime, timezone

import pytest

from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.models.persistence import (
    Asset,
    Project,
    active_assets,
    async_session_factory,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_session():
    """Create an isolated in-memory SQLite session for each test.

    Creates all tables before the test and drops them after.
    """
    engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
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
