"""Tests for the Modal model cache service."""

import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.shared.workflows.cache import _resolve_model


class TestDownloadModel:
    """Unit tests for the Modal function definition."""

    def test_download_model_is_defined(self):
        """GIVEN the cache module
        WHEN importing download_model
        THEN it is defined and is a Modal Function.
        """
        from src.shared.workflows.cache import download_model
        import modal

        assert download_model is not None
        assert isinstance(download_model, modal.Function)

    def test_download_model_mounts_volume(self):
        """GIVEN the download_model Modal function
        WHEN inspecting its volume mounts
        THEN it mounts the model volume at /root/ComfyUI/models.
        """
        from src.shared.workflows.cache import download_model

        spec = download_model.spec
        assert "/root/ComfyUI/models" in spec.volumes

    def test_download_image_is_defined(self):
        """GIVEN the download image
        WHEN importing it
        THEN it is a valid Modal Image.
        """
        from src.shared.workflows.cache import _download_image

        assert _download_image is not None


class TestResolveModel:
    """Unit tests for the core model resolution logic."""

    def test_cache_hit_returns_existing_path(self, tmp_path: Path):
        """GIVEN a model already exists locally
        WHEN resolving the model
        THEN the existing path is returned without downloading.
        """
        dest_dir = tmp_path / "models"
        dest_dir.mkdir()
        existing_file = dest_dir / "model.safetensors"
        existing_file.write_text("cached")

        result = _resolve_model(
            url="https://example.com/model.safetensors",
            filename="model.safetensors",
            dest_dir=str(dest_dir),
        )

        assert result == str(existing_file)
        assert existing_file.read_text() == "cached"

    def test_cache_miss_downloads_model(self, tmp_path: Path):
        """GIVEN a model is absent locally
        WHEN resolving the model
        THEN the file is downloaded and the path is returned.
        """
        dest_dir = tmp_path / "models"
        
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = [b"data chunk 1", b"data chunk 2"]
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
        
        result = _resolve_model(
            url="https://example.com/model.safetensors",
            filename="model.safetensors",
            dest_dir=str(dest_dir),
            client=mock_client,
        )

        dest_path = dest_dir / "model.safetensors"
        assert result == str(dest_path)
        assert dest_path.exists()
        assert dest_path.read_bytes() == b"data chunk 1data chunk 2"

    def test_download_failure_raises(self, tmp_path: Path):
        """GIVEN a model URL is unreachable
        WHEN resolving the model
        THEN an HTTPError is raised.
        """
        dest_dir = tmp_path / "models"
        
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPError("Network error")
        
        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
        
        with pytest.raises(httpx.HTTPError):
            _resolve_model(
                url="https://example.com/model.safetensors",
                filename="model.safetensors",
                dest_dir=str(dest_dir),
                client=mock_client,
            )

    def test_download_failure_does_not_leave_file(self, tmp_path: Path):
        """GIVEN a download fails
        WHEN resolving the model
        THEN no partial file is left on disk.
        """
        dest_dir = tmp_path / "models"
        
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPError("Network error")
        
        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
        
        try:
            _resolve_model(
                url="https://example.com/model.safetensors",
                filename="model.safetensors",
                dest_dir=str(dest_dir),
                client=mock_client,
            )
        except httpx.HTTPError:
            pass
        
        dest_path = dest_dir / "model.safetensors"
        assert not dest_path.exists()

    def test_nested_directories_created(self, tmp_path: Path):
        """GIVEN the destination directory does not exist
        WHEN resolving the model
        THEN nested directories are created.
        """
        dest_dir = tmp_path / "models" / "checkpoints" / "v1"
        
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
        
        result = _resolve_model(
            url="https://example.com/model.safetensors",
            filename="model.safetensors",
            dest_dir=str(dest_dir),
            client=mock_client,
        )

        assert Path(result).parent.exists()
        assert Path(result).parent == dest_dir

    def test_empty_chunks_create_file(self, tmp_path: Path):
        """GIVEN a download produces empty chunks
        WHEN resolving the model
        THEN an empty file is still created.
        """
        dest_dir = tmp_path / "models"
        
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = []
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
        
        result = _resolve_model(
            url="https://example.com/model.safetensors",
            filename="model.safetensors",
            dest_dir=str(dest_dir),
            client=mock_client,
        )

        dest_path = dest_dir / "model.safetensors"
        assert dest_path.exists()
        assert dest_path.read_bytes() == b""


class TestWhitelistLoading:
    """Unit tests for loading the model whitelist from config.

    Spec: model-weight-caching/spec.md — Requirement: Enforce Model Whitelist
    """

    def test_load_whitelist_from_env_json(self):
        """GIVEN ALLOWED_MODELS_JSON is set
        WHEN load_whitelist is called
        THEN it returns checkpoint and lora lists parsed from JSON.
        """
        from src.shared.workflows.cache import load_whitelist
        whitelist_json = json.dumps({
            "checkpoints": ["sdxl.safetensors", "sd15.safetensors"],
            "loras": ["detail_enhancer.safetensors"],
            "controlnets": ["flux-controlnet-depth-v1.safetensors"],
        })
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist_json}):
            result = load_whitelist()
        assert result["checkpoints"] == ["sdxl.safetensors", "sd15.safetensors"]
        assert result["loras"] == ["detail_enhancer.safetensors"]
        assert result["controlnets"] == ["flux-controlnet-depth-v1.safetensors"]

    def test_load_whitelist_default_when_env_missing(self):
        """GIVEN ALLOWED_MODELS_JSON is not set
        WHEN load_whitelist is called
        THEN it returns empty lists (no models allowed by default).
        """
        from src.shared.workflows.cache import load_whitelist
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("ALLOWED_MODELS_JSON", None)
            result = load_whitelist()
        assert result["checkpoints"] == []
        assert result["loras"] == []
        assert result["controlnets"] == []

    def test_load_whitelist_invalid_json_raises(self):
        """GIVEN ALLOWED_MODELS_JSON contains invalid JSON
        WHEN load_whitelist is called
        THEN it raises ValueError.
        """
        from src.shared.workflows.cache import load_whitelist
        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": "not-json"}):
            with pytest.raises(ValueError, match="ALLOWED_MODELS_JSON"):
                load_whitelist()


class TestV1CacheBoundary:
    """Unit tests for V1 cache hit/miss without runtime downloads.

    Spec: model-weight-caching/spec.md — Requirement: Pre-Cached Models Only (V1 Boundary)
    V1 constraint: no runtime downloads. Cache miss returns model_not_cached error.
    """

    def test_cache_hit_returns_existing_path_v1(self, tmp_path: Path):
        """GIVEN a requested model already exists in the Modal Volume
        WHEN the cache service resolves the model
        THEN the existing file path is returned without downloading.
        """
        from src.shared.workflows.cache import resolve_cached_model
        models_dir = tmp_path / "models"
        checkpoints_dir = models_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True)
        existing_file = checkpoints_dir / "sdxl.safetensors"
        existing_file.write_bytes(b"cached-weights")

        result = resolve_cached_model("sdxl.safetensors", "checkpoints", models_dir=str(models_dir))
        assert result == str(existing_file)
        # File content unchanged — no download happened
        assert existing_file.read_bytes() == b"cached-weights"

    def test_cache_miss_returns_model_not_cached(self, tmp_path: Path):
        """GIVEN a requested model is absent from the Modal Volume
        WHEN the cache service attempts to resolve the model
        THEN the request fails with model_not_cached error (no download attempted).
        """
        from src.shared.workflows.cache import resolve_cached_model, ModelNotCachedError
        models_dir = tmp_path / "models"
        checkpoints_dir = models_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True)

        with pytest.raises(ModelNotCachedError) as exc_info:
            resolve_cached_model("missing_model.safetensors", "checkpoints", models_dir=str(models_dir))
        assert exc_info.value.code == "model_not_cached"
        assert "missing_model.safetensors" in str(exc_info.value)

    def test_v1_no_runtime_download_attempted(self, tmp_path: Path):
        """GIVEN a model is absent from the Modal Volume
        WHEN the cache service resolves the model
        THEN no HTTP request is made (V1 boundary: no runtime downloads).
        """
        from src.shared.workflows.cache import resolve_cached_model, ModelNotCachedError
        models_dir = tmp_path / "models"
        checkpoints_dir = models_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True)

        with patch("src.shared.workflows.cache.httpx.Client") as mock_client_class:
            with pytest.raises(ModelNotCachedError):
                resolve_cached_model("missing.safetensors", "checkpoints", models_dir=str(models_dir))
            # Verify no HTTP client was even created
            mock_client_class.assert_not_called()

    def test_lora_cache_hit_returns_path(self, tmp_path: Path):
        """GIVEN a lora model exists in the Modal Volume
        WHEN resolve_cached_model is called for the lora
        THEN the existing file path is returned.
        """
        from src.shared.workflows.cache import resolve_cached_model
        models_dir = tmp_path / "models"
        lora_dir = models_dir / "loras"
        lora_dir.mkdir(parents=True)
        existing_file = lora_dir / "detail_enhancer.safetensors"
        existing_file.write_bytes(b"lora-weights")

        result = resolve_cached_model("detail_enhancer.safetensors", "loras", models_dir=str(models_dir))
        assert result == str(existing_file)

    def test_lora_cache_miss_returns_model_not_cached(self, tmp_path: Path):
        """GIVEN a lora model is absent from the Modal Volume
        WHEN resolve_cached_model is called for the lora
        THEN model_not_cached error is raised (no download attempted).
        """
        from src.shared.workflows.cache import resolve_cached_model, ModelNotCachedError
        models_dir = tmp_path / "models"
        lora_dir = models_dir / "loras"
        lora_dir.mkdir(parents=True)

        with pytest.raises(ModelNotCachedError) as exc_info:
            resolve_cached_model("bogus_lora.safetensors", "loras", models_dir=str(models_dir))
        assert exc_info.value.code == "model_not_cached"

    @pytest.mark.parametrize(
        ("model_type", "filename"),
        [
            ("gguf", "flux1-dev-q4_k_m.gguf"),
            ("pulid", "pulid_flux_v0.9.1.safetensors"),
            ("face_detector", "face_yolov8m.pt"),
        ],
    )
    def test_identity_gguf_cache_types_resolve_to_dedicated_subdirs(self, tmp_path: Path, model_type, filename):
        """GIVEN an identidad_gguf model exists in its semantic cache directory
        WHEN resolve_cached_model is called with that model type
        THEN the existing path is returned from the dedicated subdirectory.
        """
        from src.shared.workflows.cache import resolve_cached_model

        models_dir = tmp_path / "models"
        model_dir = models_dir / model_type
        model_dir.mkdir(parents=True)
        existing_file = model_dir / filename
        existing_file.write_bytes(b"cached-model")

        result = resolve_cached_model(filename, model_type, models_dir=str(models_dir))

        assert result == str(existing_file)

    def test_controlnet_cache_resolves_to_controlnet_subdir(self, tmp_path: Path):
        """GIVEN a ControlNet model exists in the controlnet subdirectory
        WHEN resolve_cached_model is called with type "controlnets"
        THEN the existing path is returned from the controlnet subdirectory.
        """
        from src.shared.workflows.cache import resolve_cached_model

        models_dir = tmp_path / "models"
        model_dir = models_dir / "controlnet"
        model_dir.mkdir(parents=True)
        existing_file = model_dir / "flux-controlnet-depth-v1.safetensors"
        existing_file.write_bytes(b"controlnet-weights")

        result = resolve_cached_model(
            "flux-controlnet-depth-v1.safetensors",
            "controlnets",
            models_dir=str(models_dir),
        )

        assert result == str(existing_file)
