"""Log sanitization — structlog processor that scrubs secret keys.

Covers the api-security spec: Log Sanitization. Structured logs MUST NOT
contain raw secrets. This processor scrubs any of the following keys (matched
case-insensitively) to ``"[REDACTED]"`` before emission:

    password, token, authorization, set-cookie, cookie, password_hash

It is designed to be wired into the structlog processor chain (see
``src.shared.logging.configure_structlog``) so every log event passes
through it. It operates on the top-level keys of the event dict only —
structlog events are flat key-value maps; deep scrubbing of nested dicts is
out of scope (and unnecessary for the spec).

Usage::

    from src.shared.security.redaction import redact_secret_keys

    structlog.configure(
        processors=[
            ...,
            redact_secret_keys,
            structlog.processors.JSONRenderer(),
        ],
    )
"""

from __future__ import annotations

from typing import Any

# The spec-defined secret keys (case-insensitive match). 4R WARNING 1
# extends the set with verification_url + raw_token (the DevEmailClient
# formerly logged the full verification URL including the raw token).
_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "authorization",
        "set-cookie",
        "cookie",
        "password_hash",
        "verification_url",
        "raw_token",
    }
)

_REDACTED: str = "[REDACTED]"


def redact_secret_keys(
    logger: Any = None,
    method_name: str | None = None,
    record: Any = None,
) -> Any:
    """Scrub secret keys from a structlog event dict.

    Structlog processor protocol: ``processor(logger, method_name, event_dict)
    -> event_dict``. This function accepts that three-argument form so it can
    be wired directly into the structlog processor chain. It also accepts a
    single-dict argument so it can be called directly as a pure function
    (useful in unit tests).

    Args:
        logger: The structlog logger (unused — present for protocol compat).
        method_name: The log method name (unused — present for protocol compat).
        record: The event dict. When called as a structlog processor, this is
            the third positional arg. When called directly as a pure function
            with a single dict arg, it is the first positional arg.

    Returns:
        The event dict with any secret key (case-insensitive) replaced by
        ``"[REDACTED]"``. Non-dict inputs pass through unchanged.
    """
    # Support both structlog-processor form (logger, method_name, record)
    # and pure-function form (record,). When called with a single argument,
    # that argument is the record (regardless of type).
    if method_name is None and record is None:
        # Pure-function call: redact_secret_keys(record)
        record = logger
    elif isinstance(logger, dict) and record is None:
        # Defensive: structlog may pass (logger=record, method_name=None).
        record = logger

    if not isinstance(record, dict):
        return record

    redacted: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(key, str) and key.lower() in _SECRET_KEYS:
            redacted[key] = _REDACTED
        else:
            redacted[key] = value
    return redacted