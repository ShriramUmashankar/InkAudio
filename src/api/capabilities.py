"""Optional Docker Lite restrictions; normal startup keeps all features."""
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


def is_lite():
    """Return whether the environment enables the restricted Docker Lite feature set."""
    return os.environ.get("PODCAST_LITE") == "1"


class LiteModeMiddleware:
    """Block local TTS and transcription POST requests when Lite mode is enabled."""
    def __init__(self, app):
        """Store the downstream ASGI application for allowed requests."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Reject restricted Lite requests before body parsing, or forward the ASGI call."""
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
    """Report available TTS modes and transcription support for the current environment."""
    lite = is_lite()
    return {"lite": lite, "tts_modes": ["bodhan"] if lite else [
        "bodhan", "custom_voice", "voice_design",
    ], "stt_enabled": not lite}


@router.get("/api/health")
async def health():
    """Process health only: examples and health do not require API credentials."""
    return {"status": "ok"}
