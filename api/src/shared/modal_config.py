import modal
import os

# Shared Modal App and Image definitions for the generation pipeline.

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

modal_app = modal.App("api-blanca-comfy")

# Pass the whitelist environment variable to the remote container
default_whitelist = '{"checkpoints": ["epicrealism_naturalSinRC1VAE.safetensors", "juggernautXL_ragnarok.safetensors", "v1-5-pruned-emaonly-fp16.safetensors"], "loras": []}'
whitelist_json = os.environ.get("ALLOWED_MODELS_JSON", default_whitelist)

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .run_commands(
        "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
        "rm -rf /root/ComfyUI/models /root/ComfyUI/output",  # Delete so Modal can mount Volumes here
        "pip install -r /root/ComfyUI/requirements.txt",
        "pip install websocket-client fastapi[standard] requests",
    )
    .env({"ALLOWED_MODELS_JSON": whitelist_json})
    .add_local_dir(src_dir, remote_path="/root/src")
)

# Volume for pre-cached .safetensors checkpoints and LoRAs.
model_volume = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)

# Volume for generated images served by the FastAPI ASGI app.
image_volume = modal.Volume.from_name("comfy-output-disk", create_if_missing=True)
