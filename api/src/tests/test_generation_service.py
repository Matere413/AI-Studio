import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.features.generation.service import (
    FLUX2_EDITING_WORKFLOW,
    FLUX2_TXT2IMG_WORKFLOW,
    GenerationService,
    download_image_to_base64,
    resolve_identity_seed,
)
from src.shared.job_store import JobStore


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"
IDENTITY_GGUF = "flux1-dev-q4_k_m.gguf"
IDENTITY_CLIP = "t5xxl_fp8_e4m3fn.safetensors"
IDENTITY_VAE = "flux-vae-bf16.safetensors"
IDENTITY_PULID = "pulid_flux_v0.9.1.safetensors"
IDENTITY_FACE_DETECTOR = "bbox/face_yolov8m.pt"

WHITELIST_JSON = json.dumps(
    {
        "loras": [FLUX2_TURBO_LORA],
        "unets": [FLUX2_UNET],
        "clip": [FLUX2_CLIP, IDENTITY_CLIP],
        "vae": [FLUX2_VAE, IDENTITY_VAE],
        "gguf": [IDENTITY_GGUF],
        "pulid": [IDENTITY_PULID],
        "face_detector": ["face_yolov8m.pt"],
    }
)


@pytest.fixture(autouse=True)
def model_whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def mock_modal_tasks():
    with patch("src.features.generation.modal_tasks.run_generation") as standard:
        with patch("src.features.generation.modal_tasks.run_generation_heavy") as heavy:
            standard.spawn.return_value = None
            heavy.spawn.return_value = None
            yield standard, heavy


class TestGenerationServiceFlux2Routing:
    """Unit tests for Flux 2 service dispatch and parameter forwarding."""

    def test_flux2_txt2img_routes_to_standard_modal_task(self, mock_modal_tasks):
        """GIVEN a Flux 2 text-to-image job
        WHEN enqueuing Modal work
        THEN WorkflowEngine receives prompt/use_turbo and standard generation is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cinematic orchid")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model") as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a cinematic orchid",
                workflow_name=FLUX2_TXT2IMG_WORKFLOW,
                use_turbo=False,
            )

        standard, heavy = mock_modal_tasks
        heavy.spawn.assert_not_called()
        standard.spawn.assert_called_once()
        graph = standard.spawn.call_args.args[1]
        assert graph["prompt"]["98:6"]["inputs"]["text"] == "a cinematic orchid"
        assert graph["prompt"]["98:104"]["inputs"]["value"] is False
        assert mock_resolve.call_args_list == [
            call(FLUX2_UNET, "diffusion_models"),
            call(FLUX2_CLIP, "text_encoders"),
            call(FLUX2_TURBO_LORA, "loras"),
            call(FLUX2_VAE, "vae"),
        ]

    def test_flux2_editing_routes_base64_image_to_standard_modal_task(self, mock_modal_tasks):
        """GIVEN a Flux 2 editing job with an image_base64 payload
        WHEN enqueuing Modal work
        THEN the resolved graph receives the image input and standard generation is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("make the background golden")
        image_base64 = "data:image/png;base64,aGVsbG8="

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="make the background golden",
                workflow_name=FLUX2_EDITING_WORKFLOW,
                image_base64=image_base64,
                use_turbo=True,
            )

        standard, heavy = mock_modal_tasks
        heavy.spawn.assert_not_called()
        standard.spawn.assert_called_once()
        graph = standard.spawn.call_args.args[1]
        assert graph["prompt"]["68:6"]["inputs"]["text"] == "make the background golden"
        assert graph["prompt"]["68:94"]["inputs"]["value"] is True
        assert graph["prompt"]["46"]["inputs"]["image_url"] == image_base64

    @patch("src.features.generation.modal_tasks.run_generation_heavy")
    def test_identity_gguf_routes_to_heavy_modal_task(self, mock_run_generation_heavy, mock_modal_tasks):
        """GIVEN an identidad_gguf request
        WHEN enqueuing Modal work
        THEN the reference image is converted and heavy generation is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("identity preserving portrait")

        with patch("src.features.generation.service.download_image_to_base64", return_value="data:image/png;base64,abc123") as mock_download:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model") as mock_resolve:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="identity preserving portrait",
                    workflow_name="identidad_gguf",
                    image_url="https://example.com/reference.png",
                    width=1152,
                    height=896,
                    seed=777,
                )

        standard, _ = mock_modal_tasks
        standard.spawn.assert_not_called()
        mock_run_generation_heavy.spawn.assert_called_once()
        mock_download.assert_called_once_with("https://example.com/reference.png")
        mock_resolve.assert_has_calls(
            [
                call(IDENTITY_VAE, "vae"),
                call(IDENTITY_GGUF, "gguf"),
                call(IDENTITY_CLIP, "text_encoders"),
                call(IDENTITY_PULID, "pulid"),
                call(IDENTITY_FACE_DETECTOR, "face_detector"),
            ],
            any_order=True,
        )
        graph = mock_run_generation_heavy.spawn.call_args.args[1]
        assert graph["prompt"]["4"]["inputs"]["text"] == "identity preserving portrait"
        assert graph["prompt"]["6"]["inputs"]["image_url"] == "data:image/png;base64,abc123"
        assert graph["prompt"]["5"]["inputs"]["width"] == 1152
        assert graph["prompt"]["5"]["inputs"]["height"] == 896
        assert graph["prompt"]["11"]["inputs"]["seed"] == 777

    def test_legacy_workflow_is_rejected_before_modal_spawn(self, mock_modal_tasks):
        """GIVEN a retired workflow name
        WHEN enqueuing Modal work
        THEN unsupported_workflow is raised and no Modal task is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("legacy prompt")

        with pytest.raises(ValueError, match="unsupported_workflow"):
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="legacy prompt",
                workflow_name="qwen_txt2img",
            )

        standard, heavy = mock_modal_tasks
        standard.spawn.assert_not_called()
        heavy.spawn.assert_not_called()


class TestGenerationServiceLifecycle:
    """Unit tests for job lifecycle helpers that remain unchanged by Flux 2 routing."""

    def test_create_job(self):
        store = JobStore()
        service = GenerationService(job_store=store)

        job_id = service.create_job("a cyberpunk cat")

        assert len(job_id) > 0
        assert store.get_job(job_id)["status"] == "pending"

    def test_create_job_with_empty_prompt(self):
        store = JobStore()
        service = GenerationService(job_store=store)

        with pytest.raises(ValueError):
            service.create_job("")

    def test_get_job_not_found(self):
        store = JobStore()
        service = GenerationService(job_store=store)

        assert service.get_job("non-existent") is None

    def test_get_job_events_unknown_job(self):
        store = JobStore()
        service = GenerationService(job_store=store)

        events = list(service.get_job_events("non-existent"))

        assert events[0]["event"] == "error"
        assert events[0]["error"]["code"] == "job_not_found"

    def test_job_completed_event(self):
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="completed", image_path="/path/to/image.png")

        events = list(service.get_job_events(job_id))

        assert events[0]["event"] == "completed"
        assert events[0]["result"]["image_path"] == "/path/to/image.png"

    @pytest.mark.asyncio
    async def test_poll_job_events_yields_state_changes(self):
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = await store.acreate_job("polling test")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            events = []
            async for event in service.poll_job_events(job_id, interval=0.001):
                events.append(event)
                if event["event"] == "booting_server":
                    await store.aupdate_job(job_id, status="generating", progress=0, message="Running inference")
                elif event["event"] == "generating":
                    await store.aupdate_job(job_id, status="completed", image_path="/img.png")
                elif event["event"] == "completed":
                    break

        assert [event["event"] for event in events] == ["booting_server", "generating", "completed"]


class TestDispatchFlow:
    """Unit tests for dispatch_flow GPU/routing logic."""

    def test_dispatch_extraction_uses_heavy_gpu_for_l4(self):
        """GIVEN an extraction flow with L4 GPU profile
        WHEN dispatch_flow is called
        THEN run_generation_heavy is spawned (not standard).
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        import json
        from pathlib import Path
        BASE_REQUEST = {
            "workflow_name": "extraction",
            "gpu_profile": "L4",
            "timeout_s": 300,
        }
        from src.shared.flows.extraction import ExtractionRequest
        from src.shared.flows.base import ImageArtifact

        request = ExtractionRequest(
            **BASE_REQUEST,
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        job_id = store.create_job("extract")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                with patch("src.features.generation.modal_tasks.run_generation") as mock_standard:
                    mock_heavy.spawn.return_value = None
                    mock_standard.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        mock_heavy.spawn.assert_called_once()
        mock_standard.spawn.assert_not_called()

    def test_dispatch_flow_does_not_send_prompt_to_extraction(self):
        """GIVEN an extraction flow whose manifest does not declare 'prompt'
        WHEN dispatch_flow resolves parameters
        THEN 'prompt' is NOT included in the engine parameters.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.extraction import ExtractionRequest
        from src.shared.flows.base import ImageArtifact

        request = ExtractionRequest(
            workflow_name="extraction",
            gpu_profile="L4",
            timeout_s=300,
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        job_id = store.create_job("extract")

        from src.shared.workflows.engine import WorkflowEngine
        from unittest.mock import PropertyMock

        with patch.object(WorkflowEngine, "execute", return_value={"prompt": {}}) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        # The engine.execute should only receive params declared in the manifest
        call_params = mock_execute.call_args[0][0]
        # Extraction manifest only has 'input_image' — 'prompt' must not be sent
        assert "prompt" not in call_params, "prompt should NOT be passed to extraction engine"
        assert "input_image" in call_params, "input_image should be passed to extraction engine"
        assert call_params["input_image"] == "input/source.png"


def test_download_image_to_base64_encodes_http_image_response():
    mock_response = MagicMock()
    mock_response.content = b"fake-png-bytes"
    mock_response.headers = {"content-type": "image/png"}
    mock_response.raise_for_status.return_value = None

    with patch("src.features.generation.service.httpx.get", return_value=mock_response) as mock_get:
        result = download_image_to_base64("https://example.com/reference.png")

    mock_get.assert_called_once_with("https://example.com/reference.png", timeout=30, follow_redirects=True)
    assert result == "data:image/png;base64,ZmFrZS1wbmctYnl0ZXM="


def test_resolve_identity_seed_preserves_explicit_seed():
    assert resolve_identity_seed(777) == 777


def test_resolve_identity_seed_randomizes_minus_one():
    with patch("src.features.generation.service.secrets.randbelow", return_value=42) as mock_randbelow:
        result = resolve_identity_seed(-1)

    mock_randbelow.assert_called_once_with(2**63)
    assert result == 42
