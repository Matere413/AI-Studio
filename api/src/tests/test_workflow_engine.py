"""Unit tests for the WorkflowEngine."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from src.shared.workflows.engine import WorkflowEngine


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"
IDENTITY_CLIP = "t5xxl_fp8_e4m3fn.safetensors"
IDENTITY_VAE = "flux-vae-bf16.safetensors"
IDENTITY_PULID = "pulid_flux_v0.9.1.safetensors"
IDENTITY_FACE_DETECTOR = "face_yolov8m.pt"

WHITELIST_JSON = json.dumps(
    {
        "loras": [FLUX2_TURBO_LORA],
        "unets": [FLUX2_UNET],
        "clip": [FLUX2_CLIP, IDENTITY_CLIP],
        "vae": [FLUX2_VAE, IDENTITY_VAE],
        "pulid": [IDENTITY_PULID],
        "face_detector": [IDENTITY_FACE_DETECTOR],
    }
)


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture
def flux2_engine():
    return WorkflowEngine(
        template_path="src/workflows/flux2_txt2img/workflow.json",
        manifest_path="src/workflows/flux2_txt2img/manifest.yaml",
    )


def test_loads_valid_flux2_template_and_manifest(flux2_engine):
    assert flux2_engine.template is not None
    assert set(["prompt", "use_turbo", "unet", "clip", "vae", "lora"]).issubset(flux2_engine.manifest.inputs)


def test_missing_template_raises():
    with pytest.raises(FileNotFoundError):
        WorkflowEngine(
            template_path="src/workflows/missing/workflow.json",
            manifest_path="src/workflows/flux2_txt2img/manifest.yaml",
        )


def test_invalid_node_reference_raises():
    bad_manifest = {"inputs": {"prompt": {"node_id": "999", "field": "text"}}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(bad_manifest, f)
        manifest_path = f.name

    try:
        with pytest.raises(ValueError, match="missing node"):
            WorkflowEngine(
                template_path="src/workflows/flux2_txt2img/workflow.json",
                manifest_path=manifest_path,
            )
    finally:
        os.unlink(manifest_path)


def test_invalid_field_reference_raises():
    bad_manifest = {"inputs": {"prompt": {"node_id": "98:6", "field": "missing"}}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(bad_manifest, f)
        manifest_path = f.name

    try:
        with pytest.raises(ValueError, match="missing field"):
            WorkflowEngine(
                template_path="src/workflows/flux2_txt2img/workflow.json",
                manifest_path=manifest_path,
            )
    finally:
        os.unlink(manifest_path)


def test_apply_flux2_txt2img_parameters(flux2_engine):
    resolved = flux2_engine.apply_parameters({"prompt": "a futuristic city", "use_turbo": False})

    assert resolved["prompt"]["98:6"]["inputs"]["text"] == "a futuristic city"
    assert resolved["prompt"]["98:104"]["inputs"]["value"] is False
    assert resolved["prompt"]["98:12"]["inputs"]["unet_name"] == FLUX2_UNET


def test_undeclared_param_rejected(flux2_engine):
    with pytest.raises(ValueError, match="not declared"):
        flux2_engine.apply_parameters({"checkpoint": "legacy.safetensors"})


def test_original_template_unchanged(flux2_engine):
    original_prompt = flux2_engine.template["prompt"]["98:6"]["inputs"]["text"]
    flux2_engine.apply_parameters({"prompt": "mutated"})

    assert flux2_engine.template["prompt"]["98:6"]["inputs"]["text"] == original_prompt


def test_flux2_editing_maps_base64_image():
    engine = WorkflowEngine(
        template_path="src/workflows/flux2_editing/workflow.json",
        manifest_path="src/workflows/flux2_editing/manifest.yaml",
    )

    resolved = engine.execute({"prompt": "edit this", "image_base64": "data:image/png;base64,aGVsbG8="})

    assert resolved["prompt"]["68:6"]["inputs"]["text"] == "edit this"
    assert resolved["prompt"]["46"]["class_type"] == "LoadImageFromBase64"
    assert resolved["prompt"]["46"]["inputs"]["image_url"] == "data:image/png;base64,aGVsbG8="


def test_identity_manifest_loads_with_model_defaults():
    engine = WorkflowEngine(
        template_path="src/workflows/identity/workflow.json",
        manifest_path="src/workflows/identity/manifest.yaml",
    )

    assert set(["prompt", "reference_face", "seed", "unet", "clip", "vae", "pulid", "face_detector"]).issubset(engine.manifest.inputs)
    assert engine.manifest.defaults["unet"] == FLUX2_UNET
    assert engine.template["prompt"]["6"]["class_type"] == "LoadImage"


def test_rejects_non_whitelisted_flux2_manifest_model():
    whitelist = json.dumps({"unets": [], "clip": [FLUX2_CLIP], "vae": [FLUX2_VAE], "loras": [FLUX2_TURBO_LORA]})

    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
        with pytest.raises(ValueError, match="model_not_allowed") as exc_info:
            WorkflowEngine(
                template_path="src/workflows/flux2_txt2img/workflow.json",
                manifest_path="src/workflows/flux2_txt2img/manifest.yaml",
            )

    assert FLUX2_UNET in str(exc_info.value)
