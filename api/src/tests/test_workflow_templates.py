"""Contract tests for supported workflow templates and manifests."""

import json
from pathlib import Path

import yaml

from src.shared.modal_config import default_whitelist
from src.shared.workflows.models import ManifestSchema


SUPPORTED_WORKFLOWS = {
    "flux2_txt2img",
    "flux2_editing",
    "identidad_gguf",
}
RETIRED_WORKFLOWS = {
    "qwen_txt2img",
    "realistic_persona",
    "product_premium",
    "txt2img",
    "controlnet",
    "img2img",
}


def _load_workflow(name: str):
    workflow_path = Path(f"src/workflows/{name}/workflow.json")
    manifest_path = Path(f"src/workflows/{name}/manifest.yaml")
    assert workflow_path.exists(), f"{name} workflow.json not found"
    assert manifest_path.exists(), f"{name} manifest.yaml not found"

    with open(workflow_path) as workflow_file:
        workflow = json.load(workflow_file)
    with open(manifest_path) as manifest_file:
        manifest = ManifestSchema.model_validate(yaml.safe_load(manifest_file))
    return workflow, manifest


def test_supported_workflow_assets_exist_and_validate():
    for workflow_name in SUPPORTED_WORKFLOWS:
        workflow, manifest = _load_workflow(workflow_name)

        assert "prompt" in workflow
        assert "prompt" in manifest.inputs


def test_flux2_txt2img_manifest_declares_turbo_and_flux2_models():
    workflow, manifest = _load_workflow("flux2_txt2img")

    assert manifest.inputs["prompt"].node_id == "98:6"
    assert manifest.inputs["use_turbo"].node_id == "98:104"
    assert workflow["prompt"]["98:104"]["class_type"] == "PrimitiveBoolean"
    assert manifest.defaults["unet"] == "flux2_dev_fp8mixed.safetensors"
    assert manifest.defaults["clip"] == "mistral_3_small_flux2_bf16.safetensors"
    assert manifest.defaults["vae"] == "full_encoder_small_decoder.safetensors"
    assert manifest.defaults["lora"] == "Flux_2-Turbo-LoRA_comfyui.safetensors"


def test_flux2_editing_manifest_declares_base64_loader():
    workflow, manifest = _load_workflow("flux2_editing")

    assert manifest.inputs["image_base64"].node_id == "46"
    assert manifest.inputs["image_base64"].field == "image_url"
    assert workflow["prompt"]["46"]["class_type"] == "LoadImageFromBase64"
    assert "width" not in manifest.inputs
    assert "height" not in manifest.inputs


def test_identity_gguf_manifest_remains_supported():
    workflow, manifest = _load_workflow("identidad_gguf")

    assert manifest.inputs["image_url"].node_id == "6"
    assert workflow["prompt"]["6"]["class_type"] == "LoadImageFromBase64"
    assert manifest.defaults["gguf"] == "flux1-dev-q4_k_m.gguf"
    assert manifest.defaults["pulid"] == "pulid_flux_v0.9.1.safetensors"


def test_retired_workflow_assets_are_removed():
    for workflow_name in RETIRED_WORKFLOWS:
        assert not Path(f"src/workflows/{workflow_name}/workflow.json").exists()
        assert not Path(f"src/workflows/{workflow_name}/manifest.yaml").exists()


def test_default_whitelist_matches_supported_workflows_only():
    whitelist = json.loads(default_whitelist)
    encoded = json.dumps(whitelist)

    assert "flux2_dev_fp8mixed.safetensors" in whitelist["unets"]
    assert "Flux_2-Turbo-LoRA_comfyui.safetensors" in whitelist["loras"]
    assert "flux1-dev-q4_k_m.gguf" in whitelist["gguf"]
    assert "qwen_image_2512_fp8_e4m3fn.safetensors" not in encoded
    assert "RealVisXL_V4.0.safetensors" not in encoded
