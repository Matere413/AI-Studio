"""Zombie / late-delivery policy — judgment-day finding #4.

The user policy keeps an UNCERTAIN delivery (a running-timeout send whose
worker cannot be force-cancelled) no-block-on-uncertain: the challenge row
stays ``delivered=False`` so the saving gate does not block a user who
cannot complete a challenge with an uncertain outcome. The finding: a late
success of that worker would later deliver a valid link, so naively issuing
a new resend would leave MULTIPLE valid links outstanding (the old uncertain
one + the new one).

The coherent approach chosen: BEFORE minting a new resend challenge, the
use case INVALIDATES the user's pending (unconsumed, unexpired) challenge
rows — setting ``consumed_at`` on them. A later-arriving link from an old
row is then unusable (``verify_email`` classifies a matching row with
``consumed_at IS NOT NULL`` as ``token_already_consumed``). There is at
most ONE valid link outstanding at a time. The ``delivered`` flag is NOT
touched, so the no-block-on-uncertain invariant is preserved (an uncertain
row keeps ``delivered=False`` → the gate still sees no delivered challenge
→ no block until the new challenge is actually delivered).

These tests assert:
1. ``invalidate_pending`` consumes unconsumed + unexpired rows; leaves
   consumed + expired rows untouched (they are already invalid).
2. ``resend_verification`` invalidates the old pending challenges before
   minting the new one → only the new challenge is verifiable.
3. A late-arriving link from an OLD (invalidated) challenge is classified
   ``token_already_consumed`` by ``verify_email`` (no second valid link).
4. The ``delivered`` flag of an invalidated uncertain row is NOT touched
   (no-block-on-uncertain invariant preserved).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.application.use_cases import (
    resend_verification,
    verify_email,
)
from src.features.auth.infrastructure.email_client import SendResult
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.models.persistence import Base, async_session_factory


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_zombie.db"
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
def jwt_service() -> JWTService:
    import secrets

    return JWTService(secret=secrets.token_hex(32))


@pytest.fixture
def ev_store(session_factory) -> EmailVerificationStore:
    return EmailVerificationStore(session_factory=session_factory)


@dataclass
class StubEmailClient:
    """A controllable EmailClient whose ``send_verification`` returns a fixed
    ``SendResult``. Records delivery_ids + emails for assertion."""
    result: SendResult
    sent_count: int = 0
    sent_delivery_ids: list = field(default_factory=list)

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        return f"https://app.test/auth/verify?token={raw_token}&email={email}"

    def send_verification(
        self, *, email: str, raw_token: str, delivery_id: str | None = None
    ) -> SendResult:
        self.sent_count += 1
        self.sent_delivery_ids.append(delivery_id)
        return self.result


# ─── invalidate_pending ───────────────────────────────────────────────────────


class TestInvalidatePending:
    """``EmailVerificationStore.invalidate_pending`` — the store primitive."""

    def test_consumes_unconsumed_unexpired_rows(self, session_factory, ev_store):
        """GIVEN a user with two pending (unconsumed, unexpired) challenge rows
        WHEN invalidate_pending(user_id) is called
        THEN both rows are consumed (consumed_at IS NOT NULL). Returns 2."""
        from src.features.auth.infrastructure.models import User

        # Create a user directly so we have a user_id.
        # Register via the store to get rows. We need a user_id; create a
        # minimal user through the async factory.
        import asyncio

        async def _make_user():
            async with session_factory() as session:
                u = User(email="zombie@test.io", password_hash="x", email_verified=False)
                session.add(u)
                await session.commit()
                await session.refresh(u)
                return u.id

        user_id = asyncio.get_event_loop().run_until_complete(_make_user())

        ev_store.create(user_id=user_id)
        ev_store.create(user_id=user_id)

        rows = ev_store.find_by_user(user_id=user_id)
        assert len(rows) == 2
        assert all(r["consumed_at"] is None for r in rows)

        count = ev_store.invalidate_pending(user_id=user_id)
        assert count == 2, "both pending rows were invalidated"

        rows_after = ev_store.find_by_user(user_id=user_id)
        assert all(r["consumed_at"] is not None for r in rows_after), (
            "invalidate_pending consumed every pending row"
        )

    def test_leaves_consumed_rows_untouched(self, session_factory, ev_store):
        """GIVEN a user with a CONSUMED challenge row
        WHEN invalidate_pending(user_id) is called
        THEN the consumed row is NOT modified (it is already invalid; leaving
        it lets verify_email still classify a stale click as
        token_already_consumed). Returns 0 — nothing new was invalidated."""
        from src.features.auth.infrastructure.models import User
        import asyncio

        async def _make_user():
            async with session_factory() as session:
                u = User(email="zombie2@test.io", password_hash="x", email_verified=False)
                session.add(u)
                await session.commit()
                await session.refresh(u)
                return u.id

        user_id = asyncio.get_event_loop().run_until_complete(_make_user())

        result = ev_store.create(user_id=user_id)
        ev_store.consume(result["token_id"])  # consume it first

        count = ev_store.invalidate_pending(user_id=user_id)
        assert count == 0, "a consumed row is NOT invalidated again"

    def test_does_not_touch_delivered_flag(self, session_factory, ev_store):
        """GIVEN a pending row with delivered=False (an uncertain send)
        WHEN invalidate_pending(user_id) is called
        THEN the row's consumed_at is set BUT delivered is still False — the
        no-block-on-uncertain invariant is preserved (the gate still sees no
        delivered challenge)."""
        from src.features.auth.infrastructure.models import User
        import asyncio

        async def _make_user():
            async with session_factory() as session:
                u = User(email="zombie3@test.io", password_hash="x", email_verified=False)
                session.add(u)
                await session.commit()
                await session.refresh(u)
                return u.id

        user_id = asyncio.get_event_loop().run_until_complete(_make_user())

        # Create a row then mark delivered=False explicitly (uncertain).
        result = ev_store.create(user_id=user_id)
        ev_store.mark_delivered(result["token_id"], delivered=False)

        ev_store.invalidate_pending(user_id=user_id)

        rows = ev_store.find_by_user(user_id=user_id)
        assert rows[0]["delivered"] is False, (
            "invalidate_pending MUST NOT touch the delivered flag"
        )
        assert rows[0]["consumed_at"] is not None


# ─── resend_verification → invalidate-then-mint ───────────────────────────────


class TestResendInvalidatesOldChallenges:
    """``resend_verification`` invalidates old pending challenges before
    minting the new one → at most one valid link outstanding."""

    def _register_user(self, session_factory, email, password):
        """Create a user directly (no email send) so resend has a target."""
        from src.features.auth.application.use_cases import register_user

        ev_store = EmailVerificationStore(session_factory=session_factory)
        jwt = JWTService(secret="test-secret-please-not-in-prod-xxx")
        refresh = RefreshTokenStore(session_factory=session_factory)
        client = StubEmailClient(result=SendResult(success=False))
        session = register_user(
            email=email,
            password=password,
            session_factory=session_factory,
            jwt_service=jwt,
            refresh_store=refresh,
            email_verification_store=ev_store,
            email_client=client,
        )
        return session.user.id, ev_store, jwt, refresh, client

    def test_resend_invalidates_old_pending_challenges(
        self, session_factory, jwt_service
    ):
        """GIVEN a user with a pending (unconsumed) registration challenge
        WHEN resend_verification is called
        THEN the OLD challenge is invalidated (consumed_at set) AND a NEW
        challenge is minted. Only the new challenge is verifiable."""
        user_id, ev_store, jwt, refresh, client = self._register_user(
            session_factory, "zombie4@test.io", "CorrectHorse42!"
        )

        old_rows = ev_store.find_by_user(user_id=user_id)
        assert len(old_rows) == 1
        old_token_id = old_rows[0]["id"]
        assert old_rows[0]["consumed_at"] is None

        # Resend with a successful send so the new row is delivered.
        client.result = SendResult(success=True)
        resend_verification(
            user_id=user_id,
            session_factory=session_factory,
            email_verification_store=ev_store,
            email_client=client,
        )

        rows_after = ev_store.find_by_user(user_id=user_id)
        assert len(rows_after) == 2, "a new challenge was minted"
        # The OLD row is now consumed.
        old_row = next(r for r in rows_after if r["id"] == old_token_id)
        assert old_row["consumed_at"] is not None, (
            "the OLD challenge MUST be invalidated (consumed_at set) before the new one"
        )
        # The NEW row is unconsumed (it is the valid link).
        new_row = next(r for r in rows_after if r["id"] != old_token_id)
        assert new_row["consumed_at"] is None, (
            "the NEW challenge is the only valid (unconsumed) link"
        )

    def test_only_one_valid_link_outstanding_after_resend(
        self, session_factory, jwt_service
    ):
        """GIVEN a user with a pending challenge
        WHEN resend_verification is called twice (two resend clicks)
        THEN only the LATEST challenge is unconsumed; all earlier ones are
        invalidated. At most ONE valid link is outstanding at a time."""
        user_id, ev_store, jwt, refresh, client = self._register_user(
            session_factory, "zombie5@test.io", "CorrectHorse42!"
        )

        client.result = SendResult(success=False)
        resend_verification(
            user_id=user_id, session_factory=session_factory,
            email_verification_store=ev_store, email_client=client,
        )
        resend_verification(
            user_id=user_id, session_factory=session_factory,
            email_verification_store=ev_store, email_client=client,
        )

        rows = ev_store.find_by_user(user_id=user_id)
        assert len(rows) == 3, "registration + 2 resends = 3 rows"
        unconsumed = [r for r in rows if r["consumed_at"] is None]
        assert len(unconsumed) == 1, (
            "exactly ONE valid (unconsumed) link outstanding after resends"
        )

    def test_concurrent_replacements_leave_one_valid_challenge(
        self, session_factory, jwt_service
    ):
        """Two synchronized resend replacements serialize on the user's row."""
        import threading

        user_id, ev_store, _jwt, _refresh, _client = self._register_user(
            session_factory, "zombie-concurrent@test.io", "CorrectHorse42!"
        )
        barrier = threading.Barrier(2)
        original_hash = ev_store._hasher.hash

        def synchronized_hash(raw_token):
            barrier.wait(timeout=5)
            return original_hash(raw_token)

        ev_store._hasher.hash = synchronized_hash
        errors: list[BaseException] = []

        def worker():
            try:
                ev_store.invalidate_and_create(user_id)
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=worker)
        second = threading.Thread(target=worker)
        first.start()
        second.start()
        first.join()
        second.join()

        assert not errors, f"concurrent replacements raised: {errors}"
        rows = ev_store.find_by_user(user_id=user_id)
        assert len([row for row in rows if row["consumed_at"] is None]) == 1


# ─── verify_email classifies an invalidated (zombie) link ────────────────────


class TestVerifyEmailRejectsInvalidatedZombie:
    """A late-arriving link from an OLD (invalidated) challenge is classified
    ``token_already_consumed`` — no second valid link can activate strict
    verification."""

    def test_late_link_from_invalidated_challenge_is_already_consumed(
        self, session_factory, jwt_service
    ):
        """GIVEN a user whose first challenge was invalidated by a resend
        (consumed_at set) AND the raw token of that first challenge
        WHEN verify_email is called with the old token
        THEN it raises TokenAlreadyConsumedError (the old link is no longer
        valid) — so a zombie / late delivery of the old link cannot verify
        the user out of band. Only the new challenge is valid."""
        from src.features.auth.application.use_cases import (
            register_user,
            resend_verification,
            TokenAlreadyConsumedError,
        )

        ev_store = EmailVerificationStore(session_factory=session_factory)
        refresh = RefreshTokenStore(session_factory=session_factory)

        # Capture the raw token of the FIRST (registration) challenge.
        captured_tokens: list[str] = []

        class _CapturingClient:
            sent_count = 0

            def build_verification_url(self, *, email, raw_token):
                return f"https://app.test/auth/verify?token={raw_token}&email={email}"

            def send_verification(self, *, email, raw_token, delivery_id=None):
                self.sent_count += 1
                # Capture the raw token on the FIRST send (the registration).
                if self.sent_count == 1:
                    captured_tokens.append(raw_token)
                return SendResult(success=False)

        client = _CapturingClient()
        session = register_user(
            email="zombie6@test.io",
            password="CorrectHorse42!",
            session_factory=session_factory,
            jwt_service=jwt_service,
            refresh_store=refresh,
            email_verification_store=ev_store,
            email_client=client,
        )
        user_id = session.user.id
        first_raw_token = captured_tokens[0]
        assert first_raw_token, "captured the registration challenge's raw token"

        # Resend — this invalidates the FIRST challenge (consumed_at set).
        resend_verification(
            user_id=user_id,
            session_factory=session_factory,
            email_verification_store=ev_store,
            email_client=client,
        )

        # A LATE link from the FIRST challenge arrives — it MUST be rejected
        # as already_consumed (the resend invalidated it).
        with pytest.raises(TokenAlreadyConsumedError):
            verify_email(
                email="zombie6@test.io",
                token=first_raw_token,
                session_factory=session_factory,
                email_verification_store=ev_store,
            )
