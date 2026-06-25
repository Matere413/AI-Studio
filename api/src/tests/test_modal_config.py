import json

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
