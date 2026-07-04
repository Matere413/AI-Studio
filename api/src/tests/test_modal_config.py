import json
import importlib

import modal
import pytest

from app import asgi_app
from src.features.generation.modal_tasks import run_generation
from src.shared.modal_config import (
    comfy_image,
    comfyui_run_commands,
    default_whitelist,
    image_volume,
    input_volume,
    modal_app,
    model_volume,
    r2_secret,
)


def test_modal_app_defined():
    assert modal_app is not None
    assert modal_app.name == "api-blanca-comfy"


def test_comfy_image_defined():
    assert comfy_image is not None


def test_r2_secret_defined():
    """GIVEN the modal_config module
    THEN r2_secret is defined and is a modal.Secret instance.
    """
    assert isinstance(r2_secret, modal.Secret)


def test_model_volume_defined():
    assert model_volume is not None


def test_image_volume_defined():
    assert image_volume is not None


def test_image_volume_named():
    assert image_volume.name == "comfy-output-disk"


def test_input_volume_defined():
    assert input_volume is not None


def test_input_volume_named():
    assert input_volume.name == "comfy-input-disk"


def test_run_generation_mounts_image_volume():
    assert "/root/ComfyUI/output" in run_generation.spec.volumes
    assert run_generation.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_asgi_app_mounts_image_volume():
    assert "/root/ComfyUI/output" in asgi_app.spec.volumes
    assert asgi_app.spec.volumes["/root/ComfyUI/output"].name == image_volume.name


def test_asgi_app_includes_r2_secret():
    """GIVEN the ASGI Modal function
    THEN it mounts the r2-secret so the FastAPI app can resolve
    asset_id → presigned GET URLs and the R2 env vars are present
    inside the container.

    Without this secret, ``_resolve_async`` in app.py raises because
    R2_ENDPOINT/R2_ACCESS_KEY/R2_SECRET_KEY/R2_BUCKET are unset, and
    every editing/extraction/composition request that references an
    uploaded asset fails with asset_resolution_unavailable.
    """
    secret_names = {s.name for s in asgi_app.spec.secrets}
    assert "r2-secret" in secret_names, (
        f"asgi_app must include the 'r2-secret' Modal Secret; got: {secret_names}"
    )


def test_planner_secret_is_optional():
    """GIVEN the modal_config module
    THEN planner_secret may be None (when the Modal secret hasn't been
    created yet) or a modal.Secret instance when configured.

    The secret is created once via: modal secret create planner-secret ...
    """
    from src.shared.modal_config import planner_secret

    assert planner_secret is None or isinstance(planner_secret, modal.Secret), (
        "planner_secret must be None or a modal.Secret instance"
    )


def test_app_config_secret_is_optional():
    """GIVEN the modal_config module
    THEN app_config_secret may be None (when the Modal secret hasn't been
    created yet) or a modal.Secret instance when configured.

    The secret is created once via: modal secret create app-config ...
    """
    from src.shared.modal_config import app_config_secret

    assert app_config_secret is None or isinstance(app_config_secret, modal.Secret), (
        "app_config_secret must be None or a modal.Secret instance"
    )


def test_app_config_secret_is_disabled_by_default(monkeypatch):
    """GIVEN no explicit app-config opt-in
    THEN modal_config must not request the app-config Modal Secret.

    This keeps local `modal serve api/app.py` from requiring Sentry or
    production configuration credentials before they are available.
    """
    import src.shared.modal_config as modal_config

    calls: list[str] = []
    original_from_name = modal.Secret.from_name

    def spy_from_name(name: str, *args, **kwargs):
        calls.append(name)
        return original_from_name(name, *args, **kwargs)

    monkeypatch.delenv("USE_APP_CONFIG_SECRET", raising=False)
    monkeypatch.setattr(modal.Secret, "from_name", spy_from_name)

    reloaded = importlib.reload(modal_config)

    assert reloaded.app_config_secret is None
    assert "app-config" not in calls


def test_app_config_secret_requires_explicit_opt_in(monkeypatch):
    """GIVEN USE_APP_CONFIG_SECRET=1
    THEN modal_config may request the app-config Modal Secret.
    """
    import src.shared.modal_config as modal_config

    calls: list[str] = []
    original_from_name = modal.Secret.from_name

    def spy_from_name(name: str, *args, **kwargs):
        calls.append(name)
        return original_from_name(name, *args, **kwargs)

    monkeypatch.setenv("USE_APP_CONFIG_SECRET", "1")
    monkeypatch.setattr(modal.Secret, "from_name", spy_from_name)

    importlib.reload(modal_config)

    assert "app-config" in calls

    monkeypatch.delenv("USE_APP_CONFIG_SECRET", raising=False)
    importlib.reload(modal_config)


def test_asgi_app_secret_list_handles_optional_secrets():
    """GIVEN the ASGI Modal function in app.py
    THEN the secrets list always includes r2-secret, and conditionally
    includes planner-secret and app-config when those secrets exist.
    """
    from src.shared.modal_config import planner_secret, app_config_secret

    secret_names = {s.name for s in asgi_app.spec.secrets}

    assert "r2-secret" in secret_names
    if planner_secret is not None:
        assert "planner-secret" in secret_names
    if app_config_secret is not None:
        assert "app-config" in secret_names
    else:
        assert "app-config" not in secret_names


def test_default_whitelist_accepts_flux2_and_identity_models():
    whitelist = json.loads(default_whitelist)

    assert whitelist["unets"] == ["flux2_dev_fp8mixed.safetensors"]
    assert "mistral_3_small_flux2_bf16.safetensors" in whitelist["clip"]
    assert "full_encoder_small_decoder.safetensors" in whitelist["vae"]
    assert "flux-vae-bf16.safetensors" in whitelist["vae"]
    assert whitelist["loras"] == ["Flux_2-Turbo-LoRA_comfyui.safetensors"]
    assert "pulid_flux_v0.9.1.safetensors" in whitelist["pulid"]
    assert "face_yolov8m.pt" in whitelist["face_detector"]


def test_default_whitelist_has_controlnet_models():
    """GIVEN the default whitelist
    THEN it includes FLUX ControlNet model filenames for depth and canny.
    """
    whitelist = json.loads(default_whitelist)

    assert "controlnets" in whitelist, (
        "Whitelist must have a 'controlnets' key for FLUX ControlNet models"
    )
    assert any("depth" in m for m in whitelist["controlnets"]), (
        "Whitelist must include a FLUX depth ControlNet model"
    )
    assert any("canny" in m for m in whitelist["controlnets"]), (
        "Whitelist must include a FLUX canny ControlNet model"
    )


def test_default_whitelist_rejects_retired_legacy_models():
    whitelist = json.loads(default_whitelist)
    encoded = json.dumps(whitelist)

    assert "qwen_image_2512_fp8_e4m3fn.safetensors" not in encoded
    assert "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" not in encoded
    assert "RealVisXL_V4.0.safetensors" not in encoded
    assert "juggernautXL_ragnarok.safetensors" not in encoded
    assert "ip-adapter-faceid-plusv2_sdxl.bin" not in encoded


def test_bria_install_must_not_use_or_true():
    """GIVEN the BRIA AI RMBG install command
    THEN it must NOT use '|| true' so failures crash the build.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "BRIA_AI-RMBG/requirements.txt || true" not in joined_commands, (
        "BRIA requirements install must not have '|| true' — failures must crash the build"
    )
    assert "BRIA_AI-RMBG/requirements.txt" in joined_commands


def test_bria_custom_node_repo_is_pinned_to_commit():
    """GIVEN the BRIA AI RMBG custom node install commands
    THEN the repo is cloned and immediately checked out to a pinned commit
    SHA (not left on the mutable default branch) so the Modal image build is
    deterministic and the BRIA_RMBG_ModelLoader_Zho / BRIA_RMBG_Zho nodes
    come from a known-good snapshot.
    """
    pinned_sha = "827fcd63ff0cfa7fbc544b8d2f4c1e3f3012742d"
    bria_repo_path = "/root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG"

    clone_line = next(
        (
            line for line in comfyui_run_commands
            if "ComfyUI-BRIA_AI-RMBG.git" in line and "git clone" in line
        ),
        None,
    )
    assert clone_line is not None, "BRIA AI RMBG repo must be git cloned"
    assert bria_repo_path in clone_line, (
        "BRIA repo must be cloned into the custom_nodes directory"
    )

    checkout_line = next(
        (
            line for line in comfyui_run_commands
            if "ComfyUI-BRIA_AI-RMBG" in line and "git checkout" in line
        ),
        None,
    )
    assert checkout_line is not None, (
        "BRIA repo must be pinned via a 'git checkout <sha>' command after clone"
    )
    assert pinned_sha in checkout_line, (
        f"BRIA repo must be pinned to commit {pinned_sha}, got: {checkout_line}"
    )
    assert "|| true" not in checkout_line, (
        "BRIA repo checkout must not mask failures with '|| true'"
    )

    # Order: clone must come before checkout.
    clone_idx = comfyui_run_commands.index(clone_line)
    checkout_idx = comfyui_run_commands.index(checkout_line)
    assert clone_idx < checkout_idx, (
        "BRIA repo git clone must precede the git checkout pin"
    )


def test_bria_custom_node_clone_retries_transient_failures():
    """GIVEN the BRIA AI RMBG custom node git clone command
    THEN it retries transient GitHub/network failures (up to 3 attempts with
    a sleep between attempts) and fails loudly on final failure. It must NOT
    use '|| true' to mask failures. The pinned checkout command must still be
    present after the clone.
    """
    bria_clone_lines = [
        line for line in comfyui_run_commands
        if "ComfyUI-BRIA_AI-RMBG.git" in line and "git clone" in line
    ]
    assert bria_clone_lines, "BRIA AI RMBG repo must be git cloned"
    clone_line = bria_clone_lines[0]

    # Retry loop must be present (up to 3 attempts).
    assert "for i in 1 2 3" in clone_line or "for i in 1 2 3;" in clone_line, (
        "BRIA git clone must retry up to 3 times on transient failures"
    )
    # Sleep between attempts.
    assert "sleep" in clone_line, (
        "BRIA git clone retry must sleep between attempts"
    )
    # Must NOT mask failures with '|| true'.
    assert "|| true" not in clone_line, (
        "BRIA git clone must not mask failures with '|| true'"
    )

    # A fail-loud guard must follow the clone so a final failure crashes the build.
    joined_commands = "\n".join(comfyui_run_commands)
    assert "BRIA AI RMBG git clone failed" in joined_commands, (
        "BRIA git clone must fail loudly with a descriptive error after exhausting retries"
    )
    fail_guard_line = next(
        (
            line for line in comfyui_run_commands
            if "BRIA AI RMBG git clone failed" in line
        ),
        None,
    )
    assert fail_guard_line is not None, (
        "BRIA git clone must have a fail-loud guard after the retry loop"
    )
    assert "exit 1" in fail_guard_line, (
        "BRIA git clone fail-loud guard must exit non-zero"
    )
    assert "|| true" not in fail_guard_line, (
        "BRIA git clone fail-loud guard must not mask failures with '|| true'"
    )

    # The pinned checkout command must still be present after the clone.
    pinned_sha = "827fcd63ff0cfa7fbc544b8d2f4c1e3f3012742d"
    assert pinned_sha in joined_commands, (
        "BRIA repo pinned checkout must still be present"
    )


def test_bria_model_weights_provisioned_from_pinned_revision():
    """GIVEN the Modal run commands
    THEN the BRIA RMBG-1.4 model.pth is downloaded into the custom node
    directory via a curl command pinned to a specific HuggingFace revision
    (not the mutable 'resolve/main' branch). The SHA256 checksum verification
    is asserted separately in test_bria_model_checksum_verified_after_download.
    """
    joined_commands = "\n".join(comfyui_run_commands)

    # The model must be placed where BRIA_RMBG_ModelLoader_Zho looks for it:
    # /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth
    target_path = "/root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth"
    assert target_path in joined_commands, (
        "BRIA RMBG-1.4/model.pth must be provisioned at the path expected by the loader node"
    )

    # Download must use the pinned revision SHA, not the mutable 'resolve/main'.
    bria_lines = [
        line for line in comfyui_run_commands
        if "BRIA_AI-RMBG/RMBG-1.4/model.pth" in line and "curl" in line
    ]
    assert bria_lines, "No curl download command for BRIA RMBG-1.4/model.pth found"
    download_line = bria_lines[0]
    assert "resolve/main/model.pth" not in download_line, (
        "BRIA model download must not use mutable 'resolve/main' — pin to a revision SHA"
    )
    pinned_revision = "2ceba5a5efaec153162aedea169f76caf9b46cf8"
    assert pinned_revision in download_line, (
        "BRIA model download must be pinned to revision SHA "
        "2ceba5a5efaec153162aedea169f76caf9b46cf8"
    )
    assert (
        f"https://huggingface.co/briaai/RMBG-1.4/resolve/{pinned_revision}/model.pth"
        in download_line
    ), "BRIA model download URL must use the pinned revision path"


def test_bria_model_download_uses_resilient_curl_flags():
    """GIVEN the BRIA model download curl command
    THEN it uses resilient flags: -fsSL, --retry, --retry-delay,
    --retry-connrefused, --connect-timeout, --max-time.
    """
    download_line = next(
        (
            line for line in comfyui_run_commands
            if "BRIA_AI-RMBG/RMBG-1.4/model.pth" in line and line.lstrip().startswith("curl")
        ),
        None,
    )
    assert download_line is not None, (
        "BRIA model provisioning must use a curl download command"
    )
    assert "-fsSL" in download_line, (
        "curl must use -fsSL to fail on HTTP errors and follow redirects silently"
    )
    assert "--retry" in download_line, "curl must use --retry for transient failures"
    assert "--retry-delay" in download_line, "curl must use --retry-delay between retries"
    assert "--retry-connrefused" in download_line, (
        "curl must use --retry-connrefused to retry on connection refused"
    )
    assert "--connect-timeout" in download_line, (
        "curl must use --connect-timeout to bound connection establishment"
    )
    assert "--max-time" in download_line, (
        "curl must use --max-time to bound total download time"
    )
    assert "|| true" not in download_line, (
        "BRIA model download must not mask failures with '|| true'"
    )


def test_bria_model_checksum_verified_after_download():
    """GIVEN the Modal run commands
    THEN a sha256sum verification step follows the BRIA model download and
    fails loudly (no '|| true') when the checksum does not match the pinned
    LFS SHA256 for model.pth. The verification must run AFTER the curl
    download (not before) so the file actually exists to verify.
    """
    expected_sha = "893c16c340b1ddafc93e78457a4d94190da9b7179149f8574284c83caebf5e8c"
    target_path = "/root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth"

    # Find the checksum line (must come after the download line).
    checksum_lines = [
        line for line in comfyui_run_commands
        if "sha256sum" in line and target_path in line
    ]
    assert checksum_lines, (
        "BRIA model download must be followed by a sha256sum verification step"
    )
    checksum_line = checksum_lines[0]
    assert expected_sha in checksum_line, (
        f"sha256sum verification must check against the pinned LFS SHA256 {expected_sha}"
    )
    assert "-c" in checksum_line, "sha256sum must use -c to check against the expected hash"
    assert "|| true" not in checksum_line, (
        "checksum verification must not mask failures with '|| true'"
    )

    # Order: the curl download must run before the checksum verification.
    download_line = next(
        (
            line for line in comfyui_run_commands
            if target_path in line and line.lstrip().startswith("curl")
        ),
        None,
    )
    assert download_line is not None, "BRIA model curl download command not found"
    download_idx = comfyui_run_commands.index(download_line)
    checksum_idx = comfyui_run_commands.index(checksum_line)
    assert download_idx < checksum_idx, (
        "BRIA model curl download must run before the sha256sum verification"
    )


def test_bria_model_target_directory_created():
    """GIVEN the Modal run commands
    THEN the RMBG-1.4 directory is created before the download runs.
    The mkdir must run BEFORE the curl download so the target path exists.
    """
    joined = "\n".join(comfyui_run_commands)
    assert "mkdir -p /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4" in joined, (
        "RMBG-1.4 directory must be created before downloading model.pth"
    )

    # Order: mkdir must precede the curl download.
    mkdir_line = next(
        (
            line for line in comfyui_run_commands
            if line.startswith("mkdir -p /root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4")
        ),
        None,
    )
    target_path = "/root/ComfyUI/custom_nodes/ComfyUI-BRIA_AI-RMBG/RMBG-1.4/model.pth"
    download_line = next(
        (
            line for line in comfyui_run_commands
            if target_path in line and line.lstrip().startswith("curl")
        ),
        None,
    )
    assert mkdir_line is not None, "mkdir -p for RMBG-1.4 directory not found"
    assert download_line is not None, "BRIA model curl download command not found"
    mkdir_idx = comfyui_run_commands.index(mkdir_line)
    download_idx = comfyui_run_commands.index(download_line)
    assert mkdir_idx < download_idx, (
        "mkdir -p for RMBG-1.4 must run before the curl download of model.pth"
    )


def test_comfy_image_installs_required_flux2_identity_extraction_nodes():
    joined_commands = "\n".join(comfyui_run_commands)

    assert "ComfyUI-GGUF" not in joined_commands, (
        "ComfyUI-GGUF must be fully removed in Phase 3"
    )
    assert "ComfyUI-PuLID-Flux" in joined_commands
    assert "ComfyUI-Impact-Pack" in joined_commands
    assert "ComfyUI-BRIA_AI-RMBG" in joined_commands
    assert "comfyui_controlnet_aux" in joined_commands
    assert "LoadImageFromBase64" in joined_commands
    assert "ComfyUI_IPAdapter_plus" not in joined_commands

def test_load_image_from_url_node_is_defined():
    """GIVEN the ComfyUI custom node config
    THEN LoadImageFromUrl is present alongside LoadImageFromBase64.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "LoadImageFromUrl" in joined_commands
    assert "LoadImageFromBase64" in joined_commands
    assert "urllib.request.urlopen" in joined_commands


def test_controlnet_aux_install_has_no_or_true():
    """GIVEN the ControlNet aux install command
    THEN it must NOT use '|| true' so failures crash the build.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "controlnet_aux/requirements.txt || true" not in joined_commands, (
        "ControlNet aux requirements install must not have '|| true'"
    )
    assert "comfyui_controlnet_aux" in joined_commands


# ─── Helpers for extracting LoadImageFromUrl class ──────────────────────────


def _extract_python_code() -> str:
    """Extract the full Python source from the base64_node.py heredoc."""
    joined = "\n".join(comfyui_run_commands)
    # Find the heredoc: cat << 'EOF' > /root/.../base64_node.py
    start_marker = "cat << 'EOF' > /root/ComfyUI/custom_nodes/base64_node.py\n"
    start = joined.find(start_marker)
    if start == -1:
        raise ValueError("Could not find base64_node.py heredoc start")
    start += len(start_marker)
    # Find the closing EOF (on its own line)
    end = joined.find("\nEOF", start)
    if end == -1:
        raise ValueError("Could not find EOF closing marker")
    return joined[start:end]


def _extract_load_image_class():
    """Extract and return the LoadImageFromUrl class (with exec)."""
    py_src = _extract_python_code()
    ns: dict = {}
    exec(py_src, ns)
    return ns["LoadImageFromUrl"]


class TestAlphaPreservation:
    """LoadImageFromUrl must preserve the alpha channel, not strip it."""

    def test_alpha_preserved_for_rgba_source(self):
        """GIVEN an RGBA PNG image
        WHEN LoadImageFromUrl.load_image processes it
        THEN the output tensor has 4 channels (RGBA).
        """
        import io
        import base64
        from PIL import Image

        cls = _extract_load_image_class()
        instance = cls()

        # Create an RGBA test image
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_data = base64.b64encode(buf.getvalue()).decode()
        data_url = f"data:image/png;base64,{b64_data}"

        result = instance.load_image(data_url)
        tensor = result[0]
        # ComfyUI shape: (1, H, W, C) — we expect C=4 for RGBA
        assert tensor.shape[-1] == 4, f"Expected 4 channels (RGBA), got {tensor.shape[-1]}"

    def test_rgb_source_unchanged(self):
        """GIVEN an RGB JPEG image (no alpha)
        WHEN LoadImageFromUrl.load_image processes it
        THEN the output tensor still has 3 channels (RGB).
        """
        import io
        import base64
        from PIL import Image

        cls = _extract_load_image_class()
        instance = cls()

        # Create an RGB test image
        img = Image.new("RGB", (16, 16), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64_data = base64.b64encode(buf.getvalue()).decode()
        data_url = f"data:image/png;base64,{b64_data}"

        result = instance.load_image(data_url)
        tensor = result[0]
        assert tensor.shape[-1] == 3, f"Expected 3 channels (RGB), got {tensor.shape[-1]}"


class TestSSRFProtection:
    """LoadImageFromUrl must reject non-HTTPS URLs to prevent SSRF."""

    def test_rejects_http_url(self):
        """GIVEN an http:// URL (not https)
        WHEN LoadImageFromUrl.load_image is called
        THEN ValueError is raised with SSRF_REJECTED.
        """
        cls = _extract_load_image_class()
        instance = cls()

        with pytest.raises(ValueError) as excinfo:
            instance.load_image("http://internal.service/secrets")
        assert "SSRF_REJECTED" in str(excinfo.value)

    def test_rejects_file_url(self):
        """GIVEN a file:// URL
        WHEN LoadImageFromUrl.load_image is called
        THEN ValueError is raised with SSRF_REJECTED.
        """
        cls = _extract_load_image_class()
        instance = cls()

        with pytest.raises(ValueError) as excinfo:
            instance.load_image("file:///etc/passwd")
        assert "SSRF_REJECTED" in str(excinfo.value)

    def test_rejects_ftp_url(self):
        """GIVEN an ftp:// URL
        WHEN LoadImageFromUrl.load_image is called
        THEN ValueError is raised with SSRF_REJECTED.
        """
        cls = _extract_load_image_class()
        instance = cls()

        with pytest.raises(ValueError) as excinfo:
            instance.load_image("ftp://files.example.com/image.png")
        assert "SSRF_REJECTED" in str(excinfo.value)

    def test_https_url_accepted(self):
        """GIVEN an https:// URL
        WHEN LoadImageFromUrl.load_image is called
        THEN it attempts to download (no SSRF rejection).
        """
        import urllib.request
        cls = _extract_load_image_class()
        instance = cls()

        # We just need to verify it doesn't raise SSRF_REJECTED
        # The download will fail with URLError (no network), which is fine
        with pytest.raises(Exception) as excinfo:
            instance.load_image("https://valid.example.com/image.png")
        assert "SSRF_REJECTED" not in str(excinfo.value)


class TestNetworkRetry:
    """LoadImageFromUrl must retry transient network failures."""

    def test_retry_on_transient_failure(self):
        """GIVEN urllib.request.urlopen fails twice then succeeds
        WHEN LoadImageFromUrl.load_image is called
        THEN it retries and eventually succeeds (3 attempts).
        """
        import io
        import time
        import urllib.request
        from unittest.mock import patch, MagicMock
        from PIL import Image

        cls = _extract_load_image_class()
        instance = cls()

        # Create a small valid PNG for the successful response
        img = Image.new("RGB", (8, 8), (0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        call_count = [0]

        def mock_urlopen(url, timeout=30):
            call_count[0] += 1
            if call_count[0] < 3:
                raise OSError(f"Transient error {call_count[0]}")
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value.read.return_value = png_data
            return mock_resp

        original_urlopen = urllib.request.urlopen

        try:
            urllib.request.urlopen = mock_urlopen
            start = time.monotonic()
            result = instance.load_image("https://retry-test.example.com/img.png")
            elapsed = time.monotonic() - start
            # Verify it succeeded after retries
            assert result[0] is not None
            assert call_count[0] == 3, f"Expected 3 calls, got {call_count[0]}"
            # Verify there was a sleep (elapsed > 2s for 2 sleeps at 1s each)
            assert elapsed >= 1.5, f"Expected at least 1.5s for retry backoff, got {elapsed:.2f}s"
        finally:
            urllib.request.urlopen = original_urlopen

    def test_exhaust_retries_raises(self):
        """GIVEN urllib.request.urlopen always fails
        WHEN LoadImageFromUrl.load_image is called
        THEN it raises after exhausting 3 retries.
        """
        import urllib.request
        from unittest.mock import patch

        cls = _extract_load_image_class()
        instance = cls()

        call_count = [0]

        def mock_urlopen(url, timeout=30):
            call_count[0] += 1
            raise OSError(f"Persistent error {call_count[0]}")

        original_urlopen = urllib.request.urlopen

        try:
            urllib.request.urlopen = mock_urlopen
            with pytest.raises(OSError):
                instance.load_image("https://fails-always.example.com/img.png")
            assert call_count[0] == 3, f"Expected 3 retries, got {call_count[0]}"
        finally:
            urllib.request.urlopen = original_urlopen


class TestCodePatterns:
    """String-level checks that the heredoc contains required patterns."""

    def test_no_unconditional_rgb_convert(self):
        """GIVEN the LoadImageFromUrl implementation
        THEN the class methods must NOT call .convert("RGB") directly.
        """
        py_src = _extract_python_code()
        # Class methods must use _preserve_alpha() helper, not direct convert.
        # Find lines in class methods (indented by 4 spaces) that call convert
        for line in py_src.split("\n"):
            stripped = line.strip()
            if 'convert("RGB")' in stripped and 'convert("RGBA")' not in stripped:
                # Convert calls in class methods start with at least 8 spaces
                # (one for class, one for def)
                if line.startswith(" " * 8):
                    pytest.fail(
                        f"Class method calls .convert('RGB') directly: {stripped}"
                    )

    def test_retry_import_present(self):
        """GIVEN the base64_node.py Python module
        THEN it must import 'time' for retry backoff.
        """
        py_src = _extract_python_code()
        assert "import time" in py_src

    def test_retry_loop_present(self):
        """GIVEN the LoadImageFromUrl implementation
        THEN it must have a retry loop around urllib.request.urlopen.
        """
        py_src = _extract_python_code()
        assert "for attempt in range" in py_src or "for _ in range" in py_src

    def test_ssrf_guard_present(self):
        """GIVEN the LoadImageFromUrl implementation
        THEN it must check for https:// before calling urlopen.
        """
        py_src = _extract_python_code()
        assert ".startswith(\"https://\")" in py_src or ".startswith('https://')" in py_src


def test_controlnet_aux_git_clone_is_pinned_to_stable_commit():
    """GIVEN the ControlNet aux git clone command
    THEN it includes a git checkout to a specific stable commit hash
    to make the Modal image build deterministic.
    """
    joined_commands = "\n".join(comfyui_run_commands)
    assert "git checkout" in joined_commands, (
        "ControlNet aux must have a pinned commit via git checkout"
    )
    for line in comfyui_run_commands:
        if "comfyui_controlnet_aux" in line and "checkout" in line:
            assert len(line.split()[-1]) >= 40, (
                "Checkout hash must be a full SHA"
            )
            break
    else:
        pytest.fail("No git checkout for comfyui_controlnet_aux found")
