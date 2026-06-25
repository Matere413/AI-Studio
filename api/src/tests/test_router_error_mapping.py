"""Approval tests for router error-to-AppError conversion.

These tests capture the current error-handling contract between
router endpoints and the global AppError handler. They document
what the endpoints DO with each error type — not how.
"""

import json
import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from src.features.generation.router import router as generation_router
from src.shared.errors import register_app_error_handlers
from src.tests.client_helpers import LazyTestClient

FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"
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
        "pulid": [IDENTITY_PULID],
        "face_detector": [IDENTITY_FACE_DETECTOR],
        "controlnets": [CONTROLNET_DEPTH, CONTROLNET_CANNY],
    }
)


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as standard:
        with patch("src.features.generation.modal_tasks.run_generation_heavy") as heavy:
            with patch("src.features.generation.modal_tasks.run_generation_a100") as a100:
                standard.spawn.return_value = None
                heavy.spawn.return_value = None
                a100.spawn.return_value = None
                yield standard, heavy, a100


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def cached_models():
    with patch("src.features.generation.service.resolve_cached_model", return_value="/root/ComfyUI/models/cached/model") as mock:
        yield mock


_TEST_SESSION_HEADERS = {"X-Session-ID": "test-session"}

app = FastAPI()
register_app_error_handlers(app)
app.include_router(generation_router)
client = LazyTestClient(app)


class TestRouterErrorMapping:
    """Approval tests: verify router error handling preserves existing contracts."""

    def test_generate_model_not_cached_returns_500(self):
        """GIVEN a model that is not cached
        WHEN POST /generate
        THEN 500 with model_not_cached error code.
        """
        from src.shared.workflows.cache import ModelNotCachedError
        with patch(
            "src.features.generation.service.resolve_cached_model",
            side_effect=ModelNotCachedError(FLUX2_UNET, "diffusion_models", "/root/ComfyUI/models"),
        ):
            response = client.post(
                "/generate",
                json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"

    def test_generate_model_not_allowed_returns_400(self):
        """GIVEN a model that is not whitelisted
        WHEN POST /generate
        THEN 400 with model_not_allowed error code.
        """
        with patch(
            "src.features.generation.router._service.enqueue_modal_work",
            side_effect=ValueError("model_not_allowed: Manifest unet 'forbidden.safetensors' is not in the approved whitelist"),
        ):
            response = client.post(
                "/generate",
                json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "model_not_allowed"

    def test_legacy_workflow_returns_422(self):
        """GIVEN a retired workflow name
        WHEN POST /generate
        THEN 422 with unsupported_workflow error code.
        """
        response = client.post(
            "/generate",
            json={"prompt": "legacy", "workflow": "qwen_txt2img"},
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422
        assert "unsupported_workflow" in response.text

    def test_generate_unsupported_workflow_valueerror_returns_422(self):
        """GIVEN an unsupported workflow ValueError from the service
        WHEN POST /generate
        THEN 422 with unsupported_workflow code.
        """
        with patch(
            "src.features.generation.router._service.enqueue_modal_work",
            side_effect=ValueError("unsupported_workflow: Workflow 'invalid' is not supported"),
        ):
            response = client.post(
                "/generate",
                json={"prompt": "test", "workflow": "flux2_txt2img"},
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 422
        # Should have structured error through AppError handler
        assert "error" in response.json()
        assert response.json()["error"]["code"] == "unsupported_workflow"

    def test_extraction_model_not_cached_returns_500(self):
        """GIVEN an extraction request with an uncached model
        WHEN POST /generate/extraction
        THEN 500 with model_not_cached error code.
        """
        from src.shared.workflows.cache import ModelNotCachedError
        with patch(
            "src.features.generation.router._service.dispatch_flow",
            side_effect=ModelNotCachedError("bria_rmbg.safetensors", "unet", "/root/ComfyUI/models"),
        ):
            response = client.post(
                "/generate/extraction",
                json={
                    "prompt": "test",
                    "input_image": {"volume_path": "input/source.png", "media_type": "image/png", "owner_session_id": "test-session"},
                },
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"

    def test_composition_model_not_cached_returns_500(self):
        """GIVEN a composition request with an uncached model
        WHEN POST /generate/composition
        THEN 500 with model_not_cached error code.
        """
        from src.shared.workflows.cache import ModelNotCachedError
        with patch(
            "src.features.generation.router._service.dispatch_flow",
            side_effect=ModelNotCachedError("flux-controlnet-depth-v1.safetensors", "controlnets", "/root/ComfyUI/models"),
        ):
            response = client.post(
                "/generate/composition",
                json={
                    "prompt": "compose with depth",
                    "background_image": {"volume_path": "input/bg.png", "media_type": "image/png", "owner_session_id": "test-session"},
                    "foreground_image": {"volume_path": "input/fg.png", "media_type": "image/png", "owner_session_id": "test-session"},
                    "control_mode": "depth",
                },
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"

    def test_identity_model_not_cached_returns_500(self):
        """GIVEN an identity request with an uncached model
        WHEN POST /generate/identity
        THEN 500 with model_not_cached error code.
        """
        from src.shared.workflows.cache import ModelNotCachedError
        with patch(
            "src.features.generation.router._service.dispatch_flow",
            side_effect=ModelNotCachedError("pulid_flux_v0.9.1.safetensors", "pulid", "/root/ComfyUI/models"),
        ):
            response = client.post(
                "/generate/identity",
                json={
                    "prompt": "identity preserve",
                    "reference_face": {"volume_path": "input/reference.png", "media_type": "image/png", "owner_session_id": "test-session"},
                },
                headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"

    def test_successful_generate_returns_202(self, mock_run_generation):
        """GIVEN a valid generation request
        WHEN POST /generate
        THEN 202 Accepted with job_id.
        """
        response = client.post(
            "/generate",
            json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
            headers=_TEST_SESSION_HEADERS,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0
