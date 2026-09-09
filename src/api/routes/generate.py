import json
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.api import job_queue

router = APIRouter()

VALID_TTS_MODES = {"bodhan", "custom_voice", "voice_design"}

_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "src" / "tts_requirements"


@router.get("/api/tts/template")
async def get_template(mode: str):
    if mode not in VALID_TTS_MODES:
        raise HTTPException(status_code=404, detail=f"Unknown TTS mode: {mode}")
    path = _TEMPLATE_DIR / f"{mode}.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"template not found: {mode}")
    return JSONResponse(yaml.safe_load(path.read_text(encoding="utf-8")))


@router.post("/api/job/{mode}")
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

    merged_config = {}
    if config:
        try:
            merged_config = json.loads(config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid config JSON")

    try:
        job = job_queue.create_job(mode, merged_config)
    except job_queue.JobBusyError:
        raise HTTPException(status_code=409, detail="generation already in progress")

    try:
        Path(job.content_pdf_path).write_bytes(await content_pdf.read())
        if questions_pdf and questions_pdf.filename:
            Path(job.questions_pdf_path).write_bytes(await questions_pdf.read())
    except Exception as e:
        job_queue.abandon(job)
        raise HTTPException(status_code=500, detail=f"failed to save upload: {e}")

    job_queue.run_job(job)
    return JSONResponse(status_code=202, content={"status": "running", "tts_mode": mode})