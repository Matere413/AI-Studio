import json
import os
from typing import Dict, Any

# Import shared Modal configuration
from src.shared.modal_config import modal_app, comfy_image, model_volume


def _load_graph_from_dict(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return the resolved ComfyUI workflow graph.

    The graph is already resolved by the WorkflowEngine before being passed here.
    """
    if not graph or "prompt" not in graph:
        raise ValueError("Invalid workflow graph: missing 'prompt' key")
    return graph


@modal_app.function(image=comfy_image, volumes={"/root/ComfyUI/models": model_volume}, gpu="T4")
def run_generation(job_id: str, graph: Dict[str, Any]) -> str:
    """Modal background function to execute the ComfyUI GPU workflow.

    Accepts a pre-resolved workflow graph (from WorkflowEngine) and executes it.
    Returns the image path or raises on failure.
    """
    import time
    from src.shared.job_store import JobStore

    store = JobStore()

    # 1. Update status to running
    store.update_job(job_id, status="running")

    # Validate the resolved graph
    payload = _load_graph_from_dict(graph)

    # TODO: In production, this will connect to ComfyUI via WebSocket and execute the workflow
    # For the MVP stub, we simulate a successful execution with a delay
    time.sleep(3)

    image_path = f"/tmp/comfyui/output/{job_id}.png"

    # 2. Update status to completed
    store.update_job(job_id, status="completed", image_path=image_path)

    return image_path
