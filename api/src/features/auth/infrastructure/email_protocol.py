"""Email delivery protocol and development implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import quote_plus

import structlog

TOKEN_PREFIX_LENGTH = 8
# Keep the established logger name while the compatibility facade remains public.
_log = structlog.get_logger("src.features.auth.infrastructure.email_client")


@dataclass(frozen=True)
class SendResult:
    """A known or uncertain outcome of one verification-email attempt."""

    success: bool
    definitive: bool = True


@runtime_checkable
class EmailClient(Protocol):
    def send_verification(
        self, *, email: str, raw_token: str, delivery_id: str | None = None
    ) -> SendResult: ...

    def build_verification_url(self, *, email: str, raw_token: str) -> str: ...


def build_verification_url(app_base_url: str, email: str, raw_token: str) -> str:
    return (
        f"{(app_base_url or '').rstrip('/')}/auth/verify?token={raw_token}"
        f"&email={quote_plus(email)}"
    )


class DevEmailClient:
    """Local development client that records only safe delivery metadata."""

    def __init__(self, app_base_url: str = "") -> None:
        self._app_base_url = app_base_url

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        return build_verification_url(self._app_base_url, email, raw_token)

    def send_verification(
        self, *, email: str, raw_token: str, delivery_id: str | None = None
    ) -> SendResult:
        _log.info(
            "email_verification_link",
            _provider="dev",
            email=email,
            token_prefix=raw_token[:TOKEN_PREFIX_LENGTH],
        )
        return SendResult(success=False)
