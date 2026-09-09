import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from src.api import job_queue

router = APIRouter()


@router.get("/api/job")
async def job_status():
    job = job_queue.get_current_job()
    if job is None:
        return {"status": "idle"}
    return {
        "status": job.status,
        "tts_mode": job.tts_mode,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "error": job.error,
    }


@router.get("/api/job/result")
async def get_result():
    job = job_queue.get_current_job()
    if job is None:
        raise HTTPException(status_code=404, detail="no job")
    path = Path(job.temp_dir) / "final_podcast.mp3"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="podcast not ready")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/api/job/script")
async def get_script():
    job = job_queue.get_current_job()
    if job is None:
        raise HTTPException(status_code=404, detail="no job")
    path = Path(job.temp_dir) / "script.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="script not ready")
    return FileResponse(path, media_type="application/json")


@router.get("/api/job/questions")
async def get_questions():
    job = job_queue.get_current_job()
    if job is None or not job.questions_report:
        raise HTTPException(status_code=404, detail="no questions report")
    return JSONResponse(job.questions_report)


@router.get("/api/job/events")
async def job_events():
    job = job_queue.get_current_job()
    if job is None:
        raise HTTPException(status_code=404, detail="no job")

    async def event_generator() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        listener = asyncio.Queue()
        job._sse_listeners.append((listener, loop))
        try:
            while job.status == "running":
                try:
                    payload = await asyncio.wait_for(listener.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {payload}\n\n"
            while not listener.empty():
                try:
                    payload = listener.get_nowait()
                except asyncio.QueueEmpty:
                    break
                yield f"data: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
        finally:
            job._sse_listeners[:] = [l for l, _ in job._sse_listeners if l is not listener]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )