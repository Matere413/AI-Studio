import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.features.generation.service import (
    FLUX2_EDITING_WORKFLOW,
    FLUX2_TXT2IMG_WORKFLOW,
    GenerationService,
)
from src.shared.job_store import JobStore


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"
IDENTITY_CLIP = "t5xxl_fp8_e4m3fn.safetensors"
IDENTITY_VAE = "flux-vae-bf16.safetensors"
IDENTITY_PULID = "pulid_flux_v0.9.1.safetensors"
IDENTITY_FACE_DETECTOR = "face_yolov8m.pt"
CONTROLNET_DEPTH = "flux-controlnet-depth-v1.safetensors"
CONTROLNET_CANNY = "flux-controlnet-canny-v1.safetensors"

WHITELIST_JSON = json.dumps(
    {
        "loras": [FLUX2_TURBO_LORA],
        "unets": [FLUX2_UNET],
        "clip": [FLUX2_CLIP, IDENTITY_CLIP],
        "vae": [FLUX2_VAE, IDENTITY_VAE],
        "pulid": [IDENTITY_PULID],
        "face_detector": [IDENTITY_FACE_DETECTOR],
        "controlnets": [CONTROLNET_DEPTH, CONTROLNET_CANNY],
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
            with patch("src.features.generation.modal_tasks.run_generation_a100") as a100:
                standard.spawn.return_value = None
                heavy.spawn.return_value = None
                a100.spawn.return_value = None
                yield standard, heavy, a100


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

        standard, heavy, a100 = mock_modal_tasks
        heavy.spawn.assert_not_called()
        a100.spawn.assert_not_called()
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

        standard, heavy, a100 = mock_modal_tasks
        heavy.spawn.assert_not_called()
        a100.spawn.assert_not_called()
        standard.spawn.assert_called_once()
        graph = standard.spawn.call_args.args[1]
        assert graph["prompt"]["68:6"]["inputs"]["text"] == "make the background golden"
        assert graph["prompt"]["68:94"]["inputs"]["value"] is True
        assert graph["prompt"]["46"]["inputs"]["image_url"] == image_base64

    def test_identidad_gguf_workflow_is_rejected_before_modal_spawn(self, mock_modal_tasks):
        """GIVEN the retired identidad_gguf workflow name
        WHEN enqueuing Modal work
        THEN unsupported_workflow is raised and no Modal task is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("legacy identity")

        with pytest.raises(ValueError, match="unsupported_workflow"):
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="legacy identity",
                workflow_name="identidad_gguf",
            )

        standard, heavy, a100 = mock_modal_tasks
        standard.spawn.assert_not_called()
        heavy.spawn.assert_not_called()
        a100.spawn.assert_not_called()

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

        standard, heavy, a100 = mock_modal_tasks
        standard.spawn.assert_not_called()
        heavy.spawn.assert_not_called()
        a100.spawn.assert_not_called()


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
        # image_path is intentionally omitted from WS events
        assert "image_path" not in events[0].get("result", {})

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
                    assert "image_path" not in event.get("result", {}), (
                        "completed event must not expose image_path"
                    )
                    break

        assert [event["event"] for event in events] == ["booting_server", "generating", "completed"]


class TestDispatchFlow:
    """Unit tests for dispatch_flow GPU/routing logic."""

    def test_dispatch_extraction_uses_heavy_gpu_for_l4(self):
        """GIVEN an extraction flow with L4 GPU profile
        WHEN dispatch_flow is called
        THEN run_generation_heavy is spawned (not standard, not a100).
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

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                with patch("src.features.generation.modal_tasks.run_generation") as mock_standard:
                    with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                        mock_heavy.spawn.return_value = None
                        mock_standard.spawn.return_value = None
                        mock_a100.spawn.return_value = None
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

        with patch.object(WorkflowEngine, "execute", return_value={"prompt": {}}) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        call_params = mock_execute.call_args[0][0]
        assert "prompt" not in call_params, "prompt should NOT be passed to extraction engine"
        assert "input_image" in call_params, "input_image should be passed to extraction engine"
        assert call_params["input_image"] == "input/source.png"

    def test_dispatch_composition_uses_heavy_gpu_for_l4(self):
        """GIVEN a composition flow with L4 GPU profile
        WHEN dispatch_flow is called
        THEN run_generation_heavy is spawned (not standard, not a100).
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose subject",
        )
        job_id = store.create_job("compose")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                with patch("src.features.generation.modal_tasks.run_generation") as mock_standard:
                    with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                        mock_heavy.spawn.return_value = None
                        mock_standard.spawn.return_value = None
                        mock_a100.spawn.return_value = None
                        service.dispatch_flow(job_id, request)

        mock_heavy.spawn.assert_called_once()
        mock_standard.spawn.assert_not_called()
        mock_a100.spawn.assert_not_called()

    def test_dispatch_composition_sends_correct_params(self):
        """GIVEN a composition flow
        WHEN dispatch_flow resolves parameters
        THEN prompt, background_image, foreground_image, control_strength,
        and control_net_name are passed.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            control_strength=0.8,
            prompt="compose subject onto background",
        )
        job_id = store.create_job("compose")

        from src.shared.workflows.engine import WorkflowEngine

        with patch.object(WorkflowEngine, "execute", return_value={"prompt": {}}) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        call_params = mock_execute.call_args[0][0]
        assert "prompt" in call_params
        assert call_params["prompt"] == "compose subject onto background"
        assert "background_image" in call_params
        assert call_params["background_image"] == "input/bg.png"
        assert "foreground_image" in call_params
        assert call_params["foreground_image"] == "input/fg.png"
        assert "control_mode" not in call_params
        assert "control_net_name" in call_params
        assert call_params["control_net_name"] == "flux-controlnet-depth-v1.safetensors"
        assert "control_strength" in call_params
        assert call_params["control_strength"] == 0.8

    def test_dispatch_composition_canny_mode_resolves_to_canny_model(self):
        """GIVEN a composition flow with canny mode
        WHEN dispatch_flow resolves parameters
        THEN control_net_name maps to the canny ControlNet model.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="canny",
            prompt="compose with canny",
        )
        job_id = store.create_job("compose")

        from src.shared.workflows.engine import WorkflowEngine

        graph_with_cn = {"prompt": {"15": {"inputs": {"image": ["18", 0], "strength": 1.0}}}}
        with patch.object(WorkflowEngine, "execute", return_value=graph_with_cn) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        call_params = mock_execute.call_args[0][0]
        assert call_params["control_net_name"] == "flux-controlnet-canny-v1.safetensors"

    def test_dispatch_composition_forwards_timeout_s_to_spawn(self):
        """GIVEN a composition flow with timeout_s=600
        WHEN dispatch_flow spawns the modal task
        THEN pipeline_timeout_s=600 is forwarded to spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose",
        )
        job_id = store.create_job("compose")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.return_value = None
                service.dispatch_flow(job_id, request)

        call = mock_heavy.spawn.call_args
        assert call is not None
        assert "pipeline_timeout_s" in call.kwargs
        assert call.kwargs["pipeline_timeout_s"] == 600

    def test_dispatch_composition_canny_switches_to_canny_preprocessor(self):
        """GIVEN a composition flow with control_mode="canny"
        WHEN dispatch_flow executes the workflow
        THEN the resolved graph has ControlNetApply.image set to the canny preprocessor.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="canny",
            prompt="compose with canny",
        )
        job_id = store.create_job("compose")

        from src.shared.workflows.engine import WorkflowEngine

        graph_with_cn = {"prompt": {"15": {"inputs": {"image": ["18", 0], "strength": 1.0}}}}
        with patch.object(WorkflowEngine, "execute", return_value=graph_with_cn) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        graph = mock_heavy.spawn.call_args.args[1]
        assert graph["prompt"]["15"]["inputs"]["image"] == ["19", 0], (
            "ControlNetApply.image must point to canny preprocessor (node 19)"
        )

    def test_dispatch_composition_depth_uses_depth_preprocessor(self):
        """GIVEN a composition flow with control_mode="depth"
        WHEN dispatch_flow executes the workflow
        THEN the resolved graph has ControlNetApply.image set to the depth preprocessor.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose with depth",
        )
        job_id = store.create_job("compose")

        from src.shared.workflows.engine import WorkflowEngine

        graph_with_cn = {"prompt": {"15": {"inputs": {"image": ["18", 0], "strength": 1.0}}}}
        with patch.object(WorkflowEngine, "execute", return_value=graph_with_cn) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    mock_heavy.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        graph = mock_heavy.spawn.call_args.args[1]
        assert graph["prompt"]["15"]["inputs"]["image"] == ["18", 0], (
            "ControlNetApply.image must point to depth preprocessor (node 18)"
        )

    def test_dispatch_identity_uses_a100_gpu(self):
        """GIVEN an identity flow with A100 GPU profile
        WHEN dispatch_flow is called
        THEN run_generation_a100 is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.identity import IdentityRequest
        from src.shared.flows.base import ImageArtifact

        request = IdentityRequest(
            workflow_name="identity",
            gpu_profile="A100",
            timeout_s=1200,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        job_id = store.create_job("identity")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                    with patch("src.features.generation.modal_tasks.run_generation") as mock_standard:
                        mock_a100.spawn.return_value = None
                        mock_heavy.spawn.return_value = None
                        mock_standard.spawn.return_value = None
                        service.dispatch_flow(job_id, request)

        mock_a100.spawn.assert_called_once()
        mock_heavy.spawn.assert_not_called()
        mock_standard.spawn.assert_not_called()

    def test_dispatch_identity_sends_correct_params(self):
        """GIVEN an identity flow
        WHEN dispatch_flow resolves parameters
        THEN reference_face, prompt are passed (correctly mapped).
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.identity import IdentityRequest
        from src.shared.flows.base import ImageArtifact

        request = IdentityRequest(
            workflow_name="identity",
            gpu_profile="A100",
            timeout_s=1200,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        job_id = store.create_job("identity")

        from src.shared.workflows.engine import WorkflowEngine

        with patch.object(WorkflowEngine, "execute", return_value={"prompt": {}}) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                    mock_a100.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        call_params = mock_execute.call_args[0][0]
        assert "prompt" in call_params
        assert call_params["prompt"] == "identity preserving portrait"
        assert "reference_face" in call_params
        assert call_params["reference_face"] == "input/reference.png"

    def test_dispatch_identity_forwards_timeout_s_to_spawn(self):
        """GIVEN an identity flow with timeout_s=1200
        WHEN dispatch_flow spawns the modal task
        THEN pipeline_timeout_s=1200 is forwarded to spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.identity import IdentityRequest
        from src.shared.flows.base import ImageArtifact

        request = IdentityRequest(
            workflow_name="identity",
            gpu_profile="A100",
            timeout_s=1200,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        job_id = store.create_job("identity")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                mock_a100.spawn.return_value = None
                service.dispatch_flow(job_id, request)

        call = mock_a100.spawn.call_args
        assert call is not None
        assert "pipeline_timeout_s" in call.kwargs
        assert call.kwargs["pipeline_timeout_s"] == 1200

    def test_dispatch_identity_sends_seed_to_engine(self):
        """GIVEN an identity flow with an explicit seed
        WHEN dispatch_flow resolves parameters
        THEN seed is included in engine params.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.identity import IdentityRequest
        from src.shared.flows.base import ImageArtifact

        request = IdentityRequest(
            workflow_name="identity",
            gpu_profile="A100",
            timeout_s=1200,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            seed=42,
            prompt="seeded identity",
        )
        job_id = store.create_job("identity")

        from src.shared.workflows.engine import WorkflowEngine

        with patch.object(WorkflowEngine, "execute", return_value={"prompt": {}}) as mock_execute:
            with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
                with patch("src.features.generation.modal_tasks.run_generation_a100") as mock_a100:
                    mock_a100.spawn.return_value = None
                    service.dispatch_flow(job_id, request)

        call_params = mock_execute.call_args[0][0]
        assert "seed" in call_params
        assert call_params["seed"] == 42


class TestValidateArtifactOwnership:
    """Unit tests for artifact ownership validation."""

    def test_rejects_artifact_without_source_job_and_non_input_path(self):
        """GIVEN an image artifact with no source_job_id and path not starting with input/
        WHEN dispatch_flow is called
        THEN ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="output/arbitrary/result.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="malicious path",
        )
        job_id = store.create_job("bad")

        with pytest.raises(ValueError, match="invalid_artifact"):
            service.dispatch_flow(job_id, request)

    def test_accepts_artifact_with_input_path_and_no_source_job(self):
        """GIVEN an image artifact with path starting with input/ and no source_job_id
        WHEN dispatch_flow validates
        THEN validation passes.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="valid input paths",
        )
        job_id = store.create_job("valid")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.return_value = None
                service.dispatch_flow(job_id, request)

    def test_accepts_artifact_with_valid_source_job_id(self):
        """GIVEN an image artifact with valid completed source_job_id
        WHEN dispatch_flow validates
        THEN validation passes.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        source_job_id = store.create_job("source extraction")
        store.update_job(source_job_id, status="completed", image_path="/path/to/result.png")

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="output/source_job/result.png",
                media_type="image/png",
                source_job_id=source_job_id,
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="chained artifact",
        )
        job_id = store.create_job("chained")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.return_value = None
                service.dispatch_flow(job_id, request)

    def test_rejects_artifact_with_bogus_source_job_id(self):
        """GIVEN an image artifact with source_job_id that does not exist
        WHEN dispatch_flow validates
        THEN ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="output/bogus/result.png",
                media_type="image/png",
                source_job_id="nonexistent-job",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="bogus source",
        )
        job_id = store.create_job("bogus")

        with pytest.raises(ValueError, match="invalid_artifact"):
            service.dispatch_flow(job_id, request)

    def test_rejects_artifact_with_pending_source_job_id(self):
        """GIVEN an image artifact with source_job_id that is not yet completed
        WHEN dispatch_flow validates
        THEN ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        pending_job_id = store.create_job("pending source")

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="output/pending/result.png",
                media_type="image/png",
                source_job_id=pending_job_id,
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="pending source",
        )
        job_id = store.create_job("pending-artifact")

        with pytest.raises(ValueError, match="invalid_artifact"):
            service.dispatch_flow(job_id, request)

    def test_rejects_asset_id_without_resolver(self):
        """GIVEN an image artifact with asset_id set
        WHEN dispatch_flow is called WITHOUT resolve_asset_url callback
        THEN ValueError is raised (fail-closed — must not trust volume_path).
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/malicious.png",
                media_type="image/png",
                asset_id="fake-asset-123",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="asset without resolver",
        )
        job_id = store.create_job("malicious-asset")

        # Mock model resolution so the test exercises the parameter path,
        # where the fail-open would occur.
        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.return_value = None
                # No resolve_asset_url passed — must reject, not fall back to volume_path
                with pytest.raises(ValueError, match="invalid_artifact"):
                    service.dispatch_flow(job_id, request)

    def test_accepts_asset_id_with_resolver(self):
        """GIVEN an image artifact with asset_id set
        WHEN dispatch_flow is called WITH resolve_asset_url callback
        THEN validation passes and the resolver is called.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/legit.png",
                media_type="image/png",
                asset_id="asset-legit-456",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="asset with resolver",
        )
        job_id = store.create_job("legit-asset")

        def fake_resolver(asset_id: str, session_id: str) -> str:
            return f"https://r2.example.com/{asset_id}"

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.return_value = None
                service.dispatch_flow(job_id, request, resolve_asset_url=fake_resolver)


    def test_dispatch_flow_marks_job_error_on_validation_failure(self):
        """GIVEN a pending job
        WHEN dispatch_flow raises ValueError (e.g. invalid artifact)
        THEN the job is updated to "error" status so it is not orphaned.
        """
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="etc/malicious",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="test orphaning",
        )
        job_id = store.create_job("test-orphaning")

        with patch("src.features.generation.service.resolve_cached_model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy"):
                with pytest.raises(ValueError, match="invalid_artifact"):
                    service.dispatch_flow(job_id, request)

        # The job MUST NOT stay "pending" — it must be terminal "error"
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status, got {job['status']!r}"
        )
        # Verify error metadata is recorded
        assert job.get("error_code") == "dispatch_failed"
        assert job.get("error_detail") is not None

    def test_dispatch_flow_marks_job_error_on_unsupported_workflow(self):
        """GIVEN a pending job
        WHEN dispatch_flow raises ValueError from an unsupported workflow
        THEN the job is updated to "error" status.
        """
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        request = CompositionRequest(
            workflow_name="nonexistent_workflow",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="test unsupported",
        )
        job_id = store.create_job("test-unsupported")

        with pytest.raises(ValueError, match="unsupported_workflow"):
            service.dispatch_flow(job_id, request)

        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error"

    def test_dispatch_flow_marks_job_error_on_storage_presign_failure(self):
        """GIVEN a pending job
        WHEN dispatch_flow calls resolve_asset_url and it raises StorageError
        THEN the job is updated to "error" status (not orphaned) and StorageError
        propagates as an infrastructure error (NOT wrapped as ValueError).
        """
        from src.shared.storage import StorageError
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        def _failing_resolver(asset_id: str, session_id: str) -> str:
            raise StorageError("R2 presigned GET failed: network error")

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
                asset_id="asset-1",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
                asset_id="asset-2",
            ),
            control_mode="depth",
            prompt="test storage presign failure",
        )
        job_id = store.create_job("test-storage-presign")

        with patch("src.features.generation.service.resolve_cached_model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy"):
                with pytest.raises(StorageError):
                    service.dispatch_flow(job_id, request, resolve_asset_url=_failing_resolver)

        # The job MUST NOT stay "pending" — it must be terminal "error"
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status, got {job['status']!r} — "
            "StorageError from resolver must be caught and job marked terminal"
        )
        assert job.get("error_code") == "dispatch_failed"

    def test_dispatch_flow_marks_job_error_on_generic_resolver_failure(self):
        """GIVEN a pending job
        WHEN dispatch_flow calls resolve_asset_url and it raises a generic
        Exception (e.g. ConnectionError)
        THEN the job is updated to "error" status as defense-in-depth.
        """
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        def _bomb_resolver(asset_id: str, session_id: str) -> str:
            raise ConnectionError("storage backend unreachable")

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
                asset_id="asset-1",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
                asset_id="asset-2",
            ),
            control_mode="depth",
            prompt="test generic resolver failure",
        )
        job_id = store.create_job("test-generic-fail")

        with patch("src.features.generation.service.resolve_cached_model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy"):
                with pytest.raises(ValueError):
                    service.dispatch_flow(job_id, request, resolve_asset_url=_bomb_resolver)

        # Defense-in-depth: even a non-standard exception from the
        # resolver must not orphan the job.
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status, got {job['status']!r}"
        )
        assert job.get("error_code") == "dispatch_failed"

    def test_dispatch_flow_marks_job_error_on_spawn_failure(self):
        """GIVEN a pending job
        WHEN dispatch_flow passes validation and task_fn.spawn raises
        THEN the job is marked "error" so it is not orphaned as "pending".
        """
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="test spawn failure",
        )
        job_id = store.create_job("test-spawn-fail")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.side_effect = RuntimeError("Modal GPU task failed to start")
                with pytest.raises(RuntimeError, match="Modal GPU task failed to start"):
                    service.dispatch_flow(job_id, request)

        # The job MUST NOT stay "pending" — spawn failure must mark it terminal
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status after spawn failure, got {job['status']!r}"
        )
        assert job.get("error_code") == "dispatch_failed"

    def test_dispatch_flow_marks_job_error_on_modal_infrastructure_failure(self):
        """GIVEN a pending job
        WHEN dispatch_flow passes validation and task_fn.spawn raises a
        non-standard infrastructure error (e.g. Modal timeout)
        THEN the job is marked "error" to prevent orphaning.
        """
        from src.shared.flows.extraction import ExtractionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

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
        job_id = store.create_job("test-infra-fail")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation_heavy") as mock_heavy:
                mock_heavy.spawn.side_effect = ConnectionError("Modal sandbox connection lost")
                with pytest.raises(ConnectionError):
                    service.dispatch_flow(job_id, request)

        # Even non-ValueError infrastructure failures must not orphan the job
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status after infra failure, got {job['status']!r}"
        )
        assert job.get("error_code") == "dispatch_failed"

    def test_dispatch_flow_marks_job_error_on_model_not_cached(self):
        """GIVEN a pending job
        WHEN dispatch_flow raises ModelNotCachedError during model resolution
        THEN the job is updated to "error" status so it is not orphaned.
        """
        from src.shared.workflows.cache import ModelNotCachedError
        from src.shared.flows.composition import CompositionRequest
        from src.shared.flows.base import ImageArtifact

        store = JobStore()
        service = GenerationService(job_store=store)

        request = CompositionRequest(
            workflow_name="composition",
            gpu_profile="L4",
            timeout_s=600,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="test model not cached",
        )
        job_id = store.create_job("test-model-not-cached")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            side_effect=ModelNotCachedError("flux2_dev_fp8mixed.safetensors", "diffusion_models", "/root/ComfyUI/models"),
        ):
            with patch("src.features.generation.modal_tasks.run_generation_heavy"):
                with pytest.raises(ModelNotCachedError):
                    service.dispatch_flow(job_id, request)

        # The job MUST be terminal — ModelNotCachedError is not a ValueError
        # so it was NOT caught by the old except ValueError handler.
        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status after ModelNotCachedError, got {job['status']!r}"
        )
        assert job.get("error_code") == "dispatch_failed"

class TestEnqueueModalWork:
    """Unit tests for enqueue_modal_work job orphaning protection."""

    def test_enqueue_modal_work_marks_job_error_on_model_not_cached(self):
        """GIVEN a pending job
        WHEN enqueue_modal_work raises ModelNotCachedError from model resolution
        THEN the job is updated to "error" status so it is not orphaned.
        """
        from src.shared.workflows.cache import ModelNotCachedError

        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("test-legacy-model-cache", session_id="session-1")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            side_effect=ModelNotCachedError(FLUX2_UNET, "diffusion_models", "/root/ComfyUI/models"),
        ):
            with patch("src.features.generation.modal_tasks.run_generation"):
                with pytest.raises(ModelNotCachedError):
                    service.enqueue_modal_work(
                        job_id=job_id,
                        prompt="a test prompt",
                        workflow_name=FLUX2_TXT2IMG_WORKFLOW,
                        use_turbo=False,
                    )

        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status after ModelNotCachedError, got {job['status']!r}"
        )
        assert job.get("error_code") == "modal_enqueue_failed"

    def test_enqueue_modal_work_marks_job_error_on_spawn_failure(self):
        """GIVEN a pending job
        WHEN enqueue_modal_work passes validation but Modal spawn raises
        THEN the job is updated to "error" status so it is not orphaned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("test-legacy-spawn-fail", session_id="session-1")

        with patch("src.features.generation.service.resolve_cached_model", return_value="/cached/model"):
            with patch("src.features.generation.modal_tasks.run_generation") as mock_standard:
                mock_standard.spawn.side_effect = RuntimeError("Modal task failed to start")
                with pytest.raises(RuntimeError, match="Modal task failed to start"):
                    service.enqueue_modal_work(
                        job_id=job_id,
                        prompt="a test prompt",
                        workflow_name=FLUX2_TXT2IMG_WORKFLOW,
                        use_turbo=False,
                    )

        job = store.get_job(job_id)
        assert job is not None
        assert job["status"] == "error", (
            f"Expected error status after spawn failure, got {job['status']!r}"
        )
        assert job.get("error_code") == "modal_enqueue_failed"
