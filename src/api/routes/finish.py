from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue

router = APIRouter()


@router.post("/api/job/finish")
async def finish_job():
    job = job_queue.get_current_job()
    if job is None:
        raise HTTPException(status_code=400, detail="no job to finish")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="job running; use /api/job/terminate or wait")
    job_queue.finish_job(job)
    return JSONResponse(content={"status": "cleaned_up"})


@router.post("/api/job/terminate")
async def terminate_job():
    job = job_queue.get_current_job()
    if job is None or job.status != "running":
        raise HTTPException(status_code=400, detail="no running job")
    job.cancel_requested = True
    return JSONResponse(content={"status": "terminating", "tts_mode": job.tts_mode})