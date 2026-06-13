import json
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch
from src.features.controlnet.router import router as controlnet_router


WHITELIST_JSON = json.dumps({
    "checkpoints": ["model.safetensors", "sdxl.safetensors", "sd15.safetensors"],
    "loras": ["lora.safetensors", "detail_enhancer.safetensors"],
})


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def mock_download_model():
    with patch("src.shared.workflows.cache.download_model") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def mock_resolve_cached_model():
    """V1 boundary: treat all referenced models as physically cached in tests."""
    with patch("src.features.generation.service.resolve_cached_model") as mock:
        mock.return_value = "/root/ComfyUI/models/checkpoints/model.safetensors"
        yield mock


# Create a minimal FastAPI app for testing the router
app = FastAPI()
app.include_router(controlnet_router)
client = TestClient(app)


class TestPostControlNet:
    """Integration tests for POST /controlnet endpoint."""

    def test_valid_request_returns_202(self):
        """GIVEN a valid controlnet request
        WHEN POST /controlnet is called
        THEN the response status is 202
        AND the body contains a unique job_id and status='pending'.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "a cyberpunk cat",
                "control_image_url": "https://example.com/control.png",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0
        assert data["status"] == "pending"

    def test_missing_prompt_returns_422(self):
        """GIVEN no prompt is provided
        WHEN POST /controlnet is called
        THEN the request is rejected with a validation error.
        """
        response = client.post(
            "/controlnet", json={"control_image_url": "https://example.com/control.png"}
        )
        assert response.status_code == 422

    def test_missing_control_image_url_returns_422(self):
        """GIVEN no control_image_url is provided
        WHEN POST /controlnet is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/controlnet", json={"prompt": "a cyberpunk cat"})
        assert response.status_code == 422

    def test_extra_fields_rejected(self):
        """GIVEN extra fields are provided
        WHEN POST /controlnet is called
        THEN the request is rejected with a validation error.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "valid",
                "control_image_url": "https://example.com/control.png",
                "extra": "field",
            },
        )
        assert response.status_code == 422

    def test_checkpoint_url_accepted(self):
        """GIVEN a checkpoint_url is provided
        WHEN POST /controlnet is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "a cyberpunk cat",
                "control_image_url": "https://example.com/control.png",
                "checkpoint_url": "https://example.com/model.safetensors",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_control_strength_range_enforced(self):
        """GIVEN a control_strength value outside [0, 2]
        WHEN POST /controlnet is called
        THEN the request is rejected with a validation error.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "a cyberpunk cat",
                "control_image_url": "https://example.com/control.png",
                "control_strength": 2.5,
            },
        )
        assert response.status_code == 422

    def test_control_strength_within_range_accepted(self):
        """GIVEN a control_strength value within [0, 2]
        WHEN POST /controlnet is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "a cyberpunk cat",
                "control_image_url": "https://example.com/control.png",
                "control_strength": 1.0,
            },
        )
        assert response.status_code == 202

    def test_control_params_propagated_to_graph(self, mock_run_generation):
        """GIVEN a valid controlnet request with control params
        WHEN POST /controlnet is called
        THEN the resolved graph contains the control parameters.
        """
        response = client.post(
            "/controlnet",
            json={
                "prompt": "a cyberpunk cat",
                "control_image_url": "https://example.com/control.png",
                "control_strength": 1.5,
            },
        )
        assert response.status_code == 202
        call_args = mock_run_generation.spawn.call_args
        graph = call_args[0][1]
        assert graph["prompt"]["10"]["inputs"]["image"] == "https://example.com/control.png"
        assert graph["prompt"]["11"]["inputs"]["strength"] == 1.5
