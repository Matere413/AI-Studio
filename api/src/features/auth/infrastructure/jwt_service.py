"""JWT access-token service — HS256, 15min, 60s leeway.

Spec: session-management — Access Token Validation. JWT HS256 signed with
``JWT_SECRET``, ``exp = 15min``, payload ``{sub, email, email_verified,
iat, exp, jti}``, 60s clock-skew leeway. Validation rejects expired,
malformed, and signature-mismatched tokens.

The secret is supplied at construction time. In production the app loads
it from the Modal ``app-config`` secret via :func:`src.shared.config.load_config`
and caches the :class:`AuthConfig` on ``app.state.config`` (slice 1a boot
guard). The auth router constructs a :class:`JWTService` from that cached
secret at request time.
"""

from __future__ import annotations

import secrets as _secrets
import time
from typing import Protocol

import jwt

_ALGORITHM: str = "HS256"
_ACCESS_TOKEN_TTL_SECONDS: int = 15 * 60  # 15 minutes (binding)
_LEEWAY_SECONDS: int = 60  # clock-skew tolerance (binding)


class AccessTokenError(Exception):
    """Raised when an access token cannot be decoded/validated.

    The auth dependency catches this and raises :class:`UnauthorizedError`,
    so callers see a uniform ``401 unauthenticated`` for expired, malformed,
    and bad-signature tokens (anti-enumeration: no token detail leaks).
    """


class _UserLike(Protocol):
    """Minimal user shape the JWT service needs to issue a token.

    Any object exposing ``id``, ``email``, and ``email_verified`` works —
    the ORM :class:`~src.features.auth.infrastructure.models.User`, a
    dataclass in tests, or a TypedDict-backed value.
    """

    id: str
    email: str
    email_verified: bool


class JWTService:
    """Encode/decode HS256 JWT access tokens.

    Args:
        secret: The HS256 signing secret. MUST NOT be empty. In production
            this comes from the ``app-config`` Modal secret
            (``JWT_SECRET``); the slice 1a boot guard refuses to start the
            server when it is missing in production mode.
    """

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("JWTService requires a non-empty secret")
        self._secret: str = secret

    def issue_access(self, user: _UserLike) -> str:
        """Issue a 15-minute HS256 access token for ``user``.

        The payload is ``{sub, email, email_verified, iat, exp, jti}`` per
        the binding. ``sub`` is the user's id; ``jti`` is a unique token id
        (random URL-safe string) so each issued token is distinguishable
        even for the same user.

        Args:
            user: Anything exposing ``id``, ``email``, ``email_verified``.

        Returns:
            The encoded JWT string.
        """
        now = int(time.time())
        payload = {
            "sub": user.id,
            "email": user.email,
            "email_verified": bool(user.email_verified),
            "iat": now,
            "exp": now + _ACCESS_TOKEN_TTL_SECONDS,
            "jti": _secrets.token_urlsafe(16),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def decode(self, token: str) -> dict:
        """Decode + validate an access token.

        Args:
            token: The encoded JWT string.

        Returns:
            The validated payload dict (contains ``sub``, ``email``,
            ``email_verified``, ``iat``, ``exp``, ``jti``).

        Raises:
            AccessTokenError: For expired, malformed, or bad-signature
                tokens. The caller should map this to ``401 unauthenticated``.
        """
        if not token:
            raise AccessTokenError("empty access token")
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                leeway=_LEEWAY_SECONDS,
            )
        except jwt.PyJWTError as exc:
            # All PyJWT decode failures (ExpiredSignatureError,
            # InvalidSignatureError, DecodeError, ...) collapse to a single
            # AccessTokenError so the dependency layer can map them to a
            # uniform 401 — no detail about WHY the token failed leaks.
            raise AccessTokenError("invalid access token") from exc


__all__ = ["JWTService", "AccessTokenError"]