"""Integration tests for the Assets API endpoints.

Covers the full Project + Asset lifecycle:
- POST /projects — Create a project
- GET /projects — List projects for the caller's session
- POST /projects/{id}/upload-ticket — Request a presigned PUT URL
- PATCH /assets/{id}/finalize — Confirm an upload
- DELETE /assets/{id} — Soft-delete an asset

All endpoints enforce ``X-Session-ID`` for session-scoped ownership.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from datetime import datetime, timezone

from src.features.assets.exceptions import (
    AssetNotFoundError,
    ProjectNotFoundError,
    ProjectOwnershipError,
    StorageNotConfiguredError,
    StorageOperationError,
)
from src.shared.errors import register_app_error_handlers
from src.shared.models.persistence import Project, Asset
from src.tests.client_helpers import LazyTestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_service():
    """Replace the router's module-level ``_service`` with a clean mock.

    Each test gets a fresh ``AsyncMock`` instance that covers all service
    methods used by the router endpoints.  Tests that need specific return
    values or side effects can override the relevant method on this mock.
    """
    svc = AsyncMock()
    svc.create_project = AsyncMock()
    svc.list_projects = AsyncMock()
    svc.request_upload_ticket = AsyncMock()
    svc.finalize_asset = AsyncMock()
    svc.soft_delete_asset = AsyncMock()
    svc.get_asset_by_r2_key = AsyncMock()

    with patch("src.features.assets.router._service", svc):
        yield svc


@pytest.fixture
def app():
    """Return a FastAPI test app with only the assets router mounted."""
    from src.features.assets.router import router as assets_router

    _app = FastAPI()
    register_app_error_handlers(_app)
    _app.include_router(assets_router)
    return _app


@pytest.fixture
def client(app):
    """Return a ``LazyTestClient`` pointed at the test app."""
    return LazyTestClient(app)


# ─── Test data helpers ────────────────────────────────────────────────────────


def make_project_data(
    project_id: str | None = None,
    name: str = "Campaign A",
    owner_id: str | None = "user-abc",
    session_id: str = "session-abc",
) -> dict:
    """Return a dict shaped like a ``Project`` ORM object (as returned by the
    service layer).  The service returns dicts so the router does not depend on
    SQLAlchemy models."""
    return {
        "id": project_id or str(uuid4()),
        "name": name,
        "owner_id": owner_id,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [],
    }


def make_asset_data(
    asset_id: str | None = None,
    name: str = "portrait.webp",
    content_type: str = "image/webp",
    r2_key: str | None = None,
    project_id: str | None = None,
) -> dict:
    """Return a dict shaped like an ``Asset`` response."""
    return {
        "id": asset_id or str(uuid4()),
        "name": name,
        "content_type": content_type,
        "r2_key": r2_key or f"projects/{project_id or 'unknown'}/{name}",
        "project_id": project_id or str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ==============================================================================
# POST /projects
# ==============================================================================


class TestCreateProject:
    """POST /projects — Create a project bound to the caller's session."""

    def test_creates_project_and_returns_201(self, client, mock_service):
        """GIVEN a valid name and X-Session-ID
        WHEN POST /projects
        THEN 201 Created with project data.
        """
        expected = make_project_data(name="Campaign A", session_id="session-abc")
        mock_service.create_project.return_value = expected

        response = client.post(
            "/projects",
            json={"name": "Campaign A"},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Campaign A"
        assert data["session_id"] == "session-abc"
        assert "id" in data
        mock_service.create_project.assert_awaited_once_with(
            name="Campaign A",
            session_id="session-abc",
        )

    def test_rejects_empty_name(self, client, mock_service):
        """GIVEN an empty name
        WHEN POST /projects
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/projects",
            json={"name": ""},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 422
        mock_service.create_project.assert_not_called()

    def test_rejects_name_over_128_chars(self, client, mock_service):
        """GIVEN a name longer than 128 characters
        WHEN POST /projects
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/projects",
            json={"name": "A" * 129},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 422
        mock_service.create_project.assert_not_called()

    def test_rejects_missing_session_id(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN POST /projects
        THEN 422 Unprocessable Entity (empty session not allowed).
        """
        response = client.post(
            "/projects",
            json={"name": "Campaign A"},
        )

        assert response.status_code == 422
        mock_service.create_project.assert_not_called()


# ==============================================================================
# GET /projects
# ==============================================================================


class TestListProjects:
    """GET /projects — List projects for the caller's session."""

    def test_returns_projects_for_session(self, client, mock_service):
        """GIVEN projects exist for the caller's session
        WHEN GET /projects with matching X-Session-ID
        THEN 200 with a list of projects (newest first).
        """
        projects = [
            make_project_data(name="Campaign B", session_id="session-abc"),
            make_project_data(name="Campaign A", session_id="session-abc"),
        ]
        mock_service.list_projects.return_value = projects

        response = client.get(
            "/projects",
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Campaign B"
        assert data[1]["name"] == "Campaign A"
        mock_service.list_projects.assert_awaited_once_with(session_id="session-abc")

    def test_returns_empty_list_when_no_projects(self, client, mock_service):
        """GIVEN no projects for the caller's session
        WHEN GET /projects
        THEN 200 with an empty list.
        """
        mock_service.list_projects.return_value = []

        response = client.get(
            "/projects",
            headers={"X-Session-ID": "session-empty"},
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_rejects_missing_session_id(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN GET /projects
        THEN 422 Unprocessable Entity.
        """
        response = client.get("/projects")
        assert response.status_code == 422
        mock_service.list_projects.assert_not_called()


# ==============================================================================
# POST /projects/{id}/upload-ticket
# ==============================================================================


class TestUploadTicket:
    """POST /projects/{id}/upload-ticket — Request a presigned PUT URL."""

    def test_returns_upload_ticket(self, client, mock_service):
        """GIVEN a valid project owned by the caller
        WHEN POST /projects/{id}/upload-ticket
        THEN 200 with asset_id, presigned_url, and r2_key.
        """
        project_id = str(uuid4())
        expected = {
            "asset_id": str(uuid4()),
            "presigned_url": "https://r2.example.com/presigned-put-url",
            "r2_key": f"projects/{project_id}/portrait.webp",
        }
        mock_service.request_upload_ticket.return_value = expected

        response = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "portrait.webp", "content_type": "image/webp"},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["asset_id"] == expected["asset_id"]
        assert "presigned_url" in data and data["presigned_url"].startswith("https://")
        assert "r2_key" in data
        mock_service.request_upload_ticket.assert_awaited_once_with(
            project_id=project_id,
            asset_name="portrait.webp",
            session_id="session-abc",
            content_type="image/webp",
        )

    def test_uses_default_content_type(self, client, mock_service):
        """GIVEN no content_type in the request body
        WHEN POST /projects/{id}/upload-ticket
        THEN the service receives content_type="image/webp".
        """
        project_id = str(uuid4())
        mock_service.request_upload_ticket.return_value = {
            "asset_id": str(uuid4()),
            "presigned_url": "https://r2.example.com/put",
            "r2_key": f"projects/{project_id}/asset.webp",
        }

        client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "asset.webp"},
            headers={"X-Session-ID": "session-abc"},
        )

        call_kwargs = mock_service.request_upload_ticket.call_args.kwargs
        assert call_kwargs["content_type"] == "image/webp"

    def test_rejects_empty_asset_name(self, client, mock_service):
        """GIVEN an empty asset_name
        WHEN POST /projects/{id}/upload-ticket
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            f"/projects/{str(uuid4())}/upload-ticket",
            json={"asset_name": ""},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 422
        mock_service.request_upload_ticket.assert_not_called()

    def test_rejects_missing_project_id(self, client, mock_service):
        """GIVEN a non-existent project_id
        WHEN POST /projects/{id}/upload-ticket
        THEN 404 Not Found.
        """
        mock_service.request_upload_ticket.side_effect = ProjectNotFoundError("Project x not found")

        response = client.post(
            f"/projects/{str(uuid4())}/upload-ticket",
            json={"asset_name": "portrait.webp"},
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "project_not_found"

    def test_rejects_session_mismatch(self, client, mock_service):
        """GIVEN a project owned by a different session
        WHEN POST /projects/{id}/upload-ticket with a mismatched session
        THEN 403 Forbidden.
        """
        mock_service.request_upload_ticket.side_effect = ProjectOwnershipError("mismatch")

        response = client.post(
            f"/projects/{str(uuid4())}/upload-ticket",
            json={"asset_name": "portrait.webp"},
            headers={"X-Session-ID": "session-wrong"},
        )

        assert response.status_code == 403

    def test_rejects_missing_session_id(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN POST /projects/{id}/upload-ticket
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            f"/projects/{str(uuid4())}/upload-ticket",
            json={"asset_name": "portrait.webp"},
        )

        assert response.status_code == 422
        mock_service.request_upload_ticket.assert_not_called()


# ==============================================================================
# PATCH /assets/{id}/finalize
# ==============================================================================


class TestFinalizeAsset:
    """PATCH /assets/{id}/finalize — Confirm an upload completed."""

    def test_finalizes_asset_and_returns_200(self, client, mock_service):
        """GIVEN an asset owned by the caller
        WHEN PATCH /assets/{id}/finalize
        THEN 200 with the finalized asset data.
        """
        asset_id = str(uuid4())
        expected = make_asset_data(asset_id=asset_id)
        mock_service.finalize_asset.return_value = expected

        response = client.patch(
            f"/assets/{asset_id}/finalize",
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == asset_id
        mock_service.finalize_asset.assert_awaited_once_with(
            asset_id=asset_id,
            session_id="session-abc",
        )

    def test_rejects_unknown_asset(self, client, mock_service):
        """GIVEN a non-existent asset_id
        WHEN PATCH /assets/{id}/finalize
        THEN 404 Not Found.
        """
        mock_service.finalize_asset.side_effect = AssetNotFoundError("Asset x not found")

        response = client.patch(
            f"/assets/{str(uuid4())}/finalize",
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 404

    def test_rejects_session_mismatch(self, client, mock_service):
        """GIVEN an asset owned by a different session
        WHEN PATCH /assets/{id}/finalize with mismatched session
        THEN 403 Forbidden.
        """
        mock_service.finalize_asset.side_effect = ProjectOwnershipError("mismatch")

        response = client.patch(
            f"/assets/{str(uuid4())}/finalize",
            headers={"X-Session-ID": "session-wrong"},
        )

        assert response.status_code == 403

    def test_rejects_missing_session_id(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN PATCH /assets/{id}/finalize
        THEN 422 Unprocessable Entity.
        """
        response = client.patch(
            f"/assets/{str(uuid4())}/finalize",
        )

        assert response.status_code == 422
        mock_service.finalize_asset.assert_not_called()


# ==============================================================================
# DELETE /assets/{id}
# ==============================================================================


class TestDeleteAsset:
    """DELETE /assets/{id} — Soft-delete an asset."""

    def test_soft_deletes_asset_and_returns_204(self, client, mock_service):
        """GIVEN an asset owned by the caller
        WHEN DELETE /assets/{id}
        THEN 204 No Content.
        """
        asset_id = str(uuid4())
        mock_service.soft_delete_asset.return_value = None

        response = client.delete(
            f"/assets/{asset_id}",
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 204
        mock_service.soft_delete_asset.assert_awaited_once_with(
            asset_id=asset_id,
            session_id="session-abc",
        )

    def test_rejects_unknown_asset(self, client, mock_service):
        """GIVEN a non-existent asset_id
        WHEN DELETE /assets/{id}
        THEN 404 Not Found.
        """
        mock_service.soft_delete_asset.side_effect = AssetNotFoundError("Asset x not found")

        response = client.delete(
            f"/assets/{str(uuid4())}",
            headers={"X-Session-ID": "session-abc"},
        )

        assert response.status_code == 404

    def test_rejects_session_mismatch(self, client, mock_service):
        """GIVEN an asset owned by a different session
        WHEN DELETE /assets/{id} with mismatched session
        THEN 403 Forbidden.
        """
        mock_service.soft_delete_asset.side_effect = ProjectOwnershipError("mismatch")

        response = client.delete(
            f"/assets/{str(uuid4())}",
            headers={"X-Session-ID": "session-wrong"},
        )

        assert response.status_code == 403

    def test_rejects_missing_session_id(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN DELETE /assets/{id}
        THEN 422 Unprocessable Entity.
        """
        response = client.delete(
            f"/assets/{str(uuid4())}",
        )

        assert response.status_code == 422
        mock_service.soft_delete_asset.assert_not_called()


# ==============================================================================
# Full upload flow integration
# ==============================================================================


class TestFullUploadFlow:
    """End-to-end upload flow: create project → ticket → finalize → list."""

    def test_complete_upload_flow(self, client, mock_service):
        """GIVEN a full upload flow
        WHEN create → ticket → finalize → list
        THEN all steps complete successfully.
        """
        project_id = str(uuid4())
        asset_id = str(uuid4())
        r2_key = f"projects/{project_id}/final.webp"

        # Step 1: Create project
        project_data = make_project_data(
            project_id=project_id,
            name="Test Flow",
            session_id="session-flow",
        )
        mock_service.create_project.return_value = project_data

        response = client.post(
            "/projects",
            json={"name": "Test Flow"},
            headers={"X-Session-ID": "session-flow"},
        )
        assert response.status_code == 201
        created = response.json()
        assert created["name"] == "Test Flow"

        # Step 2: Request upload ticket
        ticket_data = {
            "asset_id": asset_id,
            "presigned_url": "https://r2.example.com/presigned-url",
            "r2_key": r2_key,
        }
        mock_service.request_upload_ticket.return_value = ticket_data

        response = client.post(
            f"/projects/{project_id}/upload-ticket",
            json={"asset_name": "final.webp", "content_type": "image/webp"},
            headers={"X-Session-ID": "session-flow"},
        )
        assert response.status_code == 200
        ticket = response.json()
        assert ticket["asset_id"] == asset_id
        assert ticket["r2_key"] == r2_key

        # Step 3: Finalize asset (simulate upload completed)
        asset_data = make_asset_data(
            asset_id=asset_id,
            project_id=project_id,
            r2_key=r2_key,
        )
        mock_service.finalize_asset.return_value = asset_data

        response = client.patch(
            f"/assets/{asset_id}/finalize",
            headers={"X-Session-ID": "session-flow"},
        )
        assert response.status_code == 200
        finalized = response.json()
        assert finalized["id"] == asset_id
        assert finalized["r2_key"] == r2_key

        # Step 4: List projects — should include the asset
        project_with_assets = {**project_data, "assets": [asset_data]}
        mock_service.list_projects.return_value = [project_with_assets]

        response = client.get(
            "/projects",
            headers={"X-Session-ID": "session-flow"},
        )
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert len(projects[0]["assets"]) == 1
        assert projects[0]["assets"][0]["id"] == asset_id


# ===============================================================================
# GET /r2/{r2_key:path}
# ===============================================================================


class TestGetR2Asset:
    """GET /r2/{r2_key:path} — return a redirect to a presigned R2 URL."""

    def test_redirects_to_presigned_r2_url(self, client, mock_service):
        """GIVEN an owned asset key
        WHEN GET /r2/{r2_key}
        THEN 307 Temporary Redirect with a Location header.
        """
        r2_key = "projects/p1/thumbnail.webp"
        mock_service.get_asset_by_r2_key.return_value = {
            "id": "asset-1",
            "r2_key": r2_key,
            "project_id": "p1",
            "name": "thumbnail.webp",
        }
        mock_service._storage = AsyncMock()
        mock_service._storage.presigned_get.return_value = (
            "https://r2.example.com/presigned-get?signature=abc"
        )

        response = client.get(
            f"/r2/{r2_key}",
            headers={"X-Session-ID": "session-abc"},
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert response.headers["location"] == "https://r2.example.com/presigned-get?signature=abc"
        mock_service.get_asset_by_r2_key.assert_awaited_once_with(
            r2_key=r2_key,
            session_id="session-abc",
        )

    def test_masks_missing_asset_key_as_404(self, client, mock_service):
        """GIVEN a missing r2_key
        WHEN GET /r2/{r2_key}
        THEN 404 with asset_not_found.
        """
        mock_service.get_asset_by_r2_key.side_effect = AssetNotFoundError("missing")

        response = client.get(
            "/r2/projects/missing/thumbnail.webp",
            headers={"X-Session-ID": "session-abc"},
            follow_redirects=False,
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "asset_not_found"

    def test_rejects_missing_session_header(self, client, mock_service):
        """GIVEN no X-Session-ID header
        WHEN GET /r2/{r2_key}
        THEN 422 Unprocessable Entity.
        """
        response = client.get(
            "/r2/projects/p1/thumbnail.webp",
            follow_redirects=False,
        )

        assert response.status_code == 422
        mock_service.get_asset_by_r2_key.assert_not_called()

    def test_returns_503_when_storage_is_unconfigured(self, client, mock_service):
        """GIVEN storage is not configured
        WHEN GET /r2/{r2_key}
        THEN 503 Service Unavailable.
        """
        mock_service.get_asset_by_r2_key.return_value = {
            "id": "asset-1",
            "r2_key": "projects/p1/thumbnail.webp",
            "project_id": "p1",
            "name": "thumbnail.webp",
        }
        mock_service._storage = AsyncMock()
        mock_service._storage.presigned_get.side_effect = StorageNotConfiguredError(
            "R2Storage not configured"
        )

        response = client.get(
            "/r2/projects/p1/thumbnail.webp",
            headers={"X-Session-ID": "session-abc"},
            follow_redirects=False,
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "storage_not_configured"

    def test_returns_502_when_storage_fails(self, client, mock_service):
        """GIVEN presigned GET generation fails
        WHEN GET /r2/{r2_key}
        THEN 502 Bad Gateway with a generic body.
        """
        mock_service.get_asset_by_r2_key.return_value = {
            "id": "asset-1",
            "r2_key": "projects/p1/thumbnail.webp",
            "project_id": "p1",
            "name": "thumbnail.webp",
        }
        mock_service._storage = AsyncMock()
        mock_service._storage.presigned_get.side_effect = StorageOperationError(
            "botocore ClientError: boom"
        )

        response = client.get(
            "/r2/projects/p1/thumbnail.webp",
            headers={"X-Session-ID": "session-abc"},
            follow_redirects=False,
        )

        assert response.status_code == 502
        body = response.json()
        assert body["error"]["code"] == "storage_error"
        assert "botocore" not in body["error"]["detail"].lower()
