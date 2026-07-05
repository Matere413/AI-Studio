"""Slice 1a — Auth error subclasses.

Covers the auth + api-security + session-management specs: structured
error codes that the global AppError handler returns as JSON.

Each error MUST extend AppError with the correct status_code + code.
"""

import pytest

from src.shared.errors import AppError
from src.shared.errors_auth import (
    AlreadyVerifiedError,
    EmailNotVerifiedError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotOwnerError,
    RateLimitedError,
    TokenAlreadyConsumedError,
    TokenExpiredError,
    TokenRevokedError,
    UnauthorizedError,
    WeakPasswordError,
)


class TestAuthErrorStatusCodes:
    """Each auth error MUST carry the spec-defined HTTP status + code."""

    @pytest.mark.parametrize(
        "exc_factory, expected_status, expected_code",
        [
            (lambda: UnauthorizedError(), 401, "unauthenticated"),
            (lambda: InvalidCredentialsError(), 401, "invalid_credentials"),
            (lambda: EmailTakenError(), 409, "email_taken"),
            (lambda: WeakPasswordError(), 400, "weak_password"),
            (lambda: EmailNotVerifiedError(), 403, "email_not_verified"),
            (lambda: TokenExpiredError(), 400, "token_expired"),
            (lambda: InvalidTokenError(), 400, "invalid_token"),
            (lambda: TokenAlreadyConsumedError(), 400, "token_already_consumed"),
            (lambda: TokenRevokedError(), 401, "token_revoked"),
            (lambda: AlreadyVerifiedError(), 400, "already_verified"),
            (lambda: RateLimitedError(), 429, "rate_limited"),
            (lambda: NotOwnerError(), 403, "not_owner"),
        ],
    )
    def test_error_has_correct_status_and_code(self, exc_factory, expected_status, expected_code):
        """GIVEN an auth error WHEN instantiated THEN status_code + code match spec."""
        exc = exc_factory()
        assert exc.status_code == expected_status
        assert exc.code == expected_code
        assert isinstance(exc, AppError), f"{type(exc).__name__} must extend AppError"

    def test_all_errors_have_nonempty_user_message(self):
        """GIVEN each auth error WHEN instantiated THEN user_message is non-empty."""
        errors = [
            UnauthorizedError(),
            InvalidCredentialsError(),
            EmailTakenError(),
            WeakPasswordError(),
            EmailNotVerifiedError(),
            TokenExpiredError(),
            InvalidTokenError(),
            TokenAlreadyConsumedError(),
            TokenRevokedError(),
            AlreadyVerifiedError(),
            RateLimitedError(),
            NotOwnerError(),
        ]
        for exc in errors:
            assert exc.user_message, f"{type(exc).__name__} has empty user_message"

    def test_unauthorized_error_is_app_error_subclass(self):
        assert issubclass(UnauthorizedError, AppError)

    def test_credentials_error_does_not_leak_which_field(self):
        """GIVEN InvalidCredentialsError WHEN inspected
        THEN the message does not reference 'email' or 'password' specifically
        (anti-enumeration: identical shape for nonexistent email vs wrong password).
        """
        exc = InvalidCredentialsError()
        msg = exc.user_message.lower()
        assert "email" not in msg or "invalid" in msg
        assert "password" not in msg or "invalid" in msg