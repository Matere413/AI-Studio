import modal
from fastapi import FastAPI
from src.features.generation.router import router as generation_router
from src.shared.modal_config import modal_app, comfy_image, model_volume

# FastAPI ASGI application
fastapi_app = FastAPI()
fastapi_app.include_router(generation_router)

# Modal ASGI endpoint to serve the FastAPI application
app = modal_app  # Expose the app instance for 'modal serve' command

@app.function(image=comfy_image, volumes={"/root/ComfyUI/models": model_volume}, gpu="T4")
@modal.asgi_app()
def asgi_app():
    """Serve the FastAPI application via Modal's ASGI app wrapper."""
    return fastapi_app
