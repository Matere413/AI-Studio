"""Slice 2 — GET /projects owner_id filtering (verify-fix, surgical).

Spec: workspace-projects — authenticated ``GET /projects`` returns projects
where ``owner_id = user.id``; anonymous ``GET /projects`` continues with
``session_id`` (anonymous coexistence binding).

The sdd-verify pass on slice 2 surfaced 1 CRITICAL: ``GET /projects`` still
filtered only by ``session_id`` for authenticated users. These tests are
written FIRST (RED) — the endpoint currently uses ``_require_session`` +
``service.list_projects(session_id=...)`` regardless of authentication.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.assets.router import init_assets
from src.features.assets.service import AssetsService
from src.features.auth.infrastructure.email_client import DevEmailClient
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Base, async_session_factory, Project
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_listing.db"
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
def refresh_store(session_factory) -> RefreshTokenStore:
    return RefreshTokenStore(session_factory=session_factory)


@pytest.fixture
def ev_store(session_factory) -> EmailVerificationStore:
    return EmailVerificationStore(session_factory=session_factory)


@pytest.fixture
def email_client() -> DevEmailClient:
    return DevEmailClient(app_base_url="https://app.test")


@pytest.fixture
def assets_service(session_factory) -> AssetsService:
    return AssetsService(session_factory=session_factory, storage=None)


@pytest.fixture
def app(
    session_factory,
    jwt_service,
    refresh_store,
    ev_store,
    email_client,
    assets_service,
):
    from src.features.auth.presentation.router import build_auth_router
    from src.features.auth.presentation.dependencies import init_auth_providers

    init_auth_providers(
        session_factory=session_factory,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        email_verification_store=ev_store,
        email_client=email_client,
    )
    init_assets(assets_service)
    _app = __import__("fastapi").FastAPI()
    register_app_error_handlers(_app)
    _app.include_router(build_auth_router())
    from src.features.assets.router import router as assets_router

    _app.include_router(assets_router)
    return _app


@pytest.fixture
def client(app):
    return LazyTestClient(app)


def _strong_pw() -> str:
    return "CorrectHorse42!"


def _extract_cookies(response) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for raw in response.headers.get_list("set-cookie"):
        head = raw.split(";", 1)[0]
        if "=" not in head:
            continue
        name, _, value = head.partition("=")
        cookies[name.strip()] = value.strip()
    return cookies


def _register(client, email: str = "alice@test.io"):
    return client.post(
        "/auth/register", json={"email": email, "password": _strong_pw()}
    )


def _login(client, email: str = "alice@test.io") -> str:
    resp = client.post(
        "/auth/login", json={"email": email, "password": _strong_pw()}
    )
    return _extract_cookies(resp)["ai-studio-auth"]


def _verify_user(session_factory, email: str):
    """Mark a user verified directly (bypass email flow)."""
    import asyncio

    async def _go():
        async with session_factory() as session:
            u = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one()
            u.email_verified = True
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_go())


# ─── GET /projects owner_id filtering ─────────────────────────────────────────


class TestGetProjectsOwnerFiltering:
    """Spec: workspace-projects — authenticated listing by owner_id."""

    def test_authenticated_user_lists_own_projects_by_owner_id(
        self, client, session_factory
    ):
        """GIVEN a verified user with claimed projects (owner_id = user.id)
        WHEN GET /projects with the auth cookie
        THEN the response lists only that user's projects (filtered by
        owner_id), NOT other projects that happen to share the session_id."""
        # 1. Register + verify + login Alice.
        _register(client, "alice@test.io")
        access_a = _login(client, "alice@test.io")
        _verify_user(session_factory, "alice@test.io")
        access_a = _login(client, "alice@test.io")

        # 2. Alice creates two projects (authenticated path → owner_id = Alice).
        for name in ["Alice A", "Alice B"]:
            resp = client.post(
                "/projects",
                json={"name": name},
                cookies={"ai-studio-auth": access_a},
            )
            assert resp.status_code == 201, resp.text

        # 3. Independently create a project on the SAME session_id but owned
        #    by nobody (anonymous project). Use the service directly so we
        #    control the session_id binding without logging Alice out.
        import asyncio
        from src.features.assets.service import AssetsService as _Svc

        svc = _Svc(session_factory=session_factory, storage=None)

        async def _seed_foreign():
            # Alice's projects were saved with session_id = Alice's user id
            # (the authenticated path uses `session_id or user.id`). Find
            # Alice's user id to reuse it for the foreign anon project.
            async with session_factory() as session:
                u = (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()
                alice_session = u.id  # the session_id Alice's projects carry
            # Create an anonymous project on the same session_id, owner_id=None.
            await svc.create_project(
                name="Foreign Anon",
                session_id=alice_session,
                owner_id=None,
            )

        asyncio.get_event_loop().run_until_complete(_seed_foreign())

        # 4. Alice lists her projects via GET /projects with the auth cookie.
        resp = client.get(
            "/projects",
            cookies={"ai-studio-auth": access_a},
        )
        assert resp.status_code == 200, resp.text
        names = sorted(p["name"] for p in resp.json())
        # Only Alice's two projects — the foreign anonymous project must NOT
        # appear (it shares session_id but owner_id != Alice).
        assert names == ["Alice A", "Alice B"], names

    def test_anonymous_user_lists_session_scoped_projects(self, client):
        """GIVEN an anonymous visitor with projects bound to X-Session-ID=S1
        WHEN GET /projects with X-Session-ID: S1 (no auth cookie)
        THEN the response lists the session-scoped projects (existing
        anonymous behavior preserved)."""
        # 1. Anonymous visitor creates two projects via X-Session-ID.
        for name in ["Anon A", "Anon B"]:
            resp = client.post(
                "/projects",
                json={"name": name},
                headers={"X-Session-ID": "anon-session-1"},
            )
            assert resp.status_code == 201, resp.text

        # 2. GET /projects with the same X-Session-ID (no auth cookie).
        resp = client.get(
            "/projects",
            headers={"X-Session-ID": "anon-session-1"},
        )
        assert resp.status_code == 200, resp.text
        names = sorted(p["name"] for p in resp.json())
        assert names == ["Anon A", "Anon B"], names

    def test_anonymous_get_projects_without_session_returns_422(self, client):
        """GIVEN an anonymous visitor with no X-Session-ID
        WHEN GET /projects
        THEN 422 (the anonymous path still requires X-Session-ID)."""
        resp = client.get("/projects")
        assert resp.status_code == 422