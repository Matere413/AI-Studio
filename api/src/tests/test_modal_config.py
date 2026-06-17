import json

from src.shared.modal_config import (
    comfyui_run_commands,
    default_whitelist,
    modal_app,
    comfy_image,
    model_volume,
    image_volume,
)
from src.features.generation.modal_tasks import run_generation
from app import asgi_app


def test_modal_app_defined():
    """GIVEN the modal_config module
    WHEN importing modal_app
    THEN it is a valid modal App instance.
    """
    assert modal_app is not None
    assert modal_app.name == "api-blanca-comfy"


def test_comfy_image_defined():
    """GIVEN the modal_config module
    WHEN importing comfy_image
    THEN it is a valid modal Image instance.
    """
    assert comfy_image is not None


def test_model_volume_defined():
    """GIVEN the modal_config module
    WHEN importing model_volume
    THEN it is a valid modal Volume instance.
    """
    assert model_volume is not None


def test_image_volume_defined():
    """GIVEN the modal_config module
    WHEN importing image_volume
    THEN it is a valid modal Volume instance.
    """
    assert image_volume is not None


def test_image_volume_named():
    """GIVEN the image volume
    THEN it has the expected name for persisted ComfyUI outputs.
    """
    assert image_volume.name == "comfy-output-disk"


def test_run_generation_mounts_image_volume():
    """GIVEN the run_generation Modal function
    WHEN inspecting its volume mounts
    THEN it mounts the image volume at /root/ComfyUI/output.
    """
    assert "/root/ComfyUI/output" in run_generation.spec.volumes
    assert run_generation.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_asgi_app_mounts_image_volume():
    """GIVEN the asgi_app Modal function
    WHEN inspecting its volume mounts
    THEN it mounts the image volume at /root/ComfyUI/output.
    """
    assert "/root/ComfyUI/output" in asgi_app.spec.volumes
    assert asgi_app.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_default_whitelist_includes_realistic_persona_checkpoint():
    """GIVEN the default Modal model whitelist
    WHEN decoding the checkpoint allow-list
    THEN the realistic_persona checkpoint is approved by default.
    """
    whitelist = json.loads(default_whitelist)

    assert "RealVisXL_V4.0.safetensors" in whitelist["checkpoints"]


def test_default_whitelist_includes_identity_preservation_models():
    """GIVEN the default Modal model whitelist
    WHEN decoding the model allow-list
    THEN the FaceID adapter and CLIP Vision model are approved by default.
    """
    whitelist = json.loads(default_whitelist)

    assert "ip-adapter-faceid-plusv2_sdxl.bin" in whitelist["ipadapter"]
    assert "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" in whitelist["clip_vision"]


def test_default_whitelist_includes_identity_gguf_models():
    """GIVEN the default Modal model whitelist
    WHEN decoding the model allow-list
    THEN all identidad_gguf model assets are approved by default.
    """
    whitelist = json.loads(default_whitelist)

    assert "flux1-dev-q4_k_m.gguf" in whitelist["gguf"]
    assert "pulid_flux_v0.9.1.safetensors" in whitelist["pulid"]
    assert "face_yolov8m.onnx" in whitelist["face_detector"]
    assert "t5xxl_fp8_e4m3fn.safetensors" in whitelist["clip"]


def test_comfy_image_installs_identity_gguf_custom_nodes():
    """GIVEN the ComfyUI image run commands
    WHEN checking installed custom nodes
    THEN GGUF, PuLID Flux, and Impact Pack nodes are cloned before runtime.
    """
    joined_commands = "\n".join(comfyui_run_commands)

    assert "ComfyUI-GGUF" in joined_commands
    assert "PuLID_ComfyUI" in joined_commands
    assert "ComfyUI-Impact-Pack" in joined_commands


def test_comfy_image_installs_ip_adapter_plus_custom_node():
    """GIVEN the ComfyUI image run commands
    WHEN checking installed custom nodes
    THEN ComfyUI_IPAdapter_plus is cloned before runtime.
    """
    assert any(
        "ComfyUI_IPAdapter_plus" in command
        for command in comfyui_run_commands
    )


def test_default_whitelist_excludes_moody_checkpoint():
    """GIVEN the default Modal model whitelist
    WHEN decoding the checkpoint allow-list
    THEN the moody checkpoint is not approved by default.
    """
    whitelist = json.loads(default_whitelist)

    assert "moodyRealMix_zitV7.safetensors" not in whitelist["checkpoints"]
