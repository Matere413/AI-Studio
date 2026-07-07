"""Slice 1a — Auth config boot guard and env reads.

Covers api-security spec: JWT Secret Management (load from env, refuse
to boot in prod without it) and EMAIL_PROVIDER default.

Scenarios:
- Secret loaded from app-config (USE_APP_CONFIG_SECRET=1 + JWT_SECRET present)
- Missing secret blocks boot in prod
- EMAIL_PROVIDER defaults to "dev"
- RESEND_API_KEY / APP_BASE_URL / CORS_ORIGINS read from env
"""

import pytest

from src.shared.config import AuthConfig, ConfigError, load_config


class TestConfigLoadsFromEnv:
    """GIVEN env vars WHEN load_config THEN they populate AuthConfig."""

    def test_jwt_secret_loaded_from_env(self):
        """GIVEN JWT_SECRET in env
        WHEN load_config is called
        THEN config.jwt_secret equals that value.
        """
        cfg = load_config({"JWT_SECRET": "super-secret-value"})
        assert cfg.jwt_secret == "super-secret-value"

    def test_email_provider_defaults_to_dev(self):
        """GIVEN no EMAIL_PROVIDER in env
        WHEN load_config is called
        THEN config.email_provider == "dev".
        """
        cfg = load_config({"JWT_SECRET": "x"})
        assert cfg.email_provider == "dev"

    def test_email_provider_resend_when_set(self):
        """GIVEN EMAIL_PROVIDER=resend
        WHEN load_config is called
        THEN config.email_provider == "resend".
        """
        cfg = load_config({"JWT_SECRET": "x", "EMAIL_PROVIDER": "resend"})
        assert cfg.email_provider == "resend"

    def test_resend_api_key_read_from_env(self):
        """GIVEN RESEND_API_KEY in env
        WHEN load_config is called
        THEN config.resend_api_key equals that value.
        """
        cfg = load_config({"JWT_SECRET": "x", "RESEND_API_KEY": "re_abc123"})
        assert cfg.resend_api_key == "re_abc123"

    def test_resend_api_key_none_when_unset(self):
        """GIVEN no RESEND_API_KEY in env
        WHEN load_config is called
        THEN config.resend_api_key is None.
        """
        cfg = load_config({"JWT_SECRET": "x"})
        assert cfg.resend_api_key is None

    def test_app_base_url_read_from_env(self):
        """GIVEN APP_BASE_URL in env
        WHEN load_config is called
        THEN config.app_base_url equals that value.
        """
        cfg = load_config({"JWT_SECRET": "x", "APP_BASE_URL": "https://app.test"})
        assert cfg.app_base_url == "https://app.test"

    def test_cors_origins_parsed_as_list(self):
        """GIVEN CORS_ORIGINS with comma-separated values
        WHEN load_config is called
        THEN config.cors_origins is a list of stripped origins.
        """
        cfg = load_config({
            "JWT_SECRET": "x",
            "CORS_ORIGINS": "https://app.test, https://www.test",
        })
        assert cfg.cors_origins == ["https://app.test", "https://www.test"]

    def test_cors_origins_single_value(self):
        """GIVEN CORS_ORIGINS with one value
        WHEN load_config is called
        THEN config.cors_origins is a single-element list.
        """
        cfg = load_config({"JWT_SECRET": "x", "CORS_ORIGINS": "https://app.test"})
        assert cfg.cors_origins == ["https://app.test"]


class TestConfigBootGuard:
    """GIVEN production mode (USE_APP_CONFIG_SECRET=1)
    WHEN JWT_SECRET is missing
    THEN load_config raises ConfigError (refuses to boot).
    """

    def test_prod_without_jwt_secret_raises(self):
        """GIVEN USE_APP_CONFIG_SECRET=1 and no JWT_SECRET
        WHEN load_config is called
        THEN ConfigError is raised.
        """
        with pytest.raises(ConfigError):
            load_config({"USE_APP_CONFIG_SECRET": "1"})

    def test_prod_with_jwt_secret_boots(self):
        """GIVEN USE_APP_CONFIG_SECRET=1 and JWT_SECRET present
        WHEN load_config is called
        THEN config loads successfully.
        """
        cfg = load_config({"USE_APP_CONFIG_SECRET": "1", "JWT_SECRET": "prod-secret"})
        assert cfg.jwt_secret == "prod-secret"

    def test_dev_without_jwt_secret_does_not_raise(self):
        """GIVEN no USE_APP_CONFIG_SECRET flag and no JWT_SECRET
        WHEN load_config is called
        THEN it does NOT raise (dev mode tolerates missing secret).
        """
        cfg = load_config({})
        # Dev mode: a fallback secret is acceptable so local dev works.
        assert cfg.jwt_secret  # non-empty

    def test_prod_error_message_mentions_jwt_secret(self):
        """GIVEN prod mode without JWT_SECRET
        WHEN load_config raises
        THEN the error message references JWT_SECRET for operator clarity.
        """
        with pytest.raises(ConfigError, match="JWT_SECRET"):
            load_config({"USE_APP_CONFIG_SECRET": "1"})