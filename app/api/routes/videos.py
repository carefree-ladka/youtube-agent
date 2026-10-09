"""Video generation endpoints (asynchronous / background jobs)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_job_manager
from app.core.logging import get_logger
from app.models.schemas import VideoJob, VideoJobCreated, VideoRequest
from app.services.video.jobs import VideoJobManager

logger = get_logger(__name__)
router = APIRouter(prefix="/videos", tags=["video"])


@router.post("/generate", response_model=VideoJobCreated, status_code=202)
async def generate_video(
    request: VideoRequest,
    jobs: VideoJobManager = Depends(get_job_manager),
) -> VideoJobCreated:
    """Queue a video generation job and return its id immediately.

    Rendering runs in the background; poll ``GET /videos/{jobId}`` for status.
    """
    job = jobs.submit(request)
    return VideoJobCreated(jobId=job.jobId, status=job.status)


@router.get("/{job_id}", response_model=VideoJob)
async def get_video_job(
    job_id: str,
    jobs: VideoJobManager = Depends(get_job_manager),
) -> VideoJob:
    """Return the current status (and result when completed) of a video job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[VideoJob])
async def list_video_jobs(
    jobs: VideoJobManager = Depends(get_job_manager),
) -> list[VideoJob]:
    """List all known video jobs (newest state in memory)."""
    return jobs.list_jobs()
