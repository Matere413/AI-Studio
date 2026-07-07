"""4R corrective pass — WARNING 1: DevEmailClient must not log the raw token.

The DevEmailClient logged the full verification URL (including the raw
token) via structlog, which leaks the verification secret into logs. The
fix logs the email + a token PREFIX (first 8 chars) for debugging, NOT
the full token. The redaction processor is also extended to scrub
``verification_url`` and ``raw_token`` keys.
"""

from __future__ import annotations

import re

import pytest
import structlog

from src.features.auth.infrastructure.email_client import DevEmailClient
from src.shared.security.redaction import redact_secret_keys


# ─── DevEmailClient ────────────────────────────────────────────────────────────


class TestDevEmailClientTokenRedaction:
    """send_verification MUST NOT log the full raw token."""

    def test_send_verification_logs_token_prefix_not_full(self, caplog):
        """GIVEN a raw token of 32+ chars
        WHEN DevEmailClient.send_verification logs the event
        THEN the log contains the email + a token PREFIX (first 8 chars)
        AND does NOT contain the full raw token."""
        client = DevEmailClient(app_base_url="https://app.test")
        raw_token = "supercalifragilistic-expialidocious-token-1234567890"

        # Capture via stdlib logging (structlog writes through to it) so
        # the test is robust to other tests' global structlog configs.
        import logging

        records: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _CaptureHandler()
        logger = logging.getLogger("src.features.auth.infrastructure.email_client")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            client.send_verification(email="alice@test.io", raw_token=raw_token)
        finally:
            logger.removeHandler(handler)

        assert len(records) == 1, "send_verification MUST log exactly one event"
        record = records[0]
        # structlog stores the event dict as record.msg (before the JSON
        # renderer) OR as record.msg after rendering. Extract the event dict.
        msg = record.msg
        # structlog passes the event_dict as record.msg before the renderer
        # processes it; after JSONRenderer it's a JSON string. Parse both.
        ev: dict
        if isinstance(msg, str):
            import json
            try:
                ev = json.loads(msg)
            except Exception:
                ev = {}
        elif isinstance(msg, dict):
            ev = msg
        else:
            ev = getattr(record, "_logger_event", {}) or {}

        # The email is logged (not secret).
        assert ev.get("email") == "alice@test.io"
        # A token_prefix field (first 8 chars) is logged for debugging.
        prefix = ev.get("token_prefix")
        assert prefix is not None, f"token_prefix MUST be logged for debugging. event was: {ev}"
        assert prefix == raw_token[:8]
        # The full raw token MUST NOT appear anywhere in the rendered event.
        rendered = str(msg)
        assert raw_token not in rendered, "the full raw token MUST NOT be in the log output"
        # The verification_url (which contains the token) MUST NOT be logged.
        assert "verification_url" not in ev, "verification_url MUST NOT be a log key (it carries the raw token)"

    def test_send_verification_token_prefix_is_short(self, caplog):
        """GIVEN a short raw token (< 8 chars)
        WHEN send_verification logs it
        THEN token_prefix is the whole token (no index error)."""
        client = DevEmailClient(app_base_url="https://app.test")
        raw_token = "short"

        import logging

        records: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _CaptureHandler()
        logger = logging.getLogger("src.features.auth.infrastructure.email_client")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            client.send_verification(email="bob@test.io", raw_token=raw_token)
        finally:
            logger.removeHandler(handler)

        record = records[0]
        msg = record.msg
        ev: dict
        if isinstance(msg, str):
            import json
            try:
                ev = json.loads(msg)
            except Exception:
                ev = {}
        elif isinstance(msg, dict):
            ev = msg
        else:
            ev = {}

        assert ev.get("token_prefix") == "short"


# ─── Redaction processor ───────────────────────────────────────────────────────


class TestRedactionVerificationKeys:
    """redact_secret_keys MUST scrub verification_url + raw_token."""

    def test_redact_verification_url(self):
        ev = {
            "event": "email_verification_link",
            "verification_url": "https://app.test/auth/verify?token=SECRET&email=a%40b.com",
        }
        out = redact_secret_keys(ev)
        assert out["verification_url"] == "[REDACTED]"

    def test_redact_raw_token(self):
        ev = {"event": "x", "raw_token": "the-secret-token-value"}
        out = redact_secret_keys(ev)
        assert out["raw_token"] == "[REDACTED]"

    def test_redact_token_prefix_NOT_redacted(self):
        """token_prefix is a debugging aid (first 8 chars), NOT a secret —
        it MUST NOT be redacted."""
        ev = {"event": "x", "token_prefix": "supercal"}
        out = redact_secret_keys(ev)
        assert out["token_prefix"] == "supercal", "token_prefix is a prefix, not the full token — MUST NOT be redacted"

    def test_redact_case_insensitive_verification_url(self):
        ev = {"event": "x", "Verification_URL": "https://...?token=x"}
        out = redact_secret_keys(ev)
        assert out["Verification_URL"] == "[REDACTED]"