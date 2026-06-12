import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch
from src.features.editing.router import router as editing_router


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


# Create a minimal FastAPI app for testing the router
app = FastAPI()
app.include_router(editing_router)
client = TestClient(app)


class TestPostEdit:
    """Integration tests for POST /edit endpoint."""

    def test_valid_request_returns_202(self):
        """GIVEN a valid edit request
        WHEN POST /edit is called
        THEN the response status is 202
        AND the body contains a unique job_id and status='pending'.
        """
        response = client.post(
            "/edit",
            json={
                "prompt": "a cyberpunk cat",
                "image_url": "https://example.com/image.png",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0
        assert data["status"] == "pending"

    def test_missing_prompt_returns_422(self):
        """GIVEN no prompt is provided
        WHEN POST /edit is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/edit", json={"image_url": "https://example.com/image.png"})
        assert response.status_code == 422

    def test_missing_image_url_returns_422(self):
        """GIVEN no image_url is provided
        WHEN POST /edit is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/edit", json={"prompt": "a cyberpunk cat"})
        assert response.status_code == 422

    def test_extra_fields_rejected(self):
        """GIVEN extra fields are provided
        WHEN POST /edit is called
        THEN the request is rejected with a validation error.
        """
        response = client.post(
            "/edit",
            json={
                "prompt": "valid",
                "image_url": "https://example.com/image.png",
                "extra": "field",
            },
        )
        assert response.status_code == 422

    def test_checkpoint_url_accepted(self):
        """GIVEN a checkpoint_url is provided
        WHEN POST /edit is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/edit",
            json={
                "prompt": "a cyberpunk cat",
                "image_url": "https://example.com/image.png",
                "checkpoint_url": "https://example.com/model.safetensors",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_denoise_range_enforced(self):
        """GIVEN a denoise value outside [0, 1]
        WHEN POST /edit is called
        THEN the request is rejected with a validation error.
        """
        response = client.post(
            "/edit",
            json={
                "prompt": "a cyberpunk cat",
                "image_url": "https://example.com/image.png",
                "denoise": 1.5,
            },
        )
        assert response.status_code == 422

    def test_denoise_within_range_accepted(self):
        """GIVEN a denoise value within [0, 1]
        WHEN POST /edit is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/edit",
            json={
                "prompt": "a cyberpunk cat",
                "image_url": "https://example.com/image.png",
                "denoise": 0.5,
            },
        )
        assert response.status_code == 202
