import modal

# Shared Modal App and Image definitions for the generation pipeline.

modal_app = modal.App("api-blanca-comfy")

comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .run_commands(
        "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
        "pip install -r /root/ComfyUI/requirements.txt",
        "pip install websocket-client fastapi[standard]",
    )
)

model_volume = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)
