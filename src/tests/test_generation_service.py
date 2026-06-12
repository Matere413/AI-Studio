import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.features.generation.service import GenerationService
from src.shared.job_store import JobStore


class TestGenerationService:
    """Unit tests for GenerationService business logic."""

    def test_create_job(self):
        """GIVEN a prompt
        WHEN creating a job
        THEN a job_id is returned and the job is stored with pending status.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        assert job_id is not None
        assert len(job_id) > 0
        job = store.get_job(job_id)
        assert job["status"] == "pending"
        assert job["prompt"] == "a cyberpunk cat"

    def test_create_job_with_empty_prompt(self):
        """GIVEN an empty prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises(ValueError):
            service.create_job("")

    def test_create_job_with_whitespace_prompt(self):
        """GIVEN a whitespace-only prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises(ValueError):
            service.create_job("   ")

    def test_create_job_with_none_prompt(self):
        """GIVEN None as prompt
        WHEN creating a job
        THEN a ValueError is raised.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        with pytest.raises((ValueError, TypeError)):
            service.create_job(None)

    def test_get_job_status(self):
        """GIVEN a created job
        WHEN getting its status
        THEN the job data is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        job = service.get_job(job_id)
        assert job["status"] == "pending"

    def test_get_job_not_found(self):
        """GIVEN no job exists
        WHEN getting a job
        THEN None is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job = service.get_job("non-existent")
        assert job is None

    def test_map_failure_to_terminal_error(self):
        """GIVEN a failure occurs
        WHEN mapping the failure
        THEN a terminal error with code and detail is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        error = service.map_failure_to_error("GPU_TIMEOUT", "GPU execution timed out")
        assert error["code"] == "GPU_TIMEOUT"
        assert error["detail"] == "GPU execution timed out"

    @patch("src.features.generation.modal_tasks.run_generation")
    def test_enqueue_modal_work(self, mock_run_generation):
        """GIVEN a job is created
        WHEN enqueuing Modal work
        THEN the Modal task is called.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        service.enqueue_modal_work(job_id, "a cyberpunk cat")
        mock_run_generation.assert_called_once()

    def test_job_lifecycle_events(self):
        """GIVEN a job exists
        WHEN getting lifecycle events
        THEN the current event is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        events = list(service.get_job_events(job_id))
        assert len(events) > 0
        assert events[0]["event"] == "pending"

    def test_job_completed_event(self):
        """GIVEN a job is completed
        WHEN getting lifecycle events
        THEN a completed event with image_path is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="completed", image_path="/path/to/image.png")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "completed"
        assert events[0]["result"]["image_path"] == "/path/to/image.png"

    def test_job_running_event(self):
        """GIVEN a job is running
        WHEN getting lifecycle events
        THEN a running event with progress and message is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="running")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "running"
        assert events[0]["progress"] == 50
        assert events[0]["message"] == "Processing"

    def test_job_error_event(self):
        """GIVEN a job fails
        WHEN getting lifecycle events
        THEN an error event with code and detail is returned.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        store.update_job(job_id, status="error", error_code="FAILURE", error_detail="GPU unavailable")
        events = list(service.get_job_events(job_id))
        assert events[0]["event"] == "error"
        assert events[0]["error"]["code"] == "FAILURE"
        assert events[0]["error"]["detail"] == "GPU unavailable"

    def test_enqueue_modal_work_failure(self):
        """GIVEN a Modal task fails
        WHEN enqueuing work
        THEN the error is propagated.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("a cyberpunk cat")
        with patch("src.features.generation.modal_tasks.run_generation") as mock_run:
            mock_run.side_effect = Exception("GPU unavailable")
            with pytest.raises(Exception):
                service.enqueue_modal_work(job_id, "a cyberpunk cat")

    @pytest.mark.asyncio
    async def test_poll_job_events_yields_state_changes(self):
        """GIVEN a job exists and transitions through states
        WHEN polling for events
        THEN events are yielded for each state change.
        """
        store = JobStore()
        service = GenerationService(job_store=store)
        job_id = service.create_job("polling test")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            events = []
            async for event in service.poll_job_events(job_id, interval=0.001):
                events.append(event)
                if event["event"] == "pending":
                    store.update_job(job_id, status="running")
                elif event["event"] == "running":
                    store.update_job(job_id, status="completed", image_path="/img.png")
                elif event["event"] == "completed":
                    break

            assert len(events) == 3
            assert events[0]["event"] == "pending"
            assert events[1]["event"] == "running"
            assert events[2]["event"] == "completed"
            assert events[2]["result"]["image_path"] == "/img.png"

    @pytest.mark.asyncio
    async def test_poll_job_events_unknown_job(self):
        """GIVEN no job exists
        WHEN polling for events
        THEN a terminal error event is yielded.
        """
        store = JobStore()
        service = GenerationService(job_store=store)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            events = []
            async for event in service.poll_job_events("unknown-job", interval=0.001):
                events.append(event)

            assert len(events) == 1
            assert events[0]["event"] == "error"
            assert events[0]["error"]["code"] == "NOT_FOUND"
