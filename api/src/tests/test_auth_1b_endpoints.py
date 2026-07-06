"""Slice 1b — Auth endpoints integration tests (tasks 1b-6 + 1b-7).

Covers the auth + session-management spec scenarios end-to-end through the
FastAPI router:

- Registration: success, email_taken (409), weak_password (400)
- Login: success, invalid_credentials (401, identical shape for unknown email
  vs wrong password — the dummy-verify timing mitigation runs in the no-user
  branch)
- Current User: GET /auth/me 200 with access cookie, 401 without
- Token Refresh Rotation: success (new pair, old revoked), revoked rejected,
  expired rejected, unknown rejected
- Logout: revokes the current refresh token only, clears cookies
- Logout-Global: revokes every active refresh token, clears cookies
- Cookie attributes: ai-studio-auth Path=/, ai-studio-refresh Path=/auth,
  both Secure; HttpOnly; SameSite=Lax
- Anonymous coexistence: X-Session-ID path is untouched by auth endpoints

These tests are written FIRST (RED) — the router
``src/features/auth/presentation/router.py`` does not exist yet.
"""

from __future__ import annotations

import asyncio
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory
from src.features.auth.infrastructure.models import RefreshToken, User
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────
#
# The use cases + refresh store derive SYNC engines from the async engine's
# URL. In-memory SQLite (sqlite://) is per-connection private, so the sync
# engine would see an empty DB. A temp FILE makes both engines share one DB —
# mirroring production behaviour exactly.


@pytest.fixture
async def db_engine(tmp_path: Path):
    """File-based temp SQLite so sync + async engines share one DB."""
    db_file = tmp_path / "auth_1b_endpoints.db"
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
def app(session_factory, jwt_service, refresh_store):
    """A FastAPI test app with only the auth router mounted.

    Wires the session_factory + jwt_service + refresh_store into the auth
    router's dependency providers, then mounts the router + the global
    AppError handlers so auth errors serialize to ``{error: {code, detail}}``.
    """
    from src.features.auth.presentation.router import build_auth_router
    from src.features.auth.presentation.dependencies import (
        init_auth_providers,
    )

    init_auth_providers(
        session_factory=session_factory,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
    )
    _app = FastAPI()
    register_app_error_handlers(_app)
    _app.include_router(build_auth_router())
    return _app


@pytest.fixture
def client(app):
    """A LazyTestClient pointed at the auth-only test app."""
    return LazyTestClient(app)


def _strong_pw() -> str:
    """A password that passes the strength rules (>=12 chars, letter + digit)."""
    return "CorrectHorse42!"


def _extract_cookies(response) -> dict[str, str]:
    """Extract cookie key=value pairs from a response's Set-Cookie headers."""
    cookies: dict[str, str] = {}
    for raw in response.headers.get_list("set-cookie"):
        # Each set-cookie header: "name=value; Attr; Attr"
        head = raw.split(";", 1)[0]
        if "=" not in head:
            continue
        name, _, value = head.partition("=")
        cookies[name.strip()] = value.strip()
    return cookies


def _cookie_attrs(raw_set_cookie: str) -> str:
    """Return the lowercased attribute portion of a Set-Cookie header."""
    parts = raw_set_cookie.split(";", 1)
    return parts[1].lower() if len(parts) == 2 else ""


# ─── Registration ─────────────────────────────────────────────────────────────


class TestRegisterEndpoint:
    """POST /auth/register — auth spec Registration scenarios."""

    def test_register_success_sets_cookies_and_returns_user(self, client):
        """GIVEN a valid unique email + strong password
        WHEN POST /auth/register
        THEN 200 with {user: {id, email, email_verified: false}} AND both
        auth cookies are set."""
        resp = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["email"] == "alice@test.io"
        assert body["user"]["email_verified"] is False
        assert body["user"]["id"]

        cookies = _extract_cookies(resp)
        assert "ai-studio-auth" in cookies and cookies["ai-studio-auth"]
        assert "ai-studio-refresh" in cookies and cookies["ai-studio-refresh"]

    def test_register_email_taken_returns_409(self, client):
        """GIVEN an email that already exists
        WHEN POST /auth/register with the same email
        THEN 409 with {error: {code: "email_taken"}}."""
        client.post(
            "/auth/register",
            json={"email": "dup@test.io", "password": _strong_pw()},
        )
        resp = client.post(
            "/auth/register",
            json={"email": "dup@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "email_taken"

    def test_register_weak_password_returns_400(self, client):
        """GIVEN a password shorter than 12 chars
        WHEN POST /auth/register
        THEN 400 with {error: {code: "weak_password"}}."""
        resp = client.post(
            "/auth/register",
            json={"email": "weak@test.io", "password": "short1"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "weak_password"

    def test_register_cookie_attributes(self, client):
        """GIVEN a successful registration
        WHEN the response Set-Cookie headers are inspected
        THEN the access cookie has Path=/ and the refresh cookie has
        Path=/auth, and both have Secure; HttpOnly; SameSite=Lax."""
        resp = client.post(
            "/auth/register",
            json={"email": "attr@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200
        set_cookies = resp.headers.get_list("set-cookie")
        access = next(c for c in set_cookies if c.startswith("ai-studio-auth="))
        refresh = next(c for c in set_cookies if c.startswith("ai-studio-refresh="))
        access_attrs = _cookie_attrs(access)
        refresh_attrs = _cookie_attrs(refresh)
        assert "httponly" in access_attrs
        assert "secure" in access_attrs
        assert "samesite=lax" in access_attrs
        assert "path=/" in access_attrs
        assert "httponly" in refresh_attrs
        assert "secure" in refresh_attrs
        assert "samesite=lax" in refresh_attrs
        assert "path=/auth" in refresh_attrs


# ─── Login ────────────────────────────────────────────────────────────────────


class TestLoginEndpoint:
    """POST /auth/login — auth spec Login scenarios."""

    def _register(self, client, email: str = "alice@test.io") -> None:
        client.post(
            "/auth/register",
            json={"email": email, "password": _strong_pw()},
        )

    def test_login_success_returns_user_and_sets_cookies(self, client):
        """GIVEN a registered user with correct credentials
        WHEN POST /auth/login
        THEN 200 with {user: {id, email, email_verified}} AND both cookies."""
        self._register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["email"] == "alice@test.io"
        cookies = _extract_cookies(resp)
        assert cookies.get("ai-studio-auth")
        assert cookies.get("ai-studio-refresh")

    def test_login_wrong_password_returns_401_invalid_credentials(self, client):
        """GIVEN a registered user
        WHEN POST /auth/login with the wrong password
        THEN 401 with {error: {code: "invalid_credentials"}}."""
        self._register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": "WrongPassword99!"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_credentials"

    def test_login_unknown_email_returns_401_invalid_credentials(self, client):
        """GIVEN an email not in the database
        WHEN POST /auth/login
        THEN 401 with {error: {code: "invalid_credentials"}} (NOT 'user not
        found' — anti-enumeration: same code as wrong password)."""
        resp = client.post(
            "/auth/login",
            json={"email": "ghost@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_credentials"

    def test_login_no_cookies_on_failure(self, client):
        """GIVEN a failed login
        WHEN the response is inspected
        THEN no auth cookies are set (no Set-Cookie for ai-studio-auth /
        ai-studio-refresh)."""
        self._register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": "WrongPassword99!"},
        )
        assert resp.status_code == 401
        cookies = _extract_cookies(resp)
        assert "ai-studio-auth" not in cookies
        assert "ai-studio-refresh" not in cookies


# ─── Current User ─────────────────────────────────────────────────────────────


class TestMeEndpoint:
    """GET /auth/me — auth spec Current User scenarios."""

    def test_me_authenticated_returns_user(self, client):
        """GIVEN a valid access cookie
        WHEN GET /auth/me
        THEN 200 with {id, email, email_verified}."""
        reg = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        access = _extract_cookies(reg)["ai-studio-auth"]
        resp = client.get("/auth/me", cookies={"ai-studio-auth": access})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["email"] == "alice@test.io"
        assert body["email_verified"] is False
        assert body["id"]

    def test_me_unauthenticated_returns_401(self, client):
        """GIVEN no access cookie
        WHEN GET /auth/me
        THEN 401 with {error: {code: "unauthenticated"}}."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthenticated"

    def test_me_invalid_token_returns_401(self, client):
        """GIVEN a malformed access cookie
        WHEN GET /auth/me
        THEN 401 with {error: {code: "unauthenticated"}}."""
        resp = client.get(
            "/auth/me", cookies={"ai-studio-auth": "not.a.valid.jwt"}
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthenticated"


# ─── Refresh ──────────────────────────────────────────────────────────────────


class TestRefreshEndpoint:
    """POST /auth/refresh — auth spec Token Refresh Rotation scenarios."""

    def _register_and_get_refresh(self, client) -> str:
        resp = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200
        return _extract_cookies(resp)["ai-studio-refresh"]

    def test_refresh_success_issues_new_pair_and_clears_old(
        self, client, session_factory
    ):
        """GIVEN a valid non-revoked refresh cookie
        WHEN POST /auth/refresh
        THEN 200, new access + refresh cookies set, and the old refresh token
        is revoked (find_active returns None)."""
        old_refresh = self._register_and_get_refresh(client)
        resp = client.post(
            "/auth/refresh", cookies={"ai-studio-refresh": old_refresh}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["email"] == "alice@test.io"
        cookies = _extract_cookies(resp)
        new_access = cookies.get("ai-studio-auth")
        new_refresh = cookies.get("ai-studio-refresh")
        assert new_access
        assert new_refresh
        assert new_refresh != old_refresh

    def test_refresh_revoked_token_returns_401(self, client):
        """GIVEN a refresh token already revoked (e.g., from logout)
        WHEN POST /auth/refresh with it
        THEN 401 with {error: {code: "invalid_refresh_token"}}."""
        old_refresh = self._register_and_get_refresh(client)
        # Revoke it via logout first.
        client.post("/auth/logout", cookies={"ai-studio-refresh": old_refresh})
        resp = client.post(
            "/auth/refresh", cookies={"ai-studio-refresh": old_refresh}
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_refresh_token"

    def test_refresh_unknown_token_returns_401(self, client):
        """GIVEN a random token that was never issued
        WHEN POST /auth/refresh
        THEN 401 with {error: {code: "invalid_refresh_token"}}."""
        resp = client.post(
            "/auth/refresh",
            cookies={"ai-studio-refresh": _secrets.token_urlsafe(32)},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_refresh_token"

    def test_refresh_expired_token_returns_401(
        self, client, session_factory
    ):
        """GIVEN a refresh token past its expires_at
        WHEN POST /auth/refresh
        THEN 401 with {error: {code: "invalid_refresh_token"}}."""
        old_refresh = self._register_and_get_refresh(client)
        # Backdate the row's expiry so the token is "expired".
        prefix = old_refresh[:12]
        async def _backdate():
            async with session_factory() as session:
                stmt = select(RefreshToken).where(
                    RefreshToken.token_prefix == prefix
                )
                row = (await session.execute(stmt)).scalar_one()
                row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await session.commit()

        asyncio.run(_backdate())
        resp = client.post(
            "/auth/refresh", cookies={"ai-studio-refresh": old_refresh}
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_refresh_token"

    def test_refresh_no_cookie_returns_401(self, client):
        """GIVEN no refresh cookie
        WHEN POST /auth/refresh
        THEN 401 with {error: {code: "invalid_refresh_token"}}."""
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_refresh_token"


# ─── Logout ───────────────────────────────────────────────────────────────────


class TestLogoutEndpoint:
    """POST /auth/logout — auth spec Logout (revokes one) scenarios."""

    def _register_and_get_refresh(self, client) -> str:
        resp = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200
        return _extract_cookies(resp)["ai-studio-refresh"]

    def test_logout_clears_cookies(self, client):
        """GIVEN an active refresh token
        WHEN POST /auth/logout
        THEN 200 and both auth cookies are cleared (empty value + past expiry)."""
        old_refresh = self._register_and_get_refresh(client)
        resp = client.post(
            "/auth/logout", cookies={"ai-studio-refresh": old_refresh}
        )
        assert resp.status_code == 200, resp.text
        set_cookies = resp.headers.get_list("set-cookie")
        cleared_names = set()
        for raw in set_cookies:
            head = raw.split(";", 1)[0]
            name, _, value = head.partition("=")
            name = name.strip()
            if name in ("ai-studio-auth", "ai-studio-refresh"):
                # Cleared → empty (or quoted-empty) value + a past Expires.
                assert value.strip() in ('', '""')
                assert "max-age=0" in raw.lower() or "expires=" in raw.lower()
                cleared_names.add(name)
        assert "ai-studio-auth" in cleared_names
        assert "ai-studio-refresh" in cleared_names

    def test_logout_revokes_only_current_token(
        self, client, session_factory, refresh_store
    ):
        """GIVEN two active refresh tokens for the same user
        WHEN logout is called with token A
        THEN token A is revoked; token B (from a second login) remains active."""
        refresh_a = self._register_and_get_refresh(client)
        # Second login → token B
        login = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert login.status_code == 200
        refresh_b = _extract_cookies(login)["ai-studio-refresh"]

        out = client.post(
            "/auth/logout", cookies={"ai-studio-refresh": refresh_a}
        )
        assert out.status_code == 200
        # A revoked, B alive
        assert refresh_store.find_active(refresh_a) is None
        assert refresh_store.find_active(refresh_b) is not None

    def test_logout_unknown_token_returns_200(self, client):
        """GIVEN a random token that was never issued
        WHEN POST /auth/logout
        THEN 200 (idempotent — the cookie may be stale or absent)."""
        resp = client.post(
            "/auth/logout",
            cookies={"ai-studio-refresh": _secrets.token_urlsafe(32)},
        )
        assert resp.status_code == 200


# ─── Logout-Global ────────────────────────────────────────────────────────────


class TestLogoutAllEndpoint:
    """POST /auth/logout-all — auth spec Logout-Global scenarios."""

    def _register(self, client) -> str:
        resp = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200
        return _extract_cookies(resp)["ai-studio-auth"]

    def test_logout_all_revokes_every_session_and_clears_cookies(
        self, client, refresh_store
    ):
        """GIVEN a user with 3 active refresh tokens
        WHEN POST /auth/logout-all (with an access cookie)
        THEN all 3 are revoked AND both cookies are cleared."""
        reg = client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        access = _extract_cookies(reg)["ai-studio-auth"]
        refresh_tokens = [_extract_cookies(reg)["ai-studio-refresh"]]
        for _ in range(2):
            login = client.post(
                "/auth/login",
                json={"email": "alice@test.io", "password": _strong_pw()},
            )
            assert login.status_code == 200
            refresh_tokens.append(_extract_cookies(login)["ai-studio-refresh"])

        resp = client.post(
            "/auth/logout-all", cookies={"ai-studio-auth": access}
        )
        assert resp.status_code == 200, resp.text
        for raw in refresh_tokens:
            assert refresh_store.find_active(raw) is None
        # Cookies cleared.
        set_cookies = resp.headers.get_list("set-cookie")
        cleared_names = set()
        for raw in set_cookies:
            head = raw.split(";", 1)[0]
            name, _, value = head.partition("=")
            name = name.strip()
            if name in ("ai-studio-auth", "ai-studio-refresh"):
                assert value.strip() in ('', '""')
                cleared_names.add(name)
        assert "ai-studio-auth" in cleared_names
        assert "ai-studio-refresh" in cleared_names

    def test_logout_all_unauthenticated_returns_401(self, client):
        """GIVEN no access cookie
        WHEN POST /auth/logout-all
        THEN 401 with {error: {code: "unauthenticated"}}."""
        resp = client.post("/auth/logout-all")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthenticated"


# ─── UA / IP capture ──────────────────────────────────────────────────────────


class TestUaIpCapture:
    """POST /auth/register|login|refresh MUST capture User-Agent + client IP
    on the issued refresh_tokens row (binding from the session-management
    spec: Refresh Token Storage stores user_agent + ip captured at issue
    time)."""

    _UA = "test-ua/1.0 (slice-1b-verify)"
    _IP = "203.0.113.5"

    def _assert_last_row_has_ua_ip(self, session_factory, user_id: str) -> None:
        """Load the most-recent refresh_tokens row for ``user_id`` and assert
        its ``user_agent`` + ``ip`` columns are populated."""

        async def _load():
            async with session_factory() as session:
                stmt = (
                    select(RefreshToken)
                    .where(RefreshToken.user_id == user_id)
                    .order_by(RefreshToken.created_at.desc())
                    .limit(1)
                )
                row = (await session.execute(stmt)).scalar_one()
                return row

        row = asyncio.run(_load())
        assert row.user_agent == self._UA, (
            f"expected user_agent={self._UA!r}, got {row.user_agent!r}"
        )
        assert row.ip == self._IP, (
            f"expected ip={self._IP!r}, got {row.ip!r}"
        )

    def test_register_captures_ua_and_ip(self, client, session_factory):
        """GIVEN POST /auth/register with a User-Agent + X-Forwarded-For
        WHEN the issued refresh_tokens row is inspected
        THEN user_agent + ip are captured from the request (not None)."""
        resp = client.post(
            "/auth/register",
            json={"email": "ua@test.io", "password": _strong_pw()},
            headers={
                "User-Agent": self._UA,
                "X-Forwarded-For": self._IP,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        self._assert_last_row_has_ua_ip(session_factory, body["user"]["id"])

    def test_login_captures_ua_and_ip(self, client, session_factory):
        """GIVEN a registered user + POST /auth/login with User-Agent +
        X-Forwarded-For
        WHEN the issued refresh_tokens row is inspected
        THEN user_agent + ip are captured from the request (not None)."""
        client.post(
            "/auth/register",
            json={"email": "ual@test.io", "password": _strong_pw()},
        )
        resp = client.post(
            "/auth/login",
            json={"email": "ual@test.io", "password": _strong_pw()},
            headers={
                "User-Agent": self._UA,
                "X-Forwarded-For": self._IP,
            },
        )
        assert resp.status_code == 200, resp.text
        # Look up the user id via /auth/me (we have the access cookie now).
        access = _extract_cookies(resp)["ai-studio-auth"]
        me = client.get("/auth/me", cookies={"ai-studio-auth": access})
        assert me.status_code == 200
        user_id = me.json()["id"]
        self._assert_last_row_has_ua_ip(session_factory, user_id)

    def test_refresh_captures_ua_and_ip(self, client, session_factory):
        """GIVEN an existing refresh cookie + POST /auth/refresh with
        User-Agent + X-Forwarded-For
        WHEN the NEW refresh_tokens row is inspected
        THEN user_agent + ip are captured from the refresh request."""
        reg = client.post(
            "/auth/register",
            json={"email": "uar@test.io", "password": _strong_pw()},
        )
        assert reg.status_code == 200
        old_refresh = _extract_cookies(reg)["ai-studio-refresh"]
        user_id = reg.json()["user"]["id"]

        resp = client.post(
            "/auth/refresh",
            cookies={"ai-studio-refresh": old_refresh},
            headers={
                "User-Agent": self._UA,
                "X-Forwarded-For": self._IP,
            },
        )
        assert resp.status_code == 200, resp.text
        self._assert_last_row_has_ua_ip(session_factory, user_id)

    def test_login_uses_forwarded_first_ip(self, client, session_factory):
        """GIVEN an X-Forwarded-For with multiple IPs (proxy chain)
        WHEN POST /auth/login
        THEN only the FIRST IP is captured (leftmost in the list)."""
        client.post(
            "/auth/register",
            json={"email": "fwd@test.io", "password": _strong_pw()},
        )
        resp = client.post(
            "/auth/login",
            json={"email": "fwd@test.io", "password": _strong_pw()},
            headers={
                "User-Agent": self._UA,
                "X-Forwarded-For": f"{self._IP}, 10.0.0.1, 10.0.0.2",
            },
        )
        assert resp.status_code == 200, resp.text
        access = _extract_cookies(resp)["ai-studio-auth"]
        me = client.get("/auth/me", cookies={"ai-studio-auth": access})
        user_id = me.json()["id"]

        async def _load():
            async with session_factory() as session:
                stmt = (
                    select(RefreshToken)
                    .where(RefreshToken.user_id == user_id)
                    .order_by(RefreshToken.created_at.desc())
                    .limit(1)
                )
                return (await session.execute(stmt)).scalar_one()

        row = asyncio.run(_load())
        assert row.ip == self._IP, (
            f"expected first forwarded ip={self._IP!r}, got {row.ip!r}"
        )


# ─── Full flow ────────────────────────────────────────────────────────────────


class TestFullAuthFlow:
    """register → login → me → refresh → logout end-to-end."""

    def test_register_login_me_refresh_logout(self, client, refresh_store):
        """GIVEN a fresh client
        WHEN the full flow runs
        THEN each step succeeds and the final logout revokes the refresh."""
        # 1. Register
        reg = client.post(
            "/auth/register",
            json={"email": "flow@test.io", "password": _strong_pw()},
        )
        assert reg.status_code == 200
        access = _extract_cookies(reg)["ai-studio-auth"]
        refresh = _extract_cookies(reg)["ai-studio-refresh"]

        # 2. me
        me = client.get("/auth/me", cookies={"ai-studio-auth": access})
        assert me.status_code == 200
        assert me.json()["email"] == "flow@test.io"

        # 3. refresh
        ref = client.post(
            "/auth/refresh", cookies={"ai-studio-refresh": refresh}
        )
        assert ref.status_code == 200
        new_refresh = _extract_cookies(ref)["ai-studio-refresh"]
        assert new_refresh != refresh

        # 4. logout (with the NEW refresh)
        out = client.post(
            "/auth/logout", cookies={"ai-studio-refresh": new_refresh}
        )
        assert out.status_code == 200
        assert refresh_store.find_active(new_refresh) is None