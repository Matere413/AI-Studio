import json
import os
import pytest
from fastapi import FastAPI
from unittest.mock import patch
from src.tests.client_helpers import LazyTestClient


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"

WHITELIST_JSON = json.dumps({
    "checkpoints": [],
    "loras": [FLUX2_TURBO_LORA],
    "unets": [FLUX2_UNET],
    "clip": [FLUX2_CLIP],
    "vae": [FLUX2_VAE],
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
    def _resolve(filename, model_type, models_dir="/root/ComfyUI/models"):
        return f"{models_dir}/{model_type}/{filename}"

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
    client = LazyTestClient(fastapi_app)
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
    client = LazyTestClient(fastapi_app)
    with client.websocket_connect("/ws/generate/unknown-job") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "error"
        assert data["error"]["code"] == "job_not_found"
