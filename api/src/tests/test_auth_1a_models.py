"""Slice 1a — User and RefreshToken ORM models.

Covers:
- auth spec: Registration (users row with email_verified=FALSE)
- session-management spec: Refresh Token Storage (token_hash argon2id,
  token_prefix clear + indexed, expires_at 30d, revoked_at, last_used_at,
  user_agent, ip, created_at; raw token NEVER stored)
- workspace-projects spec: Project Model (owner_id FK -> users.id, nullable)

The EmailVerification ORM is added in slice 2 (task 2-1), NOT here.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.models.persistence import (
    Base,
    Project,
    async_session_factory,
    close_db,
    init_db,
)
from src.features.auth.infrastructure.models import User, RefreshToken


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine with all auth + project tables."""
    engine = _create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.execute(text("PRAGMA foreign_keys=ON")))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_session_factory(db_engine)
    async with factory() as session:
        yield session


@pytest.fixture
async def sample_user(db_session):
    user = User(email="alice@test.io", password_hash="$argon2id$dummy")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ─── User Model ───────────────────────────────────────────────────────────────


class TestUserModel:
    """User ORM creation, columns, constraints."""

    async def test_create_user_with_required_fields(self, db_session):
        """GIVEN a User with email + password_hash
        WHEN persisted
        THEN id, email_verified=False, created_at, updated_at are populated.
        """
        user = User(email="bob@test.io", password_hash="$argon2id$real")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, str)
        assert user.email == "bob@test.io"
        assert user.password_hash == "$argon2id$real"
        assert user.email_verified is False
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
        assert user.last_login_at is None

    async def test_email_unique_constraint(self, db_session, sample_user):
        """GIVEN an existing user
        WHEN inserting a second user with the same email
        THEN IntegrityError is raised (email uniqueness).
        """
        dup = User(email=sample_user.email, password_hash="$argon2id$x")
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_email_verified_defaults_to_false(self, db_session):
        """GIVEN a newly created user
        WHEN persisted without email_verified
        THEN email_verified is False (server_default 0).
        """
        user = User(email="new@test.io", password_hash="$argon2id$h")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.email_verified is False

    async def test_password_hash_is_not_stored_as_plaintext(self, db_session):
        """GIVEN a user registers with password 'CorrectHorse42!'
        WHEN the row is persisted
        THEN password_hash starts with '$argon2id$' (per api-security spec).

        Note: the hashing itself happens in the use case (slice 1b); here we
        only assert the column accepts and stores the argon2id-formatted string.
        """
        user = User(email="pw@test.io", password_hash="$argon2id$v=19$m=65536,t=3,p=2$abc")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.password_hash.startswith("$argon2id$")

    async def test_created_at_and_updated_at_present(self, db_session):
        """GIVEN a newly created user
        WHEN persisted
        THEN created_at and updated_at are set to ~now.
        """
        before = datetime.now(timezone.utc)
        user = User(email="ts@test.io", password_hash="$argon2id$t")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert (user.created_at.replace(tzinfo=timezone.utc) - before).total_seconds() < 5
        assert (user.updated_at.replace(tzinfo=timezone.utc) - before).total_seconds() < 5

    async def test_last_login_at_nullable(self, db_session, sample_user):
        """GIVEN a user
        WHEN first created
        THEN last_login_at is None (never logged in yet).
        """
        assert sample_user.last_login_at is None

    async def test_last_login_at_can_be_set(self, db_session, sample_user):
        """GIVEN an existing user
        WHEN last_login_at is set
        THEN it persists.
        """
        now = datetime.now(timezone.utc)
        sample_user.last_login_at = now
        await db_session.commit()
        await db_session.refresh(sample_user)
        assert sample_user.last_login_at is not None


# ─── RefreshToken Model ───────────────────────────────────────────────────────


class TestRefreshTokenModel:
    """RefreshToken ORM: token_prefix (indexed), token_hash (argon2id), FK, lifecycle."""

    async def test_create_refresh_token_with_all_fields(self, db_session, sample_user):
        """GIVEN a valid refresh token
        WHEN persisted
        THEN token_prefix, token_hash, expires_at, user_id are stored; raw token NEVER stored.
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="abc123def456",
            token_hash="$argon2id$hashed",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            user_agent="Mozilla/5.0",
            ip="192.168.1.1",
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)

        assert rt.id is not None
        assert rt.user_id == sample_user.id
        assert rt.token_prefix == "abc123def456"
        assert rt.token_hash == "$argon2id$hashed"
        assert rt.revoked_at is None
        assert rt.last_used_at is None
        assert isinstance(rt.expires_at, datetime)
        assert rt.user_agent == "Mozilla/5.0"
        assert rt.ip == "192.168.1.1"
        assert isinstance(rt.created_at, datetime)

    async def test_token_prefix_is_indexed(self, db_engine):
        """GIVEN the refresh_tokens table
        WHEN schema is inspected
        THEN token_prefix has an index (O(log N) lookup per design).
        """
        def get_indexes(sync_conn):
            insp = inspect(sync_conn)
            idxs = insp.get_indexes("refresh_tokens")
            cols = [c["column_names"] for c in idxs]
            return cols

        async with db_engine.connect() as conn:
            cols = await conn.run_sync(get_indexes)
        assert any("token_prefix" in c for c in cols), (
            f"token_prefix must be indexed; found indexes on: {cols}"
        )

    async def test_token_hash_is_indexed_and_unique(self, db_engine):
        """GIVEN the refresh_tokens table
        WHEN schema is inspected
        THEN token_hash has a unique index.
        """
        def get_indexes(sync_conn):
            insp = inspect(sync_conn)
            idxs = insp.get_indexes("refresh_tokens")
            return [(c["column_names"], c["unique"]) for c in idxs]

        async with db_engine.connect() as conn:
            idxs = await conn.run_sync(get_indexes)
        hash_idxs = [u for (cols, u) in idxs if "token_hash" in cols]
        assert hash_idxs, "token_hash must be indexed"
        assert any(u for u in hash_idxs if u), "token_hash index must be unique"

    async def test_user_id_fk_to_users(self, db_session, sample_user):
        """GIVEN a refresh_token referencing a real user
        WHEN persisted
        THEN it succeeds (valid FK).
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="prefix12345",
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)
        assert rt.user_id == sample_user.id

    async def test_user_id_fk_rejects_nonexistent_user(self, db_session):
        """GIVEN a refresh_token with a non-existent user_id
        WHEN committed (PRAGMA foreign_keys=ON)
        THEN IntegrityError is raised.
        """
        rt = RefreshToken(
            user_id="00000000-0000-0000-0000-000000000000",
            token_prefix="prefix99999",
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_multiple_tokens_per_user_allowed(self, db_session, sample_user):
        """GIVEN a user
        WHEN two distinct refresh tokens are created for them
        THEN both persist (multi-session support).
        """
        rt1 = RefreshToken(
            user_id=sample_user.id,
            token_prefix="device-A-pre",
            token_hash="$argon2id$h1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        rt2 = RefreshToken(
            user_id=sample_user.id,
            token_prefix="device-B-pre",
            token_hash="$argon2id$h2",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add_all([rt1, rt2])
        await db_session.commit()

        stmt = select(RefreshToken).where(RefreshToken.user_id == sample_user.id)
        result = await db_session.execute(stmt)
        tokens = result.scalars().all()
        assert len(tokens) == 2

    async def test_revoked_at_nullable_defaults_none(self, db_session, sample_user):
        """GIVEN a newly created refresh token
        WHEN persisted
        THEN revoked_at is None (active token).
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="rev-test-pr",
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)
        assert rt.revoked_at is None

    async def test_revoked_at_can_be_set(self, db_session, sample_user):
        """GIVEN an active refresh token
        WHEN revoked_at is set (logout)
        THEN it persists.
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="rev-set-pre",
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)
        now = datetime.now(timezone.utc)
        rt.revoked_at = now
        await db_session.commit()
        await db_session.refresh(rt)
        assert rt.revoked_at is not None

    async def test_user_agent_and_ip_nullable(self, db_session, sample_user):
        """GIVEN a refresh token without user_agent or ip
        WHEN persisted
        THEN it succeeds (both nullable).
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="no-ua-ip-pre",
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)
        assert rt.user_agent is None
        assert rt.ip is None

    async def test_token_prefix_max_length_12(self, db_session, sample_user):
        """GIVEN a refresh token with token_prefix of exactly 12 chars
        WHEN persisted
        THEN it succeeds (prefix is first 12 chars of raw token per design).
        """
        rt = RefreshToken(
            user_id=sample_user.id,
            token_prefix="abcdefghijkl",  # 12 chars
            token_hash="$argon2id$h",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(rt)
        await db_session.commit()
        await db_session.refresh(rt)
        assert len(rt.token_prefix) == 12


# ─── Project.owner_id FK ──────────────────────────────────────────────────────


class TestProjectOwnerFk:
    """Project.owner_id MUST be a nullable FK to users.id (was String(128), no FK)."""

    async def test_project_owner_id_can_reference_user(self, db_session, sample_user):
        """GIVEN a real user
        WHEN a project is created with owner_id = user.id
        THEN it persists (valid FK).
        """
        project = Project(name="My Project", owner_id=sample_user.id, session_id="s1")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        assert project.owner_id == sample_user.id

    async def test_project_owner_id_nullable(self, db_session):
        """GIVEN a project with no owner (anonymous)
        WHEN persisted
        THEN owner_id is NULL.
        """
        project = Project(name="Anon", session_id="s-anon")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        assert project.owner_id is None

    async def test_project_owner_id_rejects_nonexistent_user(self, db_session):
        """GIVEN a project with owner_id pointing to a non-existent user
        WHEN committed (PRAGMA foreign_keys=ON)
        THEN IntegrityError is raised (real FK enforcement).
        """
        project = Project(
            name="Bad Owner",
            owner_id="00000000-0000-0000-0000-000000000000",
            session_id="s-bad",
        )
        db_session.add(project)
        with pytest.raises(IntegrityError):
            await db_session.commit()