from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
import json
import asyncio
from typing import AsyncIterator

from src.api import job_queue as job_queue_mod
from src.api.models import JobInfo, JobResult

router = APIRouter()


@router.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    queue = job_queue_mod.get_job_queue()
    for job in queue:
        if job.job_id == job_id:
            result = None
            if job.result:
                try:
                    result = JobResult(**job.result)
                except ValidationError:
                    result = None
            return JobInfo(
                job_id=job.job_id,
                tts_mode=job.tts_mode,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
                result=result,
                error=job.error,
            )
    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    queue = job_queue_mod.get_job_queue()
    job = None
    for j in queue:
        if j.job_id == job_id:
            job = j
            break
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator() -> AsyncIterator[str]:
        while isinstance(job.status, str) and job.status not in ("completed", "failed"):
            await asyncio.sleep(0.5)
            yield f"event: status\ndata: {json.dumps({'status': job.status})}\n\n"
            if job.result:
                try:
                    yield f"event: partial\ndata: {json.dumps(job.result)}\n\n"
                except TypeError:
                    yield f"event: partial\ndata: {json.dumps(str(job.result))}\n\n"
        if job.result:
            try:
                yield f"event: complete\ndata: {json.dumps(job.result)}\n\n"
            except TypeError:
                yield f"event: complete\ndata: {json.dumps(str(job.result))}\n\n"
        if job.error:
            yield f"event: error\ndata: {json.dumps({'message': str(job.error)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
