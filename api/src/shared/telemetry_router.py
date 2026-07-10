"""Frontend telemetry ingestion endpoint — the production collection path.

This is the backend half of judgment-day finding #1: the frontend telemetry
adapter emits a stable event shape (``name`` + ``fields`` + ``level``), but
previously ``auth_bootstrap_transient`` (and any other frontend event) only
reached an OPTIONAL unregistered sink or a deduped console warning — there
was no production collection path. This router receives a STRICT allowlisted
payload and forwards it into the EXISTING backend telemetry stack
(:mod:`src.shared.telemetry` → structured log + Sentry when configured).

Design contract (the hard requirements):

- ANONYMOUS-SAFE: the endpoint does NOT require authentication. A transient
  bootstrap failure may happen on an unauthenticated /auth/me before any
  session exists, so requiring auth would drop the most important signal.
- STRICT ALLOWLIST: only event names in
  ``ALLOWED_FRONTEND_EVENT_NAMES`` are accepted; anything else is 422. This
  is the abuse / typo guard — a client cannot invent event names that reach
  the structured log / Sentry.
- NO SENSITIVE PAYLOAD: the endpoint accepts ``name`` + ``fields`` + ``level``
  ONLY. The Pydantic model forbids extra keys (``model_config =
  {"extra": "forbid"}``) so a client cannot smuggle a ``token`` / ``cookie``
  / ``email`` / ``url`` / ``body`` top-level field. Field VALUES are further
  restricted to ``string | number | boolean | null`` (no nested objects /
  arrays) and capped in size. ``capture_frontend_event`` redacts sensitive
  field KEYS defensively (defense-in-depth — the schema already forbids the
  top-level sensitive keys, but a future event name with a sensitive field
  is still guarded).
- RATE-LIMITED: ``check_telemetry_events`` enforces 30/min per IP so a
  malicious / runaway client cannot flood the structured log / Sentry. The
  rate limit runs BEFORE the allowlist / Sentry / log emission so a flood of
  invalid or valid payloads is bounded. A missing IP (no trusted proxy +
  no ``request.client``) uses a bounded ``"unknown"`` bucket so an unkeyed
  flood cannot bypass the limiter.
- IP SPOOFING GUARD (judgment-day hardening): ``X-Forwarded-For`` is ONLY
  trusted when a trusted-proxy config proves the deployment runs behind a
  known proxy / TLS terminator. Without that config the header is
  client-controlled and trivially spoofable, so a malicious client could
  rotate the rate-limit bucket at will. When no trusted-proxy config exists
  the endpoint falls back to ``request.client.host`` (the transport-layer
  peer) and a bounded ``"unknown"`` bucket when even that is unavailable.
- BODY BYTE LIMIT: the raw request body is read with a bounded byte limit
  BEFORE Pydantic parsing so an oversized payload cannot exhaust memory. An
  oversized body is rejected with 413 (Payload Too Large) before the schema
  / rate-limit checks touch it.
- STRICT FIELD BOUNDS: the event ``name``, field KEYS, string field VALUES,
  and the total field COUNT are all strictly capped at the schema level so
  a malicious / buggy client cannot inflate the structured log / Sentry
  payload.
- NON-BLOCKING + NEVER RAISES: the capture helper swallows errors; a
  telemetry failure MUST NEVER block the request path. The endpoint returns
  202 (accepted) on success and 422 for schema violations; it never returns
  5xx for a telemetry-internal failure (the structured log is the sole
  signal in that case).

No new vendor SDK is required — Sentry is already a dev/prod dep and is
initialised in ``app.py`` (gated on ``SENTRY_DSN``); this router only USES
the already-initialised client via ``capture_frontend_event``.

Cookies / tokens / URLs / emails / body dumps are never accepted (schema
forbids them) and never forwarded (redaction is defense-in-depth).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.shared.rate_limit import check_telemetry_events
from src.shared.telemetry import (
    ALLOWED_FRONTEND_EVENT_NAMES,
    capture_frontend_event,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


# ─── Hardening constants ────────────────────────────────────────────────────

# Maximum raw request body size in bytes. An oversized body is rejected with
# 413 BEFORE Pydantic parsing so memory cannot be exhausted by a malicious /
# buggy client sending a multi-MB payload. 16 KiB is generous for a strict
# event (name + 32 capped fields + level) while bounding the attack surface.
_MAX_BODY_BYTES: int = 16 * 1024

# Maximum lengths / counts enforced at the schema level (defense-in-depth —
# ``capture_frontend_event`` re-caps defensively, but the schema is the first
# gate so an oversized value is rejected before it reaches the log / Sentry).
_MAX_NAME_LEN: int = 128
_MAX_FIELDS: int = 32
_MAX_FIELD_KEY_LEN: int = 64
_MAX_FIELD_STR_LEN: int = 512

# Bounded bucket key for requests with no attributable client IP (no trusted
# proxy + no ``request.client``). Using a FIXED key means an unkeyed flood
# is still bounded by the rate limiter — it cannot bypass the limiter by
# having no IP. The bucket is shared (all unkeyed clients hit the same
# bucket), which is the correct conservative behaviour: a flood from an
# unknown source is still capped.
_UNKNOWN_IP_BUCKET: str = "unknown"


# ─── Trusted-proxy config ───────────────────────────────────────────────────
#
# ``X-Forwarded-For`` is ONLY trusted when the deployment proves it runs
# behind a known proxy / TLS terminator. This is checked at import time via
# an environment opt-in (``TRUSTED_PROXY=1``). When NOT set, the header is
# treated as client-controlled and UNTRUSTED — the endpoint falls back to
# ``request.client.host`` (the transport-layer peer) so a malicious client
# cannot spoof the rate-limit bucket by rotating the header.
#
# The auth router's ``_client_ip`` still trusts the header unconditionally
# (it is behind Modal's TLS terminator in production); the telemetry
# endpoint is the abuse-facing anonymous endpoint so it gets the stricter
# treatment. A future hardening pass should apply the same guard to the auth
# router once a trusted-proxy config is wired through ``AuthConfig``.

import os

_TRUSTED_PROXY: bool = os.environ.get("TRUSTED_PROXY", "").strip() == "1"


# ─── Request schema ──────────────────────────────────────────────────────────


# Field value: string | number | boolean | null ONLY. No nested objects /
# arrays so a client cannot inflate the payload or smuggle a structure the
# log / Sentry cannot serialize. Strings are capped so a huge value cannot
# inflate the payload (``capture_frontend_event`` re-caps defensively).
FieldKey = Annotated[str, Field(min_length=1, max_length=_MAX_FIELD_KEY_LEN)]
FieldString = Annotated[str, Field(max_length=_MAX_FIELD_STR_LEN)]
FieldValue = FieldString | int | float | bool | None


class TelemetryEventBody(BaseModel):
    """The strict allowlisted body for ``POST /telemetry/events``.

    ``extra="forbid"`` rejects any top-level key other than ``name`` /
    ``fields`` / ``level`` — so a client cannot smuggle a ``token`` /
    ``cookie`` / ``email`` / ``url`` / ``body`` top-level field. The field
    VALUES are restricted to primitives (no nesting) + capped in size. The
    field KEYS are free-form strings (capped) so the frontend can pass
    operational metadata (e.g. ``code``), but ``capture_frontend_event``
    redacts sensitive keys defensively.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=_MAX_NAME_LEN)
    fields: dict[FieldKey, FieldValue] = Field(
        default_factory=dict, max_length=_MAX_FIELDS
    )
    level: str = Field(default="info", pattern="^(info|warn|error)$")


# ─── IP extraction (spoofing-guarded) ────────────────────────────────────────


def _client_ip(request: Request) -> str | None:
    """Extract the client IP for the telemetry rate-limit bucket.

    Judgment-day hardening: ``X-Forwarded-For`` is ONLY trusted when a
    trusted-proxy config proves the deployment runs behind a known proxy /
    TLS terminator (``TRUSTED_PROXY=1``). Without that config the header is
    client-controlled and trivially spoofable — a malicious client could
    rotate the rate-limit bucket at will by sending a different ``XFF`` per
    request. When untrusted, the endpoint falls back to
    ``request.client.host`` (the transport-layer peer set by the server, not
    the client) so the bucket reflects the actual connection source.

    Returns ``None`` only when BOTH the header (when trusted) and
    ``request.client`` are unavailable — the caller maps ``None`` to the
    bounded ``"unknown"`` bucket so the limiter is never bypassed.
    """
    if _TRUSTED_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",", 1)[0].strip()
            if ip:
                return ip
    # Untrusted XFF (or trusted but no header) → fall back to the
    # transport-layer peer, which the server sets from the actual TCP
    # connection and the client cannot spoof.
    if request.client is not None:
        return request.client.host
    return None


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
