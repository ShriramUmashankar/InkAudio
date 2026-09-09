from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue as job_queue_mod
from src.api.models import RevisionRequest
from src.config import load_settings
from src.script_gen import revise_script

router = APIRouter()


@router.post("/api/jobs/{job_id}/revise")
async def revise_job(job_id: str, request: RevisionRequest):
    queue = job_queue_mod.get_job_queue()
    job = None
    for j in queue:
        if j.job_id == job_id:
            job = j
            break
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "failed":
        raise HTTPException(status_code=400, detail="Cannot revise a failed job")

    settings = load_settings()
    settings.tts.mode = job.tts_mode

    revise_script(settings, request.feedback)

    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "completed"})
