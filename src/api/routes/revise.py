from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue
from src.api.models import RevisionRequest

router = APIRouter()


@router.post("/api/job/revise")
async def revise_job(request: RevisionRequest):
    job = job_queue.get_current_job()
    if job is None or job.status != "completed":
        raise HTTPException(status_code=400, detail="no completed job to revise")
    job.config = {**job.config, "feedback": request.feedback, "revision": True}
    job.status = "running"
    job.result = None
    job.error = None
    job.cancel_requested = False
    job_queue.run_job(job)
    return JSONResponse(status_code=202, content={"status": "running", "tts_mode": job.tts_mode})