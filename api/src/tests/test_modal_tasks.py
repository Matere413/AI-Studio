import json
import os
import signal
import subprocess
import time
import pytest
from unittest.mock import MagicMock, patch
from src.features.generation.modal_tasks import (
    _boot_comfyui,
    _execute_generation,
    _load_graph_from_dict,
    _shutdown_process_group,
    run_generation,
)


class TestLoadGraphFromDict:
    """Unit tests for graph validation helper."""

    def test_valid_graph_passes(self):
        """GIVEN a valid resolved graph dict
        WHEN validating it
        THEN it is returned unchanged.
        """
        graph = {"prompt": {"6": {"inputs": {"text": "test"}}}}
        result = _load_graph_from_dict(graph)
        assert result == graph

    def test_empty_graph_raises(self):
        """GIVEN an empty graph
        WHEN validating it
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError):
            _load_graph_from_dict({})

    def test_missing_prompt_key_raises(self):
        """GIVEN a graph without 'prompt' key
        WHEN validating it
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError):
            _load_graph_from_dict({"other": "data"})


class TestRunGeneration:
    """Unit tests for run_generation Modal function signature."""

    def test_run_generation_is_modal_function(self):
        """GIVEN the module is loaded
        THEN run_generation is a Modal function object.
        """
        import modal
        assert isinstance(run_generation, modal.Function)

    def test_run_generation_accepts_graph_param(self):
        """GIVEN the run_generation signature
        THEN it accepts job_id and graph parameters.
        """
        # Verify the function has the expected parameters by checking its local signature
        import inspect
        # Note: Modal wraps the function, so we inspect the underlying function
        sig = inspect.signature(run_generation.info.raw_f)
        params = list(sig.parameters.keys())
        assert "job_id" in params
        assert "graph" in params


class _FakeStore:
    """In-memory stand-in for JobStore used by modal_tasks tests."""

    def __init__(self):
        self.jobs = {}
        self.updates = []

    def create_job(self, prompt: str) -> str:
        job_id = f"job-{len(self.jobs)}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "pending",
            "image_path": None,
            "error_code": None,
            "error_detail": None,
            "progress": 0,
            "message": "",
        }
        return job_id

    def update_job(self, job_id, status, **kwargs):
        self.jobs[job_id]["status"] = status
        for key, value in kwargs.items():
            self.jobs[job_id][key] = value
        self.updates.append({"status": status, **kwargs})


class _FakeClient:
    """In-memory stand-in for ComfyUIClient used by modal_tasks tests."""

    def __init__(self, events=None, output_path="/root/ComfyUI/output/img.png", raise_on=None):
        self.events = events or []
        self.output_path = output_path
        self.raise_on = raise_on or {}
        self.calls = []
        self.connected = False
        self.closed = False

    def connect(self, timeout_s: float | None = None) -> None:
        self.calls.append(("connect", timeout_s))
        self.connected = True
        if "connect" in self.raise_on:
            raise self.raise_on["connect"]

    def close(self) -> None:
        self.calls.append(("close",))
        self.closed = True

    def wait_ready(self, timeout_s: float):
        self.calls.append(("wait_ready", timeout_s))
        if "wait_ready" in self.raise_on:
            raise self.raise_on["wait_ready"]

    def queue_prompt(self, payload: dict, timeout_s: float = 60.0) -> str:
        self.calls.append(("queue_prompt", payload, timeout_s))
        if "queue_prompt" in self.raise_on:
            raise self.raise_on["queue_prompt"]
        return "prompt-1"

    def stream_progress(self, prompt_id: str, deadline: float):
        self.calls.append(("stream_progress", prompt_id, deadline))
        if "stream_progress" in self.raise_on:
            raise self.raise_on["stream_progress"]
        for event in self.events:
            yield event

    def resolve_output_path(self, prompt_id: str, output_dir: str, timeout_s: float = 60.0) -> str:
        self.calls.append(("resolve_output_path", prompt_id, output_dir, timeout_s))
        return self.output_path


class TestBootComfyUI:
    """Unit tests for ComfyUI subprocess boot helper."""

    def test_boot_comfyui_spawns_process_group(self):
        """GIVEN a ComfyUI installation directory
        WHEN _boot_comfyui is called
        THEN it spawns ComfyUI in its own process group.
        """
        with patch("src.features.generation.modal_tasks.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            _boot_comfyui(port=8188, comfyui_dir="/root/ComfyUI")
            mock_popen.assert_called_once()
            _, kwargs = mock_popen.call_args
            assert kwargs["cwd"] == "/root/ComfyUI"
            assert kwargs["preexec_fn"] == os.setsid
            args = mock_popen.call_args[0][0]
            assert "main.py" in args
            assert "--listen" in args
            assert "--port" in args


class TestShutdownProcessGroup:
    """Unit tests for SIGTERM/SIGKILL cleanup helper."""

    def test_shutdown_sends_sigterm_then_sigkill(self):
        """GIVEN a running process
        WHEN _shutdown_process_group is called and the process survives SIGTERM
        THEN it sends SIGKILL after the grace period.
        """
        process = MagicMock()
        process.pid = 1234
        process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 10), None]

        with patch("os.getpgid", return_value=1234) as mock_getpgid:
            with patch("os.killpg") as mock_killpg:
                _shutdown_process_group(process, term_wait_s=0.5)

        mock_getpgid.assert_called_once_with(1234)
        assert mock_killpg.call_args_list[0][0] == (1234, signal.SIGTERM)
        assert mock_killpg.call_args_list[1][0] == (1234, signal.SIGKILL)

    def test_shutdown_skips_kill_if_process_already_gone(self):
        """GIVEN a process that no longer exists
        WHEN _shutdown_process_group is called
        THEN it exits without raising.
        """
        process = MagicMock()
        process.pid = 1234

        with patch("os.getpgid", side_effect=ProcessLookupError(1234)):
            _shutdown_process_group(process, term_wait_s=0.5)

        process.wait.assert_not_called()


class TestExecuteGeneration:
    """Unit tests for the real ComfyUI execution pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_stores_completed_image(self):
        """GIVEN a valid graph and a responsive ComfyUI
        WHEN _execute_generation runs
        THEN the job transitions through boot/generate/completed.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        events = [
            {"event": "progress", "progress": 25, "message": "step 1"},
            {"event": "progress", "progress": 75, "message": "step 2"},
        ]
        client = _FakeClient(events=events, output_path="/root/ComfyUI/output/result.png")

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group") as mock_shutdown:
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client)

        mock_boot.assert_called_once()
        mock_shutdown.assert_called_once()
        assert store.jobs[job_id]["status"] == "completed"
        assert store.jobs[job_id]["image_path"] == "/root/ComfyUI/output/result.png"
        assert store.jobs[job_id]["progress"] == 100
        statuses = [u["status"] for u in store.updates]
        assert statuses == [
            "booting_server",
            "downloading_weights",
            "generating",
            "progress",
            "progress",
            "completed",
        ]

    @pytest.mark.asyncio
    async def test_timeout_while_generating_sets_timeout_error(self):
        """GIVEN generation exceeds the deadline
        WHEN _execute_generation runs
        THEN the job is set to error with code timeout.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(raise_on={"stream_progress": TimeoutError("deadline")})

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client)

        assert store.jobs[job_id]["status"] == "error"
        assert store.jobs[job_id]["error_code"] == "timeout"

    @pytest.mark.asyncio
    async def test_execution_error_sets_comfyui_error(self):
        """GIVEN ComfyUI reports an execution_error
        WHEN _execute_generation runs
        THEN the job is set to error with code comfyui_execution_failed.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(events=[{"event": "error", "progress": 0, "message": "node exploded"}])

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client)

        assert store.jobs[job_id]["status"] == "error"
        assert store.jobs[job_id]["error_code"] == "comfyui_execution_failed"
        assert "node exploded" in store.jobs[job_id]["error_detail"]

    @pytest.mark.asyncio
    async def test_boot_timeout_sets_timeout_error(self):
        """GIVEN ComfyUI never becomes ready
        WHEN _execute_generation runs
        THEN the job is set to error with code timeout.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(raise_on={"wait_ready": TimeoutError("not ready")})

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client, pipeline_timeout_s=30.0)

        assert store.jobs[job_id]["status"] == "error"
        assert store.jobs[job_id]["error_code"] == "timeout"

    @pytest.mark.asyncio
    async def test_connect_called_before_streaming(self):
        """GIVEN a real ComfyUI execution path
        WHEN _execute_generation runs
        THEN client.connect() is called before streaming
        AND client.close() is called during cleanup.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(events=[])

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client)

        assert client.connected
        assert client.closed
        connect_index = next(i for i, c in enumerate(client.calls) if c[0] == "connect")
        stream_index = next(i for i, c in enumerate(client.calls) if c[0] == "stream_progress")
        assert connect_index < stream_index

    @pytest.mark.asyncio
    async def test_wait_ready_happens_before_connect_and_uses_remaining_timeout(self):
        """GIVEN the ComfyUI boot path
        WHEN _execute_generation runs
        THEN readiness is confirmed before WebSocket connect
        AND connect receives a live socket timeout budget.
        """
        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(events=[])

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                await _execute_generation(job_id, {"prompt": {}}, store, client)

        wait_ready_index = next(i for i, c in enumerate(client.calls) if c[0] == "wait_ready")
        connect_index = next(i for i, c in enumerate(client.calls) if c[0] == "connect")

        assert wait_ready_index < connect_index
        assert client.calls[connect_index][1] is not None
        assert client.calls[connect_index][1] > 0

    @pytest.mark.asyncio
    async def test_asyncio_wait_for_wraps_websocket_iterator(self):
        """GIVEN streaming may block indefinitely
        WHEN _execute_generation iterates over progress events
        THEN asyncio.wait_for wraps each websocket iterator step.
        """
        import asyncio

        store = _FakeStore()
        job_id = store.create_job("a cyberpunk cat")
        client = _FakeClient(events=[{"event": "progress", "progress": 10, "message": "step"}])
        wait_for_calls = []

        original_wait_for = asyncio.wait_for

        async def _tracking_wait_for(fut, timeout, *, loop=None):
            wait_for_calls.append(timeout)
            return await original_wait_for(fut, timeout=timeout)

        with patch("src.features.generation.modal_tasks._boot_comfyui") as mock_boot:
            with patch("src.features.generation.modal_tasks._shutdown_process_group"):
                mock_boot.return_value = MagicMock()
                with patch("src.features.generation.modal_tasks.asyncio.wait_for", side_effect=_tracking_wait_for):
                    await _execute_generation(job_id, {"prompt": {}}, store, client)

        assert any(c > 0 for c in wait_for_calls), "asyncio.wait_for should be called with a positive timeout"
        assert client.connected
        assert client.closed
