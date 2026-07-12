"""Slice 2 — EmailVerificationStore (task 2-1 / 2-3 store helper).

Spec: email-verification — Token Generation + the verify-email lookup
contract from design.md.

The store:
- ``create(user_id, raw_token)`` mints a 32-byte random token, persists its
  argon2id hash + 24h expiry + ``consumed_at = None``, and returns the raw
  token ONCE. The raw token is NEVER stored.
- ``find_by_user(user_id)`` returns ALL of the user's verification rows
  (NO prefilter on consumed_at/expires_at) so the verify-email use case can
  classify expired/consumed rows that match the hash (per design.md —
  no-prefilter scan).

These tests are written FIRST (RED) — the store does not exist yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.models import EmailVerification, User
from src.shared.models.persistence import Base, async_session_factory


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_ev_store.db"
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
def store(session_factory) -> EmailVerificationStore:
    return EmailVerificationStore(session_factory=session_factory)


@pytest.fixture
async def sample_user(session_factory):
    async with session_factory() as session:
        user = User(email="evs@test.io", password_hash="$argon2id$abc")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ─── create ───────────────────────────────────────────────────────────────────


class TestEmailVerificationStoreCreate:
    """create(user_id, raw_token) hashes + persists; returns metadata."""

    def test_create_returns_raw_token(self, store, sample_user):
        result = store.create(user_id=sample_user.id)
        assert "raw_token" in result
        assert result["raw_token"]
        # 32-byte urlsafe base64 → 43 chars
        assert len(result["raw_token"]) >= 32

    def test_create_does_not_store_raw_token(self, store, sample_user):
        """Binding: the raw token MUST NOT be stored anywhere."""
        result = store.create(user_id=sample_user.id)
        raw = result["raw_token"]
        # The stored hash must NOT equal the raw token.
        rows = store.find_by_user(user_id=sample_user.id)
        for row in rows:
            assert row["token_hash"] != raw

    def test_create_stores_argon2id_hash(self, store, sample_user):
        store.create(user_id=sample_user.id)
        rows = store.find_by_user(user_id=sample_user.id)
        assert rows
        assert rows[0]["token_hash"].startswith("$argon2id$")

    def test_create_sets_24h_expiry_consumed_at_none(
        self, store, sample_user
    ):
        from datetime import datetime, timezone

        before = datetime.now(timezone.utc)
        store.create(user_id=sample_user.id)
        after = datetime.now(timezone.utc)

        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 1
        row = rows[0]
        # SQLite stores datetimes naive — coerce to UTC for the comparison.
        exp = row["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        # ~24h expiry (allow 1s slack)
        delta = exp - before
        assert timedelta(hours=23, minutes=59) < delta < timedelta(hours=24, minutes=1)
        assert row["consumed_at"] is None

    def test_create_multiple_rows_for_same_user(self, store, sample_user):
        store.create(user_id=sample_user.id)
        store.create(user_id=sample_user.id)
        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 2


# ─── find_by_user ─────────────────────────────────────────────────────────────


class TestEmailVerificationStoreFindByUser:
    """find_by_user(user_id) — NO prefilter on consumed/expired."""

    def test_find_by_user_returns_all_rows_including_consumed(
        self, store, sample_user, session_factory
    ):
        """Binding: NO prefilter on consumed_at — consumed rows MUST be
        returned so the verify use case can classify them."""
        store.create(user_id=sample_user.id)
        # Consume the first row directly.
        async def _consume():
            async with session_factory() as session:
                stmt = select(EmailVerification).where(
                    EmailVerification.user_id == sample_user.id
                )
                rows = (await session.execute(stmt)).scalars().all()
                rows[0].consumed_at = datetime.now(timezone.utc)
                await session.commit()

        import asyncio

        asyncio.get_event_loop().run_until_complete(_consume())

        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 1
        assert rows[0]["consumed_at"] is not None

    def test_find_by_user_returns_expired_rows(self, store, sample_user, session_factory):
        """Binding: NO prefilter on expires_at — expired rows MUST be
        returned so the verify use case can classify them as token_expired."""
        store.create(user_id=sample_user.id)

        async def _expire():
            async with session_factory() as session:
                stmt = select(EmailVerification).where(
                    EmailVerification.user_id == sample_user.id
                )
                rows = (await session.execute(stmt)).scalars().all()
                rows[0].expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
                await session.commit()

        import asyncio

        asyncio.get_event_loop().run_until_complete(_expire())

        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 1

    def test_find_by_user_empty_for_unknown_user(self, store):
        rows = store.find_by_user(user_id="no-such-user")
        assert rows == []

    def test_find_by_user_returns_newest_first(self, store, sample_user):
        """Rows are ordered by created_at DESC so the verify use case
        checks the newest (most likely intended) token first."""
        store.create(user_id=sample_user.id)
        store.create(user_id=sample_user.id)
        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 2
        assert rows[0]["created_at"] >= rows[1]["created_at"]


# ─── delivered state ──────────────────────────────────────────────────────────


class TestEmailVerificationStoreDeliveredState:
    def test_create_records_delivered_input(self, store, sample_user):
        store.create(user_id=sample_user.id, delivered=True)
        assert store.find_by_user(sample_user.id)[0]["delivered"] is True

    def test_mark_delivered_updates_known_row(self, store, sample_user):
        challenge = store.create(user_id=sample_user.id)
        assert store.mark_delivered(challenge["token_id"], delivered=True) is True
        assert store.find_by_user(sample_user.id)[0]["delivered"] is True

    def test_mark_delivered_ignores_unknown_row(self, store):
        assert store.mark_delivered("unknown", delivered=True) is False

    def test_has_delivered_challenge_uses_only_delivered_unconsumed_unexpired_rows(
        self, store, sample_user, session_factory
    ):
        """Undelivered, consumed, and expired rows must not enable the gate."""
        store.create(user_id=sample_user.id)
        assert store.has_delivered_challenge(sample_user.id) is False

        consumed = store.create(user_id=sample_user.id, delivered=True)
        store.consume(consumed["token_id"])
        assert store.has_delivered_challenge(sample_user.id) is False

        expired = store.create(user_id=sample_user.id, delivered=True)

        async def _expire():
            async with session_factory() as session:
                row = await session.get(EmailVerification, expired["token_id"])
                row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
                await session.commit()

        import asyncio

        asyncio.get_event_loop().run_until_complete(_expire())
        assert store.has_delivered_challenge(sample_user.id) is False

        store.create(user_id=sample_user.id, delivered=True)
        assert store.has_delivered_challenge(sample_user.id) is True

    def test_has_delivered_challenge_requires_valid_unconsumed_row(
        self, store, sample_user
    ):
        challenge = store.create(user_id=sample_user.id)
        store.mark_delivered(challenge["token_id"], delivered=True)
        assert store.has_delivered_challenge(sample_user.id) is True
        store.consume(challenge["token_id"])
        assert store.has_delivered_challenge(sample_user.id) is False


class TestEmailVerificationStoreInvalidateAndCreate:
    def test_replaces_pending_challenges_with_one_new_challenge(self, store, sample_user):
        store.create(user_id=sample_user.id)
        store.create(user_id=sample_user.id)

        result = store.invalidate_and_create(user_id=sample_user.id)

        assert result["invalidated"] == 2
        rows = store.find_by_user(user_id=sample_user.id)
        assert len(rows) == 3
        assert sum(row["consumed_at"] is None for row in rows) == 1
        assert next(row for row in rows if row["consumed_at"] is None)["id"] == result[
            "token_id"
        ]

    @pytest.mark.parametrize("state", ["expired", "consumed"])
    def test_invalidate_pending_preserves_classifiable_nonpending_rows(
        self, store, sample_user, state
    ):
        challenge = store.create(user_id=sample_user.id)
        with store._sync_factory() as session:
            row = session.get(EmailVerification, challenge["token_id"])
            if state == "expired":
                row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            else:
                row.consumed_at = datetime.now(timezone.utc)
            session.commit()

        assert store.invalidate_pending(sample_user.id) == 0
        row = store.find_by_user(sample_user.id)[0]
        expires_at = row["expires_at"].replace(tzinfo=timezone.utc)
        assert (expires_at <= datetime.now(timezone.utc)) == (state == "expired")
        assert (row["consumed_at"] is not None) == (state == "consumed")

    def test_invalidate_pending_ignores_empty_user_id(self, store):
        assert store.invalidate_pending("") == 0

    def test_concurrent_replacements_leave_one_valid_challenge(
        self, store, sample_user
    ):
        store.create(user_id=sample_user.id)
        results: list[dict] = []
        errors: list[BaseException] = []
        connections: list[int] = []
        first_locked = threading.Event()
        second_attempted = threading.Event()
        release_first = threading.Event()

        def is_invalidation(statement: str) -> bool:
            return statement.lstrip().upper().startswith("UPDATE EMAIL_VERIFICATIONS")

        def before_execute(conn, cursor, statement, parameters, context, executemany):
            if is_invalidation(statement):
                connections.append(id(conn.connection))
                if first_locked.is_set():
                    second_attempted.set()

        def after_execute(conn, cursor, statement, parameters, context, executemany):
            if is_invalidation(statement) and not first_locked.is_set():
                first_locked.set()
                assert release_first.wait(3), "test did not release SQLite writer"

        def replace() -> None:
            try:
                results.append(store.invalidate_and_create(user_id=sample_user.id))
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)

        event.listen(store._sync_engine, "before_cursor_execute", before_execute)
        event.listen(store._sync_engine, "after_cursor_execute", after_execute)
        try:
            first = threading.Thread(target=replace)
            first.start()
            assert first_locked.wait(3), "first SQLite replacement never acquired writer"
            second = threading.Thread(target=replace)
            second.start()
            assert second_attempted.wait(3), "second replacement never reached lock"
            assert second.is_alive(), "second replacement did not wait for SQLite writer"
        finally:
            release_first.set()
            first.join()
            second.join()
            event.remove(store._sync_engine, "before_cursor_execute", before_execute)
            event.remove(store._sync_engine, "after_cursor_execute", after_execute)

        assert not errors, f"threads raised: {errors}"
        assert len(results) == 2
        assert len(set(connections)) == 2
        rows = store.find_by_user(user_id=sample_user.id)
        assert sum(row["consumed_at"] is None for row in rows) == 1

    def test_replacement_issues_parent_lock_statement(self, store, sample_user):
        """Structural coverage only; runtime PostgreSQL serialization needs a service."""
        statements = []

        class Result:
            rowcount = 0

        class Session:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement):
                statements.append(statement)
                return Result()

            def add(self, row):
                row.id = "replacement-id"

            def commit(self):
                pass

            def refresh(self, row):
                pass

        original_factory = store._sync_factory
        store._sync_factory = Session
        try:
            store.invalidate_and_create(user_id=sample_user.id)
        finally:
            store._sync_factory = original_factory

        sql = str(statements[0].compile(dialect=postgresql.dialect()))
        assert sql.endswith("FOR UPDATE")
