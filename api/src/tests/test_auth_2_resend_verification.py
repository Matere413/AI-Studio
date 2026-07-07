"""Slice 2 — resend-verification endpoint (tasks 2-3 + 2-4).

Spec: email-verification — Resend Verification.

``POST /auth/resend-verification`` requires an authenticated user.
- When already verified → ``400 already_verified``.
- Otherwise creates a new ``email_verifications`` row (new token, 24h
  expiry) and sends the email.

Rate limiting is deferred to slice 4; this slice implements the endpoint
without the 429 gate.

These tests are written FIRST (RED) — the endpoint does not exist yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.email_client import DevEmailClient
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import EmailVerification, User
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_resend.db"
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


def _extract_cookies(response) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for raw in response.headers.get_list("set-cookie"):
        head = raw.split(";", 1)[0]
        if "=" not in head:
            continue
        name, _, value = head.partition("=")
        cookies[name.strip()] = value.strip()
    return cookies


# ─── resend-verification ──────────────────────────────────────────────────────


class TestResendVerificationEndpoint:
    """POST /auth/resend-verification — Resend Verification scenarios."""

    def _register(self, client, email: str = "alice@test.io") -> dict:
        resp = client.post(
            "/auth/register",
            json={"email": email, "password": _strong_pw()},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_resend_unauthenticated_returns_401(self, client):
        """GIVEN no access cookie
        WHEN POST /auth/resend-verification
        THEN 401 with {error: {code: "unauthenticated"}}."""
        resp = client.post("/auth/resend-verification")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthenticated"

    def test_resend_already_verified_returns_400_already_verified(
        self, client, ev_store, session_factory
    ):
        """GIVEN a user with email_verified=TRUE
        WHEN POST /auth/resend-verification
        THEN 400 with {error: {code: "already_verified"}}."""
        self._register(client)
        cookies = _extract_cookies(
            client.post(
                "/auth/login",
                json={"email": "alice@test.io", "password": _strong_pw()},
            )
        )
        access = cookies["ai-studio-auth"]

        # Mark the user as verified directly.
        import asyncio

        async def _verify_user():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "alice@test.io")
                u = (await session.execute(stmt)).scalar_one()
                u.email_verified = True
                await session.commit()

        asyncio.get_event_loop().run_until_complete(_verify_user())

        resp = client.post(
            "/auth/resend-verification", cookies={"ai-studio-auth": access}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "already_verified"

    def test_resend_creates_new_verification_row_and_sends_email(
        self, client, ev_store, session_factory
    ):
        """GIVEN an unverified authenticated user
        WHEN POST /auth/resend-verification
        THEN a new email_verifications row is created + email sent."""
        self._register(client)
        cookies = _extract_cookies(
            client.post(
                "/auth/login",
                json={"email": "alice@test.io", "password": _strong_pw()},
            )
        )
        access = cookies["ai-studio-auth"]

        # Count rows before
        import asyncio

        async def _find_user():
            async with session_factory() as session:
                return (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        before = len(ev_store.find_by_user(user_id=user.id))

        resp = client.post(
            "/auth/resend-verification", cookies={"ai-studio-auth": access}
        )
        assert resp.status_code == 200, resp.text
        after = len(ev_store.find_by_user(user_id=user.id))
        assert after == before + 1
        # The new row should be unconsumed + 24h expiry.
        rows = ev_store.find_by_user(user_id=user.id)
        newest = rows[0]
        assert newest["consumed_at"] is None