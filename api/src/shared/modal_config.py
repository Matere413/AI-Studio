import modal
import os

# Shared Modal App and Image definitions for the generation pipeline.

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

modal_app = modal.App("api-blanca-comfy")

# Pass the whitelist environment variable to the remote container
default_whitelist = '{"checkpoints": ["epicrealism_naturalSinRC1VAE.safetensors", "juggernautXL_ragnarok.safetensors", "v1-5-pruned-emaonly-fp16.safetensors", "RealVisXL_V4.0.safetensors"], "loras": ["Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"], "unets": ["qwen_image_2512_fp8_e4m3fn.safetensors"], "clip": ["qwen_2.5_vl_7b_fp8_scaled.safetensors", "t5xxl_fp8_e4m3fn.safetensors", "clip_l.safetensors"], "vae": ["qwen_image_vae.safetensors", "flux-vae-bf16.safetensors"], "ipadapter": ["ip-adapter-faceid-plusv2_sdxl.bin"], "clip_vision": ["CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"], "gguf": ["flux1-dev-q4_k_m.gguf"], "pulid": ["pulid_flux_v0.9.1.safetensors"], "face_detector": ["face_yolov8m.pt"]}'
whitelist_json = os.environ.get("ALLOWED_MODELS_JSON", default_whitelist)

comfyui_run_commands = (
    "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
    "git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git /root/ComfyUI/custom_nodes/ComfyUI_IPAdapter_plus",
    "git clone https://github.com/city96/ComfyUI-GGUF.git /root/ComfyUI/custom_nodes/ComfyUI-GGUF",
    "git clone https://github.com/balazik/ComfyUI-PuLID-Flux.git /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux",
    "python3 -c \"import os; f='/root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py'; data=open(f).read().replace('control=None,', 'control=None, **kwargs,'); open(f,'w').write(data)\"",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack",
    "git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack",
    "rm -rf /root/ComfyUI/models /root/ComfyUI/output",  # Delete so Modal can mount Volumes here
    "pip install -r /root/ComfyUI/requirements.txt",
    "pip install websocket-client fastapi[standard] requests insightface onnxruntime opencv-python-headless gguf facexlib timm diffusers accelerate huggingface_hub",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt || true",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux/requirements.txt || true",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt || true",
    "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Impact-Subpack/requirements.txt || true",
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

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "build-essential", "python3-dev", "libgl1", "libglib2.0-0")
    .run_commands(*comfyui_run_commands)
    .env({"ALLOWED_MODELS_JSON": whitelist_json})
    .add_local_dir(src_dir, remote_path="/root/src")
)

# Volume for pre-cached .safetensors checkpoints and LoRAs.
model_volume = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)

# Volume for generated images served by the FastAPI ASGI app.
image_volume = modal.Volume.from_name("comfy-output-disk", create_if_missing=True)
