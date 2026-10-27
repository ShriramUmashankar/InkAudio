"""Optional Docker Lite restrictions; normal startup keeps all features."""
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


def is_lite():
    return os.environ.get("PODCAST_LITE") == "1"


class LiteModeMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Reject before FastAPI parses multipart bodies or creates a job.
        if (scope["type"] == "http" and is_lite()
                and scope["method"] == "POST"
                and scope["path"].rstrip("/") in {
                    "/api/job/custom_voice", "/api/job/voice_design", "/api/transcribe",
                }):
            response = JSONResponse(
                {"detail": "Unavailable in Lite. Use Bodhan AI and typed feedback."},
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


@router.get("/api/capabilities")
async def capabilities():
    lite = is_lite()
    return {"lite": lite, "tts_modes": ["bodhan"] if lite else [
        "bodhan", "custom_voice", "voice_design",
    ], "stt_enabled": not lite}


@router.get("/api/health")
async def health():
    """Process health only: examples and health do not require API credentials."""
    return {"status": "ok"}
