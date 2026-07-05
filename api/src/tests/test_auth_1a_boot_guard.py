"""Slice 1a — JWT_SECRET boot guard wired into app startup.

Covers the CRITICAL gap surfaced in sdd-verify: ``load_config()`` in
``src/shared/config.py`` raises ``ConfigError`` in production mode
(``USE_APP_CONFIG_SECRET=1``) when ``JWT_SECRET`` is missing, but
``app.py``'s lifespan never called ``load_config()`` — so the server could
boot in production without a JWT signing secret.

Scenarios:
- Lifespan raises ConfigError in prod mode without JWT_SECRET (boot guard fires)
- Lifespan boots in dev mode without JWT_SECRET (fallback secret tolerated)
- Lifespan boots in prod mode with JWT_SECRET present
- Loaded AuthConfig is cached on app.state.config for slice 1b (JWT service)
"""

import os
import types
from unittest.mock import AsyncMock, patch

import pytest

from src.shared.config import AuthConfig, ConfigError


def _fake_app() -> types.SimpleNamespace:
    """A minimal stand-in for FastAPI with a writable ``state`` namespace."""
    return types.SimpleNamespace(state=types.SimpleNamespace())


class TestLifespanBootGuard:
    """The app lifespan MUST call load_config() so the production boot guard
    actually executes at startup (fail-fast on missing JWT_SECRET)."""

    async def test_lifespan_raises_in_prod_without_jwt_secret(self):
        """GIVEN USE_APP_CONFIG_SECRET=1 and no JWT_SECRET in env
        WHEN the lifespan starts
        THEN ConfigError is raised and the app refuses to boot."""
        with patch.dict(os.environ, {"USE_APP_CONFIG_SECRET": "1"}, clear=False):
            os.environ.pop("JWT_SECRET", None)
            with (
                patch("app.init_db", AsyncMock()),
                patch("app.close_db", AsyncMock()),
                patch("app._init_assets_service"),
                patch("app._wire_asset_resolver"),
            ):
                from app import lifespan

                with pytest.raises(ConfigError, match="JWT_SECRET"):
                    async with lifespan(_fake_app()):
                        pass

    async def test_lifespan_boots_in_dev_without_jwt_secret(self):
        """GIVEN no USE_APP_CONFIG_SECRET flag and no JWT_SECRET
        WHEN the lifespan starts
        THEN it does NOT raise (dev fallback secret is tolerated)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("USE_APP_CONFIG_SECRET", None)
            os.environ.pop("JWT_SECRET", None)
            with (
                patch("app.init_db", AsyncMock()),
                patch("app.close_db", AsyncMock()),
                patch("app._init_assets_service"),
                patch("app._wire_asset_resolver"),
            ):
                from app import lifespan

                # Should not raise — dev mode tolerates a missing secret.
                async with lifespan(_fake_app()):
                    pass

    async def test_lifespan_boots_in_prod_with_jwt_secret(self):
        """GIVEN USE_APP_CONFIG_SECRET=1 and JWT_SECRET present
        WHEN the lifespan starts
        THEN it boots without raising."""
        with patch.dict(
            os.environ,
            {"USE_APP_CONFIG_SECRET": "1", "JWT_SECRET": "prod-secret"},
            clear=False,
        ):
            with (
                patch("app.init_db", AsyncMock()),
                patch("app.close_db", AsyncMock()),
                patch("app._init_assets_service"),
                patch("app._wire_asset_resolver"),
            ):
                from app import lifespan

                async with lifespan(_fake_app()):
                    pass

    async def test_lifespan_caches_config_on_app_state(self):
        """GIVEN a successful boot in prod mode with JWT_SECRET
        WHEN the lifespan completes startup
        THEN the loaded AuthConfig is cached on app.state.config for slice 1b."""
        fake = _fake_app()
        with patch.dict(
            os.environ,
            {"USE_APP_CONFIG_SECRET": "1", "JWT_SECRET": "prod-secret"},
            clear=False,
        ):
            with (
                patch("app.init_db", AsyncMock()),
                patch("app.close_db", AsyncMock()),
                patch("app._init_assets_service"),
                patch("app._wire_asset_resolver"),
            ):
                from app import lifespan

                async with lifespan(fake):
                    pass

        assert isinstance(fake.state.config, AuthConfig)
        assert fake.state.config.jwt_secret == "prod-secret"