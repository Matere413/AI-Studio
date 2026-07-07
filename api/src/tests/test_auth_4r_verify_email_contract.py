"""4R corrective pass — CRITICAL 2: verify-email response contract.

The frontend ``verifyEmail()`` expects ``{user}`` in the response so it
can update the auth context; the backend returned only ``{verified: true}``,
so a successful verification was treated as a failure on the client.

Spec: the verify-email endpoint MUST return ``{verified: true, user:
{id, email, email_verified}}`` so the frontend can hydrate its auth
state without a second ``GET /auth/me`` round-trip.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.email_client import DevEmailClient
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures (self-contained — mirrors test_auth_2_verify_email) ──────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_4r_verify_contract.db"
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
def app(session_factory, jwt_service, refresh_store, ev_store, email_client):
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


class TestVerifyEmailContractReturnsUser:
    """POST /auth/verify-email MUST return ``{verified, user}``."""

    def test_verify_success_response_includes_user(self, client, ev_store, session_factory):
        """GIVEN a valid unconsumed non-expired token
        WHEN POST /auth/verify-email
        THEN 200 with {verified: true, user: {id, email, email_verified}}."""
        # Register via the endpoint so the user exists + a verification row
        # is triggered (register_user mints a token + sends via DevEmailClient).
        client.post(
            "/auth/register",
            json={"email": "carol@test.io", "password": "CorrectHorse42!"},
        )

        # Pull the raw token from the store (DevEmailClient logged it; we
        # reconstruct via the DB row's id + a fresh mint is not needed —
        # instead we mint directly via the store for determinism).
        async def _find_user():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "carol@test.io")
                return (await session.execute(stmt)).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        raw = ev_store.create(user_id=user.id)["raw_token"]

        resp = client.post(
            "/auth/verify-email",
            json={"email": "carol@test.io", "token": raw},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # CRITICAL 2 contract: {verified: true, user: {...}}
        assert body["verified"] is True
        assert "user" in body, "verify-email response MUST include a user object"
        user_obj = body["user"]
        assert user_obj["id"] == user.id
        assert user_obj["email"] == "carol@test.io"
        assert user_obj["email_verified"] is True

    def test_verify_user_object_email_verified_is_true_post_verify(
        self, client, ev_store, session_factory
    ):
        """GIVEN a user whose email_verified was False
        WHEN POST /auth/verify-email succeeds
        THEN the returned user.email_verified is True (not the stale False)."""
        client.post(
            "/auth/register",
            json={"email": "dave@test.io", "password": "CorrectHorse42!"},
        )

        async def _find_user():
            async with session_factory() as session:
                stmt = select(User).where(User.email == "dave@test.io")
                return (await session.execute(stmt)).scalar_one()

        user = asyncio.get_event_loop().run_until_complete(_find_user())
        assert user.email_verified is False  # precondition
        raw = ev_store.create(user_id=user.id)["raw_token"]

        resp = client.post(
            "/auth/verify-email",
            json={"email": "dave@test.io", "token": raw},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user"]["email_verified"] is True