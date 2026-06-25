import json

import modal
import pytest

from app import asgi_app
from src.features.generation.modal_tasks import run_generation
from src.shared.modal_config import (
    comfy_image,
    comfyui_run_commands,
    default_whitelist,
    image_volume,
    input_volume,
    modal_app,
    model_volume,
    r2_secret,
)


def test_modal_app_defined():
    assert modal_app is not None
    assert modal_app.name == "api-blanca-comfy"


def test_comfy_image_defined():
    assert comfy_image is not None


def test_r2_secret_defined():
    """GIVEN the modal_config module
    THEN r2_secret is defined and is a modal.Secret instance.
    """
    assert isinstance(r2_secret, modal.Secret)


def test_model_volume_defined():
    assert model_volume is not None


def test_image_volume_defined():
    assert image_volume is not None


def test_image_volume_named():
    assert image_volume.name == "comfy-output-disk"


def test_input_volume_defined():
    assert input_volume is not None


def test_input_volume_named():
    assert input_volume.name == "comfy-input-disk"


def test_run_generation_mounts_image_volume():
    assert "/root/ComfyUI/output" in run_generation.spec.volumes
    assert run_generation.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_asgi_app_mounts_image_volume():
    assert "/root/ComfyUI/output" in asgi_app.spec.volumes
    assert asgi_app.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_default_whitelist_accepts_flux2_and_identity_models():
    whitelist = json.loads(default_whitelist)

    assert whitelist["unets"] == ["flux2_dev_fp8mixed.safetensors"]
    assert "mistral_3_small_flux2_bf16.safetensors" in whitelist["clip"]
    assert "full_encoder_small_decoder.safetensors" in whitelist["vae"]
    assert "flux-vae-bf16.safetensors" in whitelist["vae"]
    assert whitelist["loras"] == ["Flux_2-Turbo-LoRA_comfyui.safetensors"]
    assert "pulid_flux_v0.9.1.safetensors" in whitelist["pulid"]
    assert "face_yolov8m.pt" in whitelist["face_detector"]


def test_default_whitelist_has_controlnet_models():
    """GIVEN the default whitelist
    THEN it includes FLUX ControlNet model filenames for depth and canny.
    """
    whitelist = json.loads(default_whitelist)

    assert "controlnets" in whitelist, (
        "Whitelist must have a 'controlnets' key for FLUX ControlNet models"
    )
    assert any("depth" in m for m in whitelist["controlnets"]), (
        "Whitelist must include a FLUX depth ControlNet model"
    )
    assert any("canny" in m for m in whitelist["controlnets"]), (
        "Whitelist must include a FLUX canny ControlNet model"
    )


def test_default_whitelist_rejects_retired_legacy_models():
    whitelist = json.loads(default_whitelist)
    encoded = json.dumps(whitelist)

    assert "qwen_image_2512_fp8_e4m3fn.safetensors" not in encoded
    assert "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" not in encoded
    assert "RealVisXL_V4.0.safetensors" not in encoded
    assert "juggernautXL_ragnarok.safetensors" not in encoded
    assert "ip-adapter-faceid-plusv2_sdxl.bin" not in encoded


def test_bria_install_must_not_use_or_true():
    """GIVEN the BRIA AI RMBG install command
    THEN it must NOT use '|| true' so failures crash the build.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "BRIA_AI-RMBG/requirements.txt || true" not in joined_commands, (
        "BRIA requirements install must not have '|| true' — failures must crash the build"
    )
    assert "BRIA_AI-RMBG/requirements.txt" in joined_commands


def test_comfy_image_installs_required_flux2_identity_extraction_nodes():
    joined_commands = "\n".join(comfyui_run_commands)

    assert "ComfyUI-GGUF" not in joined_commands, (
        "ComfyUI-GGUF must be fully removed in Phase 3"
    )
    assert "ComfyUI-PuLID-Flux" in joined_commands
    assert "ComfyUI-Impact-Pack" in joined_commands
    assert "ComfyUI-BRIA_AI-RMBG" in joined_commands
    assert "comfyui_controlnet_aux" in joined_commands
    assert "LoadImageFromBase64" in joined_commands
    assert "ComfyUI_IPAdapter_plus" not in joined_commands

def test_load_image_from_url_node_is_defined():
    """GIVEN the ComfyUI custom node config
    THEN LoadImageFromUrl is present alongside LoadImageFromBase64.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "LoadImageFromUrl" in joined_commands
    assert "LoadImageFromBase64" in joined_commands
    assert "urllib.request.urlopen" in joined_commands


def test_controlnet_aux_install_has_no_or_true():
    """GIVEN the ControlNet aux install command
    THEN it must NOT use '|| true' so failures crash the build.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "controlnet_aux/requirements.txt || true" not in joined_commands, (
        "ControlNet aux requirements install must not have '|| true'"
    )
    assert "comfyui_controlnet_aux" in joined_commands


def test_controlnet_aux_git_clone_is_pinned_to_stable_commit():
    """GIVEN the ControlNet aux git clone command
    THEN it includes a git checkout to a specific stable commit hash
    to make the Modal image build deterministic.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "git checkout" in joined_commands, (
        "ControlNet aux must have a pinned commit via git checkout"
    )
    for line in comfyui_run_commands:
        if "comfyui_controlnet_aux" in line and "checkout" in line:
            assert len(line.split()[-1]) >= 40, (
                "Checkout hash must be a full SHA"
            )
            break
    else:
        pytest.fail("No git checkout for comfyui_controlnet_aux found")
