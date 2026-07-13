"""Pinned direct HTTP transport for Resend delivery."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

RESEND_API_BASE_URL = "https://api.resend.com"
RESEND_EMAILS_PATH = "/emails"
IDEMPOTENCY_KEY_MAX_LENGTH = 128
DEFAULT_SEND_TIMEOUT_MS = 15_000
DEFAULT_CONNECT_TIMEOUT_MS = 5_000
DEFAULT_READ_TIMEOUT_MS = 10_000


class ResendHttpError(Exception):
    def __init__(self, kind: str, *, status: int | None = None) -> None:
        self.kind = kind
        self.status = status
        super().__init__(kind)


@dataclass(frozen=True)
class ResendSendRequest:
    """Immutable input for one pinned Resend email request."""

    api_key: str
    from_email: str
    to_email: str
    verification_url: str
    idempotency_key: str


def _timeout_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def resend_timeout_ms() -> int:
    return _timeout_env("RESEND_SEND_TIMEOUT_MS", DEFAULT_SEND_TIMEOUT_MS)


def derive_idempotency_key(delivery_id: str | None) -> str:
    import uuid

    return (str(delivery_id) if delivery_id else str(uuid.uuid4()))[:IDEMPOTENCY_KEY_MAX_LENGTH]


def resend_send(
    request: ResendSendRequest, *, transport: httpx.BaseTransport | None = None
) -> dict:
    """Send to the fixed Resend origin; tests inject ``transport`` instead of URLs."""
    connect_ms = _timeout_env("RESEND_SEND_CONNECT_TIMEOUT_MS", DEFAULT_CONNECT_TIMEOUT_MS)
    read_ms = _timeout_env("RESEND_SEND_READ_TIMEOUT_MS", DEFAULT_READ_TIMEOUT_MS)
    timeout = httpx.Timeout(connect=connect_ms / 1000, read=read_ms / 1000,
                            write=read_ms / 1000, pool=connect_ms / 1000)
    payload = {"from": request.from_email, "to": [request.to_email], "subject": "Verify your AI-Studio email",
               "html": f'<p><a href="{request.verification_url}">{request.verification_url}</a></p>'}
    headers = {"Authorization": f"Bearer {request.api_key}", "Content-Type": "application/json",
               "Idempotency-Key": request.idempotency_key}
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(f"{RESEND_API_BASE_URL}{RESEND_EMAILS_PATH}", json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ResendHttpError("timeout") from exc
    except httpx.HTTPError as exc:
        raise ResendHttpError("transport_error") from exc
    if not 200 <= response.status_code < 300:
        raise ResendHttpError("http_error", status=response.status_code)
    try:
        return {"id": response.json().get("id", "")}
    except Exception:
        return {"id": ""}


def classify_send_failure(exc: BaseException) -> str:
    kind, status = getattr(exc, "kind", None), getattr(exc, "status", None)
    if kind == "timeout": return "timeout"
    if kind == "transport_error": return "provider_unavailable"
    if kind == "http_error" and status in (401, 403): return "auth_error"
    if kind == "http_error" and status is not None and status >= 500: return "provider_unavailable"
    return "unknown"
