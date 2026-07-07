"""Slice 2 — Save-blocking + PUT /projects (tasks 2-5, 2-6, 2-7).

Spec:
- email-verification — Save-Blocking Enforcement: POST /projects and
  PUT /projects/:id return ``403 email_not_verified`` when the
  authenticated user is unverified. Unauthenticated → ``401
  unauthenticated``. Anonymous generation stays (POST /projects works
  for anonymous via X-Session-ID).
- workspace-projects — Auth and Verification Gate: POST /projects + PUT
  /projects/:id require auth + verification. PUT additionally requires
  ownership (``owner_id = user.id``); non-owners get ``403 not_owner``.

These tests are written FIRST (RED) — the PUT endpoint does not exist
yet and POST /projects still uses the anonymous path only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.assets.exceptions import ProjectNotFoundError
from src.features.assets.models import ProjectUpdate
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
from src.shared.models.persistence import Base, async_session_factory
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_save.db"
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


def _login(client, email: str = "alice@test.io"):
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


# ─── ProjectUpdate schema ────────────────────────────────────────────────────


class TestProjectUpdateSchema:
    def test_project_update_only_name(self):
        """Binding: only `name` is updatable on Project."""
        # name is optional (can be None to skip update)
        update = ProjectUpdate()
        assert update.name is None
        update = ProjectUpdate(name="New Name")
        assert update.name == "New Name"

    def test_project_update_rejects_empty_name(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectUpdate(name="")

    def test_project_update_rejects_name_over_128(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectUpdate(name="A" * 129)


# ─── POST /projects save-blocking ────────────────────────────────────────────


class TestPostProjectsSaveBlocking:
    """Spec: email-verification Save-Blocking + workspace-projects gate."""

    def test_post_projects_unverified_returns_403_email_not_verified(self, client):
        """GIVEN an authenticated but unverified user
        WHEN POST /projects
        THEN 403 with {error: {code: "email_not_verified"}}."""
        _register(client)
        access = _login(client)
        resp = client.post(
            "/projects",
            json={"name": "Campaign A"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "email_not_verified"

    def test_post_projects_unauthenticated_no_session_returns_422(self, client):
        """GIVEN no auth cookie AND no X-Session-ID
        WHEN POST /projects
        THEN 422 (anonymous path still requires X-Session-ID; binding:
        anonymous generation stays via X-Session-ID)."""
        resp = client.post("/projects", json={"name": "Campaign A"})
        assert resp.status_code == 422

    def test_post_projects_verified_user_creates_project_with_owner(
        self, client, session_factory
    ):
        """GIVEN an authenticated verified user
        WHEN POST /projects
        THEN 201 with the new project (owner_id = user.id)."""
        _register(client)
        access = _login(client)
        _verify_user(session_factory, "alice@test.io")
        # Re-login to refresh the access cookie (email_verified reloaded from DB).
        access = _login(client)

        resp = client.post(
            "/projects",
            json={"name": "Campaign A"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "Campaign A"
        assert data["owner_id"]

    def test_post_projects_anonymous_still_works_with_session(self, client):
        """GIVEN an anonymous visitor with X-Session-ID
        WHEN POST /projects
        THEN 201 (anonymous generation stays)."""
        resp = client.post(
            "/projects",
            json={"name": "Anon Project"},
            headers={"X-Session-ID": "anon-session-1"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["owner_id"] is None
        assert data["session_id"] == "anon-session-1"


# ─── PUT /projects ────────────────────────────────────────────────────────────


class TestPutProjectsEndpoint:
    """Spec: workspace-projects — NEW PUT /projects/{id} endpoint."""

    def _create_owned_project(self, client, session_factory, email="alice@test.io"):
        _register(client, email)
        access = _login(client, email)
        _verify_user(session_factory, email)
        access = _login(client, email)
        resp = client.post(
            "/projects",
            json={"name": "Original Name"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 201
        return access, resp.json()["id"]

    def test_put_projects_updates_name_for_owner(self, client, session_factory):
        """GIVEN an authenticated verified owner
        WHEN PUT /projects/:id with a new name
        THEN 200 with the updated name."""
        access, project_id = self._create_owned_project(client, session_factory)
        resp = client.put(
            f"/projects/{project_id}",
            json={"name": "Renamed"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "Renamed"
        assert resp.json()["id"] == project_id

    def test_put_projects_unverified_returns_403_email_not_verified(
        self, client, session_factory
    ):
        """GIVEN an authenticated but unverified user
        WHEN PUT /projects/:id
        THEN 403 with {error: {code: "email_not_verified"}}."""
        _register(client, "alice@test.io")
        access = _login(client, "alice@test.io")
        # Don't verify — use an existing project id (any UUID is fine; we'll 403 first).
        resp = client.put(
            "/projects/00000000-0000-0000-0000-000000000000",
            json={"name": "X"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "email_not_verified"

    def test_put_projects_unauthenticated_returns_401(self, client):
        """GIVEN no auth cookie
        WHEN PUT /projects/:id
        THEN 401 with {error: {code: "unauthenticated"}}."""
        resp = client.put(
            "/projects/00000000-0000-0000-0000-000000000000",
            json={"name": "X"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthenticated"

    def test_put_projects_non_owner_returns_403_not_owner(
        self, client, session_factory
    ):
        """GIVEN user A owns project P
        WHEN user B (verified) PUTs /projects/P
        THEN 403 with {error: {code: "not_owner"}}."""
        access_a, project_id = self._create_owned_project(
            client, session_factory, email="alice@test.io"
        )
        # Register + verify user B.
        _register(client, "bob@test.io")
        access_b = _login(client, "bob@test.io")
        _verify_user(session_factory, "bob@test.io")
        access_b = _login(client, "bob@test.io")

        resp = client.put(
            f"/projects/{project_id}",
            json={"name": "Hijacked"},
            cookies={"ai-studio-auth": access_b},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "not_owner"

    def test_put_projects_unknown_id_returns_404(self, client, session_factory):
        """GIVEN a verified user + a non-existent project id
        WHEN PUT /projects/:id
        THEN 404."""
        _register(client, "alice@test.io")
        access = _login(client, "alice@test.io")
        _verify_user(session_factory, "alice@test.io")
        access = _login(client, "alice@test.io")
        resp = client.put(
            "/projects/00000000-0000-0000-0000-000000000000",
            json={"name": "X"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 404

    def test_put_projects_empty_name_returns_422(self, client, session_factory):
        """GIVEN a valid owner
        WHEN PUT /projects/:id with empty name
        THEN 422."""
        access, project_id = self._create_owned_project(client, session_factory)
        resp = client.put(
            f"/projects/{project_id}",
            json={"name": ""},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 422

    def test_put_projects_no_body_returns_200_no_change(self, client, session_factory):
        """GIVEN a valid owner + empty body
        WHEN PUT /projects/:id with no name
        THEN 200 with the unchanged project."""
        access, project_id = self._create_owned_project(client, session_factory)
        resp = client.put(
            f"/projects/{project_id}",
            json={},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 200, resp.text
        # Name unchanged.
        assert resp.json()["name"] == "Original Name"