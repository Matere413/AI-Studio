import pytest
from src.shared.job_store import JobStore


class TestJobStore:
    """Unit tests for JobStore in-memory state manager."""

    def test_create_job(self):
        """GIVEN a prompt
        WHEN creating a job
        THEN a job is created with pending status and a unique job_id.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        assert job_id is not None
        assert len(job_id) > 0

    def test_get_job_status_pending(self):
        """GIVEN a newly created job
        WHEN getting its status
        THEN the status is pending.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        job = store.get_job(job_id)
        assert job["status"] == "pending"
        assert job["prompt"] == "a cyberpunk cat"

    def test_update_job_to_running(self):
        """GIVEN a pending job
        WHEN updating status to running
        THEN the job status is running.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        store.update_job(job_id, status="running")
        job = store.get_job(job_id)
        assert job["status"] == "running"

    def test_update_job_to_completed(self):
        """GIVEN a running job
        WHEN updating status to completed with image_path
        THEN the job status is completed and image_path is set.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        store.update_job(job_id, status="completed", image_path="/path/to/image.png")
        job = store.get_job(job_id)
        assert job["status"] == "completed"
        assert job["image_path"] == "/path/to/image.png"

    def test_update_job_to_error(self):
        """GIVEN a running job
        WHEN updating status to error with code and detail
        THEN the job status is error and error details are set.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        store.update_job(job_id, status="error", error_code="FAILURE", error_detail="GPU unavailable")
        job = store.get_job(job_id)
        assert job["status"] == "error"
        assert job["error_code"] == "FAILURE"
        assert job["error_detail"] == "GPU unavailable"

    def test_get_job_not_found(self):
        """GIVEN no job exists for a job_id
        WHEN getting the job
        THEN None is returned.
        """
        store = JobStore()
        job = store.get_job("non-existent")
        assert job is None

    def test_job_ids_are_unique(self):
        """GIVEN multiple jobs are created
        WHEN comparing their job_ids
        THEN each job_id is unique.
        """
        store = JobStore()
        job_id1 = store.create_job("prompt 1")
        job_id2 = store.create_job("prompt 2")
        assert job_id1 != job_id2

    def test_get_job_preserves_prompt(self):
        """GIVEN a job is created with a prompt
        WHEN getting the job after status updates
        THEN the prompt is preserved.
        """
        store = JobStore()
        job_id = store.create_job("a cyberpunk cat")
        store.update_job(job_id, status="running")
        store.update_job(job_id, status="completed", image_path="/path/to/image.png")
        job = store.get_job(job_id)
        assert job["prompt"] == "a cyberpunk cat"
