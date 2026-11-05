from fastapi import APIRouter, Header

from ..jobs import JobProgress, job_manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobProgress)
async def get_job_status(
    job_id: str, x_session_id: str | None = Header(None, alias="X-Session-Id")
):
    """Get the current progress, stage, and result of a document generation job (API-JOBS)."""
    return job_manager.get_job(job_id, session_id=x_session_id)


@router.delete("/{job_id}")
async def cancel_job(job_id: str, x_session_id: str | None = Header(None, alias="X-Session-Id")):
    """Cancel a running or queued document generation job."""
    job = job_manager.cancel_job(job_id, session_id=x_session_id)
    return {"job_id": job.job_id, "status": job.status, "message": "Job cancelled successfully."}
