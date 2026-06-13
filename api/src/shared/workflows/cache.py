"""Modal model caching service for pre-cached .safetensors weights.

V1 constraint: no runtime downloads. All models must be pre-cached in the
Modal Volume. Cache miss returns ModelNotCachedError.
"""

import json
import os
from typing import Dict, List, Optional

import httpx
import modal

from src.shared.modal_config import modal_app, model_volume


class ModelNotCachedError(Exception):
    """Raised when a whitelisted model is not found in the pre-cached Volume.

    V1 boundary: no runtime downloads are performed.
    """

    def __init__(self, filename: str, model_type: str, models_dir: str):
        self.filename = filename
        self.model_type = model_type
        self.models_dir = models_dir
        self.code = "model_not_cached"
        super().__init__(
            f"Model '{filename}' ({model_type}) is not cached in {models_dir}. "
            f"V1 requires all models to be pre-cached. Code: model_not_cached"
        )


# Lightweight image for model downloads (no ComfyUI needed)
_download_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install("httpx")
)


def load_whitelist() -> Dict[str, List[str]]:
    """Load the allowed models whitelist from the ALLOWED_MODELS_JSON env var.

    Returns:
        Dict with 'checkpoints' and 'loras' lists of allowed model filenames.

    Raises:
        ValueError: If ALLOWED_MODELS_JSON contains invalid JSON.
    """
    raw = os.environ.get("ALLOWED_MODELS_JSON", "")
    if not raw:
        return {"checkpoints": [], "loras": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"ALLOWED_MODELS_JSON contains invalid JSON: {exc}"
        ) from exc
    return {
        "checkpoints": data.get("checkpoints", []),
        "loras": data.get("loras", []),
    }


def resolve_cached_model(
    filename: str,
    model_type: str,
    models_dir: str = "/root/ComfyUI/models",
) -> str:
    """Resolve a pre-cached model from the Volume without downloading.

    V1 boundary: no runtime downloads. If the model is not in the Volume,
    raises ModelNotCachedError instead of attempting a download.

    Args:
        filename: The model filename (e.g. "sdxl.safetensors").
        model_type: The model subdirectory ("checkpoints" or "loras").
        models_dir: Root directory for model storage. Defaults to
            /root/ComfyUI/models (Modal Volume mount point).

    Returns:
        Absolute path to the cached model file.

    Raises:
        ModelNotCachedError: If the model file is not found in the Volume.
    """
    subdir = os.path.join(models_dir, model_type)
    dest_path = os.path.join(subdir, filename)

    if os.path.exists(dest_path):
        return dest_path

    raise ModelNotCachedError(filename, model_type, models_dir)


def _resolve_model(
    url: str,
    filename: str,
    dest_dir: str,
    client: Optional[httpx.Client] = None,
) -> str:
    """Resolve the local path for a model, downloading if necessary.

    NOTE: This function performs runtime downloads and should NOT be used
    in V1. Use resolve_cached_model() instead, which enforces the
    pre-cached-only boundary.

    Args:
        url: The remote URL of the .safetensors file.
        filename: The local filename to save as.
        dest_dir: The directory path where models are cached.
        client: Optional httpx client for dependency injection (testing).

    Returns:
        Absolute path to the cached model file.

    Raises:
        httpx.HTTPError: If the download fails.
    """
    dest_path = os.path.join(dest_dir, filename)

    # Cache hit: skip download
    if os.path.exists(dest_path):
        return dest_path

    # Cache miss: stream download
    os.makedirs(dest_dir, exist_ok=True)

    _client = client or httpx.Client()
    try:
        with _client.stream("GET", url, timeout=300, follow_redirects=True) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
    finally:
        if client is None:
            _client.close()

    return dest_path


@modal_app.function(
    image=_download_image,
    volumes={"/root/ComfyUI/models": model_volume},
    timeout=600,
)
def download_model(url: str, filename: str) -> str:
    """Download a .safetensors model into the Modal volume if not cached.

    Streams the file from URL to /root/ComfyUI/models/filename.
    Returns the absolute path on the volume.
    Raises on network or validation errors.
    """
    return _resolve_model(url, filename, "/root/ComfyUI/models")
