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

from fastapi import Request
from sqlalchemy import select

from src.features.auth.infrastructure.jwt_service import AccessTokenError, JWTService
from src.features.auth.infrastructure.models import User
from src.shared.errors_auth import EmailNotVerifiedError, UnauthorizedError
from src.shared.security.cookies import AUTH_COOKIE_NAME


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
    session_factory,
    jwt_service: JWTService,
) -> CurrentUser:
    """Resolve the authenticated user or raise ``UnauthorizedError``.

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
    session_factory,
    jwt_service: JWTService,
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
    session_factory,
    jwt_service: JWTService,
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


__all__ = ["CurrentUser", "get_current_user", "get_optional_user", "require_verified_user"]