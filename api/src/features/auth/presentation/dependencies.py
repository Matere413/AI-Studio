"""Auth FastAPI dependencies — cookie → JWT → user resolution.

Three dependencies coexist with the anonymous ``X-Session-ID`` path:

- ``get_current_user`` — REQUIRED auth. Reads the ``ai-studio-auth`` cookie,
  validates the JWT, loads the user from DB. Raises ``UnauthorizedError``
  (401 unauthenticated) on missing/invalid token or unknown user.
- ``require_verified_user`` — wraps ``get_current_user``; raises
  ``EmailNotVerifiedError`` (403 email_not_verified) when the user's email
  is not verified. Used by the slice 2 saving gate.
- ``get_optional_user`` — returns ``CurrentUser | None``. Anonymous requests
  (no cookie, invalid token) get ``None`` — they keep using the existing
  ``X-Session-ID`` path unchanged. Auth is purely additive.

The ``email_verified`` flag is reloaded from the DATABASE on every call
(not trusted from the JWT claim), so a user who verifies their email AFTER a
token was issued is immediately allowed through the saving gate. The JWT
claim is a hint; the DB is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select

from src.features.auth.infrastructure.jwt_service import AccessTokenError, JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.infrastructure.email_client import EmailClient, build_email_client
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.shared.errors_auth import EmailNotVerifiedError, UnauthorizedError
from src.shared.security.cookies import AUTH_COOKIE_NAME


# ─── Provider wiring ──────────────────────────────────────────────────────────
#
# The auth router + dependencies need three singletons at request time:
# ``session_factory``, ``jwt_service``, and ``refresh_store``. They are wired
# once during app startup via :func:`init_auth_providers` and then exposed as
# FastAPI dependencies (``get_session_factory`` / ``get_jwt_service`` /
# ``get_refresh_store``) so endpoints and the user-resolution dependencies
# below resolve them without re-constructing on every request.
#
# Defined FIRST so the user-resolution dependencies can use them as default
# argument values (``Depends(get_session_factory)``) — default args are
# evaluated at function-definition time, so the provider functions must
# already exist when ``get_current_user`` is defined.
#
# In production, ``init_auth_providers`` is called from the app lifespan (after
# ``load_config`` caches ``AuthConfig`` on ``app.state.config`` and ``init_db``
# creates the async engine). In tests it is called by the test fixture with
# throw-in instances.

_providers: dict[str, object] = {}


def init_auth_providers(
    *,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    email_verification_store: EmailVerificationStore | None = None,
    email_client: EmailClient | None = None,
) -> None:
    """Initialise the module-level auth provider singletons.

    MUST be called during application startup (before the auth router serves
    any request) and in test fixtures before mounting the auth router.

    Args:
        session_factory: The app's async ``async_sessionmaker``.
        jwt_service: A configured :class:`JWTService` (secret from
            ``app.state.config.jwt_secret``).
        refresh_store: A :class:`RefreshTokenStore` bound to the same engine.
        email_verification_store: A :class:`EmailVerificationStore` bound to
            the same engine. Required for verify-email / resend-verification
            (slice 2). May be ``None`` in slice 1b-only contexts.
        email_client: An :class:`EmailClient` for verification email
            delivery. Required for register / resend-verification (slice 2).
            May be ``None`` in slice 1b-only contexts.
    """
    _providers.clear()
    _providers["session_factory"] = session_factory
    _providers["jwt_service"] = jwt_service
    _providers["refresh_store"] = refresh_store
    if email_verification_store is not None:
        _providers["email_verification_store"] = email_verification_store
    if email_client is not None:
        _providers["email_client"] = email_client


def get_session_factory():
    """FastAPI dependency: the configured async session factory."""
    try:
        return _providers["session_factory"]
    except KeyError as exc:  # pragma: no cover — wired before serving
        raise RuntimeError(
            "auth providers not initialised. Call init_auth_providers() "
            "during app startup."
        ) from exc


def get_jwt_service() -> JWTService:
    """FastAPI dependency: the configured :class:`JWTService`."""
    try:
        return _providers["jwt_service"]  # type: ignore[return-value]
    except KeyError as exc:  # pragma: no cover — wired before serving
        raise RuntimeError(
            "auth providers not initialised. Call init_auth_providers() "
            "during app startup."
        ) from exc


def get_refresh_store() -> RefreshTokenStore:
    """FastAPI dependency: the configured :class:`RefreshTokenStore`."""
    try:
        return _providers["refresh_store"]  # type: ignore[return-value]
    except KeyError as exc:  # pragma: no cover — wired before serving
        raise RuntimeError(
            "auth providers not initialised. Call init_auth_providers() "
            "during app startup."
        ) from exc


def get_email_verification_store() -> EmailVerificationStore:
    """FastAPI dependency: the :class:`EmailVerificationStore` (slice 2)."""
    try:
        return _providers["email_verification_store"]  # type: ignore[return-value]
    except KeyError as exc:
        raise RuntimeError(
            "EmailVerificationStore not wired. Call init_auth_providers() "
            "with email_verification_store during app startup (slice 2)."
        ) from exc


def get_email_client() -> EmailClient:
    """FastAPI dependency: the :class:`EmailClient` (slice 2)."""
    try:
        return _providers["email_client"]  # type: ignore[return-value]
    except KeyError as exc:
        raise RuntimeError(
            "EmailClient not wired. Call init_auth_providers() "
            "with email_client during app startup (slice 2)."
        ) from exc


# ─── Current user ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated user resolved by the auth dependency.

    A frozen dataclass so it is safe to share across the request lifecycle
    and store on ``request.state.user``.

    Attributes:
        id: The user's UUID (matches ``users.id`` and the JWT ``sub``).
        email: The user's email (reloaded from DB, not the JWT claim).
        email_verified: The CURRENT DB value of ``users.email_verified`` —
            reloaded on every request so the saving gate checks the live
            state, not a stale JWT claim.
    """

    id: str
    email: str
    email_verified: bool


def _read_access_cookie(request: Request) -> str | None:
    """Read the ``ai-studio-auth`` cookie from the request (None if absent)."""
    return request.cookies.get(AUTH_COOKIE_NAME)


async def _resolve_user(
    request: Request,
    session_factory,
    jwt_service: JWTService,
) -> CurrentUser | None:
    """Resolve a CurrentUser from the access cookie, or return None.

    Returns None on: missing cookie, invalid token, unknown user id. The
    caller (get_current_user vs get_optional_user) decides whether None is
    an error or an anonymous fallthrough.
    """
    token = _read_access_cookie(request)
    if not token:
        return None
    try:
        payload = jwt_service.decode(token)
    except AccessTokenError:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    async with session_factory() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            return None
        # Reload email_verified from the DB — the saving gate must check the
        # live state, not a JWT claim issued before the user verified.
        return CurrentUser(
            id=user.id, email=user.email, email_verified=user.email_verified
        )


async def get_current_user(
    request: Request,
    session_factory=Depends(get_session_factory),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> CurrentUser:
    """Resolve the authenticated user or raise ``UnauthorizedError``.

    Usable as a FastAPI dependency (``Depends(get_current_user)``) — the
    ``session_factory`` and ``jwt_service`` default to the provider
    dependencies wired by :func:`init_auth_providers`. They can also be
    passed explicitly in unit tests.

    Raises:
        UnauthorizedError: When there is no access cookie, the token is
            invalid/expired, or the user id no longer exists in the DB.
    """
    user = await _resolve_user(request, session_factory, jwt_service)
    if user is None:
        raise UnauthorizedError()
    # Cache on request.state so downstream handlers + middleware can read it
    # without re-resolving.
    request.state.user = user
    return user


async def get_optional_user(
    request: Request,
    session_factory=Depends(get_session_factory),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> CurrentUser | None:
    """Resolve the authenticated user, or ``None`` when anonymous.

    Anonymous coexistence: a request with no/invalid auth cookie returns
    ``None`` — it does NOT raise. The existing ``X-Session-ID`` anonymous
    generation path is unchanged by this dependency.
    """
    user = await _resolve_user(request, session_factory, jwt_service)
    if user is not None:
        request.state.user = user
    return user


async def require_verified_user(
    request: Request,
    session_factory=Depends(get_session_factory),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> CurrentUser:
    """Resolve the authenticated user and require a verified email.

    Raises:
        UnauthorizedError: When not authenticated (no/invalid cookie or
            unknown user). This takes precedence over the verified check —
            an anonymous request is ``401``, not ``403``.
        EmailNotVerifiedError: When the user is authenticated but their
            email is not verified. Used by the slice 2 saving gate
            (POST/PUT /projects).
    """
    user = await get_current_user(request, session_factory, jwt_service)
    if not user.email_verified:
        raise EmailNotVerifiedError()
    return user


__all__ = [
    "CurrentUser",
    "get_current_user",
    "get_email_client",
    "get_email_verification_store",
    "get_jwt_service",
    "get_optional_user",
    "get_refresh_store",
    "get_session_factory",
    "init_auth_providers",
    "require_verified_user",
]