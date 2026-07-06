"""Auth FastAPI router — the HTTP boundary for the auth feature.

Endpoints (binding paths — hyphenated, ``logout-all`` per the spec):

    POST /auth/register      — create account, issue tokens, set cookies
    POST /auth/login         — verify credentials, issue tokens, set cookies
    POST /auth/logout        — revoke current refresh token, clear cookies
    POST /auth/logout-all    — revoke every active refresh token, clear cookies
    POST /auth/refresh       — rotate: revoke old, issue new pair, set cookies
    GET  /auth/me            — return the authenticated user's state

Cookie placement is centralised in :mod:`src.shared.security.cookies`
(``ai-studio-auth`` Path=/, ``ai-studio-refresh`` Path=/auth, both
``Secure; HttpOnly; SameSite=Lax``).

The use cases in :mod:`src.features.auth.application.use_cases` are SYNC
(argon2id + row-count work are CPU-bound). Endpoints offload them to a
thread via :func:`asyncio.to_thread` so they do not block the event loop.

Anonymous coexistence: the auth router does NOT touch the ``X-Session-ID``
header or its cookie. Auth is purely additive — the existing generation
endpoints keep working unchanged.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.features.auth.application.use_cases import (
    AuthSession,
    login_user,
    logout,
    logout_all,
    refresh_session,
    register_user,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.presentation.dependencies import (
    CurrentUser,
    get_current_user,
    get_jwt_service,
    get_refresh_store,
    get_session_factory,
)
from src.shared.errors_auth import InvalidRefreshTokenError
from src.shared.security.cookies import (
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    set_auth_cookies,
)


# ─── Request bodies ───────────────────────────────────────────────────────────


class _CredentialsBody(BaseModel):
    """Shared body for register + login: an email + a password.

    The email is validated as a non-empty string (max 254 per RFC 5321) —
    we do NOT use ``EmailStr`` here to avoid pulling in the ``email-
    validator`` runtime dependency. Deeper email shape validation is the
    use case / domain layer's job; the router only enforces presence +
    length so FastAPI returns a clean 422 on malformed bodies.
    """

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


# ─── Response shaping ─────────────────────────────────────────────────────────


def _user_dict(user: CurrentUser) -> dict:
    """Shape a CurrentUser into the public user object."""
    return {
        "id": user.id,
        "email": user.email,
        "email_verified": bool(user.email_verified),
    }


def _auth_response(session: AuthSession) -> JSONResponse:
    """Build a 200 JSONResponse with the user + both auth cookies set."""
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"user": _user_dict(session.user)},
    )
    set_auth_cookies(response, session.access_jwt, session.refresh_raw)
    return response


# ─── Router ───────────────────────────────────────────────────────────────────


def build_auth_router() -> APIRouter:
    """Construct the auth router with all six endpoints.

    The router is built by a factory (not module-level) so the test fixture
    can mount a fresh instance per test app. The dependency providers
    (session_factory / jwt_service / refresh_store) are resolved via
    ``Depends`` from the module-level provider singletons wired by
    :func:`init_auth_providers`.
    """
    router = APIRouter(prefix="/auth", tags=["auth"])

    # ── POST /auth/register ─────────────────────────────────────────────────
    @router.post("/register", summary="Register a new account")
    async def register(
        body: _CredentialsBody,
        session_factory=Depends(get_session_factory),
        jwt_service: JWTService = Depends(get_jwt_service),
        refresh_store: RefreshTokenStore = Depends(get_refresh_store),
    ) -> JSONResponse:
        """Create a new user account and issue an auth session.

        Sets both auth cookies on success. Raises ``409 email_taken`` when
        the email already exists and ``400 weak_password`` when the password
        fails the strength rules.
        """
        session = await asyncio.to_thread(
            register_user,
            email=body.email,
            password=body.password,
            session_factory=session_factory,
            jwt_service=jwt_service,
            refresh_store=refresh_store,
        )
        return _auth_response(session)

    # ── POST /auth/login ────────────────────────────────────────────────────
    @router.post("/login", summary="Login with email + password")
    async def login(
        body: _CredentialsBody,
        session_factory=Depends(get_session_factory),
        jwt_service: JWTService = Depends(get_jwt_service),
        refresh_store: RefreshTokenStore = Depends(get_refresh_store),
    ) -> JSONResponse:
        """Verify credentials and issue an auth session.

        On failure returns ``401 invalid_credentials`` with identical
        shape/timing for a non-existent email and a wrong password (the
        no-user branch runs a dummy argon2id verify to burn the same time).
        """
        session = await asyncio.to_thread(
            login_user,
            email=body.email,
            password=body.password,
            session_factory=session_factory,
            jwt_service=jwt_service,
            refresh_store=refresh_store,
        )
        return _auth_response(session)

    # ── POST /auth/logout ───────────────────────────────────────────────────
    @router.post("/logout", summary="Logout the current session")
    async def logout_endpoint(
        request: Request,
        refresh_store: RefreshTokenStore = Depends(get_refresh_store),
    ) -> JSONResponse:
        """Revoke the refresh token presented in the refresh cookie.

        Idempotent — an unknown, expired, or already-revoked refresh cookie
        still returns 200 (the cookie may be stale or absent). Clears both
        auth cookies regardless. Does NOT revoke other sessions for the
        same user (use ``/auth/logout-all`` for that).
        """
        raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
        if raw_refresh:
            await asyncio.to_thread(
                logout,
                raw_refresh=raw_refresh,
                session_factory=None,
                jwt_service=None,
                refresh_store=refresh_store,
            )
        response = JSONResponse(status_code=status.HTTP_200_OK, content={})
        clear_auth_cookies(response)
        return response

    # ── POST /auth/logout-all ───────────────────────────────────────────────
    @router.post("/logout-all", summary="Logout every session for the user")
    async def logout_all_endpoint(
        user: CurrentUser = Depends(get_current_user),
        refresh_store: RefreshTokenStore = Depends(get_refresh_store),
    ) -> JSONResponse:
        """Revoke every active refresh token for the authenticated user.

        Requires a valid access cookie (``get_current_user`` raises
        ``401 unauthenticated`` when absent/invalid). Clears both auth
        cookies. Revokes all the user's non-expired, non-revoked refresh
        rows in one UPDATE.
        """
        await asyncio.to_thread(
            logout_all,
            user_id=user.id,
            session_factory=None,
            jwt_service=None,
            refresh_store=refresh_store,
        )
        response = JSONResponse(status_code=status.HTTP_200_OK, content={})
        clear_auth_cookies(response)
        return response

    # ── POST /auth/refresh ──────────────────────────────────────────────────
    @router.post("/refresh", summary="Rotate the refresh token")
    async def refresh_endpoint(
        request: Request,
        session_factory=Depends(get_session_factory),
        jwt_service: JWTService = Depends(get_jwt_service),
        refresh_store: RefreshTokenStore = Depends(get_refresh_store),
    ) -> JSONResponse:
        """Rotate the refresh cookie: revoke old, issue a new access + refresh.

        Reads the raw refresh token from the ``ai-studio-refresh`` cookie.
        On any failure (unknown, expired, revoked, lost concurrent race)
        returns ``401 invalid_refresh_token`` — every failure uses the same
        code so a client cannot distinguish why it failed. No cookies are
        set on failure.
        """
        raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
        if not raw_refresh:
            raise InvalidRefreshTokenError()
        session = await asyncio.to_thread(
            refresh_session,
            raw_refresh=raw_refresh,
            session_factory=session_factory,
            jwt_service=jwt_service,
            refresh_store=refresh_store,
        )
        return _auth_response(session)

    # ── GET /auth/me ────────────────────────────────────────────────────────
    @router.get("/me", summary="Return the current authenticated user")
    async def me(
        user: CurrentUser = Depends(get_current_user),
    ) -> JSONResponse:
        """Return the authenticated user's state.

        Raises ``401 unauthenticated`` when there is no valid access cookie.
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=_user_dict(user),
        )

    return router


__all__ = ["build_auth_router"]