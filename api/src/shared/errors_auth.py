"""Auth error subclasses.

Each error extends :class:`src.shared.errors.AppError` with the spec-defined
HTTP status code and machine-readable error code. The global
``register_app_error_handlers`` handler converts these into the structured
``{"error": {"code": ..., "detail": ...}}`` response shape.

Error codes (binding — used consistently throughout the auth feature):

    unauthenticated          401  no/invalid access token
    invalid_credentials      401  wrong email or password (identical shape/timing)
    email_taken              409  registration email already exists
    weak_password            400  password fails strength rules
    email_not_verified       403  saving gate: email not verified
    token_expired            400  verification token past expiry
    invalid_token            400  no-match / bad-signature / no-user (anti-enumeration)
    token_already_consumed   400  verification token already used
    token_revoked            401  refresh token was revoked
    already_verified         400  resend-verification on a verified user
    rate_limited             429  brute-force mitigation (slice 4)
    not_owner                403  PUT /projects on another user's project

All auth errors take no constructor arguments — the message is fixed so the
response shape is consistent regardless of input. This is deliberate: it
prevents email enumeration (``invalid_credentials`` is identical for a
nonexistent email vs. a wrong password) and keeps the error envelope stable.
"""

from __future__ import annotations

from src.shared.errors import AppError


class _FixedAuthError(AppError):
    """Base for no-argument auth errors with a fixed status/code/message.

    Subclasses set the three class attributes below; ``__init__`` forwards
    them to :class:`AppError`.
    """

    _status_code: int = 0
    _code: str = ""
    _user_message: str = ""

    def __init__(self) -> None:
        super().__init__(
            status_code=self._status_code,
            code=self._code,
            user_message=self._user_message,
        )


class UnauthorizedError(_FixedAuthError):
    """401 unauthenticated — no or invalid access token."""

    _status_code = 401
    _code = "unauthenticated"
    _user_message = "Authentication is required."


class InvalidCredentialsError(_FixedAuthError):
    """401 invalid_credentials — wrong email or password (identical shape/timing)."""

    _status_code = 401
    _code = "invalid_credentials"
    _user_message = "Invalid email or password."


class EmailTakenError(_FixedAuthError):
    """409 email_taken — registration email already exists."""

    _status_code = 409
    _code = "email_taken"
    _user_message = "An account with this email already exists."


class WeakPasswordError(_FixedAuthError):
    """400 weak_password — password fails strength rules."""

    _status_code = 400
    _code = "weak_password"
    _user_message = "Password does not meet strength requirements."


class EmailNotVerifiedError(_FixedAuthError):
    """403 email_not_verified — saving gate: email not verified."""

    _status_code = 403
    _code = "email_not_verified"
    _user_message = "Email verification is required to save projects."


class TokenExpiredError(_FixedAuthError):
    """400 token_expired — verification token past expiry."""

    _status_code = 400
    _code = "token_expired"
    _user_message = "The token has expired."


class InvalidTokenError(_FixedAuthError):
    """400 invalid_token — no-match / bad-signature / no-user (anti-enumeration)."""

    _status_code = 400
    _code = "invalid_token"
    _user_message = "The token is invalid."


class TokenAlreadyConsumedError(_FixedAuthError):
    """400 token_already_consumed — verification token already used."""

    _status_code = 400
    _code = "token_already_consumed"
    _user_message = "The token has already been used."


class TokenRevokedError(_FixedAuthError):
    """401 token_revoked — refresh token was revoked."""

    _status_code = 401
    _code = "token_revoked"
    _user_message = "The token has been revoked."


class InvalidRefreshTokenError(_FixedAuthError):
    """401 invalid_refresh_token — refresh token unknown/expired/revoked/lost-race.

    Used by ``POST /auth/refresh`` for every refresh failure (unknown token,
    expired, already revoked, or the concurrent-rotation race loser). The
    spec mandates this exact code so a refresh client cannot distinguish
    WHY the refresh failed — anti-enumeration consistent with login.
    """

    _status_code = 401
    _code = "invalid_refresh_token"
    _user_message = "The refresh token is invalid or has expired."


class AlreadyVerifiedError(_FixedAuthError):
    """400 already_verified — resend-verification on a verified user."""

    _status_code = 400
    _code = "already_verified"
    _user_message = "Email is already verified."


class RateLimitedError(_FixedAuthError):
    """429 rate_limited — brute-force mitigation (implemented in slice 4)."""

    _status_code = 429
    _code = "rate_limited"
    _user_message = "Too many requests. Please try again later."


class NotOwnerError(_FixedAuthError):
    """403 not_owner — PUT /projects on another user's project."""

    _status_code = 403
    _code = "not_owner"
    _user_message = "You do not own this project."


__all__ = [
    "AlreadyVerifiedError",
    "EmailNotVerifiedError",
    "EmailTakenError",
    "InvalidCredentialsError",
    "InvalidRefreshTokenError",
    "InvalidTokenError",
    "NotOwnerError",
    "RateLimitedError",
    "TokenAlreadyConsumedError",
    "TokenExpiredError",
    "TokenRevokedError",
    "UnauthorizedError",
    "WeakPasswordError",
]