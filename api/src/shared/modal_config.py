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
    "git clone https://github.com/balazik/ComfyUI-PuLID-Flux.git /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux",
    "python3 -c \"import os; f='/root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py'; data=open(f).read().replace('control=None,', 'control=None, **kwargs,'); open(f,'w').write(data)\"",
    "git clone https://github.com/ZHO-ZHO-ZHO/ComfyUI-BRIA_AI-RMBG.git /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG",
    "git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git /root/ComfyUI/custom_nodes/comfyui_controlnet_aux",
    "cd /root/ComfyUI/custom_nodes/comfyui_controlnet_aux && git checkout 12f35647f0d510e03b45a47fb420fe1245a575df",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack",
    "rm -rf /root/ComfyUI/models /root/ComfyUI/output",  # Delete so Modal can mount Volumes here
    "pip install -r /root/ComfyUI/requirements.txt",
    "pip install websocket-client fastapi[standard] requests insightface onnxruntime opencv-python-headless facexlib timm diffusers accelerate huggingface_hub structlog sentry-sdk[fastapi] boto3",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/requirements.txt",
    "pip install -r /root/ComfyUI/custom_nodes/comfyui_controlnet_aux/requirements.txt",
    """cat << 'EOF' > /root/ComfyUI/custom_nodes/base64_node.py
import base64
from PIL import Image
from io import BytesIO
import torch
import numpy as np

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
        image = image.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        return (image,)

NODE_CLASS_MAPPINGS = {"LoadImageFromBase64": LoadImageFromBase64}
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

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "build-essential", "python3-dev", "libgl1", "libglib2.0-0")
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
