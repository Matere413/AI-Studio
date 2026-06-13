import modal
import os

# Shared Modal App and Image definitions for the generation pipeline.

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

modal_app = modal.App("api-blanca-comfy")

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .run_commands(
        "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
        "rm -rf /root/ComfyUI/models",  # Delete so Modal can mount the Volume here
        "pip install -r /root/ComfyUI/requirements.txt",
        "pip install websocket-client fastapi[standard]",
    )
    .add_local_dir(src_dir, remote_path="/root/src")
)

model_volume = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)
