import uuid
from typing import Optional, Dict, Any


class JobStore:
    """In-memory MVP store for generation job lifecycle states.

    Contract: create/get/update/terminal state for jobs.
    """

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self, prompt: str) -> str:
        """Create a new job with pending status.

        Returns a unique job_id.
        """
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "pending",
            "image_path": None,
            "error_code": None,
            "error_detail": None,
        }
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by job_id.

        Returns None if the job does not exist.
        """
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: str,
        image_path: Optional[str] = None,
        error_code: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Update a job's status and optional result/error details.

        Raises KeyError if the job does not exist.
        """
        if job_id not in self._jobs:
            raise KeyError(f"Job {job_id} not found")

        self._jobs[job_id]["status"] = status
        if image_path is not None:
            self._jobs[job_id]["image_path"] = image_path
        if error_code is not None:
            self._jobs[job_id]["error_code"] = error_code
        if error_detail is not None:
            self._jobs[job_id]["error_detail"] = error_detail
