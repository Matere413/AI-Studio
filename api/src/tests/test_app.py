import json
import os
import pytest
from fastapi import FastAPI
from unittest.mock import patch
from src.tests.client_helpers import LazyTestClient


FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
FLUX2_CLIP = "mistral_3_small_flux2_bf16.safetensors"
FLUX2_VAE = "full_encoder_small_decoder.safetensors"
FLUX2_TURBO_LORA = "Flux_2-Turbo-LoRA_comfyui.safetensors"

WHITELIST_JSON = json.dumps({
    "checkpoints": [],
    "loras": [FLUX2_TURBO_LORA],
    "unets": [FLUX2_UNET],
    "clip": [FLUX2_CLIP],
    "vae": [FLUX2_VAE],
})


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


@pytest.fixture(autouse=True)
def default_cached_model():
    def _resolve(filename, model_type, models_dir="/root/ComfyUI/models"):
        return f"{models_dir}/{model_type}/{filename}"

    with patch("src.features.generation.service.resolve_cached_model", side_effect=_resolve) as mock:
        yield mock


def test_app_is_fastapi_instance():
    """GIVEN app.py is imported
    THEN fastapi_app is a FastAPI instance.
    """
    from app import fastapi_app
    assert isinstance(fastapi_app, FastAPI)


def test_app_includes_generation_router():
    """GIVEN the mounted FastAPI app
    WHEN POST /generate is called
    THEN it returns 202 Accepted with a job_id.
    """
    from app import fastapi_app
    client = LazyTestClient(fastapi_app)
    response = client.post(
        "/generate",
        json={"prompt": "test app"},
        headers={"X-Session-ID": "test-session"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"


def test_resolve_asset_url_maps_all_service_errors_to_value_error():
    """GIVEN a wired AssetsService with mocked error responses
    WHEN the resolve_asset_url callback encounters AssetNotFoundError,
    ProjectOwnershipError, or AssetNotReadyError
    THEN all are mapped to ValueError("invalid_artifact: ...").
    """
    from unittest.mock import AsyncMock

    import src.features.generation.router as gen_router

    from src.features.assets.exceptions import (
        AssetNotFoundError,
        AssetNotReadyError,
        ProjectOwnershipError,
    )
    from src.features.assets.router import init_assets

    # Create a mock service that behaves like the real one
    svc = AsyncMock()
    svc._storage = AsyncMock()
    svc._storage.presigned_get.return_value = "https://r2.example.com/any"

    # Register with the router module, then wire the resolver
    init_assets(svc)
    from app import _wire_asset_resolver

    _wire_asset_resolver()

    try:
        # Access the callback through the module to get the updated value
        cb = gen_router._resolve_asset_url_cb
        assert cb is not None, "resolver should be wired"

        # AssetNotFoundError → ValueError
        svc.get_active_asset.side_effect = AssetNotFoundError("asset not found")
        with pytest.raises(ValueError, match=r"invalid_artifact"):
            cb("missing-id", "session-abc")

        # ProjectOwnershipError → ValueError
        svc.get_active_asset.side_effect = ProjectOwnershipError("not your asset")
        with pytest.raises(ValueError, match=r"invalid_artifact"):
            cb("wrong-owner-id", "session-abc")

        # AssetNotReadyError → ValueError (existing behavior preserved)
        svc.get_active_asset.side_effect = AssetNotReadyError("not finalized yet")
        with pytest.raises(ValueError, match=r"invalid_artifact"):
            cb("not-ready-id", "session-abc")

        # Happy path: successful resolution returns the presigned URL
        svc.get_active_asset.side_effect = None
        svc.get_active_asset.return_value = {
            "id": "asset-123",
            "r2_key": "projects/abc/def",
            "upload_status": "finalized",
        }
        result = cb("asset-123", "session-abc")
        assert result == "https://r2.example.com/any"
        svc._storage.presigned_get.assert_awaited_once_with("projects/abc/def")
    finally:
        # Clean up module-level state to avoid test leakage
        gen_router.set_resolve_asset_url(None)
        from src.features.assets.router import init_assets as _reset

        _reset(None)  # type: ignore[arg-type]


def test_storage_error_from_presigned_get_propagates_as_storage_error():
    """GIVEN a wired AssetsService with a storage presigned_get that raises StorageError
    WHEN the resolve_asset_url callback is called
    THEN StorageError propagates as-is (not converted to ValueError) so the
    orchestrator can distinguish infrastructure failures from user-correctable
    asset failures.
    """
    from unittest.mock import AsyncMock

    import src.features.generation.router as gen_router

    from src.features.assets.router import init_assets
    from src.shared.storage import StorageError

    # Create a mock service — get_active_asset works, but presigned_get fails
    svc = AsyncMock()
    svc._storage = AsyncMock()
    svc.get_active_asset.return_value = {
        "id": "asset-123",
        "r2_key": "projects/abc/def",
        "upload_status": "finalized",
    }
    svc._storage.presigned_get.side_effect = StorageError("R2 storage infrastructure unavailable")

    init_assets(svc)
    from app import _wire_asset_resolver

    _wire_asset_resolver()

    try:
        cb = gen_router._resolve_asset_url_cb
        assert cb is not None, "resolver should be wired"

        # StorageError must propagate — NOT be converted to ValueError
        with pytest.raises(StorageError, match="R2 storage infrastructure unavailable"):
            cb("asset-123", "session-abc")
    finally:
        gen_router.set_resolve_asset_url(None)
        from src.features.assets.router import init_assets as _reset

        _reset(None)


def test_app_websocket_unknown_job():
    """GIVEN the mounted FastAPI app
    WHEN WS /ws/generate/{unknown_job_id} is called
    THEN it returns an error event.
    """
    from app import fastapi_app
    client = LazyTestClient(fastapi_app)
    with client.websocket_connect("/ws/generate/unknown-job") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "error"
        assert data["error"]["code"] == "job_not_found"
