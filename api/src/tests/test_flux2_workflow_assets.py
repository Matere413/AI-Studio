"""Contract tests for Flux 2 workflow assets."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import yaml

from src.shared.workflows.engine import WorkflowEngine
from src.shared.workflows.models import ManifestSchema


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"


def flux2_whitelist() -> str:
    return json.dumps(
        {
            "unets": [FLUX2_UNET],
            "clip": [FLUX2_CLIP],
            "vae": [FLUX2_VAE],
            "loras": [FLUX2_TURBO_LORA],
        }
    )


class TestFlux2Txt2ImgWorkflowAssets:
    """Contract tests for the Flux 2 text-to-image workflow."""

    def test_flux2_txt2img_manifest_declares_prompt_turbo_and_model_defaults(self):
        """GIVEN the Flux 2 text-to-image manifest
        WHEN loading it as a ManifestSchema
        THEN prompt, turbo, and locked Flux 2 model defaults are declared.
        """
        manifest_path = Path("src/workflows/flux2_txt2img/manifest.yaml")

        with open(manifest_path) as f:
            manifest = ManifestSchema.model_validate(yaml.safe_load(f))

        assert manifest.inputs["prompt"].node_id == "98:6"
        assert manifest.inputs["prompt"].field == "text"
        assert manifest.inputs["use_turbo"].node_id == "98:104"
        assert manifest.inputs["use_turbo"].field == "value"
        assert manifest.defaults["unet"] == FLUX2_UNET
        assert manifest.defaults["clip"] == FLUX2_CLIP
        assert manifest.defaults["vae"] == FLUX2_VAE
        assert manifest.defaults["lora"] == FLUX2_TURBO_LORA

    def test_flux2_txt2img_engine_applies_prompt_turbo_and_defaults(self):
        """GIVEN Flux 2 text-to-image workflow assets
        WHEN applying runtime parameters
        THEN the prompt, turbo switch, and model defaults resolve into the graph.
        """
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": flux2_whitelist()}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/flux2_txt2img/workflow.json",
                manifest_path="src/workflows/flux2_txt2img/manifest.yaml",
            )

        resolved = engine.apply_parameters(
            {"prompt": "a glossy perfume bottle on obsidian", "use_turbo": True}
        )

        assert resolved["prompt"]["98:6"]["inputs"]["text"] == "a glossy perfume bottle on obsidian"
        assert resolved["prompt"]["98:104"]["inputs"]["value"] is True
        assert resolved["prompt"]["98:12"]["inputs"]["unet_name"] == FLUX2_UNET
        assert resolved["prompt"]["98:38"]["inputs"]["clip_name"] == FLUX2_CLIP
        assert resolved["prompt"]["98:10"]["inputs"]["vae_name"] == FLUX2_VAE
        assert resolved["prompt"]["98:101"]["inputs"]["lora_name"] == FLUX2_TURBO_LORA


class TestFlux2EditingWorkflowAssets:
    """Contract tests for the Flux 2 editing workflow."""

    def test_flux2_editing_workflow_replaces_load_image_with_base64_loader(self):
        """GIVEN the Flux 2 editing workflow template
        WHEN loading the JSON asset
        THEN node 46 accepts base64 image input via LoadImageFromBase64.
        """
        workflow_path = Path("src/workflows/flux2_editing/workflow.json")

        with open(workflow_path) as f:
            workflow = json.load(f)

        assert workflow["prompt"]["46"]["class_type"] == "LoadImageFromBase64"
        assert workflow["prompt"]["46"]["inputs"] == {"image_url": ""}

    def test_flux2_editing_engine_applies_prompt_turbo_image_and_defaults(self):
        """GIVEN Flux 2 editing workflow assets
        WHEN applying runtime parameters
        THEN prompt, turbo, image_base64, and model defaults resolve into the graph.
        """
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": flux2_whitelist()}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/flux2_editing/workflow.json",
                manifest_path="src/workflows/flux2_editing/manifest.yaml",
            )

        resolved = engine.apply_parameters(
            {
                "prompt": "change the jacket to matte black leather",
                "use_turbo": False,
                "image_base64": "data:image/png;base64,aGVsbG8=",
            }
        )

        assert resolved["prompt"]["68:6"]["inputs"]["text"] == "change the jacket to matte black leather"
        assert resolved["prompt"]["68:94"]["inputs"]["value"] is False
        assert resolved["prompt"]["46"]["inputs"]["image_url"] == "data:image/png;base64,aGVsbG8="
        assert resolved["prompt"]["68:12"]["inputs"]["unet_name"] == FLUX2_UNET
        assert resolved["prompt"]["68:38"]["inputs"]["clip_name"] == FLUX2_CLIP
        assert resolved["prompt"]["68:10"]["inputs"]["vae_name"] == FLUX2_VAE
        assert resolved["prompt"]["68:89"]["inputs"]["lora_name"] == FLUX2_TURBO_LORA
