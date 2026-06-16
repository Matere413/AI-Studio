import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch
from src.features.generation.service import GenerationService, resolve_qwen_quality_defaults
from src.shared.job_store import JobStore


DEFAULT_TXT2IMG_CHECKPOINT = "epicrealism_naturalSinRC1VAE.safetensors"
PRODUCT_PREMIUM_CHECKPOINT = "juggernautXL_ragnarok.safetensors"
PERSONA_CHECKPOINT = "RealVisXL_V4.0.safetensors"
QWEN_UNET = "qwen_image_2512_fp8_e4m3fn.safetensors"
QWEN_CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
QWEN_VAE = "qwen_image_vae.safetensors"
QWEN_LIGHTNING_LORA = "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"

WHITELIST_JSON = json.dumps({
    "checkpoints": [
        "sdxl.safetensors",
        "sd15.safetensors",
        "model.safetensors",
        DEFAULT_TXT2IMG_CHECKPOINT,
        PRODUCT_PREMIUM_CHECKPOINT,
        PERSONA_CHECKPOINT,
    ],
    "loras": ["detail_enhancer.safetensors", "lora.safetensors", QWEN_LIGHTNING_LORA],
    "unets": [QWEN_UNET],
    "clip": [QWEN_CLIP],
    "vae": [QWEN_VAE],
})

STRICT_WHITELIST_JSON = json.dumps({
    "checkpoints": ["sdxl.safetensors", "sd15.safetensors", "model.safetensors"],
    "loras": ["detail_enhancer.safetensors", "lora.safetensors"],
})


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def default_model_whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield





class TestModelWhitelistValidation:
    """Unit tests for model whitelist validation before Modal spawn.

    Spec: model-weight-caching/spec.md — Scenario: Non-whitelisted model rejected
    Spec: model-weight-caching/spec.md — Scenario: Whitelisted model accepted
    """

    def test_whitelisted_checkpoint_accepted(self, mock_run_generation):
        """GIVEN a request specifies a checkpoint that exists in the whitelist
        WHEN validate_models is called
        THEN no error is raised — model passes validation.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": STRICT_WHITELIST_JSON}):
            service.validate_models(checkpoint="sdxl.safetensors")
        # Should not raise — just validates

    def test_non_whitelisted_checkpoint_rejected(self, mock_run_generation):
        """GIVEN a request specifies a checkpoint NOT in the whitelist
        WHEN validate_models is called
        THEN model_not_allowed error is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": STRICT_WHITELIST_JSON}):
            with pytest.raises(ValueError, match="model_not_allowed"):
                service.validate_models(checkpoint="unknown_model.safetensors")

    def test_whitelisted_checkpoint_and_lora_accepted(self, mock_run_generation):
        """GIVEN a request specifies both a checkpoint and a lora in the whitelist
        WHEN validate_models is called
        THEN no error is raised — both models pass validation.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            service.validate_models(checkpoint="sdxl.safetensors", lora="detail_enhancer.safetensors")

    def test_non_whitelisted_lora_rejected(self, mock_run_generation):
        """GIVEN a request specifies a whitelisted checkpoint but a non-whitelisted lora
        WHEN validate_models is called
        THEN model_not_allowed is raised referencing the non-whitelisted lora.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with pytest.raises(ValueError, match="model_not_allowed") as exc_info:
                service.validate_models(checkpoint="sdxl.safetensors", lora="bogus_lora.safetensors")
        assert "bogus_lora.safetensors" in str(exc_info.value)

    def test_validated_models_spawn_modal_work(self, mock_run_generation):
        """GIVEN a request with whitelisted and cached models
        WHEN enqueue_modal_work is called
        THEN the Modal task is spawned (no model_not_allowed or model_not_cached error).
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with patch(
                "src.features.generation.service.resolve_cached_model",
                return_value="/root/ComfyUI/models/checkpoints/sdxl.safetensors",
            ) as mock_resolve:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    checkpoint_url="sdxl.safetensors",
                )
        mock_resolve.assert_called_once_with("sdxl.safetensors", "checkpoints")
        mock_run_generation.spawn.assert_called_once()

    def test_non_whitelisted_model_prevents_spawn(self, mock_run_generation):
        """GIVEN a non-whitelisted model
        WHEN enqueue_modal_work is called
        THEN no Modal task is spawned and model_not_allowed is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with pytest.raises(ValueError, match="model_not_allowed"):
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    checkpoint_url="forbidden_model.safetensors",
                )
        # No spawn should have happened
        mock_run_generation.spawn.assert_not_called()

    def test_missing_cached_model_prevents_spawn(self, mock_run_generation):
        """GIVEN a whitelisted model that is not present in the Volume
        WHEN enqueue_modal_work is called
        THEN ModelNotCachedError is raised and no Modal task is spawned.
        """
        from src.shared.workflows.cache import ModelNotCachedError

        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with pytest.raises(ModelNotCachedError) as exc_info:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    checkpoint_url="sdxl.safetensors",
                    workflow_name="txt2img",
                )
        assert exc_info.value.code == "model_not_cached"
        assert "sdxl.safetensors" in str(exc_info.value)
        mock_run_generation.spawn.assert_not_called()

    def test_default_workflow_checkpoint_without_explicit_model_is_rejected(self, mock_run_generation):
        """GIVEN a workflow template with a default checkpoint outside the whitelist
        WHEN enqueue_modal_work is called without an explicit checkpoint
        THEN the default checkpoint is validated and rejected before spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": STRICT_WHITELIST_JSON}):
            with pytest.raises(ValueError, match="model_not_allowed") as exc_info:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    workflow_name="txt2img",
                )
        assert DEFAULT_TXT2IMG_CHECKPOINT in str(exc_info.value)
        mock_run_generation.spawn.assert_not_called()

    def test_default_workflow_checkpoint_missing_from_cache_prevents_spawn(self, mock_run_generation):
        """GIVEN a workflow template whose default checkpoint is whitelisted but uncached
        WHEN enqueue_modal_work is called without an explicit checkpoint
        THEN the cache boundary is enforced before spawn.
        """
        from src.shared.workflows.cache import ModelNotCachedError

        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        allowed_models = json.dumps({"checkpoints": [DEFAULT_TXT2IMG_CHECKPOINT], "loras": []})
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": allowed_models}):
            with patch(
                "src.features.generation.service.resolve_cached_model",
                side_effect=ModelNotCachedError(DEFAULT_TXT2IMG_CHECKPOINT, "checkpoints", "/root/ComfyUI/models"),
            ) as mock_resolve:
                with pytest.raises(ModelNotCachedError):
                    service.enqueue_modal_work(
                        job_id=job_id,
                        prompt="a cyberpunk cat",
                        workflow_name="txt2img",
                    )
        mock_resolve.assert_called_once_with(DEFAULT_TXT2IMG_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_not_called()

    def test_cached_model_allows_spawn(self, mock_run_generation):
        """GIVEN a whitelisted model that is reported as cached
        WHEN enqueue_modal_work is called
        THEN cache resolution is called and the Modal task is spawned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with patch(
                "src.features.generation.service.resolve_cached_model",
                return_value="/root/ComfyUI/models/checkpoints/sdxl.safetensors",
            ) as mock_resolve:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    checkpoint_url="sdxl.safetensors",
                    workflow_name="txt2img",
                )
        mock_resolve.assert_called_once_with("sdxl.safetensors", "checkpoints")
        mock_run_generation.spawn.assert_called_once()


class TestGenerationService:
    """Unit tests for GenerationService business logic."""

    def test_product_premium_vertical_format_expands_to_manifest_dimensions(self, mock_run_generation):
        """GIVEN a product premium request in vertical format
        WHEN enqueuing Modal work
        THEN the workflow receives manifest-owned vertical dimensions.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a premium product shot")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{PRODUCT_PREMIUM_CHECKPOINT}",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a premium product shot",
                workflow_name="product_premium",
                format="vertical",
            )

        mock_resolve.assert_called_once_with(PRODUCT_PREMIUM_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        graph = mock_run_generation.spawn.call_args[0][1]
        assert graph["prompt"]["4"]["inputs"]["ckpt_name"] == PRODUCT_PREMIUM_CHECKPOINT
        assert graph["prompt"]["5"]["inputs"]["width"] == 720
        assert graph["prompt"]["5"]["inputs"]["height"] == 1280

    def test_product_premium_ignores_checkpoint_override(self, mock_run_generation):
        """GIVEN a product premium request with an explicit checkpoint override
        WHEN enqueuing Modal work
        THEN the manifest checkpoint remains in control server-side.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a premium product shot")

        override_checkpoint = "v1-5-pruned-emaonly-fp16.safetensors"
        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{PRODUCT_PREMIUM_CHECKPOINT}",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a premium product shot",
                workflow_name="product_premium",
                checkpoint_url=f"https://example.com/{override_checkpoint}",
            )

        mock_resolve.assert_called_once_with(PRODUCT_PREMIUM_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        graph = mock_run_generation.spawn.call_args[0][1]
        assert graph["prompt"]["4"]["inputs"]["ckpt_name"] == PRODUCT_PREMIUM_CHECKPOINT
        assert override_checkpoint not in str(graph)

    def test_realistic_persona_ignores_checkpoint_and_lora_overrides(self, mock_run_generation):
        """GIVEN a realistic persona request with explicit model overrides
        WHEN enqueuing Modal work
        THEN the manifest checkpoint remains locked and override models are ignored.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a documentary portrait")

        override_checkpoint = "model.safetensors"
        override_lora = "lora.safetensors"
        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{PERSONA_CHECKPOINT}",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a documentary portrait",
                workflow_name="realistic_persona",
                checkpoint_url=f"https://example.com/{override_checkpoint}",
                lora_url=f"https://example.com/{override_lora}",
                age=42,
                gender="woman",
                wardrobe="linen blazer",
                output_type="portrait",
            )

        mock_resolve.assert_called_once_with(PERSONA_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        graph = mock_run_generation.spawn.call_args[0][1]
        assert graph["prompt"]["4"]["inputs"]["ckpt_name"] == PERSONA_CHECKPOINT
        assert "42-year-old" in graph["prompt"]["6"]["inputs"]["text"]
        assert "linen blazer" in graph["prompt"]["6"]["inputs"]["text"]
        assert override_checkpoint not in str(graph)
        assert override_lora not in str(graph)

    def test_realistic_persona_uses_manifest_defaults_for_omitted_controls(self, mock_run_generation):
        """GIVEN a realistic persona request with only a prompt
        WHEN enqueuing Modal work
        THEN manifest defaults fill omitted persona controls before spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a documentary portrait")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{PERSONA_CHECKPOINT}",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a documentary portrait",
                workflow_name="realistic_persona",
            )

        mock_resolve.assert_called_once_with(PERSONA_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        graph = mock_run_generation.spawn.call_args[0][1]
        positive_prompt = graph["prompt"]["6"]["inputs"]["text"]
        assert graph["prompt"]["4"]["inputs"]["ckpt_name"] == PERSONA_CHECKPOINT
        assert "34-year-old" in positive_prompt
        assert "timeless casual wardrobe" in positive_prompt
        assert "a documentary portrait" in positive_prompt
        assert graph["prompt"]["10"]["inputs"]["image_url"] == ""
        assert graph["prompt"]["12"]["inputs"]["strength"] == 0

    def test_realistic_persona_with_reference_image_enables_faceid_strength(self, mock_run_generation):
        """GIVEN a realistic persona request with a reference image
        WHEN enqueuing Modal work
        THEN the workflow receives the image URL and FaceID strength is enabled.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a documentary portrait")
        reference_image = "data:image/png;base64,iVBORw0KGgo="

        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{PERSONA_CHECKPOINT}",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a documentary portrait",
                workflow_name="realistic_persona",
                image_url=reference_image,
            )

        mock_resolve.assert_called_once_with(PERSONA_CHECKPOINT, "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        graph = mock_run_generation.spawn.call_args[0][1]
        assert graph["prompt"]["10"]["inputs"]["image_url"] == reference_image
        assert graph["prompt"]["12"]["inputs"]["strength"] == 0.75

    def test_create_job(self):
        """GIVEN a prompt
        WHEN creating a job
        THEN a job_id is returned and the job is stored with pending status.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        assert job_id is not None
        assert len(job_id) > 0
        job = store.get_job(job_id)
        assert job["status"] == "pending"
        assert job["prompt"] == "a cyberpunk cat"

    def test_create_job_with_empty_prompt(self):
        """GIVEN an empty prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises(ValueError):
            service.create_job("")

    def test_create_job_with_whitespace_prompt(self):
        """GIVEN a whitespace-only prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises(ValueError):
            service.create_job("   ")

    def test_create_job_with_none_prompt(self):
        """GIVEN None as prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises((ValueError, TypeError)):
            service.create_job(None)

    def test_get_job_status(self):
        """GIVEN a created job
        WHEN getting its status
        THEN the job data is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        job = service.get_job(job_id)
        assert job["status"] == "pending"

    def test_get_job_not_found(self):
        """GIVEN no job exists
        WHEN getting a job
        THEN None is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job = service.get_job("non-existent")
        assert job is None

    def test_get_job_events_unknown_job(self):
        """GIVEN no job exists
        WHEN getting lifecycle events
        THEN a terminal error event with job_not_found is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        events = list(service.get_job_events("non-existent"))
        assert events[0]["event"] == "error"
        assert events[0]["error"]["code"] == "job_not_found"

    def test_map_failure_to_terminal_error(self):
        """GIVEN a failure occurs
        WHEN mapping the failure
        THEN a terminal error with code and detail is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        error = service.map_failure_to_error("GPU_TIMEOUT", "GPU execution timed out")
        assert error["code"] == "GPU_TIMEOUT"
        assert error["detail"] == "GPU execution timed out"

    def test_enqueue_modal_work(self, mock_run_generation):
        """GIVEN a job is created
        WHEN enqueuing Modal work
        THEN the Modal task spawn is called with a resolved graph dict.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{DEFAULT_TXT2IMG_CHECKPOINT}",
        ):
            service.enqueue_modal_work(job_id, "a cyberpunk cat")
        mock_run_generation.spawn.assert_called_once()
        call_args = mock_run_generation.spawn.call_args
        assert call_args[0][0] == job_id  # first positional arg
        assert isinstance(call_args[0][1], dict)  # second positional arg is a graph dict
        assert "prompt" in call_args[0][1]

    def test_enqueue_modal_work_with_workflow_params(self, mock_run_generation):
        """GIVEN checkpoint URL
        WHEN enqueuing Modal work
        THEN the resolved graph contains the whitelisted checkpoint filename
        AND cache presence is validated before spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}):
            with patch(
                "src.features.generation.service.resolve_cached_model",
                return_value="/root/ComfyUI/models/checkpoints/model.safetensors",
            ) as mock_resolve:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cyberpunk cat",
                    workflow_name="txt2img",
                    checkpoint_url="https://example.com/model.safetensors",
                )
        mock_resolve.assert_called_once_with("model.safetensors", "checkpoints")
        mock_run_generation.spawn.assert_called_once()
        call_args = mock_run_generation.spawn.call_args
        assert call_args[0][0] == job_id
        graph = call_args[0][1]
        assert isinstance(graph, dict)
        assert "prompt" in graph
        assert graph["prompt"]["4"]["inputs"]["ckpt_name"] == "model.safetensors"

    def test_enqueue_modal_work_with_image_params(self, mock_run_generation):
        """GIVEN image_url and denoise for img2img
        WHEN enqueuing Modal work
        THEN the resolved graph contains the image and denoise parameters.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{DEFAULT_TXT2IMG_CHECKPOINT}",
        ):
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a cyberpunk cat",
                workflow_name="img2img",
                image_url="https://example.com/image.png",
                denoise=0.5,
            )
        mock_run_generation.spawn.assert_called_once()
        call_args = mock_run_generation.spawn.call_args
        graph = call_args[0][1]
        assert graph["prompt"]["10"]["inputs"]["image"] == "https://example.com/image.png"
        assert graph["prompt"]["3"]["inputs"]["denoise"] == 0.5

    def test_enqueue_modal_work_with_controlnet_params(self, mock_run_generation):
        """GIVEN control_image_url and control_strength for controlnet
        WHEN enqueuing Modal work
        THEN the resolved graph contains the control parameters.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value=f"/root/ComfyUI/models/checkpoints/{DEFAULT_TXT2IMG_CHECKPOINT}",
        ):
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a cyberpunk cat",
                workflow_name="controlnet",
                control_image_url="https://example.com/control.png",
                control_strength=1.5,
            )
        mock_run_generation.spawn.assert_called_once()
        call_args = mock_run_generation.spawn.call_args
        graph = call_args[0][1]
        assert graph["prompt"]["10"]["inputs"]["image"] == "https://example.com/control.png"
        assert graph["prompt"]["11"]["inputs"]["strength"] == 1.5

    @pytest.mark.parametrize(
        ("quality_mode", "expected"),
        [
            (
                "high",
                {
                    "steps": 50,
                    "cfg": 7.0,
                    "sampler_name": "euler_ancestral",
                    "sampler_scheduler": "normal",
                },
            ),
            (
                "fast",
                {
                    "steps": 4,
                    "cfg": 1.5,
                    "sampler_name": "euler",
                    "sampler_scheduler": "sgm_uniform",
                },
            ),
        ],
    )
    def test_qwen_quality_mode_defaults_resolution(self, quality_mode, expected):
        """GIVEN a Qwen quality mode
        WHEN resolving sampler defaults
        THEN it matches the design quality table.
        """
        assert resolve_qwen_quality_defaults(quality_mode) == expected

    def test_qwen_high_quality_workflow_resolves_dimensions_and_sampler_defaults(self, mock_run_generation):
        """GIVEN a qwen_txt2img high-quality request
        WHEN enqueuing Modal work
        THEN the resolved graph receives dimensions and high-quality sampler params.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cinematic Qwen image")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value="/root/ComfyUI/models/cached/model.safetensors",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a cinematic Qwen image",
                workflow_name="qwen_txt2img",
                width=1280,
                height=768,
                quality_mode="high",
            )

        assert mock_resolve.call_args_list == [
            call(QWEN_UNET, "unets"),
            call(QWEN_CLIP, "clip"),
            call(QWEN_VAE, "vae"),
        ]
        graph = mock_run_generation.spawn.call_args[0][1]
        sampler = graph["prompt"]["6"]["inputs"]
        assert graph["prompt"]["5"]["inputs"]["width"] == 1280
        assert graph["prompt"]["5"]["inputs"]["height"] == 768
        assert sampler["steps"] == 50
        assert sampler["cfg"] == 7.0
        assert sampler["sampler_name"] == "euler_ancestral"
        assert sampler["scheduler"] == "normal"
        assert all(node["class_type"] != "LoraLoaderModelOnly" for node in graph["prompt"].values())

    def test_qwen_fast_quality_injects_lightning_lora_and_redirects_sampler_model(self, mock_run_generation):
        """GIVEN a qwen_txt2img fast request
        WHEN enqueuing Modal work
        THEN a Lightning LoRA node is inserted before KSampler.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cinematic Qwen image")

        with patch(
            "src.features.generation.service.resolve_cached_model",
            return_value="/root/ComfyUI/models/cached/model.safetensors",
        ) as mock_resolve:
            service.enqueue_modal_work(
                job_id=job_id,
                prompt="a cinematic Qwen image",
                workflow_name="qwen_txt2img",
                quality_mode="fast",
            )

        assert call(QWEN_LIGHTNING_LORA, "loras") in mock_resolve.call_args_list
        graph = mock_run_generation.spawn.call_args[0][1]
        lora_nodes = {
            node_id: node
            for node_id, node in graph["prompt"].items()
            if node["class_type"] == "LoraLoaderModelOnly"
        }
        assert lora_nodes
        lora_node_id, lora_node = next(iter(lora_nodes.items()))
        assert lora_node["inputs"]["lora_name"] == QWEN_LIGHTNING_LORA
        assert graph["prompt"]["6"]["inputs"]["model"] == [lora_node_id, 0]
        assert graph["prompt"]["6"]["inputs"]["steps"] == 4
        assert graph["prompt"]["6"]["inputs"]["cfg"] == 1.5

    def test_qwen_missing_whitelist_entry_prevents_spawn(self, mock_run_generation):
        """GIVEN Qwen model defaults are not all whitelisted
        WHEN enqueuing Modal work
        THEN model_not_allowed is raised before Modal spawn.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cinematic Qwen image")
        qwen_without_clip = json.dumps({"unets": [QWEN_UNET], "clip": [], "vae": [QWEN_VAE], "loras": [QWEN_LIGHTNING_LORA]})

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": qwen_without_clip}):
            with pytest.raises(ValueError, match="model_not_allowed") as exc_info:
                service.enqueue_modal_work(
                    job_id=job_id,
                    prompt="a cinematic Qwen image",
                    workflow_name="qwen_txt2img",
                )

        assert QWEN_CLIP in str(exc_info.value)
        mock_run_generation.spawn.assert_not_called()

    def test_resolve_workflow(self):
        """GIVEN a workflow name and params
        WHEN resolving the workflow
        THEN a resolved graph is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        graph = service.resolve_workflow("txt2img", {"prompt": "test"})
        assert isinstance(graph, dict)
        assert graph["prompt"]["6"]["inputs"]["text"] == "test"

    def test_job_lifecycle_events(self):
        """GIVEN a job exists
        WHEN getting lifecycle events
        THEN the current event is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        events = list(service.get_job_events(job_id))
        assert len(events) > 0
        assert events[0]["event"] == "booting_server"

    def test_job_completed_event(self):
        """GIVEN a job is completed
        WHEN getting lifecycle events
        THEN a completed event with image_path is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="completed", image_path="/path/to/image.png")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "completed"
        assert events[0]["result"]["image_path"] == "/path/to/image.png"

    def test_job_running_event_maps_to_generating(self):
        """GIVEN a legacy 'running' job status
        WHEN getting lifecycle events
        THEN it is mapped to a generating event.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="running")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "generating"
        assert events[0]["progress"] == 50
        assert events[0]["message"] == "Processing"

    def test_job_booting_server_event(self):
        """GIVEN a job is booting the ComfyUI server
        WHEN getting lifecycle events
        THEN a booting_server event is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="booting_server", progress=0, message="Booting ComfyUI server")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "booting_server"
        assert events[0]["progress"] == 0
        assert events[0]["message"] == "Booting ComfyUI server"

    def test_job_downloading_weights_event(self):
        """GIVEN a job is validating cached weights
        WHEN getting lifecycle events
        THEN a downloading_weights event is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="downloading_weights", progress=0, message="Validating cached weights")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "downloading_weights"
        assert events[0]["progress"] == 0

    def test_job_progress_event(self):
        """GIVEN a job reports granular progress
        WHEN getting lifecycle events
        THEN a progress event with numeric progress is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="progress", progress=42, message="Sampling step 5/10")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "progress"
        assert events[0]["progress"] == 42
        assert events[0]["message"] == "Sampling step 5/10"

    def test_job_error_event(self):
        """GIVEN a job fails
        WHEN getting lifecycle events
        THEN an error event with code and detail is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="error", error_code="comfyui_execution_failed", error_detail="GPU unavailable")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "error"
        assert events[0]["error"]["code"] == "comfyui_execution_failed"
        assert events[0]["error"]["detail"] == "GPU unavailable"

    def test_enqueue_modal_work_failure(self, mock_run_generation):
        """GIVEN a Modal task fails
        WHEN enqueuing work
        THEN the error is propagated.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("a cyberpunk cat")
        mock_run_generation.spawn.side_effect = Exception("GPU unavailable")
        with pytest.raises(Exception):
            service.enqueue_modal_work(job_id, "a cyberpunk cat")

    @pytest.mark.asyncio
    async def test_poll_job_events_yields_state_changes(self):
        """GIVEN a job exists and transitions through states
        WHEN polling for events
        THEN events are yielded for each state change.
        """
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

            assert len(events) == 3
            assert events[0]["event"] == "booting_server"
            assert events[1]["event"] == "generating"
            assert events[2]["event"] == "completed"
            assert events[2]["result"]["image_path"] == "/img.png"

    @pytest.mark.asyncio
    async def test_poll_job_events_yields_progress_changes(self):
        """GIVEN a job keeps the same status but progress changes
        WHEN polling for events
        THEN a progress event is yielded for each progress update.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = await store.acreate_job("progress polling test")
        await store.aupdate_job(job_id, status="generating", progress=10, message="Running inference")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            events = []
            async for event in service.poll_job_events(job_id, interval=0.001):
                events.append(event)
                if event["event"] == "completed":
                    break
                if event.get("progress") == 10:
                    await store.aupdate_job(job_id, status="generating", progress=50, message="Halfway")
                elif event.get("progress") == 50:
                    await store.aupdate_job(job_id, status="completed", image_path="/img.png")

            assert len(events) == 3
            assert events[0]["event"] == "generating"
            assert events[0]["progress"] == 10
            assert events[1]["event"] == "generating"
            assert events[1]["progress"] == 50
            assert events[2]["event"] == "completed"

    @pytest.mark.asyncio
    async def test_poll_job_events_unknown_job(self):
        """GIVEN no job exists
        WHEN polling for events
        THEN a terminal error event is yielded.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            events = []
            async for event in service.poll_job_events("unknown-job", interval=0.001):
                events.append(event)

            assert len(events) == 1
            assert events[0]["event"] == "error"
            assert events[0]["error"]["code"] == "job_not_found"
