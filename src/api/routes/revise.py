from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.api import job_queue as job_queue_mod
from src.api.models import RevisionRequest

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

    worker = job_queue_mod.get_worker()
    new_job_id = worker.add_job(
        tts_mode=job.tts_mode,
        content_pdf_path=job.content_pdf_path,
        questions_pdf_path=job.questions_pdf_path,
        config={**job.config, "feedback": request.feedback, "revision": True},
    )
    return JSONResponse(status_code=202, content={"job_id": new_job_id, "status": "queued", "tts_mode": job.tts_mode})