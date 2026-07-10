"""Bounded, anonymous-safe frontend telemetry ingestion."""

from __future__ import annotations

import ipaddress
import os
from typing import Annotated

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.shared.rate_limit import check_telemetry_events
from src.shared.telemetry import (
    ALLOWED_FRONTEND_EVENT_NAMES,
    capture_frontend_event,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


# ─── Hardening constants ────────────────────────────────────────────────────

# Bound raw request size before parsing.
_MAX_BODY_BYTES: int = 16 * 1024

# Maximum lengths / counts enforced at the schema level (defense-in-depth —
# ``capture_frontend_event`` re-caps defensively, but the schema is the first
# gate so an oversized value is rejected before it reaches the log / Sentry).
_MAX_NAME_LEN: int = 128
_MAX_FIELDS: int = 32
_MAX_FIELD_KEY_LEN: int = 64
_MAX_FIELD_STR_LEN: int = 512

# Missing client IPs share this rate-limit bucket.
_UNKNOWN_IP_BUCKET: str = "unknown"


_TRUSTED_PROXY: bool = os.environ.get("TRUSTED_PROXY", "").strip() == "1"
_TRUSTED_PROXY_IPS = frozenset(
    ip.strip() for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()
)
_SENSITIVE_FIELD_PARTS = frozenset(("token", "cookie", "password", "apikey", "authorization", "credential", "refresh", "session", "headers", "body", "url", "email"))


# ─── Request schema ──────────────────────────────────────────────────────────


# Field value: string | number | boolean | null ONLY. No nested objects /
# arrays so a client cannot inflate the payload or smuggle a structure the
# log / Sentry cannot serialize. Strings are capped so a huge value cannot
# inflate the payload (``capture_frontend_event`` re-caps defensively).
FieldKey = Annotated[str, Field(min_length=1, max_length=_MAX_FIELD_KEY_LEN)]
FieldString = Annotated[str, Field(max_length=_MAX_FIELD_STR_LEN)]
FieldValue = FieldString | int | float | bool | None


class TelemetryEventBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=_MAX_NAME_LEN)
    fields: dict[FieldKey, FieldValue] = Field(
        default_factory=dict, max_length=_MAX_FIELDS
    )
    level: str = Field(default="info", pattern="^(info|warn|error)$")

    @field_validator("fields")
    @classmethod
    def reject_sensitive_field_names(cls, fields: dict[str, FieldValue]) -> dict[str, FieldValue]:
        if any(part in "".join(filter(str.isalnum, key.lower())) for key in fields for part in _SENSITIVE_FIELD_PARTS):
            raise ValueError("Sensitive telemetry field names are not accepted.")
        return fields


# ─── IP extraction (spoofing-guarded) ────────────────────────────────────────


def _client_ip(request: Request) -> str | None:
    """Use XFF only from an explicitly allowlisted proxy peer."""
    peer = request.client.host if request.client is not None else None
    if _TRUSTED_PROXY and peer in _TRUSTED_PROXY_IPS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",", 1)[0].strip()
            try:
                ipaddress.ip_address(ip)
                return ip
            except ValueError:
                pass
    return peer


def _rate_limit_key(ip: str | None) -> str:
    """Map the extracted IP to a rate-limit bucket key.

    A ``None`` IP (no trusted proxy + no ``request.client``) maps to the
    bounded ``"unknown"`` bucket so an unkeyed flood is still rate-limited
    (it cannot bypass the limiter by having no attributable IP). All unkeyed
    clients share the same bucket, which is the correct conservative
    behaviour.
    """
    return ip if ip is not None else _UNKNOWN_IP_BUCKET


# ─── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/events", summary="Ingest a frontend telemetry event")
async def ingest_telemetry_event(
    request: Request,
) -> JSONResponse:
    """Receive a frontend telemetry event + forward it to the backend stack.

    Anonymous-safe (no auth). Strict allowlist: the ``name`` MUST be in
    ``ALLOWED_FRONTEND_EVENT_NAMES`` or the request is 422. Rate-limited
    per-IP (30/min) BEFORE Sentry / log emission. IP spoofing guarded:
    ``X-Forwarded-For`` is only trusted with a trusted-proxy config;
    otherwise ``request.client.host`` + a bounded ``"unknown"`` bucket are
    used. The raw body is bounded before parsing. The payload is forwarded
    to ``capture_frontend_event`` which emits a structured log + forwards to
    Sentry when configured.

    Returns 202 (accepted) on success, 413 for an oversized body, 422 for a
    schema / allowlist violation. Never returns 5xx for a telemetry-internal
    failure.
    """
    # ── 1. Rate-limit FIRST (before any Sentry / log emission) ────────────
    # The bucket is keyed by the spoofing-guarded IP. A missing IP maps to
    # the bounded ``"unknown"`` bucket so the limiter is never bypassed.
    # This runs before the body parse so a flood of oversized / malformed
    # payloads is still bounded — the rate limit is the first abuse gate.
    ip = _client_ip(request)
    check_telemetry_events(_rate_limit_key(ip))

    # ── 2. Bounded body read (before Pydantic parsing) ───────────────────
    # Consume the request incrementally so the byte limit is enforced while
    # reading, rather than after FastAPI has materialized an arbitrary body.
    chunks: list[bytes] = []
    body_size = 0
    async for chunk in request.stream():
        body_size += len(chunk)
        if body_size > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "payload_too_large",
                        "detail": (
                            f"Request body exceeds the {_MAX_BODY_BYTES}-byte limit."
                        ),
                    }
                },
            )
        chunks.append(chunk)
    raw_body = b"".join(chunks)

    # ── 3. Parse + validate the body against the strict schema ───────────
    # Parse the pre-read bytes so the body-byte limit is enforced before
    # Pydantic allocates the model. A validation failure is 422 (consistent
    # with FastAPI's default validation-rejection status).
    try:
        body = TelemetryEventBody.model_validate_json(raw_body)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_body",
                    "detail": exc.errors(include_url=False, include_context=False),
                }
            },
        )
    except ValueError:
        # Non-JSON body (e.g. a raw string / form post) → 422.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_body",
                    "detail": "Request body is not valid JSON.",
                }
            },
        )

    # ── 4. Allowlist the event name ──────────────────────────────────────
    if body.name not in ALLOWED_FRONTEND_EVENT_NAMES:
        # 422 (not 400) — consistent with FastAPI's validation-rejection
        # status so the frontend treats it the same as a malformed body.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "unknown_event",
                    "detail": f"Event name '{body.name}' is not allowlisted.",
                }
            },
        )

    # ── 5. Forward into the telemetry stack (never raises) ───────────────
    # ``capture_frontend_event`` emits a structured log + forwards to Sentry
    # when configured. It never raises — a telemetry failure MUST NEVER
    # block the request path; the structured log is the sole signal in that
    # case. A defensive try/except at the HTTP boundary guards a future
    # regression so the endpoint never returns 5xx for a telemetry failure.
    try:
        capture_frontend_event(
            name=body.name,
            fields=body.fields,
            level=body.level,
        )
    except Exception:  # pragma: no cover — defensive; capture is no-raise
        pass

    # 202 (accepted) — the event was received. We do not confirm delivery to
    # Sentry (it is optional + best-effort); the structured log is the
    # guaranteed signal. Keep the body minimal so the response is cheap.
    return JSONResponse(status_code=202, content={"accepted": True})


__all__ = ["router"]
