from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue

router = APIRouter()


@router.post("/api/job/finish")
async def finish_job():
    job = job_queue.get_current_job()
    if job is None:
        return JSONResponse(content={"status": "cleaned_up"})
    if job.status == "running":
        job.cancel_requested = True
        job_queue.finish_job(job)
        return JSONResponse(content={"status": "terminated_and_cleaned"})
    job_queue.finish_job(job)
    return JSONResponse(content={"status": "cleaned_up"})


@router.post("/api/job/terminate")
async def terminate_job():
    job = job_queue.get_current_job()
    if job is None or job.status != "running":
        raise HTTPException(status_code=400, detail="no running job")
    job.cancel_requested = True
    # Immediately unload model and clean up - don't wait for background thread
    job_queue.finish_job(job)
    return JSONResponse(content={"status": "terminated", "tts_mode": job.tts_mode})