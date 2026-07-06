"""Slice 2 — verify-email endpoint (tasks 2-3 + 2-4 + register trigger).

Spec: email-verification — Verify Endpoint.

``POST /auth/verify-email`` accepts ``{email, token}``. The lookup is
``user_id``-scoped via the email (no user → ``invalid_token``,
anti-enumeration), then an iterate-and-verify scan over the user's
verification rows with NO prefilter on consumed/expired. For each row the
argon2id hash is verified against the raw token:
- match + consumed_at IS NOT NULL → ``400 token_already_consumed``
- match + expires_at <= now → ``400 token_expired``
- match + valid → atomic consume (set consumed_at = now, set
  users.email_verified = TRUE) → ``200 {verified: true}``. BREAK.
- no match → ``400 invalid_token``.

Also covers: register triggers a verification email (an
``email_verifications`` row exists after register).

These tests are written FIRST (RED) — the endpoint does not exist yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.models import EmailVerification, User
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.infrastructure.email_client import DevEmailClient
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_verify.db"
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
def refresh_store(session_factory) -> RefreshTokenStore:
    return RefreshTokenStore(session_factory=session_factory)


@pytest.fixture
def ev_store(session_factory) -> EmailVerificationStore:
    return EmailVerificationStore(session_factory=session_factory)


@pytest.fixture
def email_client() -> DevEmailClient:
    return DevEmailClient(app_base_url="https://app.test")


@pytest.fixture
def app(
    session_factory,
    jwt_service,
    refresh_store,
    ev_store,
    email_client,
):
    from src.features.auth.presentation.router import build_auth_router
    from src.features.auth.presentation.dependencies import init_auth_providers

    init_auth_providers(
        session_factory=session_factory,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        email_verification_store=ev_store,
        email_client=email_client,
    )
    _app = __import__("fastapi").FastAPI()
    register_app_error_handlers(_app)
    _app.include_router(build_auth_router())
    return _app


@pytest.fixture
def client(app):
    return LazyTestClient(app)


def _strong_pw() -> str:
    return "CorrectHorse42!"


# ─── Register triggers verification email ──────────────────────────────────────


class TestRegisterTriggersVerification:
    """Spec: Registration — 'trigger a verification email'."""

    def test_register_creates_email_verification_row(self, client, ev_store, session_factory):
        """GIVEN a successful registration
        WHEN the system processes it
        THEN an ``email_verifications`` row exists for that user."""
        resp = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200, resp.text
        async def _find_user():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "alice@test.io")
                return (await session.execute(stmt)).scalar_one()

        import asyncio

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        rows = ev_store.find_by_user(user_id=user.id)
        assert len(rows) == 1
        assert rows[0]["consumed_at"] is None


# ─── verify-email ─────────────────────────────────────────────────────────────


class TestVerifyEmailEndpoint:
    """POST /auth/verify-email — Verify Endpoint scenarios."""

    def _register(self, client, email: str = "alice@test.io") -> dict:
        resp = client.post(
            "/auth/register",
            json={"email": email, "password": _strong_pw()},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def _extract_raw_token(self, ev_store, user_id: str) -> str:
        """We need the raw token — but the store only returns it at create
        time. Since register creates it internally, we create a fresh one
        via the store and use that for verify tests."""
        return ev_store.create(user_id=user_id)["raw_token"]

    def test_verify_success_sets_email_verified(self, client, ev_store, session_factory):
        """GIVEN a valid unconsumed non-expired token
        WHEN POST /auth/verify-email
        THEN 200 with {verified: true}, users.email_verified = TRUE,
        email_verifications.consumed_at set."""
        self._register(client)
        import asyncio

        async def _find_user():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "alice@test.io")
                return (await session.execute(stmt)).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        raw = ev_store.create(user_id=user.id)["raw_token"]

        resp = client.post(
            "/auth/verify-email",
            json={"email": "alice@test.io", "token": raw},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verified"] is True

        async def _reload():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "alice@test.io")
                u = (await session.execute(stmt)).scalar_one()
                assert u.email_verified is True
                ev_rows = (
                    await session.execute(
                        select(EmailVerification).where(
                            EmailVerification.token_hash != ""
                        )
                    )
                ).scalars().all()
                # The row we just verified should be consumed.
                consumed = [r for r in ev_rows if r.consumed_at is not None]
                assert consumed

        asyncio.get_event_loop().run_until_complete(_reload())

    def test_verify_expired_token_returns_400_token_expired(
        self, client, ev_store, session_factory
    ):
        """GIVEN a token whose expires_at < now
        WHEN POST /auth/verify-email
        THEN 400 with {error: {code: "token_expired"}}."""
        self._register(client)
        import asyncio

        async def _find_user():
            async with session_factory() as session:
                return (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        raw = ev_store.create(user_id=user.id)["raw_token"]

        async def _expire():
            async with session_factory() as session:
                await session.execute(
                    update(EmailVerification)
                    .where(EmailVerification.user_id == user.id)
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
                )
                await session.commit()

        asyncio.get_event_loop().run_until_complete(_expire())

        resp = client.post(
            "/auth/verify-email",
            json={"email": "alice@test.io", "token": raw},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "token_expired"

    def test_verify_consumed_token_returns_400_token_already_consumed(
        self, client, ev_store, session_factory
    ):
        """GIVEN a token with consumed_at set
        WHEN POST /auth/verify-email
        THEN 400 with {error: {code: "token_already_consumed"}}."""
        self._register(client)
        import asyncio

        async def _find_user():
            async with session_factory() as session:
                return (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        raw = ev_store.create(user_id=user.id)["raw_token"]
        # Consume the newest row (the one matching `raw`) directly via the store.
        newest = ev_store.find_by_user(user.id)[0]
        ev_store.consume(newest["id"])

        resp = client.post(
            "/auth/verify-email",
            json={"email": "alice@test.io", "token": raw},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "token_already_consumed"

    def test_verify_unknown_token_returns_400_invalid_token(self, client):
        """GIVEN a token not matching any hash
        WHEN POST /auth/verify-email
        THEN 400 with {error: {code: "invalid_token"}}."""
        self._register(client)
        resp = client.post(
            "/auth/verify-email",
            json={"email": "alice@test.io", "token": "completely-unknown-token-xyz"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_token"

    def test_verify_no_user_returns_400_invalid_token(self, client):
        """GIVEN an email with no user
        WHEN POST /auth/verify-email
        THEN 400 with {error: {code: "invalid_token"}} (anti-enumeration —
        same code as no-match)."""
        resp = client.post(
            "/auth/verify-email",
            json={"email": "ghost@test.io", "token": "any-token"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_token"

    def test_verify_missing_fields_returns_422(self, client):
        """GIVEN a body missing email or token
        WHEN POST /auth/verify-email
        THEN 422 Unprocessable Entity."""
        resp = client.post("/auth/verify-email", json={"email": "x@test.io"})
        assert resp.status_code == 422

    def test_verify_then_user_can_save(self, client, ev_store, session_factory):
        """GIVEN a verified user
        WHEN the user later hits a save endpoint
        THEN email_verified is TRUE in the DB (the gate will pass)."""
        self._register(client)
        import asyncio

        async def _find_user():
            async with session_factory() as session:
                return (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        raw = ev_store.create(user_id=user.id)["raw_token"]
        resp = client.post(
            "/auth/verify-email",
            json={"email": "alice@test.io", "token": raw},
        )
        assert resp.status_code == 200

        async def _reload():
            async with session_factory() as session:
                u = (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()
                assert u.email_verified is True

        asyncio.get_event_loop().run_until_complete(_reload())