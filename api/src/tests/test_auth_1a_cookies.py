"""Slice 1a — Auth cookie helpers.

Covers api-security spec: Secure Cookie Attributes.
Binding (from design.md, overrides the spec's underscore naming):
- Cookie names: ``ai-studio-auth`` / ``ai-studio-refresh`` (hyphenated)
- Both cookies: ``Secure; HttpOnly; SameSite=Lax``
- Refresh cookie: ``Path=/auth`` (NOT /auth/refresh — scopes to auth subtree)
- Access cookie: ``Path=/``

The frontend MUST NOT read token values (httpOnly).
"""

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.shared.security.cookies import clear_auth_cookies, set_auth_cookies


@pytest.fixture
def app_with_login():
    """Minimal FastAPI app that sets auth cookies on /login and clears on /logout."""
    app = FastAPI()

    @app.post("/login")
    async def login():
        resp = JSONResponse({"ok": True})
        set_auth_cookies(resp, access_jwt="access-token-value", refresh_raw="refresh-token-value")
        return resp

    @app.post("/logout")
    async def logout():
        resp = JSONResponse({"ok": True})
        clear_auth_cookies(resp)
        return resp

    return app


@pytest.fixture
def client(app_with_login):
    with TestClient(app_with_login) as c:
        yield c


class TestAccessCookieAttributes:
    """Access cookie (ai-studio-auth) MUST be Secure, HttpOnly, SameSite=Lax, Path=/."""

    def test_access_cookie_name_is_hyphenated(self, client):
        """GIVEN a login
        WHEN the Set-Cookie header is inspected
        THEN the cookie name is 'ai-studio-auth' (binding, hyphenated).
        """
        resp = client.post("/login")
        cookies = resp.headers.get_list("set-cookie")
        names = [c.split("=")[0].strip() for c in cookies]
        assert "ai-studio-auth" in names

    def test_access_cookie_has_httponly(self, client):
        resp = client.post("/login")
        access_cookie = _get_cookie(client, "ai-studio-auth")
        assert "httponly" in access_cookie.lower()

    def test_access_cookie_has_secure(self, client):
        resp = client.post("/login")
        access_cookie = _get_cookie(client, "ai-studio-auth")
        assert "secure" in access_cookie.lower()

    def test_access_cookie_has_samesite_lax(self, client):
        resp = client.post("/login")
        access_cookie = _get_cookie(client, "ai-studio-auth")
        assert "samesite=lax" in access_cookie.lower()

    def test_access_cookie_path_is_root(self, client):
        """GIVEN a login WHEN inspected THEN the access cookie Path is '/'."""
        resp = client.post("/login")
        access_cookie = _get_cookie(client, "ai-studio-auth")
        assert "path=/" in access_cookie.lower()


class TestRefreshCookieAttributes:
    """Refresh cookie (ai-studio-refresh) MUST be Secure, HttpOnly, SameSite=Lax, Path=/auth."""

    def test_refresh_cookie_name_is_hyphenated(self, client):
        resp = client.post("/login")
        cookies = resp.headers.get_list("set-cookie")
        names = [c.split("=")[0].strip() for c in cookies]
        assert "ai-studio-refresh" in names

    def test_refresh_cookie_has_httponly(self, client):
        resp = client.post("/login")
        refresh_cookie = _get_cookie(client, "ai-studio-refresh")
        assert "httponly" in refresh_cookie.lower()

    def test_refresh_cookie_has_secure(self, client):
        resp = client.post("/login")
        refresh_cookie = _get_cookie(client, "ai-studio-refresh")
        assert "secure" in refresh_cookie.lower()

    def test_refresh_cookie_has_samesite_lax(self, client):
        resp = client.post("/login")
        refresh_cookie = _get_cookie(client, "ai-studio-refresh")
        assert "samesite=lax" in refresh_cookie.lower()

    def test_refresh_cookie_path_is_auth(self, client):
        """GIVEN a login WHEN inspected THEN the refresh cookie Path is '/auth' (binding)."""
        resp = client.post("/login")
        refresh_cookie = _get_cookie(client, "ai-studio-refresh")
        assert "path=/auth" in refresh_cookie.lower()


class TestClearAuthCookies:
    """clear_auth_cookies MUST invalidate both cookies."""

    def test_clear_sets_access_cookie_to_empty(self, client):
        """GIVEN a logout
        WHEN the response is inspected
        THEN the ai-studio-auth cookie is set to empty with an expiry.
        """
        resp = client.post("/logout")
        cookies = resp.headers.get_list("set-cookie")
        access_cookie = next(
            (c for c in cookies if c.lower().startswith("ai-studio-auth=")), None
        )
        assert access_cookie is not None, f"ai-studio-auth clear cookie missing: {cookies}"
        # Empty value (the cookie is cleared, not just expired)
        assert "ai-studio-auth=" in access_cookie
        # Must include an expiry in the past to invalidate
        assert "expires=" in access_cookie.lower() or "max-age=0" in access_cookie.lower()

    def test_clear_sets_refresh_cookie_to_empty(self, client):
        """GIVEN a logout
        WHEN the response is inspected
        THEN the ai-studio-refresh cookie is set to empty with an expiry.
        """
        resp = client.post("/logout")
        cookies = resp.headers.get_list("set-cookie")
        refresh_cookie = next(
            (c for c in cookies if c.lower().startswith("ai-studio-refresh=")), None
        )
        assert refresh_cookie is not None, f"ai-studio-refresh clear cookie missing: {cookies}"
        assert "ai-studio-refresh=" in refresh_cookie
        assert "expires=" in refresh_cookie.lower() or "max-age=0" in refresh_cookie.lower()


def _get_cookie(client, name: str) -> str:
    """Extract the raw Set-Cookie header value for the given cookie name."""
    resp = client.post("/login")
    # httpx-backed TestClient uses get_list (not getlist).
    cookies = resp.headers.get_list("set-cookie")
    for c in cookies:
        if c.lower().startswith(f"{name}="):
            return c
    pytest.fail(f"Cookie '{name}' not found in Set-Cookie headers: {cookies}")