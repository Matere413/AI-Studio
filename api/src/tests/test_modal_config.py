import json

from src.shared.modal_config import (
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

    assert "juggernautXL_ragnarok.safetensors" in whitelist["checkpoints"]


def test_default_whitelist_excludes_moody_checkpoint():
    """GIVEN the default Modal model whitelist
    WHEN decoding the checkpoint allow-list
    THEN the moody checkpoint is not approved by default.
    """
    whitelist = json.loads(default_whitelist)

    assert "moodyRealMix_zitV7.safetensors" not in whitelist["checkpoints"]
