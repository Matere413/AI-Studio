import json
import os
from typing import Dict, Any

# Import shared Modal configuration
from src.shared.modal_config import modal_app, comfy_image, model_volume


def mutate_comfy_payload(prompt: str) -> Dict[str, Any]:
    """Load the base ComfyUI payload and mutate the prompt text.

    Returns the modified payload dict.
    """
    payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "payload.json")
    with open(payload_path, "r") as f:
        payload = json.load(f)

    # Mutate the positive prompt (node 6 in the payload)
    if "6" in payload["prompt"] and "inputs" in payload["prompt"]["6"]:
        payload["prompt"]["6"]["inputs"]["text"] = prompt

    return payload


@modal_app.function(image=comfy_image, volumes={"/root/ComfyUI/models": model_volume}, gpu="T4")
def run_generation(job_id: str, prompt: str) -> str:
    """Modal background function to execute the ComfyUI GPU workflow.

    Mutates the payload with the provided prompt and executes the workflow.
    Returns the image path or raises on failure.
    """
    # Load and mutate the payload
    payload = mutate_comfy_payload(prompt)

    # TODO: In production, this will connect to ComfyUI via WebSocket and execute the workflow
    # For the MVP stub, we simulate a successful execution
    image_path = f"/tmp/comfyui/output/{job_id}.png"
    return image_path
