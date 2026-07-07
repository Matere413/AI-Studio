"""Slice 1a — Log sanitization (redaction).

Covers api-security spec: Log Sanitization.
The system MUST redact sensitive fields from all logs: password, token,
authorization, set-cookie, cookie, password_hash. Structlog processors
MUST scrub these keys before emission.
"""

import pytest

from src.shared.security.redaction import redact_secret_keys


class TestRedactSecretKeys:
    """redact_secret_keys MUST scrub the 6 spec-defined secret keys."""

    def test_redacts_password(self):
        """GIVEN a log event dict with 'password'
        WHEN redact_secret_keys is called
        THEN the value is '[REDACTED]'.
        """
        record = {"event": "login", "password": "CorrectHorse42!"}
        result = redact_secret_keys(record)
        assert result["password"] == "[REDACTED]"

    def test_redacts_token(self):
        record = {"event": "refresh", "token": "abc.def.ghi"}
        result = redact_secret_keys(record)
        assert result["token"] == "[REDACTED]"

    def test_redacts_authorization(self):
        """GIVEN a log event dict with 'authorization'
        WHEN redact_secret_keys is called
        THEN the value is '[REDACTED]'."""
        record = {"event": "request", "authorization": "Bearer secret.jwt.token"}
        result = redact_secret_keys(record)
        assert result["authorization"] == "[REDACTED]"

    def test_redacts_set_cookie(self):
        record = {"event": "response", "set-cookie": "ai-studio-auth=val; HttpOnly"}
        result = redact_secret_keys(record)
        assert result["set-cookie"] == "[REDACTED]"

    def test_redacts_cookie(self):
        record = {"event": "request", "cookie": "ai-studio-auth=val"}
        result = redact_secret_keys(record)
        assert result["cookie"] == "[REDACTED]"

    def test_redacts_password_hash(self):
        """GIVEN a log event dict with 'password_hash'
        WHEN redact_secret_keys is called
        THEN the value is '[REDACTED]'."""
        record = {"event": "register", "password_hash": "$argon2id$secret"}
        result = redact_secret_keys(record)
        assert result["password_hash"] == "[REDACTED]"

    def test_does_not_touch_non_secret_keys(self):
        """GIVEN a log event with non-secret keys
        WHEN redact_secret_keys is called
        THEN non-secret keys are preserved unchanged.
        """
        record = {"event": "request", "method": "POST", "path": "/auth/login", "email": "a@b.io"}
        result = redact_secret_keys(record)
        assert result["method"] == "POST"
        assert result["path"] == "/auth/login"
        assert result["email"] == "a@b.io"
        assert result["event"] == "request"

    def test_case_insensitive_key_matching(self):
        """GIVEN keys with mixed case ('Password', 'TOKEN')
        WHEN redact_secret_keys is called
        THEN they are redacted (case-insensitive scrubbing).
        """
        record = {"Password": "secret", "TOKEN": "tok", "Set-Cookie": "x=y"}
        result = redact_secret_keys(record)
        assert result["Password"] == "[REDACTED]"
        assert result["TOKEN"] == "[REDACTED]"
        assert result["Set-Cookie"] == "[REDACTED]"

    def test_preserves_non_dict_input(self):
        """GIVEN a non-dict record (e.g. a string)
        WHEN redact_secret_keys is called
        THEN it returns the input unchanged (safe no-op).
        """
        assert redact_secret_keys("not-a-dict") == "not-a-dict"
        assert redact_secret_keys(None) is None
        assert redact_secret_keys(42) == 42

    def test_empty_dict_unchanged(self):
        """GIVEN an empty dict
        WHEN redact_secret_keys is called
        THEN it returns an empty dict."""
        assert redact_secret_keys({}) == {}

    def test_nested_secret_key_not_touched(self):
        """GIVEN a nested dict where a secret key is a sub-key
        WHEN redact_secret_keys is called
        THEN only top-level secret keys are scrubbed (one level — structlog
        events are flat key-value maps; deep scrubbing is out of scope).
        """
        record = {"event": "x", "data": {"password": "secret"}}
        result = redact_secret_keys(record)
        # Top-level keys are scrubbed; nested ones are left as-is (one level).
        assert result["event"] == "x"
        assert result["data"] == {"password": "secret"}


class TestRedactionWiredIntoStructlog:
    """Verify redact_secret_keys is wired into the structlog processor chain."""

    def test_password_redacted_in_structlog_output(self):
        """GIVEN structlog is configured with the redaction processor
        WHEN a log event with a 'password' key is emitted
        THEN the rendered JSON shows password='[REDACTED]'.
        """
        import io
        import json
        import structlog
        from src.shared.logging import configure_structlog, get_logger

        structlog.reset_defaults()
        string_io = io.StringIO()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                redact_secret_keys,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            logger_factory=structlog.PrintLoggerFactory(string_io),
            cache_logger_on_first_use=False,
        )

        log = get_logger("test_redaction_wiring")
        log.info("login_attempt", email="a@b.io", password="super-secret-pw")

        output = string_io.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["password"] == "[REDACTED]"
        assert parsed["email"] == "a@b.io"

    def test_authorization_redacted_in_structlog_output(self):
        """GIVEN structlog configured with redaction
        WHEN a log event with 'authorization' is emitted
        THEN the rendered JSON shows authorization='[REDACTED]'.
        """
        import io
        import json
        import structlog
        from src.shared.logging import get_logger

        structlog.reset_defaults()
        string_io = io.StringIO()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                redact_secret_keys,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            logger_factory=structlog.PrintLoggerFactory(string_io),
            cache_logger_on_first_use=False,
        )

        log = get_logger("test_auth_header")
        log.info("request", authorization="Bearer jwt.token.here", path="/auth/me")

        parsed = json.loads(string_io.getvalue().strip())
        assert parsed["authorization"] == "[REDACTED]"
        assert parsed["path"] == "/auth/me"

    def test_configure_structlog_includes_redaction_processor(self):
        """GIVEN configure_structlog is called
        WHEN the processor chain is inspected
        THEN redact_secret_keys is present (wired at module config time)."""
        import structlog
        from src.shared.logging import configure_structlog

        structlog.reset_defaults()
        configure_structlog()
        # The configured processors are accessible via the config.
        config = structlog.get_config()
        processors = config["processors"]
        # Verify redact_secret_keys is in the chain (by identity or name).
        names = [getattr(p, "__name__", repr(p)) for p in processors]
        assert "redact_secret_keys" in names, (
            f"redact_secret_keys not in structlog processors: {names}"
        )