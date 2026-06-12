"""Tests for the Modal model cache service."""

import os
from pathlib import Path
from unittest.mock import MagicMock

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
