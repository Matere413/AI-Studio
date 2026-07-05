"""Auth cookie helpers — centralize Set-Cookie attributes.

Binding (from design.md — overrides the spec's underscore naming):

    Cookie               Path      Attributes
    ──────────────────── ───────── ──────────────────────────────────────
    ai-studio-auth       /         Secure; HttpOnly; SameSite=Lax
    ai-studio-refresh    /auth      Secure; HttpOnly; SameSite=Lax

The refresh cookie ``Path=/auth`` scopes it to the auth subtree so it is only
sent on ``/auth/*`` requests (not on every request). This reduces exposure
surface and matches the standard opaque-rotation pattern.

Both cookies are ``HttpOnly`` so client-side JS cannot read the token values.
``SameSite=Lax`` (not Strict) keeps email deep-links (top-level navigations)
working. ``Secure`` is always set (the API is served over HTTPS in production).
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

AUTH_COOKIE_NAME: str = "ai-studio-auth"
"""Access cookie name (binding — hyphenated)."""

REFRESH_COOKIE_NAME: str = "ai-studio-refresh"
"""Refresh cookie name (binding — hyphenated)."""

_ACCESS_COOKIE_PATH: str = "/"
_REFRESH_COOKIE_PATH: str = "/auth"
_SAME_SITE: str = "lax"
# Cookies are cleared by setting an expiry in the past. A short max-age of 0
# plus an explicit Expires header ensures immediate invalidation across
# browsers. We set both for robustness.
_CLEAR_EXPIRES: str = "Thu, 01 Jan 1970 00:00:00 GMT"


def set_auth_cookies(response: JSONResponse, access_jwt: str, refresh_raw: str) -> None:
    """Set the access + refresh auth cookies on a JSONResponse.

    Args:
        response: The FastAPI ``JSONResponse`` to attach the cookies to.
        access_jwt: The signed JWT access token (15min, Path=/).
        refresh_raw: The raw opaque refresh token (30d, Path=/auth). The raw
            value is placed in the cookie; the server stores only its hash.

    Both cookies get ``Secure; HttpOnly; SameSite=Lax``. The access cookie
    gets ``Path=/`` and the refresh cookie gets ``Path=/auth``.
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_jwt,
        path=_ACCESS_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=_SAME_SITE,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_raw,
        path=_REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=_SAME_SITE,
    )


def clear_auth_cookies(response: JSONResponse) -> None:
    """Clear (invalidate) both auth cookies on a JSONResponse.

    Sets each cookie to an empty value with an expiry in the past so the
    browser deletes it immediately. The ``Path`` must match the path the
    cookie was set with (``/`` for access, ``/auth`` for refresh).
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value="",
        path=_ACCESS_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=_SAME_SITE,
        expires=_CLEAR_EXPIRES,
        max_age=0,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value="",
        path=_REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite=_SAME_SITE,
        expires=_CLEAR_EXPIRES,
        max_age=0,
    )