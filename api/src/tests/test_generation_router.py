import json
import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from src.features.generation.router import _job_store, router as generation_router
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


app = FastAPI()
register_app_error_handlers(app)
app.include_router(generation_router)
client = LazyTestClient(app)

# Shared session header for tests that need one.
_TEST_SESSION_HEADERS = {"X-Session-ID": "test-session"}



class TestPostGenerate:
    """Integration tests for POST /generate endpoint."""

    def test_flux2_txt2img_returns_202_with_job_id(self, mock_run_generation):
        response = client.post(
            "/generate",
            json={"prompt": "a luminous orchid", "workflow": "flux2_txt2img"},
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
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
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422


class TestPostGenerateExtraction:
    """Integration tests for POST /generate/extraction endpoint."""

    def test_extraction_returns_202_with_job_id(self, mock_run_generation):
        """GIVEN a valid extraction request with input_image
        WHEN POST /generate/extraction
        THEN 202 Accepted with job_id and status pending.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "extract subject from background",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0

    def test_extraction_accepts_mask_margin(self, mock_run_generation):
        """GIVEN an extraction request with mask_margin
        WHEN POST /generate/extraction
        THEN 202 Accepted.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "extract with margin",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
                "mask_margin": 5,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 202

    def test_extraction_rejects_missing_input_image(self, mock_run_generation):
        """GIVEN an extraction request without input_image
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={"prompt": "missing image"},
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_rejects_invalid_input_image_path(self, mock_run_generation):
        """GIVEN an input_image with a path that does not start with input/
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "invalid path",
                "input_image": {
                    "volume_path": "/etc/passwd",
                    "media_type": "image/png",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_rejects_extra_fields(self, mock_run_generation):
        """GIVEN an extraction request with forbidden extra fields
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "test",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
                "use_turbo": True,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_rejects_mask_margin_out_of_range(self, mock_run_generation):
        """GIVEN mask_margin outside [0, 100]
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "bad margin",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
                "mask_margin": 200,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_rejects_empty_prompt(self, mock_run_generation):
        """GIVEN an extraction request with empty prompt
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_rejects_invalid_media_type(self, mock_run_generation):
        """GIVEN an input_image with unsupported media_type
        WHEN POST /generate/extraction
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "bad media type",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/gif",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_extraction_forwards_to_dispatch_flow(self, mock_run_generation):
        """GIVEN a valid extraction request
        WHEN POST /generate/extraction
        THEN dispatch_flow is called with an ExtractionFlow instance.
        """
        from src.shared.flows.extraction import ExtractionFlow

        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/extraction",
                json={
                    "prompt": "extract this",
                    "input_image": {
                        "volume_path": "input/source.png",
                        "media_type": "image/png",
                    },
                },
            headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 202
        mock_dispatch.assert_called_once()
        _, kwargs = mock_dispatch.call_args
        flow_request = kwargs["flow_request"]
        assert isinstance(flow_request, ExtractionFlow)
        assert flow_request.workflow_name == "extraction"
        assert flow_request.gpu_profile.value == "L4"
        assert flow_request.timeout_s == 300

    def test_extraction_model_not_cached_returns_500(self, mock_run_generation):
        """GIVEN a valid extraction request but a model is not cached
        WHEN POST /generate/extraction
        THEN 500 with model_not_cached error.
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
                    "input_image": {
                        "volume_path": "input/source.png",
                        "media_type": "image/png",
                    },
                },
            headers=_TEST_SESSION_HEADERS,
            )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "model_not_cached"


class TestGetImage:
    """Integration tests for GET /images/{job_id}."""

    def test_image_served_for_completed_job(self, tmp_path):
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"}, headers=_TEST_SESSION_HEADERS)
        job_id = response.json()["job_id"]
        image_file = tmp_path / "result.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")
        _job_store.update_job(job_id, status="completed", image_path=str(image_file))

        response = client.get(
            f"/images/{job_id}",
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_job_not_found_returns_404(self):
        response = client.get("/images/non-existent-job")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "job_not_found"

    def test_session_mismatch_rejected(self, tmp_path):
        """GIVEN a job created with a specific session_id
        WHEN GET /images/{job_id} with a different X-Session-ID
        THEN 403 SessionMismatchError.
        """
        job_id = _job_store.create_job("test", session_id="session-A")
        _job_store.update_job(job_id, status="completed", image_path="/tmp/dummy.png")

        response = client.get(
            f"/images/{job_id}",
            headers={"X-Session-ID": "session-B"},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "session_mismatch"

    def test_session_match_allows_access(self, tmp_path):
        """GIVEN a job created with a specific session_id
        WHEN GET /images/{job_id} with matching X-Session-ID
        THEN the image is served.
        """
        job_id = _job_store.create_job("test", session_id="session-A")
        image_file = tmp_path / "result.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")
        _job_store.update_job(job_id, status="completed", image_path=str(image_file))

        response = client.get(
            f"/images/{job_id}",
            headers={"X-Session-ID": "session-A"},
        )

        assert response.status_code == 200

    def test_legacy_job_without_session_allows_any_request(self, tmp_path):
        """GIVEN a job created without a session_id (legacy)
        WHEN GET /images/{job_id} without X-Session-ID
        THEN the image is served (backward compat).
        """
        job_id = _job_store.create_job("test")
        image_file = tmp_path / "result.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")
        _job_store.update_job(job_id, status="completed", image_path=str(image_file))

        response = client.get(f"/images/{job_id}")

        assert response.status_code == 200


class TestPostGenerateIdentity:
    """Integration tests for POST /generate/identity endpoint."""

    def test_identity_returns_202_with_job_id(self, mock_run_generation):
        """GIVEN a valid identity request with reference_face
        WHEN POST /generate/identity
        THEN 202 Accepted with job_id and status pending.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "identity preserving portrait",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0

    def test_identity_accepts_custom_dimensions(self, mock_run_generation):
        """GIVEN an identity request with custom valid dimensions
        WHEN POST /generate/identity
        THEN 202 Accepted.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "identity preserving portrait",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "width": 768,
                "height": 1024,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    def test_identity_accepts_explicit_seed(self, mock_run_generation):
        """GIVEN an identity request with an explicit seed
        WHEN POST /generate/identity
        THEN 202 Accepted.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "seeded identity",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "seed": 42,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 202

    def test_identity_rejects_dimensions_exceeding_max(self, mock_run_generation):
        """GIVEN width or height exceeding the 2048 VRAM limit
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "too big",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "width": 3000,
                "height": 1024,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("bad_dim", [65, 100, 200])
    def test_identity_rejects_width_not_multiple_of_64(self, bad_dim, mock_run_generation):
        """GIVEN a width that is not a multiple of 64
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "bad dims",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "width": bad_dim,
                "height": 1024,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("bad_dim", [65, 100, 200])
    def test_identity_rejects_height_not_multiple_of_64(self, bad_dim, mock_run_generation):
        """GIVEN a height that is not a multiple of 64
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "bad dims",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "width": 1024,
                "height": bad_dim,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_identity_rejects_missing_reference_face(self, mock_run_generation):
        """GIVEN an identity request without reference_face
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={"prompt": "missing face"},
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_identity_rejects_invalid_reference_face_path(self, mock_run_generation):
        """GIVEN a reference_face with a path that does not start with input/
        and no source_job_id
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "malicious path",
                "reference_face": {
                    "volume_path": "/etc/passwd",
                    "media_type": "image/png",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422

    def test_identity_rejects_extra_fields(self, mock_run_generation):
        """GIVEN an identity request with forbidden extra fields
        WHEN POST /generate/identity
        THEN 422 Unprocessable Entity.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "identity",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
                "use_turbo": True,
            },
            headers=_TEST_SESSION_HEADERS,
        )

        assert response.status_code == 422


class TestWebSocketGenerate:
    """Integration tests for WS /ws/generate/{job_id}."""

    def test_unknown_job_returns_error_event(self):
        with client.websocket_connect("/ws/generate/non-existent-job") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "error"
        assert data["error"]["code"] == "job_not_found"

    def test_known_job_returns_current_event(self):
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"}, headers=_TEST_SESSION_HEADERS)
        job_id = response.json()["job_id"]

        with client.websocket_connect(f"/ws/generate/{job_id}?session_id=test-session") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "booting_server"
        assert data["job_id"] == job_id

    def test_ws_returns_node_missing_error_code(self):
        """GIVEN a job that failed with node_missing
        WHEN polling via WebSocket
        THEN the error event carries code node_missing.
        """
        job_id = _job_store.create_job("test")
        _job_store.update_job(job_id, status="error", error_code="node_missing", error_detail="BriaRMBG node not installed")

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "error"
        assert data["error"]["code"] == "node_missing"
        assert "BriaRMBG" in data["error"]["detail"]

    def test_ws_returns_gpu_oom_error_code(self):
        """GIVEN a job that failed with gpu_oom
        WHEN polling via WebSocket
        THEN the error event carries code gpu_oom.
        """
        job_id = _job_store.create_job("test")
        _job_store.update_job(job_id, status="error", error_code="gpu_oom", error_detail="CUDA out of memory")

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "error"
        assert data["error"]["code"] == "gpu_oom"

    def test_ws_returns_no_face_detected_error_code(self):
        """GIVEN a job that failed with no_face_detected
        WHEN polling via WebSocket
        THEN the error event carries code no_face_detected.
        """
        job_id = _job_store.create_job("test")
        _job_store.update_job(job_id, status="error", error_code="no_face_detected", error_detail="No face detected in reference image")

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()

        assert data["event"] == "error"
        assert data["error"]["code"] == "no_face_detected"


class TestSessionOwnership:
    """Integration tests for session-scoped artifact ownership validation."""

    def test_mismatched_session_owner_rejected(self, mock_run_generation):
        """GIVEN an extraction request with owner_session_id that doesn't match the caller
        WHEN POST /generate/extraction with a different X-Session-ID
        THEN 422 Unprocessable Entity with invalid_artifact error.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "extract this",
                "input_image": {
                    "volume_path": "input/session-abc/face.png",
                    "media_type": "image/png",
                    "owner_session_id": "session-abc",
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        # "test-session" does not match "session-abc"
        assert response.status_code == 422
        assert "invalid_artifact" in response.text

    def test_session_forwarded_to_dispatch_flow(self, mock_run_generation):
        """GIVEN an extraction request with X-Session-ID header
        WHEN POST /generate/extraction
        THEN the session_id is forwarded to dispatch_flow.
        """
        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/extraction",
                json={
                    "prompt": "extract this",
                    "input_image": {
                        "volume_path": "input/reference.png",
                        "media_type": "image/png",
                    },
                },
                headers={"X-Session-ID": "my-session-abc"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs["session_id"] == "my-session-abc"

    def test_session_forwarded_on_composition(self, mock_run_generation):
        """GIVEN a composition request with X-Session-ID header
        WHEN POST /generate/composition
        THEN the session_id is forwarded to dispatch_flow.
        """
        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/composition",
                json={
                    "prompt": "compose it",
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
                headers={"X-Session-ID": "session-456"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs["session_id"] == "session-456"

    def test_session_forwarded_on_identity(self, mock_run_generation):
        """GIVEN an identity request with X-Session-ID header
        WHEN POST /generate/identity
        THEN the session_id is forwarded to dispatch_flow.
        """
        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/identity",
                json={
                    "prompt": "preserve identity",
                    "reference_face": {
                        "volume_path": "input/reference.png",
                        "media_type": "image/png",
                    },
                },
                headers={"X-Session-ID": "session-789"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs["session_id"] == "session-789"

    def test_chained_artifact_accepted_regardless_of_session(self, mock_run_generation):
        """GIVEN an extraction request with source_job_id (chained flow)
        WHEN POST /generate/extraction
        THEN 202 Accepted — ownership propagates from source job.
        """
        from src.features.generation.router import _job_store

        source_job_id = _job_store.create_job("source extraction")
        _job_store.update_job(source_job_id, status="completed", image_path="/path/to/result.png")

        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "chain this",
                "input_image": {
                    "volume_path": "output/source/result.png",
                    "media_type": "image/png",
                    "source_job_id": source_job_id,
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        # Chained artifacts skip session validation
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["job_id"]) > 0

    def test_empty_session_rejected_for_session_owned_source_job(self, mock_run_generation):
        """GIVEN a chained source_job owned by a session different from the caller
        WHEN POST /generate/extraction with a non-matching X-Session-ID
        THEN 422 Unprocessable Entity — non-matching session_id does NOT bypass.
        """
        from src.features.generation.router import _job_store

        source_job_id = _job_store.create_job("source owned extraction", session_id="session-A")
        _job_store.update_job(source_job_id, status="completed", image_path="/path/to/result.png")

        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "chain this",
                "input_image": {
                    "volume_path": "output/source/result.png",
                    "media_type": "image/png",
                    "source_job_id": source_job_id,
                },
            },
            headers=_TEST_SESSION_HEADERS,
        )

        # "test-session" does not own the source job owned by "session-A"
        assert response.status_code == 422
        assert "invalid_artifact" in response.text


class TestResolveAssetUrlForwarding:
    """Tests that resolve_asset_url callback is forwarded to dispatch_flow."""

    def _make_resolve_asset_url(self):
        """Return a dummy resolve_asset_url callback for testing."""
        def resolve(asset_id: str, session_id: str) -> str:
            return f"https://r2.example.com/{asset_id}?session={session_id}"
        return resolve

    def test_extraction_forwards_resolve_asset_url(self, mock_run_generation):
        """GIVEN set_resolve_asset_url has been called
        WHEN POST /generate/extraction
        THEN the callback is forwarded to dispatch_flow.
        """
        from src.features.generation.router import set_resolve_asset_url, _resolve_asset_url_cb

        # Reset first
        set_resolve_asset_url(None)
        assert _resolve_asset_url_cb is None

        cb = self._make_resolve_asset_url()
        set_resolve_asset_url(cb)

        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/extraction",
                json={
                    "prompt": "extract with asset callback",
                    "input_image": {
                        "volume_path": "input/reference.png",
                        "media_type": "image/png",
                    },
                },
                headers={"X-Session-ID": "session-abc"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs.get("resolve_asset_url") is cb

        # Clean up
        set_resolve_asset_url(None)

    def test_composition_forwards_resolve_asset_url(self, mock_run_generation):
        """GIVEN set_resolve_asset_url has been called
        WHEN POST /generate/composition
        THEN the callback is forwarded to dispatch_flow.
        """
        from src.features.generation.router import set_resolve_asset_url

        cb = self._make_resolve_asset_url()
        set_resolve_asset_url(cb)

        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/composition",
                json={
                    "prompt": "compose with asset callback",
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
                headers={"X-Session-ID": "session-abc"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs.get("resolve_asset_url") is cb

        set_resolve_asset_url(None)

    def test_identity_forwards_resolve_asset_url(self, mock_run_generation):
        """GIVEN set_resolve_asset_url has been called
        WHEN POST /generate/identity
        THEN the callback is forwarded to dispatch_flow.
        """
        from src.features.generation.router import set_resolve_asset_url

        cb = self._make_resolve_asset_url()
        set_resolve_asset_url(cb)

        with patch("src.features.generation.router._service.dispatch_flow") as mock_dispatch:
            response = client.post(
                "/generate/identity",
                json={
                    "prompt": "identity with asset callback",
                    "reference_face": {
                        "volume_path": "input/reference.png",
                        "media_type": "image/png",
                    },
                },
                headers={"X-Session-ID": "session-abc"},
            )

        assert response.status_code == 202
        _, kwargs = mock_dispatch.call_args
        assert kwargs.get("resolve_asset_url") is cb

        set_resolve_asset_url(None)

    def test_default_is_none(self):
        """GIVEN set_resolve_asset_url has NOT been called
        THEN _resolve_asset_url_cb is None.
        """
        from src.features.generation.router import set_resolve_asset_url, _resolve_asset_url_cb

        set_resolve_asset_url(None)
        assert _resolve_asset_url_cb is None


# ==============================================================================
# Fix 4 (4R): Session Security — empty X-Session-ID rejected at router level
# ==============================================================================


class TestSessionValidation:
    """Endpoints MUST reject requests with empty X-Session-ID."""

    def test_generate_rejects_empty_session(self):
        """GIVEN a request without X-Session-ID
        WHEN POST /generate
        THEN 401 Unauthorized.
        """
        response = client.post(
            "/generate",
            json={"prompt": "test", "workflow": "flux2_txt2img"},
        )
        assert response.status_code == 401

    def test_extraction_rejects_empty_session(self):
        """GIVEN a request without X-Session-ID
        WHEN POST /generate/extraction
        THEN 401 Unauthorized.
        """
        response = client.post(
            "/generate/extraction",
            json={
                "prompt": "test",
                "input_image": {
                    "volume_path": "input/source.png",
                    "media_type": "image/png",
                },
            },
        )
        assert response.status_code == 401

    def test_composition_rejects_empty_session(self):
        """GIVEN a request without X-Session-ID
        WHEN POST /generate/composition
        THEN 401 Unauthorized.
        """
        response = client.post(
            "/generate/composition",
            json={
                "prompt": "test",
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
        assert response.status_code == 401

    def test_identity_rejects_empty_session(self):
        """GIVEN a request without X-Session-ID
        WHEN POST /generate/identity
        THEN 401 Unauthorized.
        """
        response = client.post(
            "/generate/identity",
            json={
                "prompt": "test",
                "reference_face": {
                    "volume_path": "input/reference.png",
                    "media_type": "image/png",
                },
            },
        )
        assert response.status_code == 401