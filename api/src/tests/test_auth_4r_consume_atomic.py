"""4R corrective pass — WARNING 2: consume must be atomic.

``EmailVerificationStore.consume`` unconditionally set ``consumed_at`` without
a ``WHERE consumed_at IS NULL`` guard, so two concurrent consumes of the
same token could both succeed (both see consumed_at=None, both set it). The
fix adds ``WHERE consumed_at IS NULL`` to the UPDATE and checks the row
count: if 0 rows were affected, the token was already consumed → raise
``token_already_consumed`` (via returning False so the use case can classify).

Spec: email-verification — a token is single-use; concurrent verifies of
the same token MUST NOT both succeed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.models import User
from src.features.auth.application.use_cases import (
    TokenAlreadyConsumedError,
    verify_email,
)
from src.shared.models.persistence import Base, async_session_factory


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_4r_consume_atomic.db"
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
        u = User(email="eve@test.io", password_hash="x")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u.id


class TestConsumeAtomic:
    """consume MUST be atomic — a concurrent double-consume of the same
    token_id MUST NOT both succeed."""

    def test_consume_succeeds_on_first_call(self, store, sample_user):
        """GIVEN a fresh token
        WHEN consume is called once
        THEN it returns True (consumed_at set)."""
        created = store.create(user_id=sample_user)
        token_id = created["token_id"]
        ok = store.consume(token_id)
        assert ok is True

    def test_consume_fails_on_second_call(self, store, sample_user):
        """GIVEN a token that was already consumed
        WHEN consume is called again on the same token_id
        THEN it returns False (the WHERE consumed_at IS NULL guard matched
        0 rows — the token was already consumed)."""
        created = store.create(user_id=sample_user)
        token_id = created["token_id"]
        first = store.consume(token_id)
        assert first is True
        second = store.consume(token_id)
        assert second is False, "consume MUST return False when the token was already consumed (row count 0)"

    def test_consume_on_unknown_token_returns_false(self, store):
        """GIVEN a token_id that does not exist
        WHEN consume is called
        THEN it returns False (no row to update)."""
        ok = store.consume("nonexistent-token-id")
        assert ok is False

    def test_concurrent_consumes_only_one_wins(self, store, sample_user):
        """GIVEN a fresh token
        WHEN two consumes run concurrently (two threads)
        THEN exactly one returns True, the other returns False — the
        ``WHERE consumed_at IS NULL`` row-count guard makes the UPDATE
        atomic."""
        import threading

        created = store.create(user_id=sample_user)
        token_id = created["token_id"]

        results: list[bool] = [False, False]
        errors: list[BaseException] = []

        def worker(idx: int):
            try:
                results[idx] = store.consume(token_id)
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)

        t1 = threading.Thread(target=worker, args=(0,))
        t2 = threading.Thread(target=worker, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"threads raised: {errors}"
        trues = sum(1 for r in results if r is True)
        falses = sum(1 for r in results if r is False)
        assert trues == 1, f"exactly one consume MUST win, got {trues} winners: {results}"
        assert falses == 1, f"exactly one consume MUST lose, got {falses} losers: {results}"

    def test_verify_does_not_mark_user_verified_when_atomic_consume_loses(
        self, session_factory, store, sample_user
    ):
        """A resend/invalidation that wins after lookup cannot verify the user."""
        class MatchingHasher:
            def verify(self, token_hash, token):
                return True

        class LosingStore:
            def find_by_user(self, *, user_id):
                return [
                    {
                        "id": "challenge-id",
                        "token_hash": "hash",
                        "consumed_at": None,
                        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                    }
                ]

            def consume(self, token_id):
                return False

        with pytest.raises(TokenAlreadyConsumedError):
            verify_email(
                email="eve@test.io",
                token="matching-token",
                session_factory=session_factory,
                email_verification_store=LosingStore(),
                hasher=MatchingHasher(),
            )

        with store._sync_factory() as session:
            user = session.get(User, sample_user)
            assert user.email_verified is False
