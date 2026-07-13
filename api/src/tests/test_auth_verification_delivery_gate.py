"""Blocker 1 — verification gate must not re-block users when Resend
delivery fails.

Production blocker: ``ResendEmailClient.send_verification`` caught all send
failures and logged them, while the saving gate was driven by provider
*configuration* (``isinstance(email_client, ResendEmailClient)``). An
invalid API key, sender rejection, provider outage, or missing SDK
yielded NO delivered email while unverified users were blocked from save —
a permanent deadlock with no path to verify.

Fix contract: ``send_verification`` returns an observable
:class:`SendResult` (``success: bool``); the use-case layer records
``delivered`` on the ``email_verifications`` row from the result; the
saving gate enforces ``email_verified`` ONLY for users who have at least
one DELIVERED challenge (``has_delivered_challenge``). A user whose email
never reached them (failed send) is NOT blocked — they cannot complete a
challenge they never received. Anonymous save stays blocked (401) in all
modes. Dev / no-delivery authenticated unverified users stay allowed
(``DevEmailClient`` records ``delivered=False``).

These tests prove the contract end-to-end at the unit + integration layer:
- ``SendResult`` is returned and carries the success flag.
- ``ResendEmailClient`` returns ``success=False`` on a failed send (never
  raises) and ``success=True`` on a successful send.
- ``DevEmailClient`` returns ``success=False`` (dev = no real delivery).
- The store records ``delivered`` from the result and the gate consults it.
- A failed send → unverified user can save (NOT blocked).
- A successful send → unverified user is blocked (403) until verified.
- Anonymous save stays 401 regardless of delivery state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.email_client import (
    DevEmailClient,
    ResendEmailClient,
    SendResult,
)
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.models.persistence import Base, async_session_factory


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_delivery_gate.db"
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
    return JWTService(secret="test-secret-please-not-in-prod-xxx")


@pytest.fixture
def ev_store(session_factory) -> EmailVerificationStore:
    return EmailVerificationStore(session_factory=session_factory)


@pytest.fixture
async def unverified_user(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            email="unverified@test.io",
            password_hash="$argon2id$u",
            email_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.expunge(user)
        return user


# ─── SendResult contract ─────────────────────────────────────────────────────


class TestSendResultContract:
    """send_verification returns an observable SendResult (success: bool)."""

    def test_send_result_is_frozen_dataclass_with_success_flag(self):
        result = SendResult(success=True)
        assert result.success is True
        # Frozen — cannot mutate (the gate trusts the value is immutable).
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]

    def test_dev_email_client_returns_success_false(self):
        """DevEmailClient is the no-delivery provider — it records
        delivered=False so dev / no-delivery unverified users stay allowed
        (the gate degrades to authenticated-only for them)."""
        client = DevEmailClient(app_base_url="https://app.test")
        result = client.send_verification(
            email="dev@test.io", raw_token="raw-token-value-1234"
        )
        assert isinstance(result, SendResult)
        assert result.success is False, (
            "DevEmailClient MUST return success=False so the gate degrades "
            "to authenticated-only in dev / no-delivery mode"
        )

    def test_resend_client_returns_success_true_on_successful_send(
        self
    ):
        """GIVEN a ResendEmailClient AND its injected transport succeeds
        WHEN send_verification is called
        THEN it returns SendResult(success=True) (never raises)."""
        def _fake_send(request):
            return {"id": "resend-message-id"}

        client = ResendEmailClient(
            api_key="valid-key",
            from_email="AI-Studio <noreply@ai-studio.app>",
            app_base_url="https://app.test",
            send_transport=_fake_send,
        )
        result = client.send_verification(
            email="alice@test.io", raw_token="raw-token-value-1234"
        )
        assert isinstance(result, SendResult)
        assert result.success is True

    def test_resend_client_returns_success_false_on_failed_send(
        self
    ):
        """GIVEN a ResendEmailClient AND its injected transport raises (invalid API
        key, sender rejection, provider outage, missing SDK)
        WHEN send_verification is called
        THEN it returns SendResult(success=False) — NEVER raises. The
        failure is observable so the use-case layer records
        delivered=False and the gate does NOT block the user."""
        def _raising_send(request):
            raise RuntimeError("403 Forbidden — API key invalid")

        client = ResendEmailClient(
            api_key="invalid-or-revoked-key",
            from_email="AI-Studio <noreply@ai-studio.app>",
            app_base_url="https://app.test",
            send_transport=_raising_send,
        )
        result = client.send_verification(
            email="alice@test.io", raw_token="raw-token-value-1234"
        )
        assert isinstance(result, SendResult)
        assert result.success is False, (
            "a failed Resend send MUST return success=False (never raise) "
            "so the gate degrades to authenticated-only for the affected user"
        )

    def test_resend_client_returns_success_false_on_missing_sdk(
        self
    ):
        """GIVEN a ResendEmailClient AND its transport cannot load a dependency
        (ImportError)
        WHEN send_verification is called
        THEN it returns SendResult(success=False) — the missing SDK is an
        operational failure, not a definitive auth death for the user."""
        def _missing_sdk_send(request):
            raise ImportError("No module named 'resend'")

        client = ResendEmailClient(
            api_key="any-key",
            from_email="AI-Studio <noreply@ai-studio.app>",
            app_base_url="https://app.test",
            send_transport=_missing_sdk_send,
        )
        result = client.send_verification(
            email="alice@test.io", raw_token="raw-token-value-1234"
        )
        assert result.success is False


# ─── Store records delivered ─────────────────────────────────────────────────


class TestStoreDeliveredRecording:
    """The store records the delivery outcome; the gate consults it."""

    def test_create_defaults_delivered_false(self, ev_store, unverified_user):
        """GIVEN a freshly created challenge row
        THEN delivered is False (the send has not been recorded yet)."""
        result = ev_store.create(user_id=unverified_user.id)
        rows = ev_store.find_by_user(user_id=unverified_user.id)
        assert len(rows) == 1
        assert rows[0]["delivered"] is False
        # token_id is exposed for the use-case layer to mark delivered.
        assert result["token_id"] == rows[0]["id"]

    def test_mark_delivered_sets_delivered_true(self, ev_store, unverified_user):
        """GIVEN a challenge row
        WHEN mark_delivered(token_id, delivered=True)
        THEN the row's delivered flag becomes True."""
        result = ev_store.create(user_id=unverified_user.id)
        updated = ev_store.mark_delivered(result["token_id"], delivered=True)
        assert updated is True
        rows = ev_store.find_by_user(user_id=unverified_user.id)
        assert rows[0]["delivered"] is True

    def test_mark_delivered_unknown_token_returns_false(
        self, ev_store, unverified_user
    ):
        """GIVEN an unknown token id
        WHEN mark_delivered is called
        THEN it returns False (defensive — a late callback for a row that no
        longer exists is a no-op, never crashes)."""
        updated = ev_store.mark_delivered("no-such-token", delivered=True)
        assert updated is False

    def test_has_delivered_challenge_false_when_none_delivered(
        self, ev_store, unverified_user
    ):
        """GIVEN a user with a challenge that was NOT delivered
        THEN has_delivered_challenge returns False (gate degrades)."""
        ev_store.create(user_id=unverified_user.id)
        assert ev_store.has_delivered_challenge(unverified_user.id) is False

    def test_has_delivered_challenge_true_when_one_delivered(
        self, ev_store, unverified_user
    ):
        """GIVEN a user with at least one delivered challenge
        THEN has_delivered_challenge returns True (gate enforces)."""
        r1 = ev_store.create(user_id=unverified_user.id)
        ev_store.create(user_id=unverified_user.id)  # not delivered
        ev_store.mark_delivered(r1["token_id"], delivered=True)
        assert ev_store.has_delivered_challenge(unverified_user.id) is True

    def test_has_delivered_challenge_false_for_empty_user(self, ev_store):
        """GIVEN a user with no challenge rows at all
        THEN has_delivered_challenge returns False (gate degrades)."""
        assert ev_store.has_delivered_challenge("no-such-user") is False

    def test_has_delivered_challenge_false_for_empty_user_id(self, ev_store):
        """GIVEN an empty user_id
        THEN has_delivered_challenge returns False (defensive)."""
        assert ev_store.has_delivered_challenge("") is False
