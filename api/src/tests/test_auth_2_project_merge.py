"""Slice 2 — Anonymous → authenticated project merge on login (task 2-8).

Spec: workspace-projects — Anonymous-to-Authenticated Project Merge.

On first successful login, the system MUST reassign projects where
``session_id`` matches the client's current ``X-Session-ID`` AND
``owner_id IS NULL`` to ``owner_id = user.id``. One-time merge.

These tests are written FIRST (RED) — login_user does not yet perform the
merge.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.assets.exceptions import ProjectNotFoundError
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
    db_file = tmp_path / "auth_2_merge.db"
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
    from src.features.assets.router import init_assets

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


# ─── Project merge on login ───────────────────────────────────────────────────


class TestProjectMergeOnLogin:
    """Spec: Anonymous-to-Authenticated Project Merge."""

    def test_anonymous_projects_claimed_on_login(
        self, client, session_factory
    ):
        """GIVEN an anonymous visitor with projects bound to X-Session-ID=S1
        WHEN the visitor logs in (sending both X-Session-ID: S1 + credentials)
        THEN all matching projects get owner_id = user.id."""
        # 1. Anonymous visitor creates projects via X-Session-ID.
        for name in ["Anon A", "Anon B"]:
            resp = client.post(
                "/projects",
                json={"name": name},
                headers={"X-Session-ID": "session-1"},
            )
            assert resp.status_code == 201, resp.text

        # 2. Register (also creates an anonymous project? No — register
        #    does not create projects. The user row is created here.)
        client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        # 3. Login with X-Session-ID present → merge fires.
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": _strong_pw()},
            headers={"X-Session-ID": "session-1"},
        )
        assert resp.status_code == 200, resp.text

        # 4. Both anonymous projects should now have owner_id = user.id.
        import asyncio

        async def _check():
            async with session_factory() as session:
                u = (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()
                stmt = select(Project).where(Project.session_id == "session-1")
                projects = (await session.execute(stmt)).scalars().all()
                assert len(projects) == 2
                for p in projects:
                    assert p.owner_id == u.id

        asyncio.get_event_loop().run_until_complete(_check())

    def test_no_merge_when_session_mismatch(self, client, session_factory):
        """GIVEN a user logs in without X-Session-ID (or with unknown session)
        WHEN login completes
        THEN no projects are merged (no row matches session_id)."""
        # Create anonymous project on session-1.
        resp = client.post(
            "/projects",
            json={"name": "Anon A"},
            headers={"X-Session-ID": "session-1"},
        )
        assert resp.status_code == 201

        # Register + login WITHOUT X-Session-ID.
        client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        assert resp.status_code == 200

        import asyncio

        async def _check():
            async with session_factory() as session:
                stmt = select(Project).where(Project.session_id == "session-1")
                projects = (await session.execute(stmt)).scalars().all()
                assert len(projects) == 1
                # owner_id still NULL (no merge).
                assert projects[0].owner_id is None

        asyncio.get_event_loop().run_until_complete(_check())

    def test_merge_does_not_claim_already_owned_projects(
        self, client, session_factory
    ):
        """GIVEN a project with owner_id already set
        WHEN login with matching X-Session-ID
        THEN that project is NOT reassigned (only owner_id IS NULL rows)."""
        # Create an anonymous project on session-1.
        resp = client.post(
            "/projects",
            json={"name": "Anon A"},
            headers={"X-Session-ID": "session-1"},
        )
        anon_project_id = resp.json()["id"]

        # Register + verify user A.
        client.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": _strong_pw()},
        )
        import asyncio

        async def _verify_a():
            async with session_factory() as session:
                u = (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()
                u.email_verified = True
                await session.commit()

        asyncio.get_event_loop().run_until_complete(_verify_a())

        # Login user A (claims the anon project via merge).
        resp = client.post(
            "/auth/login",
            json={"email": "alice@test.io", "password": _strong_pw()},
            headers={"X-Session-ID": "session-1"},
        )
        assert resp.status_code == 200

        # Now register + login user B with the SAME X-Session-ID.
        # The merge should NOT reassign the project (owner_id is now set).
        client.post(
            "/auth/register",
            json={"email": "bob@test.io", "password": _strong_pw()},
        )
        resp = client.post(
            "/auth/login",
            json={"email": "bob@test.io", "password": _strong_pw()},
            headers={"X-Session-ID": "session-1"},
        )
        assert resp.status_code == 200

        async def _check():
            async with session_factory() as session:
                stmt = select(Project).where(Project.id == anon_project_id)
                p = (await session.execute(stmt)).scalar_one()
                # Still owned by alice (the first claim).
                u = (
                    await session.execute(
                        select(User).where(User.email == "alice@test.io")
                    )
                ).scalar_one()
                assert p.owner_id == u.id

        asyncio.get_event_loop().run_until_complete(_check())