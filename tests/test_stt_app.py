import io

from fastapi.testclient import TestClient

from src.api.main import app


class MockSegment:
    def __init__(self, text: str):
        self.text = text


class MockWhisperModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, path):
        return [MockSegment("Hello world"), MockSegment("This is a test")], None


def test_transcribe_endpoint():
    import src.api.routes.transcribe as transcribe_module
    transcribe_module._model = MockWhisperModel()

    client = TestClient(app)

    audio_content = b"fake audio data"
    files = {"file": ("test.wav", io.BytesIO(audio_content), "audio/wav")}

    response = client.post("/api/transcribe", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "Hello world This is a test"

    transcribe_module._model = None


def test_transcribe_response_model():
    from src.api.models import TranscriptResponse

    resp = TranscriptResponse(transcript="test transcript")
    assert resp.transcript == "test transcript"


def test_transcribe_empty_filename():
    client = TestClient(app)

    files = {"file": ("", io.BytesIO(b""), "audio/wav")}

    response = client.post("/api/transcribe", files=files)

    assert response.status_code == 422 or response.status_code == 200
