import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from ..config import load_settings


class TranscriptResponse(BaseModel):
    transcript: str


_model = None
_settings = None


def _load_model():
    global _model, _settings
    if _settings is None:
        _settings = load_settings()
    _model = __import__("faster_whisper").WhisperModel(
        _settings.stt.model,
        device=_settings.stt.device,
        compute_type=_settings.stt.compute_type,
    )


def _unload_model():
    global _model
    if _model is not None:
        del _model
        _model = None
        if __import__("torch").cuda.is_available():
            __import__("torch").cuda.empty_cache()


router = APIRouter()


@router.post(
    "/transcribe",
    response_model=TranscriptResponse,
    summary="Transcribe audio file",
    description="Upload an audio file (WAV, MP3, FLAC, OGG, etc.) and get the transcript. "
                "Uses faster-whisper with model loaded on demand to avoid permanent GPU VRAM usage.",
)
async def transcribe(file: UploadFile = File(..., description="Audio file to transcribe")):
    if _model is None:
        _load_model()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        segments, _ = _model.transcribe(tmp_path)
        transcript = " ".join(seg.text for seg in segments).strip()

        os.unlink(tmp_path)
        return TranscriptResponse(transcript=transcript)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _unload_model()