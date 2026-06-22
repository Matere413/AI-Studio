"""Tests for output sanitization: `_sanitize_error_detail` and event cleanup."""

import pytest

from src.shared.errors import _sanitize_error_detail


class TestSanitizeErrorDetail:
    """Unit tests for `_sanitize_error_detail` sanitization.

    The function must strip:
    - Absolute paths starting with /root/ComfyUI/
    - Predictable absolute path patterns
    - node {N} references exposing internal ComfyUI topology
    """

    # ── Path sanitization ──────────────────────────────────────────

    def test_strips_root_comfyui_paths(self):
        """GIVEN an error detail containing /root/ComfyUI/...
        WHEN _sanitize_error_detail processes it
        THEN the absolute path is replaced with a placeholder.
        """
        detail = "Model not found in /root/ComfyUI/models/unet/model.safetensors"
        result = _sanitize_error_detail(detail)
        assert "/root/ComfyUI/" not in result
        assert "models/unet/model.safetensors" not in result or "[redacted]" in result

    def test_strips_node_id_references(self):
        """GIVEN an error detail containing node {N} and node_type
        WHEN _sanitize_error_detail processes it
        THEN both the node reference and node type are removed.
        """
        detail = "RuntimeError: tensor mismatch (node 19, KSamplerAdvanced)"
        result = _sanitize_error_detail(detail)
        assert "node 19" not in result
        assert "KSamplerAdvanced" not in result

    def test_strips_multiple_node_ids(self):
        """GIVEN an error detail with multiple node references
        WHEN _sanitize_error_detail processes it
        THEN all node {N} are removed.
        """
        detail = "Error in node 3 and node 42 connected to node 7"
        result = _sanitize_error_detail(detail)
        assert "node 3" not in result
        assert "node 42" not in result
        assert "node 7" not in result

    def test_preserves_normal_error_message(self):
        """GIVEN a detail with no internal paths or node IDs
        WHEN _sanitize_error_detail processes it
        THEN the original message is unchanged.
        """
        detail = "CUDA out of memory. Tried to allocate 4.00 GiB"
        result = _sanitize_error_detail(detail)
        assert result == detail

    def test_strips_other_absolute_paths(self):
        """GIVEN an error detail with a generic absolute path
        WHEN _sanitize_error_detail processes it
        THEN the absolute path is sanitized.
        """
        detail = "File not found at /var/log/system.log"
        result = _sanitize_error_detail(detail)
        assert "/var/log/system.log" not in result

    def test_strips_node_id_at_start(self):
        """GIVEN an error detail starting with node X
        WHEN _sanitize_error_detail processes it
        THEN the node reference is removed.
        """
        detail = "node 5 crashed with TypeError"
        result = _sanitize_error_detail(detail)
        assert "node 5" not in result

    def test_empty_string_returns_empty(self):
        """GIVEN an empty string
        WHEN _sanitize_error_detail processes it
        THEN empty string is returned.
        """
        assert _sanitize_error_detail("") == ""


class TestBuildEventSanitization:
    """Tests for `_build_event` sanitization integration."""

    def test_completed_event_no_image_path(self):
        """GIVEN a completed job
        WHEN _build_event constructs the event
        THEN the result does NOT contain image_path.
        """
        from src.features.generation.service import GenerationService
        from src.shared.job_store import JobStore

        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("test")
        store.update_job(job_id, status="completed", image_path="/root/ComfyUI/output/img.png")

        event = list(service.get_job_events(job_id))[0]
        assert event["event"] == "completed"
        assert "result" in event
        assert "image_path" not in event["result"], (
            "completed event must not expose result.image_path"
        )

    def test_error_event_detail_sanitized(self):
        """GIVEN a job that failed with raw node_id and node_type in detail
        WHEN _build_event constructs the error event
        THEN error.detail has both node_id and node_type stripped.
        """
        from src.features.generation.service import GenerationService
        from src.shared.job_store import JobStore

        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = store.create_job("test")
        store.update_job(
            job_id,
            status="error",
            error_code="comfyui_execution_failed",
            error_detail="RuntimeError: tensor mismatch (node 19, KSamplerAdvanced)",
        )

        event = list(service.get_job_events(job_id))[0]
        assert event["event"] == "error"
        assert "node 19" not in event["error"]["detail"], (
            "error detail must not contain node IDs"
        )
        assert "KSamplerAdvanced" not in event["error"]["detail"], (
            "error detail must not contain node types"
        )
