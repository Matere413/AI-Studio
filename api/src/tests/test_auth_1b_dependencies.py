"""Slice 1b — Auth FastAPI dependencies (task 1b-4).

Covers the auth dependency contract from design.md:

- ``get_current_user`` — reads the ``ai-studio-auth`` cookie, validates the
  JWT, loads the user from DB, sets ``request.state.user``. Raises
  ``UnauthorizedError`` (401 unauthenticated) on missing/invalid token.
- ``require_verified_user`` — wraps ``get_current_user``, raises
  ``EmailNotVerifiedError`` (403 email_not_verified) when the user is not
  verified. Used by the slice 2 saving gate.
- ``get_optional_user`` — returns the user when authenticated, ``None`` when
  anonymous (the X-Session-ID path). Anonymous coexistence: auth is additive.

The dependencies coexist with the anonymous ``X-Session-ID`` path: a request
with no auth cookie does NOT raise from ``get_optional_user`` — it returns
``None`` so the existing generation endpoints behave identically.

These tests are written FIRST (RED) —
``src/features/auth/presentation/dependencies.py`` does not exist yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.errors import register_app_error_handlers
from src.shared.errors_auth import (
    EmailNotVerifiedError,
    UnauthorizedError,
)
from src.shared.models.persistence import Base, async_session_factory
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.presentation.dependencies import (
    CurrentUser,
    get_current_user,
    get_optional_user,
    require_verified_user,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_1b_deps.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = _create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_session_factory(db_engine)


@pytest.fixture
def jwt_service() -> JWTService:
    return JWTService(secret="test-secret-please-not-in-prod-xxx")


@pytest.fixture
async def verified_user(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            email="verified@test.io",
            password_hash="$argon2id$v",
            email_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.expunge(user)
        return user


@pytest.fixture
async def unverified_user(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            email="unverified@test.io",
            password_hash="$argon2id$u",
            email_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.expunge(user)
        return user


def _make_request(cookie_value: str | None) -> Request:
    """Build a Starlette Request with the given ``ai-studio-auth`` cookie."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "app": MagicMock(),
    }
    if cookie_value is not None:
        scope["headers"].append(
            (b"cookie", f"ai-studio-auth={cookie_value}".encode("latin-1"))
        )
    req = Request(scope)
    # Ensure request.state exists (the deps set request.state.user).
    return req


# ─── get_current_user ────────────────────────────────────────────────────────


class TestGetCurrentUser:
    """get_current_user reads the access cookie, validates, loads the user."""

    async def test_returns_user_for_valid_access_cookie(
        self, session_factory, jwt_service, verified_user
    ):
        """GIVEN a valid access cookie for a real user
        WHEN get_current_user is invoked
        THEN it returns a CurrentUser with the user's id/email/verified."""
        token = jwt_service.issue_access(verified_user)
        request = _make_request(token)
        user = await get_current_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert user.id == verified_user.id
        assert user.email == verified_user.email
        assert user.email_verified is True

    async def test_sets_request_state_user(self, session_factory, jwt_service, verified_user):
        """GIVEN a successful get_current_user
        WHEN it returns
        THEN ``request.state.user`` is set to the CurrentUser."""
        token = jwt_service.issue_access(verified_user)
        request = _make_request(token)
        user = await get_current_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert request.state.user is user or request.state.user.id == user.id

    async def test_raises_unauthorized_when_no_cookie(self, session_factory, jwt_service):
        """GIVEN a request with no access cookie
        WHEN get_current_user is invoked
        THEN UnauthorizedError is raised (401 unauthenticated)."""
        request = _make_request(None)
        with pytest.raises(UnauthorizedError):
            await get_current_user(
                request=request,
                session_factory=session_factory,
                jwt_service=jwt_service,
            )

    async def test_raises_unauthorized_for_invalid_token(self, session_factory, jwt_service):
        """GIVEN a malformed token in the cookie
        WHEN get_current_user is invoked
        THEN UnauthorizedError is raised (401 unauthenticated)."""
        request = _make_request("not.a.valid.jwt")
        with pytest.raises(UnauthorizedError):
            await get_current_user(
                request=request,
                session_factory=session_factory,
                jwt_service=jwt_service,
            )

    async def test_raises_unauthorized_for_unknown_user_id(
        self, session_factory, jwt_service
    ):
        """GIVEN a valid JWT for a user that no longer exists
        WHEN get_current_user is invoked
        THEN UnauthorizedError is raised (401 unauthenticated)."""

        class _GhostUser:
            id = "00000000-0000-0000-0000-000000000000"
            email = "ghost@test.io"
            email_verified = True

        token = jwt_service.issue_access(_GhostUser())
        request = _make_request(token)
        with pytest.raises(UnauthorizedError):
            await get_current_user(
                request=request,
                session_factory=session_factory,
                jwt_service=jwt_service,
            )

    async def test_reflects_email_verified_change(
        self, session_factory, jwt_service, unverified_user
    ):
        """GIVEN a user who verifies their email AFTER a token was issued
        WHEN get_current_user reloads the user from DB
        THEN the returned CurrentUser.email_verified reflects the DB state
        (not the stale JWT claim) — the saving gate must check the DB, not
        the token."""
        # Token issued while user is unverified.
        token = jwt_service.issue_access(unverified_user)
        # User verifies their email in the DB after the token was issued.
        async with session_factory() as session:
            from sqlalchemy import update as _upd
            from src.features.auth.infrastructure.models import User as _U

            await session.execute(
                _upd(_U).where(_U.id == unverified_user.id).values(email_verified=True)
            )
            await session.commit()

        request = _make_request(token)
        user = await get_current_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        # The DB reload reflects the post-issuance verification.
        assert user.email_verified is True


# ─── get_optional_user ───────────────────────────────────────────────────────


class TestGetOptionalUser:
    """get_optional_user returns User | None — anonymous coexistence."""

    async def test_returns_none_when_no_cookie(self, session_factory, jwt_service):
        """GIVEN a request with no access cookie
        WHEN get_optional_user is invoked
        THEN it returns None (anonymous — NOT an error)."""
        request = _make_request(None)
        user = await get_optional_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert user is None

    async def test_returns_user_when_valid_cookie(
        self, session_factory, jwt_service, verified_user
    ):
        """GIVEN a valid access cookie
        WHEN get_optional_user is invoked
        THEN it returns the CurrentUser."""
        token = jwt_service.issue_access(verified_user)
        request = _make_request(token)
        user = await get_optional_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert user is not None
        assert user.id == verified_user.id

    async def test_returns_none_for_invalid_token(self, session_factory, jwt_service):
        """GIVEN an invalid token
        WHEN get_optional_user is invoked
        THEN it returns None (anonymous fallback, no raise)."""
        request = _make_request("garbage.token.value")
        user = await get_optional_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert user is None


# ─── require_verified_user ───────────────────────────────────────────────────


class TestRequireVerifiedUser:
    """require_verified_user raises EmailNotVerifiedError when not verified."""

    async def test_returns_user_when_verified(
        self, session_factory, jwt_service, verified_user
    ):
        """GIVEN a verified user's access cookie
        WHEN require_verified_user is invoked
        THEN it returns the CurrentUser (verified)."""
        token = jwt_service.issue_access(verified_user)
        request = _make_request(token)
        user = await require_verified_user(
            request=request,
            session_factory=session_factory,
            jwt_service=jwt_service,
        )
        assert user.id == verified_user.id
        assert user.email_verified is True

    async def test_raises_email_not_verified_when_unverified(
        self, session_factory, jwt_service, unverified_user
    ):
        """GIVEN an unverified user's access cookie
        WHEN require_verified_user is invoked
        THEN EmailNotVerifiedError is raised (403 email_not_verified)."""
        token = jwt_service.issue_access(unverified_user)
        request = _make_request(token)
        with pytest.raises(EmailNotVerifiedError):
            await require_verified_user(
                request=request,
                session_factory=session_factory,
                jwt_service=jwt_service,
            )

    async def test_raises_unauthorized_when_no_cookie(self, session_factory, jwt_service):
        """GIVEN no access cookie
        WHEN require_verified_user is invoked
        THEN UnauthorizedError is raised (401 — unauthenticated takes
        precedence over email_not_verified)."""
        request = _make_request(None)
        with pytest.raises(UnauthorizedError):
            await require_verified_user(
                request=request,
                session_factory=session_factory,
                jwt_service=jwt_service,
            )