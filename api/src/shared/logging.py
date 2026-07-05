"""Structured logging configuration for the AI-Studio API.

Configures structlog once at import time so that all modules
(including modal_tasks.py which is imported before app.py is fully
initialized) produce consistent JSON output to stdout.

Usage:
    from src.shared.logging import get_logger
    log = get_logger(__name__)
    log.info("event_name", key="value")

The processor chain includes ``redact_secret_keys`` so that secret fields
(password, token, authorization, set-cookie, cookie, password_hash) are
scrubbed from every log event before emission (api-security spec: Log
Sanitization).
"""

import logging
import structlog

from src.shared.security.redaction import redact_secret_keys


def configure_structlog() -> None:
    """Configure structlog for JSON output to stdout.

    Safe to call multiple times — idempotent via structlog.is_configured().
    """
    if structlog.is_configured():
        return

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Scrub secret keys (password, token, authorization, set-cookie,
            # cookie, password_hash) from every log event before rendering.
            redact_secret_keys,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Suppress noisy uvicorn / httpx access logs so they don't
    # compete with our structured JSON output.
    for name in ("uvicorn.access", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


# Configure once at import time so every module gets JSON output.
configure_structlog()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound with the given name."""
    return structlog.get_logger(name)
