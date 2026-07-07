"""Slice 1a — init_db creates auth tables and migrates Project.owner_id.

Covers:
- session-management spec: Refresh Token Storage (table created on boot)
- workspace-projects spec: Project Model (owner_id FK migration idempotent)
- The existing ``init_db`` pattern from ``persistence.py``.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.models.persistence import (
    Base,
    Project,
    async_session_factory,
    close_db,
    ensure_project_owner_fk,
    init_db,
)
from src.features.auth.infrastructure.models import User, RefreshToken


async def _table_exists(engine, table_name: str) -> bool:
    """Check if a table exists via SQLAlchemy introspection on the engine."""
    def _check(sync_conn):
        insp = inspect(sync_conn)
        return insp.has_table(table_name)
    async with engine.connect() as conn:
        return await conn.run_sync(_check)


@pytest.fixture
def file_db_url(tmp_path: Path) -> str:
    """Return a file-based SQLite URL that accepts pool_size/max_overflow.

    ``init_db`` passes ``pool_size=5, max_overflow=10`` to the engine, which
    in-memory SQLite (StaticPool) rejects. A temp file lets the full
    ``init_db`` path run end-to-end.
    """
    db_file = tmp_path / "auth_test.db"
    return f"sqlite+aiosqlite:///{db_file}"


class TestInitDbCreatesAuthTables:
    """init_db MUST provision users + refresh_tokens alongside projects/assets."""

    async def test_init_db_creates_users_table(self, file_db_url):
        """GIVEN an empty file DB
        WHEN init_db is called
        THEN the users table exists.
        """
        engine = await init_db(file_db_url)
        try:
            assert await _table_exists(engine, "users")
        finally:
            await close_db()

    async def test_init_db_creates_refresh_tokens_table(self, file_db_url):
        """GIVEN an empty file DB
        WHEN init_db is called
        THEN the refresh_tokens table exists.
        """
        engine = await init_db(file_db_url)
        try:
            assert await _table_exists(engine, "refresh_tokens")
        finally:
            await close_db()

    async def test_init_db_creates_projects_and_assets(self, file_db_url):
        """GIVEN an empty file DB
        WHEN init_db is called
        THEN projects and assets still exist (no regression).
        """
        engine = await init_db(file_db_url)
        try:
            assert await _table_exists(engine, "projects")
            assert await _table_exists(engine, "assets")
        finally:
            await close_db()

    async def test_init_db_can_persist_user_and_refresh_token(self, file_db_url):
        """GIVEN init_db has run
        WHEN a User + RefreshToken are persisted
        THEN they round-trip (integration of schema + ORM).
        """
        engine = await init_db(file_db_url)
        try:
            factory = async_session_factory(engine)
            async with factory() as session:
                user = User(email="round-trip@test.io", password_hash="$argon2id$h")
                session.add(user)
                await session.commit()
                await session.refresh(user)

                rt = RefreshToken(
                    user_id=user.id,
                    token_prefix="roundtrip-pre",
                    token_hash="$argon2id$rt",
                    expires_at=datetime.now(timezone.utc),
                )
                session.add(rt)
                await session.commit()

                fetched = await session.get(RefreshToken, rt.id)
                assert fetched is not None
                assert fetched.user_id == user.id
        finally:
            await close_db()


class TestEnsureProjectOwnerFkIdempotent:
    """ensure_project_owner_fk MUST be safe to call repeatedly (idempotent)."""

    async def test_idempotent_on_fresh_schema(self):
        """GIVEN a fresh schema (create_all with FK)
        WHEN ensure_project_owner_fk is called twice
        THEN no error is raised.
        """
        engine = _create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_session_factory(engine)

        async with factory() as session:
            await ensure_project_owner_fk(session)
            await session.commit()
        async with factory() as session:
            await ensure_project_owner_fk(session)
            await session.commit()

        await engine.dispose()

    async def test_projects_owner_id_accepts_real_user_after_migration(self):
        """GIVEN a fresh schema with the FK
        WHEN a real User + Project with owner_id=user.id are created
        THEN it persists (FK satisfied).
        """
        engine = _create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_session_factory(engine)

        async with factory() as session:
            await ensure_project_owner_fk(session)
            await session.commit()

            user = User(email="mig@test.io", password_hash="$argon2id$h")
            session.add(user)
            await session.commit()
            await session.refresh(user)

            project = Project(name="Migrated", owner_id=user.id, session_id="s")
            session.add(project)
            await session.commit()
            await session.refresh(project)
            assert project.owner_id == user.id

        await engine.dispose()

    async def test_anonymous_project_owner_null_still_works(self):
        """GIVEN a fresh schema with the FK
        WHEN a project with owner_id=None is created
        THEN it persists (anonymous project, FK allows NULL).
        """
        engine = _create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_session_factory(engine)

        async with factory() as session:
            await ensure_project_owner_fk(session)
            await session.commit()

            project = Project(name="Anon", owner_id=None, session_id="s-anon")
            session.add(project)
            await session.commit()
            await session.refresh(project)
            assert project.owner_id is None

        await engine.dispose()