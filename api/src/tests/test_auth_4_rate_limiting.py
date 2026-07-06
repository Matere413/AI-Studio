"""Slice 4 — Rate limiting on auth endpoints (task 4-1 + 4-5).

Covers the ``api-security`` Rate Limiting requirement:

- POST /auth/login         — 5 attempts/min per IP + per email
- POST /auth/register      — 3/min per IP
- POST /auth/verify-email  — 5/min per IP
- POST /auth/resend-verification — 3/min per user

When the limit is exceeded the response MUST be ``429`` with the body
``{"error": {"code": "rate_limited"}}`` and a ``Retry-After`` header.

These tests are written FIRST (RED). The rate limiter module
``src/shared/rate_limit.py`` does not exist yet, and the router does not
enforce any limits — so every "Nth request returns 429" assertion fails
until both are implemented.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi import FastAPI

from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory
from src.features.auth.infrastructure.models import RefreshToken, User
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.infrastructure.email_client import DevEmailClient
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────
#
# Note: the rate limiter is reset before every test by the autouse fixture in
# ``api/conftest.py`` (the global reset). Each test in this file therefore
# starts with empty buckets — the "6th request → 429" assertions are not
# contaminated by previous tests' counts.


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_4_rate_limit.db"
    from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

    engine = _create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
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
    """Auth-only test app with the global error handlers + rate-limited router."""
    from src.features.auth.presentation.router import build_auth_router
    from src.features.auth.presentation.dependencies import (
        init_auth_providers,
    )

    init_auth_providers(
        session_factory=session_factory,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        email_verification_store=ev_store,
        email_client=email_client,
    )
    _app = FastAPI()
    register_app_error_handlers(_app)
    _app.include_router(build_auth_router())
    return _app


@pytest.fixture
def client(app):
    return LazyTestClient(app)


def _strong_pw() -> str:
    return "CorrectHorse42!"


def _login_body(email: str, password: str = _strong_pw()) -> dict:
    return {"email": email, "password": password}


# ─── Login: 5/min per IP + per email ───────────────────────────────────────────


class TestLoginRateLimit:
    """POST /auth/login — 5 attempts/min per IP + per email.

    Per the spec, both the IP bucket and the email bucket are enforced.
    We verify the 6th request from one IP returns 429 rate_limited, and
    that exceeding the per-email bucket (different IPs) also returns 429.
    """

    def test_first_five_logins_from_one_ip_succeed_then_sixth_is_rate_limited(
        self, client
    ):
        """GIVEN the same IP sends 5 login attempts for the same email
        WHEN the 6th attempt arrives within the window
        THEN it returns 429 with {error: {code: "rate_limited"}} and Retry-After."""
        email = "ratelimit-login@example.com"
        # 5 attempts — all 401 invalid_credentials (wrong password is fine;
        # the limiter counts attempts, not successes). The IP bucket is 5.
        for i in range(5):
            resp = client.post(
                "/auth/login",
                json=_login_body(email, "WrongPassword1!"),
                headers={"x-forwarded-for": "203.0.113.1"},
            )
            assert resp.status_code == 401, f"attempt {i+1} should be 401 (wrong pw)"

        # 6th attempt from the same IP → 429
        resp = client.post(
            "/auth/login",
            json=_login_body(email, "WrongPassword1!"),
            headers={"x-forwarded-for": "203.0.113.1"},
        )
        assert resp.status_code == 429, "6th login from same IP MUST be 429"
        body = resp.json()
        assert body["error"]["code"] == "rate_limited"
        header_names = {k.lower() for k in resp.headers.keys()}
        assert "retry-after" in header_names, (
            "rate_limited response MUST include a Retry-After header"
        )

    def test_per_email_bucket_limits_across_different_ips(self, client):
        """GIVEN 5 login attempts for the same email from different IPs
        WHEN the 6th attempt for that email arrives
        THEN it returns 429 (the per-email bucket is exhausted)."""
        email = "email-bucket@example.com"
        for i in range(5):
            resp = client.post(
                "/auth/login",
                json=_login_body(email, "WrongPassword1!"),
                headers={"x-forwarded-for": f"203.0.113.{10 + i}"},
            )
            assert resp.status_code == 401, f"attempt {i+1} should be 401"

        # 6th from a NEW IP — still 429 because the email bucket is exhausted
        resp = client.post(
            "/auth/login",
            json=_login_body(email, "WrongPassword1!"),
            headers={"x-forwarded-for": "203.0.113.99"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"

    def test_different_emails_under_same_ip_share_the_ip_bucket(self, client):
        """GIVEN 5 login attempts for 5 different emails from one IP
        WHEN the 6th attempt (a 6th email) arrives from that IP
        THEN it returns 429 (the per-IP bucket is exhausted even though
        each email bucket has room)."""
        for i in range(5):
            resp = client.post(
                "/auth/login",
                json=_login_body(f"ip-bucket-{i}@example.com", "WrongPassword1!"),
                headers={"x-forwarded-for": "203.0.113.200"},
            )
            assert resp.status_code == 401, f"attempt {i+1} should be 401"

        resp = client.post(
            "/auth/login",
            json=_login_body("ip-bucket-6@example.com", "WrongPassword1!"),
            headers={"x-forwarded-for": "203.0.113.200"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"


# ─── Register: 3/min per IP ────────────────────────────────────────────────────


class TestRegisterRateLimit:
    """POST /auth/register — 3 per minute per IP.

    The IP bucket is shared across all emails from that IP.
    """

    def test_fourth_register_from_one_ip_is_rate_limited(self, client):
        for i in range(3):
            resp = client.post(
                "/auth/register",
                json=_login_body(f"reg-{i}@example.com"),
                headers={"x-forwarded-for": "198.51.100.1"},
            )
            # 200 on first register; 409 on duplicate emails — but here each
            # email is unique so all 3 succeed.
            assert resp.status_code == 200, f"attempt {i+1} should be 200"

        # 4th from the same IP → 429
        resp = client.post(
            "/auth/register",
            json=_login_body("reg-4@example.com"),
            headers={"x-forwarded-for": "198.51.100.1"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"
        header_names = {k.lower() for k in resp.headers.keys()}
        assert "retry-after" in header_names


# ─── Verify-email: 5/min per IP ───────────────────────────────────────────────


class TestVerifyEmailRateLimit:
    """POST /auth/verify-email — 5 per minute per IP.

    The verify endpoint is unauthenticated (the user may not be logged in
    when clicking the email link), so the limit is per-IP only.
    """

    def test_sixth_verify_email_from_one_ip_is_rate_limited(self, client):
        body = {"email": "verify-rl@example.com", "token": "any-token-value"}
        for i in range(5):
            resp = client.post(
                "/auth/verify-email",
                json=body,
                headers={"x-forwarded-for": "192.0.2.1"},
            )
            # All 5 are 400 invalid_token (no such user / token) — but counted.
            assert resp.status_code == 400, f"attempt {i+1} should be 400"

        resp = client.post(
            "/auth/verify-email",
            json=body,
            headers={"x-forwarded-for": "192.0.2.1"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"


# ─── Resend-verification: 3/min per user ──────────────────────────────────────


class TestResendVerificationRateLimit:
    """POST /auth/resend-verification — 3 per minute per user.

    The endpoint requires an authenticated user (access cookie). The limit
    is per-user (user_id), NOT per-IP — a NAT'd office sharing one IP should
    not starve each other.
    """

    def test_fourth_resend_from_one_user_is_rate_limited(
        self, client, session_factory, jwt_service
    ):
        # Register + issue an access cookie. The user is unverified so
        # resend is allowed (returns 200).
        reg = client.post(
            "/auth/register",
            json=_login_body("resend-rl@example.com"),
            headers={"x-forwarded-for": "203.0.113.50"},
        )
        assert reg.status_code == 200
        access_cookie = reg.headers.get_list("set-cookie")[0]
        # Extract just the cookie pair (name=value)
        cookie_pair = access_cookie.split(";", 1)[0]
        assert cookie_pair.startswith("ai-studio-auth=")

        for i in range(3):
            resp = client.post(
                "/auth/resend-verification",
                headers={
                    "cookie": cookie_pair,
                    "x-forwarded-for": "203.0.113.51",
                },
            )
            assert resp.status_code == 200, f"resend {i+1} should be 200"

        # 4th resend from the same user → 429
        resp = client.post(
            "/auth/resend-verification",
            headers={
                "cookie": cookie_pair,
                "x-forwarded-for": "203.0.113.51",
            },
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"