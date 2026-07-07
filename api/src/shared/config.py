"""Application configuration for the AI-Studio API.

Reads auth-related configuration (JWT_SECRET, EMAIL_PROVIDER,
RESEND_API_KEY, APP_BASE_URL, CORS_ORIGINS) from the environment.

Boot guard:
    In production mode (``USE_APP_CONFIG_SECRET=1``) the server MUST refuse
    to boot when ``JWT_SECRET`` is missing. In dev mode a fallback secret is
    generated so local development works without operator action.

The secret MUST NOT be logged, echoed, or returned in any response.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    """Raised when the application cannot boot because required config is missing.

    This is a fatal boot-time error — the server MUST NOT start when this is
    raised. It is intentionally a ``RuntimeError`` subclass (not ``AppError``)
    because it is a startup failure, not a request error.
    """


_DEFAULT_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
_DEV_FALLBACK_SECRET_LENGTH: int = 64


@dataclass(frozen=True)
class AuthConfig:
    """Immutable snapshot of auth-related application configuration.

    Attributes:
        jwt_secret: HS256 signing secret for access tokens. In production this
            MUST come from the ``app-config`` Modal secret. In dev a random
            fallback is generated so the server boots locally.
        email_provider: ``"dev"`` (structlog print) or ``"resend"`` (HTTP POST).
        resend_api_key: Resend API key when ``email_provider == "resend"``;
            ``None`` in dev mode.
        app_base_url: Frontend base URL used to build verification email links.
        cors_origins: Explicit allowlist of CORS origins (no wildcard).
    """

    jwt_secret: str
    email_provider: str = "dev"
    resend_api_key: str | None = None
    app_base_url: str = ""
    cors_origins: list[str] = field(default_factory=lambda: list(_DEFAULT_CORS_ORIGINS))


def _is_production(env: dict[str, str]) -> bool:
    """Return True when the ``app-config`` Modal secret is opted in.

    Per the existing pattern in ``modal_config.py``, production configuration
    is gated behind ``USE_APP_CONFIG_SECRET=1`` so local ``modal serve`` does
    not require production credentials.
    """
    return env.get("USE_APP_CONFIG_SECRET") == "1"


def load_config(env: dict[str, str] | None = None) -> AuthConfig:
    """Build an :class:`AuthConfig` from the given (or process) environment.

    Args:
        env: Optional explicit environment mapping. When ``None``, reads from
            ``os.environ`` so callers (and tests) can inject a controlled env.

    Raises:
        ConfigError: In production mode (``USE_APP_CONFIG_SECRET=1``) when
            ``JWT_SECRET`` is missing or empty.
    """
    source = env if env is not None else os.environ
    production = _is_production(source)

    jwt_secret = source.get("JWT_SECRET", "").strip()
    if not jwt_secret:
        if production:
            raise ConfigError(
                "JWT_SECRET is required in production (USE_APP_CONFIG_SECRET=1). "
                "Set it in the Modal 'app-config' secret."
            )
        # Dev fallback: a random secret so local dev boots without operator action.
        jwt_secret = secrets.token_urlsafe(_DEV_FALLBACK_SECRET_LENGTH)

    email_provider = source.get("EMAIL_PROVIDER", "dev").strip() or "dev"
    resend_api_key = source.get("RESEND_API_KEY") or None
    resend_api_key = resend_api_key.strip() if resend_api_key else None
    app_base_url = source.get("APP_BASE_URL", "").strip()

    raw_cors = source.get("CORS_ORIGINS", "")
    if raw_cors.strip():
        cors_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
    else:
        cors_origins = list(_DEFAULT_CORS_ORIGINS)

    return AuthConfig(
        jwt_secret=jwt_secret,
        email_provider=email_provider,
        resend_api_key=resend_api_key,
        app_base_url=app_base_url,
        cors_origins=cors_origins,
    )