import uuid
import modal
from typing import Optional, Dict, Any


class JobStore:
    """Distributed store for generation job lifecycle states using modal.Dict.

    Contract: create/get/update/terminal state for jobs across containers.
    """

    def __init__(self):
        # Conecta a un diccionario distribuido de Modal que sobrevive a los contenedores
        self._jobs = modal.Dict.from_name("api-blanca-jobs", create_if_missing=True)

    def create_job(self, prompt: str, session_id: str = "") -> str:
        """Create a new job with pending status.

        Args:
            prompt: Generation prompt.
            session_id: Optional session UUID for ownership tracking.

        Returns a unique job_id.
        """
        job_id = str(uuid.uuid4())
        self._store_job(job_id, prompt, session_id=session_id)
        return job_id

    async def acreate_job(self, prompt: str, session_id: str = "") -> str:
        """Create a new job asynchronously (for async contexts).

        Args:
            prompt: Generation prompt.
            session_id: Optional session UUID for ownership tracking.
        """
        job_id = str(uuid.uuid4())
        await self._astore_job(job_id, prompt, session_id=session_id)
        return job_id

    def _store_job(self, job_id: str, prompt: str, session_id: str = "") -> None:
        self._jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "pending",
            "session_id": session_id,
            "image_path": None,
            "volume_path": None,
            "error_code": None,
            "error_detail": None,
            "artifacts": None,
        }

    async def _astore_job(self, job_id: str, prompt: str, session_id: str = "") -> None:
        await self._jobs.__setitem__.aio(
            job_id,
            {
                "job_id": job_id,
                "prompt": prompt,
                "status": "pending",
                "session_id": session_id,
                "image_path": None,
                "volume_path": None,
                "error_code": None,
                "error_detail": None,
                "artifacts": None,
            },
        )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by job_id.

        Returns None if the job does not exist.
        """
        try:
            return self._jobs.get(job_id)
        except Exception:
            return None

    async def aget_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job asynchronously (for async contexts)."""
        try:
            return await self._jobs.get.aio(job_id)
        except Exception:
            return None

    def update_job(
        self,
        job_id: str,
        status: str,
        image_path: Optional[str] = None,
        volume_path: Optional[str] = None,
        error_code: Optional[str] = None,
        error_detail: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        artifacts: Optional[list] = None,
    ) -> None:
        """Update a job's status and optional result/error details.

        ``volume_path`` is the relative path within the image volume
        (used for public WS events, while ``image_path`` is the
        absolute filesystem path used by GET /images/{job_id}).

        Raises KeyError if the job does not exist.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found")

        job["status"] = status
        if image_path is not None:
            job["image_path"] = image_path
        if volume_path is not None:
            job["volume_path"] = volume_path
        if error_code is not None:
            job["error_code"] = error_code
        if error_detail is not None:
            job["error_detail"] = error_detail
        if progress is not None:
            job["progress"] = progress
        if message is not None:
            job["message"] = message
        if artifacts is not None:
            job["artifacts"] = artifacts

        # Reasignar para que Modal persista los cambios
        self._jobs[job_id] = job

    async def aupdate_job(
        self,
        job_id: str,
        status: str,
        image_path: Optional[str] = None,
        volume_path: Optional[str] = None,
        error_code: Optional[str] = None,
        error_detail: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        artifacts: Optional[list] = None,
    ) -> None:
        """Update a job asynchronously (for async contexts).

        ``volume_path`` is the relative path within the image volume,
        complementary to the absolute ``image_path``.
        """
        job = await self._jobs.get.aio(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found")

        job["status"] = status
        if image_path is not None:
            job["image_path"] = image_path
        if volume_path is not None:
            job["volume_path"] = volume_path
        if error_code is not None:
            job["error_code"] = error_code
        if error_detail is not None:
            job["error_detail"] = error_detail
        if progress is not None:
            job["progress"] = progress
        if message is not None:
            job["message"] = message
        if artifacts is not None:
            job["artifacts"] = artifacts

        await self._jobs.put.aio(job_id, job)
