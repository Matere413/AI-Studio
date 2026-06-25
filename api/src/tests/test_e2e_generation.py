import json
import os
from unittest.mock import patch

import pytest

from app import fastapi_app
from src.features.generation.router import _job_store
from src.tests.client_helpers import LazyTestClient


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"

WHITELIST_JSON = json.dumps(
    {
        "checkpoints": [],
        "loras": [FLUX2_TURBO_LORA],
        "unets": [FLUX2_UNET],
        "clip": [FLUX2_CLIP],
        "vae": [FLUX2_VAE],
    }
)


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
def cached_models():
    with patch("src.features.generation.service.resolve_cached_model", return_value="/root/ComfyUI/models/cached/model") as mock:
        yield mock


client = LazyTestClient(fastapi_app)


class TestE2EGenerationFlow:
    """End-to-end tests covering the Flux 2 POST + WebSocket lifecycle."""

    def test_e2e_flux2_txt2img_accepted_request(self):
        response = client.post("/generate", json={"prompt": "e2e accepted", "workflow": "flux2_txt2img"}, headers={"X-Session-ID": "e2e-test"})

        assert response.status_code == 202
        data = response.json()
        assert len(data["job_id"]) > 0
        assert data["status"] == "pending"

        with client.websocket_connect(f"/ws/generate/{data['job_id']}?session_id=e2e-test") as websocket:
            event = websocket.receive_json()

        assert event["event"] == "booting_server"
        assert event["job_id"] == data["job_id"]

    def test_e2e_flux2_editing_accepted_request(self):
        response = client.post(
            "/generate",
            json={
                "prompt": "replace the background",
                "workflow": "flux2_editing",
                "image_base64": "data:image/png;base64,aGVsbG8=",
            },
            headers={"X-Session-ID": "e2e-test"},
        )

        assert response.status_code == 202
        assert len(response.json()["job_id"]) > 0

    def test_e2e_validation_failure(self):
        assert client.post("/generate", json={}).status_code == 422
        assert client.post("/generate", json={"prompt": ""}).status_code == 422
        assert client.post("/generate", json={"prompt": "valid", "extra": "field"}).status_code == 422

    @pytest.mark.parametrize("workflow", ["qwen_txt2img", "txt2img"])
    def test_e2e_legacy_workflows_rejected(self, workflow):
        response = client.post(
            "/generate",
            json={"prompt": "legacy", "workflow": workflow},
            headers={"X-Session-ID": "e2e-test"},
        )

        assert response.status_code == 422
        assert "unsupported_workflow" in response.text

    def test_e2e_unknown_job(self):
        with client.websocket_connect("/ws/generate/non-existent-e2e-job") as websocket:
            event = websocket.receive_json()

        assert event["event"] == "error"
        assert event["error"]["code"] == "job_not_found"

    def test_e2e_reconnect(self):
        response = client.post("/generate", json={"prompt": "e2e reconnect"}, headers={"X-Session-ID": "e2e-test"})
        job_id = response.json()["job_id"]

        with client.websocket_connect(f"/ws/generate/{job_id}?session_id=e2e-test") as websocket:
            assert websocket.receive_json()["event"] == "booting_server"

        _job_store.update_job(job_id, status="running")

        with client.websocket_connect(f"/ws/generate/{job_id}?session_id=e2e-test") as websocket:
            event = websocket.receive_json()

        assert event["event"] == "generating"
        assert event["progress"] == 50

    def test_e2e_completed_stream(self):
        response = client.post("/generate", json={"prompt": "e2e completed"}, headers={"X-Session-ID": "e2e-test"})
        job_id = response.json()["job_id"]
        _job_store.update_job(job_id, status="completed", image_path="/e2e/image.png")

        with client.websocket_connect(f"/ws/generate/{job_id}?session_id=e2e-test") as websocket:
            event = websocket.receive_json()

        assert event["event"] == "completed"
        # image_path is intentionally omitted from WS events
        assert "image_path" not in event.get("result", {})
