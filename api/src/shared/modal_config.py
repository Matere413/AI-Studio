import modal
import os

# Shared Modal App and Image definitions for the generation pipeline.

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

modal_app = modal.App("api-blanca-comfy")

# Pass the whitelist environment variable to the remote container.
default_whitelist = '{"checkpoints": [], "loras": ["Flux_2-Turbo-LoRA_comfyui.safetensors"], "unets": ["flux2_dev_fp8mixed.safetensors"], "clip": ["mistral_3_small_flux2_bf16.safetensors", "t5xxl_fp8_e4m3fn.safetensors"], "vae": ["full_encoder_small_decoder.safetensors", "flux-vae-bf16.safetensors"], "pulid": ["pulid_flux_v0.9.1.safetensors"], "face_detector": ["face_yolov8m.pt"], "controlnets": ["flux-controlnet-depth-v1.safetensors", "flux-controlnet-canny-v1.safetensors"]}'
whitelist_json = os.environ.get("ALLOWED_MODELS_JSON", default_whitelist)

comfyui_run_commands = (
    "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
    # Pin ComfyUI core to an explicit commit for a reproducible image build.
    # An unpinned clone follows master, and recent ComfyUI master changed the
    # FLUX forward_orig signature / model dispatch path, which breaks the PuLID
    # monkeypatch at runtime ('NoneType object is not callable'). The existing
    # build-time patch (control=None, **kwargs) absorbs the new kwargs; pinning
    # the commit makes the build deterministic and stops the drift. This is only
    # one side of the compatibility contract — the custom nodes below are pinned
    # too. Update this SHA deliberately when bumping ComfyUI after validating
    # PuLID compatibility against the pinned ComfyUI-PuLID-Flux commit.
    "cd /root/ComfyUI && git checkout 7c8450ef2b720bb096f0d94ff933c62fd174cb57",
    "git clone https://github.com/balazik/ComfyUI-PuLID-Flux.git /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux",
    # Pin ComfyUI-PuLID-Flux to an explicit commit so the Modal image build is
    # deterministic. An unpinned clone follows the mutable master branch, and
    # arbitrary Python from a moving branch runs in the container with access
    # to volumes and secrets — a supply-chain risk AND a reproducibility risk.
    # The runtime compatibility issue is between ComfyUI core and this node, so
    # both sides must be pinned. Update this SHA deliberately after validating
    # compatibility with the pinned ComfyUI core commit above.
    "cd /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux && git checkout a80912fc3435c358607bf4b43a58dbcbebdb09ff",
    "python3 -c \"import os; f='/root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py'; data=open(f).read().replace('control=None,', 'control=None, **kwargs,'); open(f,'w').write(data)\"",
    "for i in 1 2 3; do git clone https://github.com/ZHO-ZHO-ZHO/ComfyUI-BRIA_AI-RMBG.git /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG && break || ([ $i -lt 3 ] && sleep 3); done",
    "test -d /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/.git || { echo 'BRIA AI RMBG git clone failed after 3 attempts' >&2; exit 1; }",
    "cd /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG && git checkout 827fcd63ff0cfa7fbc544b8d2f4c1e3f3012742d",
    "mkdir -p /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4",
    "curl -fsSL --retry 5 --retry-delay 3 --retry-connrefused --connect-timeout 15 --max-time 300 -o /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth https://huggingface.co/briaai/RMBG-1.4/resolve/2ceba5a5efaec153162aedea169f76caf9b46cf8/model.pth",
    "echo '893c16c340b1ddafc93e78457a4d94190da9b7179149f8574284c83caebf5e8c  /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth' | sha256sum -c -",
    "git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git /root/ComfyUI/custom_nodes/comfyui_controlnet_aux",
    "cd /root/ComfyUI/custom_nodes/comfyui_controlnet_aux && git checkout 12f35647f0d510e03b45a47fb420fe1245a575df",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack",
    # Pin ComfyUI-Impact-Pack to an explicit commit for a deterministic Modal
    # image build. An unpinned clone follows the mutable Main branch; arbitrary
    # Python from a moving branch runs in the container with access to volumes
    # and secrets. Update this SHA deliberately after validating compatibility
    # with the pinned ComfyUI core commit.
    "cd /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack && git checkout 429d0159ad429e64d2b3916e6e7be9c22d025c3c",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack",
    # Pin ComfyUI-Impact-Subpack to an explicit commit for a deterministic
    # Modal image build (same rationale as ComfyUI-Impact-Pack above).
    "cd /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack && git checkout 50c7b71a6a224734cc9b21963c6d1926816a97f1",
    "rm -rf /root/ComfyUI/models /root/ComfyUI/output /root/ComfyUI/input",  # Delete so Modal can mount Volumes here
    "pip install -r /root/ComfyUI/requirements.txt",
    "pip install websocket-client fastapi[standard] requests insightface onnxruntime opencv-python-headless facexlib timm diffusers accelerate huggingface_hub structlog sentry-sdk[fastapi] boto3 sqlalchemy aiosqlite",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt",
    "if [ -f /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/requirements.txt ]; then pip install -r /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/requirements.txt; fi",
    "pip install -r /root/ComfyUI/custom_nodes/comfyui_controlnet_aux/requirements.txt",
    """cat << 'EOF' > /root/ComfyUI/custom_nodes/base64_node.py
import base64
import time
import urllib.request
from io import BytesIO
import torch
import numpy as np
from PIL import Image


def _preserve_alpha(image):
    # Convert to RGBA when the source has transparency, RGB otherwise.
    if image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        return image.convert("RGBA")
    return image.convert("RGB")


class LoadImageFromBase64:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"image_url": ("STRING", {"multiline": True})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load_image"
    CATEGORY = "image"

    def load_image(self, image_url):
        if not image_url:
            return (torch.zeros((1, 64, 64, 3)),)
        if image_url.startswith("data:image/"):
            image_url = image_url.split(",")[1]
        image = Image.open(BytesIO(base64.b64decode(image_url)))
        image = _preserve_alpha(image)
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        return (image,)

class LoadImageFromUrl:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"image_url": ("STRING", {"multiline": True})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load_image"
    CATEGORY = "image"

    def load_image(self, image_url):
        if not image_url:
            return (torch.zeros((1, 64, 64, 3)),)
        if image_url.startswith("data:image/"):
            # Fallback: handle base64 inline URLs too
            image_url = image_url.split(",")[1]
            image = Image.open(BytesIO(base64.b64decode(image_url)))
        else:
            # SSRF guard: only HTTPS URLs are allowed
            if not image_url.startswith("https://"):
                raise ValueError(
                    f"SSRF_REJECTED: Only HTTPS URLs are allowed, got: {image_url[:80]}"
                )
            # Download with retry for transient network failures
            last_error = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(image_url, timeout=30) as resp:
                        image = Image.open(BytesIO(resp.read()))
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt == 2:
                        raise
                    time.sleep(1)
        image = _preserve_alpha(image)
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        return (image,)

NODE_CLASS_MAPPINGS = {
    "LoadImageFromBase64": LoadImageFromBase64,
    "LoadImageFromUrl": LoadImageFromUrl,
}
EOF""",
)

# Pass SENTRY_DSN so that _init_sentry() in modal_tasks.py can
# initialise the SDK inside Modal workers. Empty string when unset
# is safe — _init_sentry() checks if dsn is truthy.
sentry_dsn = os.environ.get("SENTRY_DSN", "")

# Modal Secret reference for R2 bucket credentials used to generate
# presigned URLs inside Modal workers.  The secret must define the
# env vars R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, and R2_BUCKET.
# Created once via: modal secret create r2-secret ...
r2_secret = modal.Secret.from_name("r2-secret")

# Optional Modal Secret for planner provider credentials.
# Created via: modal secret create planner-secret ...
# Defines: PLANNER_API_URL, PLANNER_API_KEY, PLANNER_MODEL
try:
    planner_secret = modal.Secret.from_name("planner-secret")
except modal.exception.NotFoundError:
    planner_secret = None

# Optional Modal Secret for general application configuration (DATABASE_URL,
# CORS_ORIGINS, SENTRY_DSN, etc.). Keep disabled by default so local `modal serve`
# does not require Sentry or production config credentials.
# Enable only when the secret exists via:
#   USE_APP_CONFIG_SECRET=1 modal serve api/app.py
# Created via:
#   modal secret create app-config DATABASE_URL=... CORS_ORIGINS=... SENTRY_DSN=...
app_config_secret = (
    modal.Secret.from_name("app-config")
    if os.environ.get("USE_APP_CONFIG_SECRET") == "1"
    else None
)

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "curl", "build-essential", "python3-dev", "libgl1", "libglib2.0-0")
    .run_commands(*comfyui_run_commands)
    .env({
        "ALLOWED_MODELS_JSON": whitelist_json,
        "SENTRY_DSN": sentry_dsn,
    })
    .add_local_dir(src_dir, remote_path="/root/src")
)

# Volume for pre-cached .safetensors checkpoints and LoRAs.
model_volume = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)

# Volume for generated images served by the FastAPI ASGI app.
image_volume = modal.Volume.from_name("comfy-output-disk", create_if_missing=True)

# Volume for input images used by LoadImage node during artifact chaining.
input_volume = modal.Volume.from_name("comfy-input-disk", create_if_missing=True)
