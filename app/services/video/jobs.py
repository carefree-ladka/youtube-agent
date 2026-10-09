"""In-process async job manager for background video generation.

Keeps the project simple (no external queue/broker): jobs run as asyncio tasks
on the app's event loop, with a semaphore so heavy Remotion renders don't run on
top of each other. Job state is tracked in memory and exposed via the API.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import VideoJob, VideoJobStatus, VideoRequest
from app.services.video.video_orchestrator import VideoOrchestrator

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VideoJobManager:
    """Creates, runs, and tracks asynchronous video generation jobs."""

    def __init__(
        self,
        orchestrator: VideoOrchestrator,
        settings: Settings,
        *,
        max_concurrent: int = 1,
    ) -> None:
        self._orchestrator = orchestrator
        self._settings = settings
        self._jobs: dict[str, VideoJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def submit(self, request: VideoRequest) -> VideoJob:
        """Create a queued job and schedule it; returns immediately."""
        job_id = uuid.uuid4().hex
        now = _now()
        job = VideoJob(jobId=job_id, status="queued", topic=request.topic, createdAt=now, updatedAt=now)
        self._jobs[job_id] = job
        self._tasks[job_id] = asyncio.create_task(self._run(job_id, request))
        logger.info("Queued video job %s for '%s'", job_id, request.topic)
        return job

    def get(self, job_id: str) -> VideoJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[VideoJob]:
        return list(self._jobs.values())

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _set_status(self, job_id: str, status: VideoJobStatus) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status = status
            job.updatedAt = _now()
            logger.info("Job %s -> %s", job_id, status)

    async def _run(self, job_id: str, request: VideoRequest) -> None:
        async with self._semaphore:
            try:
                result = await self._orchestrator.run(
                    request, progress=lambda s: self._set_status(job_id, s)
                )
                job = self._jobs[job_id]
                job.result = result
                job.videoUrl = self._to_url(result.video_path)
                job.status = "completed" if result.video_path else "failed"
                if not result.video_path:
                    job.error = "; ".join(result.warnings) or "Render produced no video."
                job.updatedAt = _now()
                logger.info("Job %s %s", job_id, job.status)
            except Exception as exc:  # noqa: BLE001 - surface any failure on the job
                logger.exception("Video job %s failed", job_id)
                job = self._jobs.get(job_id)
                if job:
                    job.status = "failed"
                    job.error = str(exc)
                    job.updatedAt = _now()

    def _to_url(self, video_path: str | None) -> str | None:
        """Map an on-disk video path to its public /media URL."""
        if not video_path:
            return None
        try:
            rel = Path(video_path).resolve().relative_to(self._settings.output_path.resolve())
        except ValueError:
            return None
        return f"/media/{rel.as_posix()}"
