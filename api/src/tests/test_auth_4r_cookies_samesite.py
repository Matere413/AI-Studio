"""4R corrective pass — CRITICAL 3: configurable SameSite for cross-origin.

Cross-site fetch does not send ``SameSite=Lax`` cookies, so auth breaks in
cross-origin production (the frontend on one origin, the Modal backend on
another). The cookie SameSite attribute MUST be configurable via the
``COOKIE_SAMESITE`` environment variable:

- default (unset / ``lax``) → ``SameSite=Lax`` (the safe default)
- ``none`` → ``SameSite=None; Secure`` (cross-origin production opt-in)

The existing slice 1a cookie tests assert ``SameSite=Lax`` by default —
they continue to pass. These tests cover the opt-in ``none`` path.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.shared.security.cookies import (
    clear_auth_cookies,
    set_auth_cookies,
    _resolve_samesite,
)


def _get_cookie(resp, name: str) -> str:
    for c in resp.headers.get_list("set-cookie"):
        if c.lower().startswith(f"{name}="):
            return c
    pytest.fail(f"Cookie '{name}' not found")


class TestResolveSameSite:
    """``_resolve_samesite()`` reads the env + returns the right value."""

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
        assert _resolve_samesite() == "lax"

    def test_explicit_lax(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SAMESITE", "lax")
        assert _resolve_samesite() == "lax"

    def test_none_opt_in(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SAMESITE", "none")
        assert _resolve_samesite() == "none"

    def test_unknown_falls_back_to_lax(self, monkeypatch):
        # Defensive — an unrecognized value MUST NOT produce "none" (the
        # insecure cross-origin mode). It falls back to the safe default.
        monkeypatch.setenv("COOKIE_SAMESITE", "bogus")
        assert _resolve_samesite() == "lax"

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SAMESITE", "NONE")
        assert _resolve_samesite() == "none"


class TestSetAuthCookiesSameSiteConfigurable:
    """``set_auth_cookies`` honours ``COOKIE_SAMESITE``."""

    def test_default_emits_samesite_lax(self, monkeypatch):
        monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
        app = FastAPI()

        @app.post("/login")
        async def login():
            resp = JSONResponse({"ok": True})
            set_auth_cookies(resp, "a", "r")
            return resp

        with TestClient(app) as c:
            resp = c.post("/login")
            access = _get_cookie(resp, "ai-studio-auth")
            assert "samesite=lax" in access.lower()
            assert "samesite=none" not in access.lower()

    def test_none_emits_samesite_none_with_secure(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SAMESITE", "none")
        app = FastAPI()

        @app.post("/login")
        async def login():
            resp = JSONResponse({"ok": True})
            set_auth_cookies(resp, "a", "r")
            return resp

        with TestClient(app) as c:
            resp = c.post("/login")
            access = _get_cookie(resp, "ai-studio-auth")
            refresh = _get_cookie(resp, "ai-studio-refresh")
            # SameSite=None MUST be present (case-insensitive)
            assert "samesite=none" in access.lower()
            assert "samesite=none" in refresh.lower()
            # Secure is ALWAYS present (None requires Secure per RFC 6265bis)
            assert "secure" in access.lower()
            assert "secure" in refresh.lower()

    def test_clear_cookies_also_honours_samesite_none(self, monkeypatch):
        """Clearing cookies MUST set the same SameSite as setting them, so
        the browser deletes the cookie (a SameSite mismatch on the clear
        would leave the stale cookie in place)."""
        monkeypatch.setenv("COOKIE_SAMESITE", "none")
        app = FastAPI()

        @app.post("/logout")
        async def logout():
            resp = JSONResponse({"ok": True})
            clear_auth_cookies(resp)
            return resp

        with TestClient(app) as c:
            resp = c.post("/logout")
            access = _get_cookie(resp, "ai-studio-auth")
            assert "samesite=none" in access.lower()