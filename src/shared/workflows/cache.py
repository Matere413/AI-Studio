"""Modal model caching service for downloading .safetensors weights."""

import os
from typing import Optional

import httpx
import modal

from src.shared.modal_config import modal_app, model_volume


# Lightweight image for model downloads (no ComfyUI needed)
_download_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install("httpx")
)


def _resolve_model(
    url: str,
    filename: str,
    dest_dir: str,
    client: Optional[httpx.Client] = None,
) -> str:
    """Resolve the local path for a model, downloading if necessary.

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
