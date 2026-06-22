"""Contract tests for supported workflow templates and manifests."""

import json
from pathlib import Path

import yaml

from src.shared.modal_config import default_whitelist
from src.shared.workflows.models import ManifestSchema


SUPPORTED_WORKFLOWS = {
    "flux2_txt2img",
    "flux2_editing",
    "extraction",
    "composition",
    "identity",
}
RETIRED_WORKFLOWS = {
    "identidad_gguf",
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
        # Extraction flow does not map prompt as a node input
        # (the BRIA workflow doesn't use text prompts)
        if workflow_name in ("flux2_txt2img", "flux2_editing", "composition", "identity"):
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


def test_extraction_manifest_declares_input_image():
    """GIVEN the extraction workflow
    THEN its manifest declares input_image pointing to LoadImage.
    """
    workflow, manifest = _load_workflow("extraction")

    assert "input_image" in manifest.inputs
    mapping = manifest.inputs["input_image"]
    node = workflow["prompt"][mapping.node_id]
    assert node["class_type"] in ("LoadImage", "LoadImageFromBase64")


def test_composition_manifest_declares_control_net_inputs():
    """GIVEN the composition workflow
    THEN its manifest declares control_net_name and control_strength.
    """
    workflow, manifest = _load_workflow("composition")

    assert "control_net_name" in manifest.inputs
    assert "control_strength" in manifest.inputs

    cn_mapping = manifest.inputs["control_net_name"]
    cn_node = workflow["prompt"][cn_mapping.node_id]
    assert cn_node["class_type"] == "ControlNetLoader"

    cs_mapping = manifest.inputs["control_strength"]
    cs_node = workflow["prompt"][cs_mapping.node_id]
    assert cs_node["class_type"] == "ControlNetApply"


def test_identity_manifest_declares_reference_face_and_pulid():
    """GIVEN the identity workflow
    THEN its manifest declares reference_face pointing to LoadImage
    and pulid model inputs.
    """
    workflow, manifest = _load_workflow("identity")

    assert "reference_face" in manifest.inputs
    mapping = manifest.inputs["reference_face"]
    node = workflow["prompt"][mapping.node_id]
    assert node["class_type"] in ("LoadImage",)

    assert "pulid" in manifest.inputs
    pulid_mapping = manifest.inputs["pulid"]
    pulid_node = workflow["prompt"][pulid_mapping.node_id]
    assert pulid_node["class_type"] == "PulidFluxModelLoader"


def test_retired_workflow_assets_are_removed():
    for workflow_name in RETIRED_WORKFLOWS:
        assert not Path(f"src/workflows/{workflow_name}/workflow.json").exists()
        assert not Path(f"src/workflows/{workflow_name}/manifest.yaml").exists()


def test_default_whitelist_matches_supported_workflows_only():
    whitelist = json.loads(default_whitelist)
    encoded = json.dumps(whitelist)

    assert "flux2_dev_fp8mixed.safetensors" in whitelist["unets"]
    assert "Flux_2-Turbo-LoRA_comfyui.safetensors" in whitelist["loras"]
    assert "pulid_flux_v0.9.1.safetensors" in whitelist["pulid"]
    assert "qwen_image_2512_fp8_e4m3fn.safetensors" not in encoded
    assert "RealVisXL_V4.0.safetensors" not in encoded
