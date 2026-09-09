from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[3]
CONTENT_DIR = BASE_DIR / "Content"
AUDIO_DIR = BASE_DIR / "Audio"
ALLOWED_DIRS = (CONTENT_DIR, AUDIO_DIR)


@router.get("/api/files/{path:path}")
async def serve_file(path: str):
    resolved = (BASE_DIR / path).resolve()
    if not any(base == resolved or base in resolved.parents for base in ALLOWED_DIRS):
        raise HTTPException(status_code=404, detail="File not found")
    if resolved.is_file():
        return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="File not found")