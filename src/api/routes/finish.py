from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue as job_queue_mod
from src.api import model_manager as model_manager_mod

router = APIRouter()


@router.post("/api/jobs/{job_id}/finish")
async def finish_job(job_id: str):
    queue = job_queue_mod.get_job_queue()
    job = None
    for j in queue:
        if j.job_id == job_id:
            job = j
            break
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    mm = model_manager_mod.get_model_manager()
    mm.unload(job.tts_mode)
    model_unloaded = job.tts_mode != "bodhan"

    return JSONResponse(status_code=200, content={"status": "cleaned_up", "model_unloaded": model_unloaded})