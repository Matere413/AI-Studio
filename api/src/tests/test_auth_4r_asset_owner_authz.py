"""4R corrective pass — CRITICAL 1: authorize assets by owner_id.

Spec: workspace-projects — when a user logs in, anonymous projects are
claimed (``owner_id`` set). The asset endpoints (upload-ticket, finalize,
delete, R2 GET) MUST authorize by ``owner_id`` when the caller is
authenticated, and fall back to ``session_id`` for anonymous callers.

These tests are written FIRST (RED). They use a real DB + a fake storage
so the ownership check is exercised end-to-end through the router.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.assets.service import AssetsService
from src.features.auth.infrastructure.email_client import DevEmailClient
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Asset, Base, Project, async_session_factory
from src.shared.storage import R2Storage
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_4r_asset_owner.db"
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


def _fake_storage() -> AsyncMock:
    storage = AsyncMock(spec=R2Storage)
    storage.presigned_put.return_value = "https://r2.example.com/presigned-put-url"
    storage.object_exists.return_value = True
    storage.presigned_get.return_value = "https://r2.example.com/presigned-get-url"
    storage.mark_deleted.return_value = None
    return storage


@pytest.fixture
def assets_service(session_factory) -> AssetsService:
    return AssetsService(
        session_factory=session_factory,
        storage=_fake_storage(),
    )


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
    from src.features.assets.router import init_assets, router as assets_router

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

    async def _go():
        async with session_factory() as session:
            u = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one()
            u.email_verified = True
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_go())


def _create_owned_project(client, session_factory, email="alice@test.io"):
    """Register + verify + login + POST /projects. Returns (access, project_id)."""
    _register(client, email)
    _verify_user(session_factory, email)
    access = _login(client, email)
    resp = client.post(
        "/projects",
        json={"name": "Owned Project"},
        cookies={"ai-studio-auth": access},
    )
    assert resp.status_code == 201, resp.text
    return access, resp.json()["id"]


def _create_anon_project(client, session_id="anon-session-1"):
    """Create an anonymous project via X-Session-ID. Returns (session_id, project_id)."""
    resp = client.post(
        "/projects",
        json={"name": "Anon Project"},
        headers={"X-Session-ID": session_id},
    )
    assert resp.status_code == 201, resp.text
    return session_id, resp.json()["id"]


def _claim_anon_project_on_login(
    client, session_factory, email="bob@test.io", anon_session_id="anon-session-1"
):
    """Create an anon project, then register + login with X-Session-ID to claim it.
    Returns (access, project_id)."""
    # 1. Create an anonymous project bound to anon_session_id.
    client.post(
        "/projects",
        json={"name": "Anon Project"},
        headers={"X-Session-ID": anon_session_id},
    )
    # 2. Register + verify the user.
    _register(client, email)
    _verify_user(session_factory, email)
    # 3. Login WITH the anon X-Session-ID so the merge claims the anon project.
    resp = client.post(
        "/auth/login",
        json={"email": email, "password": _strong_pw()},
        headers={"X-Session-ID": anon_session_id},
    )
    assert resp.status_code == 200, resp.text
    access = _extract_cookies(resp)["ai-studio-auth"]
    # The anon project is now owned by this user. Find it via GET /projects.
    resp = client.get("/projects", cookies={"ai-studio-auth": access})
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1, f"expected 1 claimed project, got {len(projects)}"
    return access, projects[0]["id"]


# ─── CRITICAL 1: upload-ticket authorizes by owner_id for authenticated ─────────


class TestUploadTicketOwnerAuthz:
    """POST /projects/{id}/upload-ticket — authorize by owner_id (authed) or
    session_id (anon)."""

    def test_authenticated_owner_can_request_upload_ticket(
        self, client, session_factory
    ):
        """GIVEN an authenticated verified user who owns project P
        WHEN POST /projects/P/upload-ticket (no X-Session-ID)
        THEN 200 — authorized by owner_id."""
        access, project_id = _create_owned_project(client, session_factory)
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "asset_id" in data
        assert "presigned_url" in data

    def test_authenticated_non_owner_cannot_upload_to_others_project(
        self, client, session_factory
    ):
        """GIVEN user A owns project P
        WHEN user B (verified) POSTs /projects/P/upload-ticket
        THEN 403 — authorized by owner_id (B != A)."""
        _access_a, project_id = _create_owned_project(
            client, session_factory, email="alice@test.io"
        )
        _register(client, "bob@test.io")
        _verify_user(session_factory, "bob@test.io")
        access_b = _login(client, "bob@test.io")

        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            cookies={"ai-studio-auth": access_b},
        )
        assert resp.status_code == 403, resp.text

    def test_anonymous_session_can_request_upload_ticket(self, client):
        """GIVEN an anonymous project bound to X-Session-ID
        WHEN POST /projects/P/upload-ticket with that X-Session-ID
        THEN 200 — authorized by session_id (preserved)."""
        session_id, project_id = _create_anon_project(client)
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            headers={"X-Session-ID": session_id},
        )
        assert resp.status_code == 200, resp.text

    def test_anonymous_wrong_session_cannot_upload(self, client):
        """GIVEN an anon project bound to session-1
        WHEN POST /projects/P/upload-ticket with session-2
        THEN 403 — session_mismatch."""
        _session_id, project_id = _create_anon_project(client, "anon-session-1")
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            headers={"X-Session-ID": "different-session"},
        )
        assert resp.status_code == 403, resp.text

    def test_claimed_anon_project_upload_works_for_owner(
        self, client, session_factory
    ):
        """GIVEN an anon project claimed on login (owner_id now set, session_id
        unchanged)
        WHEN the authenticated owner POSTs /projects/P/upload-ticket (no X-Session-ID)
        THEN 200 — authorized by owner_id (the CRITICAL 1 bug: previously 403
        because the endpoint only checked session_id, which the owner does
        not know)."""
        access, project_id = _claim_anon_project_on_login(
            client, session_factory, email="bob@test.io", anon_session_id="anon-session-1"
        )
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 200, resp.text


# ─── CRITICAL 1: finalize authorizes by owner_id for authenticated ─────────────


class TestFinalizeAssetOwnerAuthz:
    """PATCH /assets/{id}/finalize — authorize by owner_id (authed) or
    session_id (anon)."""

    def _upload_asset(self, client, access_or_headers, project_id):
        """Request an upload ticket and return the asset_id."""
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            **(
                {"cookies": {"ai-studio-auth": access_or_headers}}
                if isinstance(access_or_headers, str)
                else {"headers": access_or_headers}
            ),
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["asset_id"]

    def test_authenticated_owner_can_finalize(self, client, session_factory):
        """GIVEN an authenticated owner with a pending asset
        WHEN PATCH /assets/{id}/finalize (no X-Session-ID)
        THEN 200 — authorized by owner_id."""
        access, project_id = _create_owned_project(client, session_factory)
        asset_id = self._upload_asset(client, access, project_id)
        resp = client.patch(
            f"/assets/{asset_id}/finalize",
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 200, resp.text

    def test_authenticated_non_owner_cannot_finalize(self, client, session_factory):
        """GIVEN user A owns an asset
        WHEN user B PATCHes /assets/{id}/finalize
        THEN 403 — owner_id mismatch."""
        access_a, project_id = _create_owned_project(
            client, session_factory, email="alice@test.io"
        )
        asset_id = self._upload_asset(client, access_a, project_id)
        _register(client, "bob@test.io")
        _verify_user(session_factory, "bob@test.io")
        access_b = _login(client, "bob@test.io")
        resp = client.patch(
            f"/assets/{asset_id}/finalize",
            cookies={"ai-studio-auth": access_b},
        )
        assert resp.status_code == 403, resp.text

    def test_anonymous_session_can_finalize(self, client):
        """GIVEN an anon asset bound to X-Session-ID
        WHEN PATCH /assets/{id}/finalize with that X-Session-ID
        THEN 200 — authorized by session_id (preserved)."""
        session_id, project_id = _create_anon_project(client)
        asset_id = self._upload_asset(
            client, {"X-Session-ID": session_id}, project_id
        )
        resp = client.patch(
            f"/assets/{asset_id}/finalize",
            headers={"X-Session-ID": session_id},
        )
        assert resp.status_code == 200, resp.text


# ─── CRITICAL 1: delete authorizes by owner_id for authenticated ───────────────


class TestDeleteAssetOwnerAuthz:
    """DELETE /assets/{id} — authorize by owner_id (authed) or session_id (anon)."""

    def _upload_and_finalize(self, client, access_or_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            **(
                {"cookies": {"ai-studio-auth": access_or_headers}}
                if isinstance(access_or_headers, str)
                else {"headers": access_or_headers}
            ),
        )
        assert resp.status_code == 200, resp.text
        asset_id = resp.json()["asset_id"]
        finalize_resp = client.patch(
            f"/assets/{asset_id}/finalize",
            **(
                {"cookies": {"ai-studio-auth": access_or_headers}}
                if isinstance(access_or_headers, str)
                else {"headers": access_or_headers}
            ),
        )
        assert finalize_resp.status_code == 200, finalize_resp.text
        return asset_id

    def test_authenticated_owner_can_delete(self, client, session_factory):
        """GIVEN an authenticated owner with a finalized asset
        WHEN DELETE /assets/{id} (no X-Session-ID)
        THEN 204 — authorized by owner_id."""
        access, project_id = _create_owned_project(client, session_factory)
        asset_id = self._upload_and_finalize(client, access, project_id)
        resp = client.delete(
            f"/assets/{asset_id}",
            cookies={"ai-studio-auth": access},
        )
        assert resp.status_code == 204, resp.text

    def test_authenticated_non_owner_cannot_delete(self, client, session_factory):
        """GIVEN user A owns an asset
        WHEN user B DELETEs /assets/{id}
        THEN 403 — owner_id mismatch."""
        access_a, project_id = _create_owned_project(
            client, session_factory, email="alice@test.io"
        )
        asset_id = self._upload_and_finalize(client, access_a, project_id)
        _register(client, "bob@test.io")
        _verify_user(session_factory, "bob@test.io")
        access_b = _login(client, "bob@test.io")
        resp = client.delete(
            f"/assets/{asset_id}",
            cookies={"ai-studio-auth": access_b},
        )
        assert resp.status_code == 403, resp.text

    def test_anonymous_session_can_delete(self, client):
        """GIVEN an anon asset bound to X-Session-ID
        WHEN DELETE /assets/{id} with that X-Session-ID
        THEN 204 — authorized by session_id (preserved)."""
        session_id, project_id = _create_anon_project(client)
        asset_id = self._upload_and_finalize(
            client, {"X-Session-ID": session_id}, project_id
        )
        resp = client.delete(
            f"/assets/{asset_id}",
            headers={"X-Session-ID": session_id},
        )
        assert resp.status_code == 204, resp.text


# ─── CRITICAL 1: R2 GET authorizes by owner_id for authenticated ──────────────


class TestR2GetOwnerAuthz:
    """GET /r2/{r2_key} — authorize by owner_id (authed) or session_id (anon)."""

    def _upload_finalize_get_r2_key(self, client, access_or_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "img.webp", "content_type": "image/webp"},
            **(
                {"cookies": {"ai-studio-auth": access_or_headers}}
                if isinstance(access_or_headers, str)
                else {"headers": access_or_headers}
            ),
        )
        assert resp.status_code == 200, resp.text
        asset_id = resp.json()["asset_id"]
        r2_key = resp.json()["r2_key"]
        finalize_resp = client.patch(
            f"/assets/{asset_id}/finalize",
            **(
                {"cookies": {"ai-studio-auth": access_or_headers}}
                if isinstance(access_or_headers, str)
                else {"headers": access_or_headers}
            ),
        )
        assert finalize_resp.status_code == 200, finalize_resp.text
        return r2_key

    def test_authenticated_owner_can_get_r2_asset(self, client, session_factory):
        """GIVEN an authenticated owner with a finalized asset
        WHEN GET /r2/{r2_key} (no X-Session-ID)
        THEN 307 redirect — authorized by owner_id."""
        access, project_id = _create_owned_project(client, session_factory)
        r2_key = self._upload_finalize_get_r2_key(client, access, project_id)
        resp = client.get(
            f"/r2/{r2_key}",
            cookies={"ai-studio-auth": access},
            follow_redirects=False,
        )
        assert resp.status_code == 307, resp.text

    def test_authenticated_non_owner_cannot_get_r2_asset(
        self, client, session_factory
    ):
        """GIVEN user A owns an asset with r2_key K
        WHEN user B GETs /r2/K (no X-Session-ID)
        THEN 404 — owner_id mismatch (masked as not found)."""
        access_a, project_id = _create_owned_project(
            client, session_factory, email="alice@test.io"
        )
        r2_key = self._upload_finalize_get_r2_key(client, access_a, project_id)
        _register(client, "bob@test.io")
        _verify_user(session_factory, "bob@test.io")
        access_b = _login(client, "bob@test.io")
        resp = client.get(
            f"/r2/{r2_key}",
            cookies={"ai-studio-auth": access_b},
            follow_redirects=False,
        )
        # Non-owner is masked as not found (404).
        assert resp.status_code == 404, resp.text

    def test_anonymous_session_can_get_r2_asset(self, client):
        """GIVEN an anon asset bound to X-Session-ID
        WHEN GET /r2/{r2_key} with that X-Session-ID
        THEN 307 redirect — authorized by session_id (preserved)."""
        session_id, project_id = _create_anon_project(client)
        r2_key = self._upload_finalize_get_r2_key(
            client, {"X-Session-ID": session_id}, project_id
        )
        resp = client.get(
            f"/r2/{r2_key}",
            headers={"X-Session-ID": session_id},
            follow_redirects=False,
        )
        assert resp.status_code == 307, resp.text