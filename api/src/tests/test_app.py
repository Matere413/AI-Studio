import json
import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch


DEFAULT_TXT2IMG_CHECKPOINT = "epicrealism_naturalSinRC1VAE.safetensors"

WHITELIST_JSON = json.dumps({
    "checkpoints": [
        "model.safetensors",
        "sdxl.safetensors",
        "sd15.safetensors",
        DEFAULT_TXT2IMG_CHECKPOINT,
    ],
    "loras": ["lora.safetensors", "detail_enhancer.safetensors"],
})


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def default_cached_model():
    from src.shared.workflows.cache import resolve_cached_model as real_resolve_cached_model

    def _resolve(filename, model_type, models_dir="/root/ComfyUI/models"):
        if filename == DEFAULT_TXT2IMG_CHECKPOINT:
            return f"{models_dir}/{model_type}/{filename}"
        return real_resolve_cached_model(filename, model_type, models_dir)

    with patch("src.features.generation.service.resolve_cached_model", side_effect=_resolve) as mock:
        yield mock


def test_app_is_fastapi_instance():
    """GIVEN app.py is imported
    THEN fastapi_app is a FastAPI instance.
    """
    from app import fastapi_app
    assert isinstance(fastapi_app, FastAPI)


def test_app_includes_generation_router():
    """GIVEN the mounted FastAPI app
    WHEN POST /generate is called
    THEN it returns 202 Accepted with a job_id.
    """
    from app import fastapi_app
    client = TestClient(fastapi_app)
    response = client.post("/generate", json={"prompt": "test app"})
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"


def test_app_websocket_unknown_job():
    """GIVEN the mounted FastAPI app
    WHEN WS /ws/generate/{unknown_job_id} is called
    THEN it returns an error event.
    """
    from app import fastapi_app
    client = TestClient(fastapi_app)
    with client.websocket_connect("/ws/generate/unknown-job") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "error"
        assert data["error"]["code"] == "job_not_found"
