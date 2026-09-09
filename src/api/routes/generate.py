from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse
from pathlib import Path as P
from typing import Optional
import json
import os

from src.api import job_queue
from src.api.models import GenerateRequest

router = APIRouter()

VALID_TTS_MODES = {"bodhan", "custom_voice", "voice_design"}


@router.post("/api/jobs/{mode}")
async def generate_job(
    mode: str,
    content_pdf: UploadFile = File(..., description="Content PDF"),
    questions_pdf: Optional[UploadFile] = File(None, description="Optional questions PDF"),
    config: Optional[str] = Body(None, description="JSON config overrides"),
):
    if mode not in VALID_TTS_MODES:
        raise HTTPException(status_code=404, detail=f"Unknown TTS mode: {mode}")

    if not content_pdf or not content_pdf.filename:
        raise HTTPException(status_code=400, detail="content_pdf is required")
    safe_name = P(content_pdf.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="content_pdf is required")

    content_dir = "Content"
    os.makedirs(content_dir, exist_ok=True)
    os.makedirs("Audio", exist_ok=True)

    content_pdf_path = os.path.join(content_dir, safe_name)
    with open(content_pdf_path, "wb") as f:
        content = await content_pdf.read()
        f.write(content)

    questions_pdf_path = None
    if questions_pdf and questions_pdf.filename:
        questions_safe_name = P(questions_pdf.filename).name
        if questions_safe_name:
            questions_pdf_path = os.path.join(content_dir, questions_safe_name)
            with open(questions_pdf_path, "wb") as f:
                q_content = await questions_pdf.read()
                f.write(q_content)

    merged_config = {}
    if config:
        try:
            merged_config = json.loads(config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid config JSON")

    worker = job_queue.get_worker()
    job_id = worker.add_job(
        tts_mode=mode,
        content_pdf_path=content_pdf_path,
        questions_pdf_path=questions_pdf_path,
        config=merged_config,
    )

    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "queued", "tts_mode": mode})