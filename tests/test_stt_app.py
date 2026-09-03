import io
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/home/shriram/Documents/SEM9/RAGenAI/PodcastGeneration")


class MockSegment:
    def __init__(self, text: str):
        self.text = text


class MockWhisperModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, path):
        return [MockSegment("Hello world"), MockSegment("This is a test")], None


def test_transcribe_endpoint():
    import src.stt_app as stt_app_module
    stt_app_module._model = MockWhisperModel()

    from src.stt_app import app
    client = TestClient(app)

    audio_content = b"fake audio data"
    files = {"file": ("test.wav", io.BytesIO(audio_content), "audio/wav")}

    response = client.post("/api/transcribe", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "Hello world This is a test"

    stt_app_module._model = None


def test_transcribe_response_model():
    from src.stt_app import TranscriptResponse

    resp = TranscriptResponse(transcript="test transcript")
    assert resp.transcript == "test transcript"


def test_transcribe_empty_filename():
    from src.stt_app import app

    client = TestClient(app)

    files = {"file": ("", io.BytesIO(b""), "audio/wav")}

    response = client.post("/api/transcribe", files=files)

    assert response.status_code == 422 or response.status_code == 200