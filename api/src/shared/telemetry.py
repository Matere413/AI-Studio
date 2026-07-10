"""Production telemetry bridge for delivery/authorization reliability events.

This module is the SINGLE place where delivery, backpressure, and bootstrap
events are forwarded to a production telemetry backend. It does NOT install
or configure any SDK — that is the responsibility of ``app.py`` (Sentry is
initialised there, gated on ``SENTRY_DSN``). This module only USES an
already-initialised Sentry client when present, and otherwise degrades
gracefully to structured logs (the existing production logging path via
``src.shared.logging``).

Design contract (from the delivery/authorization reliability fix):

- Stable event ids (``EVENT_ID_*``) are the alerting key. Operators dash /
  alert on ``event_id`` + ``failure_category`` without parsing free text.
- Safe tags only: never the raw token, never provider internals. The token
  PREFIX (8 chars) is the correlation handle (the prefix alone cannot verify
  the email — argon2id verify needs the full raw token).
- No new SDK dependency. ``sentry_sdk`` is already a dev/prod dep (it is
  imported lazily here so environments without it still import this module).
- Idempotent + never raises: a telemetry failure MUST NEVER block delivery
  or authorization. Every public function swallows errors and falls back to
  structured logging.

Frontend bootstrap telemetry limitation: the frontend has no telemetry SDK
wired (no Sentry/analytics dependency). The ``AuthProvider`` already emits a
deduplicated ``console.warn`` keyed by ``auth_bootstrap_transient`` for
transient bootstrap failures — that is the existing-compatible signal. This
module documents that limitation; a future frontend telemetry SDK would
hook the same call site.
"""

from __future__ import annotations

from typing import Any

import structlog

_log = structlog.get_logger(__name__)


# ─── Stable event ids ─────────────────────────────────────────────────────────
#
# Centralised so the email client + tests reference stable strings. These are
# the operational alerting keys; operators aggregate on ``event_id`` from the
# structured JSON logs (and Sentry tags, when configured).

EVENT_ID_DELIVERY_FAILED = "email_verification_send_failed"
EVENT_ID_DELIVERY_TIMEOUT = "email_verification_send_timeout"
EVENT_ID_DELIVERY_BACKPRESSURE = "email_verification_send_backpressure"
EVENT_ID_DELIVERY_LATE_RESOLVED = "email_verification_send_late_resolved"
EVENT_ID_BOOTSTRAP_TRANSIENT = "auth_bootstrap_transient"


def _sentry_capture(
    event_id: str,
    level: str,
    tags: dict[str, str],
    extra: dict[str, Any] | None = None,
) -> None:
    """Forward an event to Sentry when it is initialised.

    Never raises — Sentry is optional (only configured when ``SENTRY_DSN`` is
    set in ``app.py``). When not initialised, this is a no-op and the caller's
    structured log is the sole signal. Uses stable ``event_id`` as a tag so
    Sentry issues can be filtered without parsing the message.
    """
    try:
        import sentry_sdk  # lazy import — optional dependency
    except Exception:  # pragma: no cover — telemetry MUST NEVER raise
        return
    try:
        if not sentry_sdk.is_initialized():
            return
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("event_id", event_id)
            for key, value in tags.items():
                scope.set_tag(key, value)
            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_message(
                f"{event_id}: {', '.join(f'{k}={v}' for k, v in tags.items())}",
                level=level,
            )
    except Exception:  # pragma: no cover — telemetry MUST NEVER raise
        # Best-effort: swallow. A telemetry failure cannot be allowed to
        # block delivery or authorization.
        return


def _safe_log(level: str, message: str, fields: dict[str, Any]) -> None:
    try: getattr(_log, level)(message, **fields)
    except Exception: pass


def capture_delivery_failed(
    *,
    provider: str,
    failure_category: str,
    timeout_ms: int,
    token_prefix: str,
) -> None:
    """Capture a definitively-failed delivery (provider rejected / errored)."""
    fields = {
        "event_id": EVENT_ID_DELIVERY_FAILED,
        "_provider": provider,
        "failure_category": failure_category,
        "timeout_ms": timeout_ms,
        "token_prefix": token_prefix,
    }
    _safe_log("warning", "email verification send failed", fields)
    _sentry_capture(
        EVENT_ID_DELIVERY_FAILED,
        level="warning",
        tags={
            "provider": provider,
            "failure_category": failure_category,
        },
        extra={"timeout_ms": timeout_ms, "token_prefix": token_prefix},
    )


def capture_delivery_timeout(
    *,
    provider: str,
    timeout_ms: int,
    token_prefix: str,
    phase: str,
) -> None:
    """Capture a delivery timeout.

    ``phase`` is ``"queued"`` (cancelled before running — never delivered) or
    ``"running"`` (cannot be force-cancelled; outcome uncertain). The phase
    is a stable tag so operators can distinguish the two in dashboards/alerts.
    """
    fields = {
        "event_id": EVENT_ID_DELIVERY_TIMEOUT,
        "_provider": provider,
        "failure_category": "timeout",
        "timeout_ms": timeout_ms,
        "token_prefix": token_prefix,
        "phase": phase,
    }
    _safe_log("warning", "email verification send timed out", fields)
    _sentry_capture(
        EVENT_ID_DELIVERY_TIMEOUT,
        level="warning",
        tags={"provider": provider, "failure_category": "timeout", "phase": phase},
        extra={"timeout_ms": timeout_ms, "token_prefix": token_prefix},
    )


def capture_delivery_backpressure(
    *,
    provider: str,
    timeout_ms: int,
    token_prefix: str,
    reason: str,
) -> None:
    """Capture a backpressure rejection (bounded pool saturated)."""
    fields = {
        "event_id": EVENT_ID_DELIVERY_BACKPRESSURE,
        "_provider": provider,
        "failure_category": "backpressure",
        "timeout_ms": timeout_ms,
        "token_prefix": token_prefix,
        "reason": reason,
    }
    _safe_log("warning", "email verification send backpressure", fields)
    _sentry_capture(
        EVENT_ID_DELIVERY_BACKPRESSURE,
        level="warning",
        tags={"provider": provider, "failure_category": "backpressure", "reason": reason},
        extra={"timeout_ms": timeout_ms, "token_prefix": token_prefix},
    )


def capture_delivery_late_resolved(
    *,
    provider: str,
    late_success: bool,
    token_prefix: str,
) -> None:
    """Capture a late resolution of a previously-timed-out running call.

    This is the observability story for the uncertain-timeout policy: a
    running HTTP call that exceeded the join deadline and later resolved.
    Per the user policy, uncertain delivery MUST NOT silently open the
    authorization gate, so the challenge row is NOT transitioned to
    ``delivered=True`` on a late success — the row stays in its
    pending/uncertain state (save-allowed). This event lets operators see
    how often late resolutions occur (a high rate signals a provider
    latency problem worth tuning the deadline for).
    """
    fields = {
        "event_id": EVENT_ID_DELIVERY_LATE_RESOLVED,
        "_provider": provider,
        "late_success": late_success,
        "token_prefix": token_prefix,
    }
    _safe_log("info", "email verification send late resolved", fields)
    _sentry_capture(
        EVENT_ID_DELIVERY_LATE_RESOLVED,
        level="info",
        tags={"provider": provider, "late_success": str(late_success)},
        extra={"token_prefix": token_prefix},
    )


# ─── Frontend telemetry ingestion (judgment-day finding #1) ─────────────────
#
# The frontend emits a STABLE event shape (``name`` + ``fields`` + ``level``)
# via the telemetry adapter. Previously ``auth_bootstrap_transient`` (and any
# other frontend event) only reached an OPTIONAL unregistered sink or a
# deduped console warning — there was no production collection path. This
# helper is the bridge: the new ``POST /telemetry/events`` endpoint receives
# a strict allowlisted payload, calls this helper, and the event flows into
# the EXISTING telemetry stack (structured log + Sentry when configured).
#
# Safety contract (mirrors the frontend adapter):
# - ``name`` is a stable, greppable event id (allowlisted server-side).
# - ``fields`` are operational, non-sensitive metadata. The helper redacts
#   known-sensitive keys defensively so a caller mistake cannot leak a
#   token / cookie / email / URL through the structured shape.
# - ``level`` is one of ``info`` / ``warn`` / ``error``.
# - Never raises — a telemetry failure MUST NEVER block the request path.


# Event names the frontend is allowed to send. Anything else is rejected by
# the endpoint (validated before this helper runs). Centralised here so the
# allowlist + the helper stay co-located and the tests can assert against it.
ALLOWED_FRONTEND_EVENT_NAMES = frozenset(
    {
        EVENT_ID_BOOTSTRAP_TRANSIENT,
    }
)

# The same conservative sensitive-key fragments the frontend adapter redacts
# on. Redundant defense-in-depth: the endpoint validates the schema, but a
# caller mistake (a future event name with a sensitive field) is still guarded
# so the value never reaches the structured log / Sentry.
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "cookie",
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "session",
    "refresh",
    "header",
    "body",
    "url",
    "email",
)

# Approved-safe exceptions mirroring the frontend adapter: keys that CONTAIN
# a sensitive fragment but are an established NON-sensitive convention (the
# 8-char prefix alone cannot verify the token).
_SAFE_KEY_EXCEPTIONS = frozenset({"token_prefix"})

# Bounds so a malicious / buggy client cannot blow up the structured log or
# Sentry. The endpoint enforces these before calling this helper; they are
# re-checked here as defense-in-depth.
_MAX_FIELDS = 32
_MAX_NAME_LEN = 128
_MAX_FIELD_KEY_LEN = 64
_MAX_FIELD_STR_LEN = 512


def _redact_frontend_fields(
    fields: dict[str, str | int | float | bool | None],
) -> dict[str, str | int | float | bool | None]:
    """Redact sensitive keys + bound field sizes defensively.

    Mirrors the frontend adapter's redaction so the server-side log / Sentry
    cannot leak a value a caller mistakenly included. Also caps string
    lengths so a huge value cannot inflate the structured log or Sentry
    payload. Numbers and booleans pass through unchanged.
    """
    if len(fields) > _MAX_FIELDS:
        # Truncate the map (keep the first N by insertion order) so a flood
        # of fields cannot blow up the payload. The endpoint already rejects
        # >_MAX_FIELDS, so this is defense-in-depth.
        items = list(fields.items())[:_MAX_FIELDS]
        fields = dict(items)
    redacted: dict[str, str | int | float | bool | None] = {}
    for key, value in fields.items():
        key_str = str(key)
        if len(key_str) > _MAX_FIELD_KEY_LEN:
            key_str = key_str[:_MAX_FIELD_KEY_LEN]
        lower_key = key_str.lower()
        if _SAFE_KEY_EXCEPTIONS.__contains__(lower_key):
            redacted[key_str] = value
        elif any(frag in lower_key for frag in _SENSITIVE_KEY_FRAGMENTS):
            redacted[key_str] = "[redacted]"
        elif isinstance(value, str) and len(value) > _MAX_FIELD_STR_LEN:
            redacted[key_str] = value[:_MAX_FIELD_STR_LEN]
        else:
            redacted[key_str] = value
    return redacted


def capture_frontend_event(
    *,
    name: str,
    fields: dict[str, str | int | float | bool | None],
    level: str,
) -> None:
    """Forward a frontend telemetry event into the backend telemetry stack.

    This is the SINGLE production collection path for frontend telemetry: the
    ``POST /telemetry/events`` endpoint validates + allowlists the payload,
    then calls this helper, which emits a structured log (the existing
    production logging path) AND forwards to Sentry when configured (the same
    ``_sentry_capture`` seam the delivery helpers use). No new vendor SDK.

    The ``name`` is used as the Sentry ``event_id`` tag so operators can
    filter frontend events the same way they filter delivery events. The
    ``fields`` are attached as Sentry ``extra`` (capped + redacted) and logged
    as structured fields. ``level`` is forwarded to both the log level and
    the Sentry capture level.

    Never raises — a telemetry failure MUST NEVER block the request path.
    """
    # Bound the name defensively (the endpoint already enforces the allowlist
    # + length, but this helper is also importable by tests + future callers).
    safe_name = name[:_MAX_NAME_LEN] if len(name) > _MAX_NAME_LEN else name
    safe_fields = _redact_frontend_fields(fields)
    # Map the frontend level to a structlog level + Sentry level. The
    # frontend emits ``info`` / ``warn`` / ``error``; structlog expects
    # ``info`` / ``warning`` / ``error`` (no ``warn``). Map ``warn`` →
    # ``warning``; anything unknown degrades to ``info`` so a buggy client
    # cannot force an error level. Sentry accepts ``warning`` (not
    # ``warn``), so the same mapping applies to the Sentry level.
    _level_map = {"info": "info", "warn": "warning", "warning": "warning", "error": "error"}
    log_level = sentry_level = _level_map.get(level, "info")
    log_fields = {
        "event_id": safe_name,
        "source": "frontend",
    }
    log_fields.update(safe_fields)
    _safe_log(log_level, "frontend telemetry event", log_fields)
    _sentry_capture(
        safe_name,
        level=sentry_level,
        tags={"source": "frontend"},
        extra=safe_fields,
    )


__all__ = [
    "ALLOWED_FRONTEND_EVENT_NAMES",
    "EVENT_ID_BOOTSTRAP_TRANSIENT",
    "EVENT_ID_DELIVERY_BACKPRESSURE",
    "EVENT_ID_DELIVERY_FAILED",
    "EVENT_ID_DELIVERY_LATE_RESOLVED",
    "EVENT_ID_DELIVERY_TIMEOUT",
    "capture_delivery_backpressure",
    "capture_delivery_failed",
    "capture_delivery_late_resolved",
    "capture_delivery_timeout",
    "capture_frontend_event",
]
