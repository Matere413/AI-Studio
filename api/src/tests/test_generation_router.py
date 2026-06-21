import json
import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from src.features.generation.router import _job_store, router as generation_router
from src.tests.client_helpers import LazyTestClient


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"
IDENTITY_GGUF = "flux1-dev-q4_k_m.gguf"
IDENTITY_CLIP = "t5xxl_fp8_e4m3fn.safetensors"
IDENTITY_PULID = "pulid_flux_v0.9.1.safetensors"
IDENTITY_FACE_DETECTOR = "face_yolov8m.pt"
CONTROLNET_DEPTH = "flux-controlnet-depth-v1.safetensors"
CONTROLNET_CANNY = "flux-controlnet-canny-v1.safetensors"

WHITELIST_JSON = json.dumps(
    {
        "loras": [FLUX2_TURBO_LORA],
        "unets": [FLUX2_UNET],
        "clip": [FLUX2_CLIP, IDENTITY_CLIP],
        "vae": [FLUX2_VAE],
        "gguf": [IDENTITY_GGUF],
        "pulid": [IDENTITY_PULID],
        "face_detector": [IDENTITY_FACE_DETECTOR],
        "controlnets": [CONTROLNET_DEPTH, CONTROLNET_CANNY],
    }
)


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as standard:
        with patch("src.features.generation.modal_tasks.run_generation_heavy") as heavy:
            standard.spawn.return_value = None
            heavy.spawn.return_value = None
            yield standard, heavy


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def cached_models():
    with patch("src.features.generation.service.resolve_cached_model", return_value="/root/ComfyUI/models/cached/model") as mock:
        yield mock


app = FastAPI()
app.include_router(generation_router)
client = LazyTestClient(app)


class TestPostGenerate:
    """Integration tests for POST /generate endpoint."""

    def test_flux2_txt2img_returns_202_with_job_id(self, mock_run_generation):
        response = client.post(
            "/generate",
            json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0
        graph = mock_run_generation[0].spawn.call_args.args[1]
        assert graph["prompt"]["98:6"]["inputs"]["text"] == "a luminous orchid"
        assert graph["prompt"]["98:104"]["inputs"]["value"] is True

    def test_flux2_txt2img_forwards_explicit_turbo_false(self):
        with patch("src.features.generation.router._service.enqueue_modal_work") as mock_enqueue:
            response = client.post(
                "/generate",
                json={
                    "prompt": "a base Flux 2 image",
                    "workflow": "flux2_txt2img",
                    "use_turbo": False,
                },
            )

        assert response.status_code == 202
        assert mock_enqueue.call_args.kwargs["workflow_name"] == "flux2_txt2img"
        assert mock_enqueue.call_args.kwargs["use_turbo"] is False

    def test_flux2_editing_with_image_base64_returns_202(self, mock_run_generation):
        image_base64 = "data:image/png;base64,aGVsbG8="

        response = client.post(
            "/generate",
            json={
                "prompt": "replace the background",
                "workflow": "flux2_editing",
                "image_base64": image_base64,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert len(data["job_id"]) > 0
        graph = mock_run_generation[0].spawn.call_args.args[1]
        assert graph["prompt"]["46"]["inputs"]["image_url"] == image_base64

    @pytest.mark.parametrize("workflow", ["qwen_txt2img", "txt2img"])
    def test_legacy_workflows_return_422_with_unsupported_workflow(self, workflow):
        response = client.post(
            "/generate",
            json={"prompt": "legacy prompt", "workflow": workflow},
        )

        assert response.status_code == 422
        assert "unsupported_workflow" in response.text

    def test_model_not_cached_returns_500(self):
        from src.shared.workflows.cache import ModelNotCachedError

        with patch(
            "src.features.generation.service.resolve_cached_model",
            side_effect=ModelNotCachedError(FLUX2_UNET, "diffusion_models", "/root/ComfyUI/models"),
        ):
            response = client.post(
                "/generate",
                json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"

    def test_model_not_allowed_returns_400(self):
        with patch(
            "src.features.generation.router._service.enqueue_modal_work",
            side_effect=ValueError("model_not_allowed: Manifest unet 'forbidden.safetensors' is not in the approved whitelist"),
        ):
            response = client.post(
                "/generate",
                json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
            )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "model_not_allowed"


class TestPostGenerateComposition:
    """Integration tests for POST /generate/composition endpoint."""

    def test_composition_returns_202_with_job_id(self, mock_run_generation):
        """GIVEN a valid composition request
        WHEN POST /generate/composition
        THEN 202 Accepted with job_id and status pending.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose subject into scene",
                "background_image": {
                    "volume_path": "input/bg.png",
                    "media_type": "image/png",
                },
                "foreground_image": {
                    "volume_path": "input/fg.png",
                    "media_type": "image/png",
                },
                "control_mode": "depth",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0

    def test_composition_accepts_control_strength(self, mock_run_generation):
        """GIVEN a composition request with explicit control_strength
        WHEN POST /generate/composition
        THEN 202 Accepted and control_strength is forwarded.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose subject into scene",
                "background_image": {
                    "volume_path": "input/bg.png",
                    "media_type": "image/png",
                },
                "foreground_image": {
                    "volume_path": "input/fg.png",
                    "media_type": "image/png",
                },
                "control_mode": "depth",
                "control_strength": 0.75,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    def test_composition_canny_mode_returns_202(self, mock_run_generation):
        """GIVEN a composition request with control_mode="canny"
        WHEN POST /generate/composition
        THEN 202 Accepted.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose with edges",
                "background_image": {
                    "volume_path": "input/bg.png",
                    "media_type": "image/png",
                },
                "foreground_image": {
                    "volume_path": "input/fg.png",
                    "media_type": "image/png",
                },
                "control_mode": "canny",
            },
        )

        assert response.status_code == 202

    def test_composition_invalid_control_mode_returns_422(self, mock_run_generation):
        """GIVEN a composition request with invalid control_mode
        WHEN POST /generate/composition
        THEN 422 Unprocessable Entity with validation error.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose subject into scene",
                "background_image": {
                    "volume_path": "input/bg.png",
                    "media_type": "image/png",
                },
                "foreground_image": {
                    "volume_path": "input/fg.png",
                    "media_type": "image/png",
                },
                "control_mode": "pose",
            },
        )

        assert response.status_code == 422

    def test_composition_missing_images_returns_422(self, mock_run_generation):
        """GIVEN a composition request missing images
        WHEN POST /generate/composition
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose subject into scene",
                "control_mode": "depth",
            },
        )

        assert response.status_code == 422

    def test_composition_control_strength_out_of_bounds_returns_422(self, mock_run_generation):
        """GIVEN a composition request with control_strength out of [0, 2]
        WHEN POST /generate/composition
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "compose subject",
                "background_image": {
                    "volume_path": "input/bg.png",
                    "media_type": "image/png",
                },
                "foreground_image": {
                    "volume_path": "input/fg.png",
                    "media_type": "image/png",
                },
                "control_mode": "depth",
                "control_strength": -0.5,
            },
        )

        assert response.status_code == 422


class TestGetImage:
    """Integration tests for GET /images/{job_id}."""

    def test_image_served_for_completed_job(self, tmp_path):
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"})
        job_id = response.json()["job_id"]
        image_file = tmp_path / "result.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")
        _job_store.update_job(job_id, status="completed", image_path=str(image_file))

        response = client.get(f"/images/{job_id}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_job_not_found_returns_404(self):
        response = client.get("/images/non-existent-job")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "job_not_found"


class TestWebSocketGenerate:
    """Integration tests for WS /ws/generate/{job_id}."""

    def test_unknown_job_returns_error_event(self):
        with client.websocket_connect("/ws/generate/non-existent-job") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "error"
        assert data["error"]["code"] == "job_not_found"

    def test_known_job_returns_current_event(self):
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"})
        job_id = response.json()["job_id"]

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "booting_server"
        assert data["job_id"] == job_id
