"""Email delivery for the auth feature (task 2-2).

Spec: email-verification — Email Delivery.

Two implementations selected by ``EMAIL_PROVIDER``:
- ``DevEmailClient`` (``EMAIL_PROVIDER=dev``) — logs the verification URL
  via structlog. No external HTTP call. The default for local dev so the
  stack boots with zero external deps.
- ``ResendEmailClient`` (``EMAIL_PROVIDER=resend``) — calls the Resend
  HTTP API with the verification link. The ``resend`` SDK is imported
  lazily so dev/test environments without it still import this module.

Delivery failure MUST NOT block registration (non-blocking per spec): the
``send_verification`` methods catch + log errors and never raise.
"""

from __future__ import annotations

from urllib.parse import quote_plus
from typing import Protocol, runtime_checkable

import structlog

_log = structlog.get_logger(__name__)


def _build_url(app_base_url: str, email: str, raw_token: str) -> str:
    """Build the verification URL: <base>/auth/verify?token=...&email=<urlencoded>."""
    base = (app_base_url or "").rstrip("/")
    return f"{base}/auth/verify?token={raw_token}&email={quote_plus(email)}"


@runtime_checkable
class EmailClient(Protocol):
    """Abstract email delivery interface."""

    def send_verification(self, *, email: str, raw_token: str) -> None:
        ...

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        ...


# ─── DevEmailClient ────────────────────────────────────────────────────────────


class DevEmailClient:
    """``EMAIL_PROVIDER=dev`` — log the verification URL via structlog.

    No external call. The default for local dev.
    """

    def __init__(self, app_base_url: str = "") -> None:
        self._app_base_url = app_base_url or ""

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        return _build_url(self._app_base_url, email, raw_token)

    def send_verification(self, *, email: str, raw_token: str) -> None:
        # 4R WARNING 1 — do NOT log the full verification URL (it carries
        # the raw token). Log the email + a token PREFIX (first 8 chars)
        # for debugging + correlation, which is safe (the prefix alone
        # cannot verify the email — the argon2id verify needs the full raw
        # token). The full URL is built for the email body but not logged.
        url = self.build_verification_url(email=email, raw_token=raw_token)
        _log.info(
            "email_verification_link",
            _provider="dev",
            email=email,
            token_prefix=raw_token[:8] if raw_token else "",
        )


# ─── ResendEmailClient ────────────────────────────────────────────────────────


class ResendEmailClient:
    """``EMAIL_PROVIDER=resend`` — call the Resend HTTP API.

    The ``resend`` SDK is imported lazily inside ``_resend_send`` so dev
    / test environments without the SDK installed still import this
    module. Delivery failure is non-blocking (caught + logged, never
    raised).
    """

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        app_base_url: str = "",
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._app_base_url = app_base_url or ""

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        return _build_url(self._app_base_url, email, raw_token)

    def send_verification(self, *, email: str, raw_token: str) -> None:
        url = self.build_verification_url(email=email, raw_token=raw_token)
        try:
            _resend_send(
                api_key=self._api_key,
                from_email=self._from_email,
                to_email=email,
                verification_url=url,
            )
        except Exception as exc:  # non-blocking per spec
            _log.warning(
                "email_verification_send_failed",
                _provider="resend",
                email=email,
                error=str(exc),
            )


def _resend_send(
    *,
    api_key: str,
    from_email: str,
    to_email: str,
    verification_url: str,
) -> dict:
    """Send a verification email via the Resend SDK.

    The SDK is imported lazily so the module imports cleanly without it.
    Raises on failure — the caller (ResendEmailClient) catches + logs.
    """
    import resend  # lazy import

    resend.api_key = api_key
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Verify your AI-Studio email",
        "html": (
            f'<p>Verify your email by visiting:</p>'
            f'<p><a href="{verification_url}">{verification_url}</a></p>'
        ),
    }
    email = resend.Emails.send(params)
    # resend.Emails.send returns an object with .id
    try:
        return {"id": email.id}
    except AttributeError:
        return {"id": str(email)}


# ─── build_email_client factory ───────────────────────────────────────────────


def build_email_client(
    *,
    provider: str,
    api_key: str | None = None,
    from_email: str = "",
    app_base_url: str = "",
) -> EmailClient:
    """Select an EmailClient implementation from ``EMAIL_PROVIDER``.

    Falls back to ``DevEmailClient`` when:
    - provider is unknown (defensive default)
    - provider is "resend" but no API key is configured (non-blocking)
    """
    if provider == "resend" and api_key and from_email:
        return ResendEmailClient(
            api_key=api_key, from_email=from_email, app_base_url=app_base_url
        )
    return DevEmailClient(app_base_url=app_base_url)


__all__ = [
    "DevEmailClient",
    "EmailClient",
    "ResendEmailClient",
    "build_email_client",
]