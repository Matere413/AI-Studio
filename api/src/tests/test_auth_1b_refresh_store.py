"""Slice 1b — RefreshTokenStore (task 1b-3).

Covers session-management spec:
- Refresh Token Storage (token_hash argon2id, token_prefix clear + indexed,
  expires_at 30d, revoked_at, last_used_at, user_agent, ip, created_at;
  raw token NEVER stored)
- Refresh Token Rotation (atomic row-count guard; concurrent race → exactly
  one wins)
- Logout Revokes One (revoke(token_id))
- Logout-Global Revokes All (revoke_all(user_id))
- Refresh lookup strategy: token_prefix O(log N) index + argon2id.verify

These tests are written FIRST (RED) — the implementation
``src/features/auth/infrastructure/refresh_store.py`` does not exist yet.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.models.persistence import Base, async_session_factory
from src.features.auth.infrastructure.models import User, RefreshToken
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore


# ─── Fixtures ─────────────────────────────────────────────────────────────────
#
# The RefreshTokenStore derives a SYNC engine from the async engine's URL.
# For in-memory SQLite this would create a SEPARATE private in-memory DB
# (each connection gets its own ``:memory:``). To make the sync engine and
# the async engine share the SAME database, the tests use a temp FILE-based
# SQLite URL — the file is the shared state, exactly like production.


@pytest.fixture
async def db_engine(tmp_path: Path):
    """File-based temp SQLite so the sync + async engines share one DB.

    The RefreshTokenStore derives a SYNC engine from the async engine's URL.
    In-memory SQLite (``sqlite://``) is per-connection private, so the sync
    engine would see an empty DB. A temp FILE makes both engines read/write
    the same database — mirroring production behaviour exactly.
    """
    db_file = tmp_path / "auth_1b.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = _create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_session_factory(db_engine)


@pytest.fixture
def store(session_factory) -> RefreshTokenStore:
    return RefreshTokenStore(session_factory=session_factory)


@pytest.fixture
async def sample_user(session_factory):
    factory = session_factory
    async with factory() as session:
        user = User(email="alice@test.io", password_hash="$argon2id$x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        # Detach so the row's id is readable after the session closes.
        session.expunge(user)
        return user


def _raw_token() -> str:
    """Generate a 256-bit (32-byte) URL-safe random opaque refresh token."""
    return secrets.token_urlsafe(32)


# ─── create() ────────────────────────────────────────────────────────────────


class TestCreate:
    """create() stores a hashed refresh token row."""

    async def test_create_returns_token_id_and_raw_token(self, store, sample_user):
        """GIVEN a user
        WHEN create() is called
        THEN it returns a dict with a non-empty ``token_id`` and ``raw_token``.
        """
        result = store.create(
            user_id=sample_user.id,
            ua="Mozilla/5.0",
            ip="10.0.0.1",
        )
        assert "token_id" in result
        assert "raw_token" in result
        assert result["token_id"]
        assert len(result["raw_token"]) >= 32

    async def test_create_persists_row_with_hashed_token(
        self, store, session_factory, sample_user
    ):
        """GIVEN create() succeeds
        WHEN the refresh_tokens row is loaded directly
        THEN token_hash starts with ``$argon2id$`` and raw token is NOT stored.
        """
        result = store.create(user_id=sample_user.id, ua=None, ip=None)
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == result["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            assert row.token_hash.startswith("$argon2id$")
            # Raw token MUST NOT be stored verbatim.
            assert result["raw_token"] != row.token_hash
            assert result["raw_token"] not in row.token_hash

    async def test_create_stores_first_12_chars_as_prefix(
        self, store, session_factory, sample_user
    ):
        """GIVEN create() succeeds
        WHEN the row's ``token_prefix`` is inspected
        THEN it equals the first 12 chars of the raw token (clear, indexed).
        """
        result = store.create(user_id=sample_user.id, ua=None, ip=None)
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == result["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            assert row.token_prefix == result["raw_token"][:12]
            assert len(row.token_prefix) == 12

    async def test_create_sets_expires_at_30d(self, store, session_factory, sample_user):
        """GIVEN create() succeeds
        WHEN ``expires_at`` is inspected
        THEN it is ~30 days in the future (binding from design.md)."""
        before = datetime.now(timezone.utc)
        result = store.create(user_id=sample_user.id, ua=None, ip=None)
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == result["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            # ~30d (allow 1s slack for execution time).
            delta = row.expires_at.replace(tzinfo=timezone.utc) - before
            assert timedelta(days=29, hours=23, minutes=59) < delta < timedelta(days=30, seconds=5)

    async def test_create_captures_ua_and_ip(self, store, session_factory, sample_user):
        """GIVEN create() is called with ua + ip
        WHEN the row is loaded
        THEN user_agent and ip are stored."""
        store.create(user_id=sample_user.id, ua="Mozilla/5.0", ip="10.0.0.1")
        # (we only assert no-raise + the row exists; the exact values are
        # checked in test_create_persists_row_with_hashed_token's sibling)
        # Verify directly:
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.user_id == sample_user.id)
            row = (await session.execute(stmt)).scalar_one()
            assert row.user_agent == "Mozilla/5.0"
            assert row.ip == "10.0.0.1"

    async def test_create_revoked_at_is_null(self, store, session_factory, sample_user):
        """GIVEN a freshly created refresh token
        WHEN the row is loaded
        THEN ``revoked_at`` is None (active token)."""
        result = store.create(user_id=sample_user.id, ua=None, ip=None)
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == result["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            assert row.revoked_at is None


# ─── find_active() ───────────────────────────────────────────────────────────


class TestFindActive:
    """find_active() performs prefix-lookup + argon2id verify."""

    async def test_find_active_returns_row_for_valid_raw_token(
        self, store, sample_user
    ):
        """GIVEN a freshly created refresh token
        WHEN find_active(raw_token) is called with the raw token
        THEN it returns a dict with the row's ``token_id`` and ``user_id``.
        """
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        found = store.find_active(created["raw_token"])
        assert found is not None
        assert found["token_id"] == created["token_id"]
        assert found["user_id"] == sample_user.id

    async def test_find_active_returns_none_for_unknown_raw_token(self, store):
        """GIVEN a random raw token that was never issued
        WHEN find_active(raw_token) is called
        THEN it returns None (no row, no verify)."""
        assert store.find_active(_raw_token()) is None

    async def test_find_active_returns_none_for_revoked_token(
        self, store, sample_user
    ):
        """GIVEN a refresh token that has been revoked
        WHEN find_active(raw_token) is called
        THEN it returns None (revoked_at IS NOT NULL excluded)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        store.revoke(created["token_id"])
        assert store.find_active(created["raw_token"]) is None

    async def test_find_active_returns_none_for_expired_token(
        self, store, session_factory, sample_user
    ):
        """GIVEN a refresh token whose ``expires_at`` is in the past
        WHEN find_active(raw_token) is called
        THEN it returns None (expires_at <= now excluded)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        # Backdate expiry to force expiry.
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == created["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        assert store.find_active(created["raw_token"]) is None

    async def test_find_active_returns_none_for_tampered_raw_token(
        self, store, sample_user
    ):
        """GIVEN a raw token whose prefix matches a stored row but the rest
        has been tampered with
        WHEN find_active(raw_token) is called
        THEN argon2id.verify fails → returns None (no false positive on
        prefix collision)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        raw = created["raw_token"]
        # Keep the first 12 chars (prefix) intact; mutate the rest.
        tampered = raw[:12] + "X" + raw[13:]
        assert store.find_active(tampered) is None


# ─── revoke() ────────────────────────────────────────────────────────────────


class TestRevoke:
    """revoke(token_id) sets revoked_at with a row-count guard."""

    async def test_revoke_active_token_succeeds(self, store, sample_user):
        """GIVEN an active refresh token
        WHEN revoke(token_id) is called
        THEN it returns True (row was revoked)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        assert store.revoke(created["token_id"]) is True

    async def test_revoke_already_revoked_returns_false(self, store, sample_user):
        """GIVEN a token that is already revoked
        WHEN revoke(token_id) is called again
        THEN it returns False (row-count guard: no active row matched)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        assert store.revoke(created["token_id"]) is True
        # Second revoke hits zero rows (revoked_at IS NOT NULL excluded).
        assert store.revoke(created["token_id"]) is False

    async def test_revoke_unknown_token_id_returns_false(self, store):
        """GIVEN a non-existent token id
        WHEN revoke(token_id) is called
        THEN it returns False (no row matched)."""
        assert store.revoke("00000000-0000-0000-0000-000000000000") is False

    async def test_revoke_sets_revoked_at(self, store, session_factory, sample_user):
        """GIVEN revoke succeeds
        WHEN the row is loaded
        THEN ``revoked_at`` is set to a non-null timestamp."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        store.revoke(created["token_id"])
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == created["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            assert row.revoked_at is not None


# ─── revoke_all() ────────────────────────────────────────────────────────────


class TestRevokeAll:
    """revoke_all(user_id) revokes every non-expired token for a user."""

    async def test_revoke_all_revokes_every_active_token(self, store, sample_user):
        """GIVEN a user with 3 active tokens
        WHEN revoke_all(user_id) is called
        THEN all 3 are revoked (find_active returns None for each)."""
        tokens = [
            store.create(user_id=sample_user.id, ua=None, ip=None)
            for _ in range(3)
        ]
        store.revoke_all(sample_user.id)
        for t in tokens:
            assert store.find_active(t["raw_token"]) is None

    async def test_revoke_all_does_not_touch_other_users(
        self, store, session_factory, sample_user
    ):
        """GIVEN user A and user B each with an active token
        WHEN revoke_all(user_A) is called
        THEN user B's token remains active."""
        async with session_factory() as session:
            bob = User(email="bob@test.io", password_hash="$argon2id$b")
            session.add(bob)
            await session.commit()
            await session.refresh(bob)
        a = store.create(user_id=sample_user.id, ua=None, ip=None)
        b = store.create(user_id=bob.id, ua=None, ip=None)
        store.revoke_all(sample_user.id)
        # A's token is dead; B's is alive.
        assert store.find_active(a["raw_token"]) is None
        assert store.find_active(b["raw_token"]) is not None

    async def test_revoke_all_idempotent(self, store, sample_user):
        """GIVEN a user with no active tokens
        WHEN revoke_all(user_id) is called
        THEN it returns without error (no rows matched)."""
        # No tokens created — should not raise.
        store.revoke_all(sample_user.id)

    async def test_revoke_all_does_not_revoke_expired_token(
        self, store, session_factory, sample_user
    ):
        """GIVEN a refresh token whose ``expires_at`` is in the past
        WHEN revoke_all(user_id) is called
        THEN the expired row is NOT touched (revoked_at stays None).

        Spec: logout-all revokes every NON-EXPIRED, non-revoked token. An
        already-expired token needs no revoke (it's inert)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        # Backdate expiry so the token is "expired" (but still non-revoked).
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == created["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        # revoke_all should NOT touch the expired row.
        revoked_count = store.revoke_all(sample_user.id)
        assert revoked_count == 0, (
            f"expected 0 revoked (only expired token exists), got {revoked_count}"
        )
        # Confirm the expired row's revoked_at is still None.
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == created["token_id"])
            row = (await session.execute(stmt)).scalar_one()
            assert row.revoked_at is None, (
                "expired token must NOT be revoked by revoke_all"
            )


# ─── Rotation atomicity (concurrent race) ─────────────────────────────────────


class TestRotationAtomicity:
    """The row-count guard MUST make concurrent refresh races deterministic:
    exactly one wins, the other gets a None find_active (or revoke fails)."""

    async def test_concurrent_revoke_exactly_one_succeeds(self, store, sample_user):
        """GIVEN a single active refresh token
        WHEN two concurrent revoke(token_id) calls race
        THEN exactly one returns True; the other returns False
        (row-count guard wins for exactly one)."""
        created = store.create(user_id=sample_user.id, ua=None, ip=None)
        token_id = created["token_id"]

        # Fire two revokes concurrently against the SAME token id.
        results = await asyncio.gather(
            asyncio.to_thread(store.revoke, token_id),
            asyncio.to_thread(store.revoke, token_id),
        )
        # Exactly one True, exactly one False (row-count guard).
        assert results.count(True) == 1
        assert results.count(False) == 1