"""Run with: python -m pytest docker/test_lite.py -q (no cloud/model calls)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api import job_queue
from src.api.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("PODCAST_LITE", raising=False)
    monkeypatch.setattr(job_queue, "TEMP_ROOT", tmp_path / "job")
    monkeypatch.setattr(job_queue, "_current_job", None)
    return TestClient(app)


@pytest.mark.parametrize("flag,lite,modes", [
    (None, False, ["bodhan", "custom_voice", "voice_design"]),
    ("0", False, ["bodhan", "custom_voice", "voice_design"]),
    ("1", True, ["bodhan"]),
])
def test_capabilities_are_opt_in(client, monkeypatch, flag, lite, modes):
    if flag is not None:
        monkeypatch.setenv("PODCAST_LITE", flag)
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.json() == {"lite": lite, "tts_modes": modes, "stt_enabled": not lite}


@pytest.mark.parametrize("path", [
    "/api/job/custom_voice", "/api/job/voice_design", "/api/transcribe",
    "/api/job/custom_voice/", "/api/transcribe/",
])
def test_lite_rejects_before_parsing_upload_or_starting_job(client, monkeypatch, path):
    monkeypatch.setenv("PODCAST_LITE", "1")
    monkeypatch.setattr(job_queue, "create_job", lambda *a: pytest.fail("job was created"))
    monkeypatch.setattr("src.api.routes.transcribe._load_model", lambda: pytest.fail("STT loaded"))
    # Intentionally malformed multipart: a route-level guard would run too late.
    response = client.post(path, content=b"invalid", headers={"Content-Type": "multipart/form-data"})
    assert response.status_code == 403
    assert "Lite" in response.json()["detail"]
    assert job_queue.get_current_job() is None


@pytest.mark.parametrize("mode", ["bodhan", "custom_voice", "voice_design"])
@pytest.mark.parametrize("lite", [False, True])
def test_only_lite_limits_generation(client, monkeypatch, tmp_path, mode, lite):
    if lite:
        monkeypatch.setenv("PODCAST_LITE", "1")
    job = SimpleNamespace(content_pdf_path=str(tmp_path / "upload.pdf"), questions_pdf_path="unused")
    monkeypatch.setattr(job_queue, "create_job", lambda *a: job)
    started = []
    monkeypatch.setattr(job_queue, "run_job", started.append)
    response = client.post(f"/api/job/{mode}", files={"content_pdf": ("a.pdf", b"%PDF", "application/pdf")})
    if lite and mode != "bodhan":
        assert response.status_code == 403
        assert started == []
    else:
        assert response.status_code == 202
        assert started == [job]


def test_health_and_examples_need_no_credentials(client, monkeypatch):
    monkeypatch.setenv("PODCAST_LITE", "1")
    monkeypatch.setattr("src.config.load_settings", lambda *a: pytest.fail("settings loaded"))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/examples.html").status_code == 200
    response = client.get("/podcast_examples/Cell-English-Custom-Voice/final_podcast.mp3",
                          headers={"Range": "bytes=0-127"})
    assert response.status_code == 206
    assert len(response.content) == 128


def test_normal_transcription_still_works(client, monkeypatch):
    from src.api.routes import transcribe
    monkeypatch.setattr(transcribe, "_model", SimpleNamespace(
        transcribe=lambda path: ([SimpleNamespace(text="Typed or spoken feedback")], None)))
    monkeypatch.setattr(transcribe, "_unload_model", lambda: None)
    response = client.post("/api/transcribe", files={"file": ("voice.wav", b"audio", "audio/wav")})
    assert response.status_code == 200
    assert response.json()["transcript"] == "Typed or spoken feedback"


def test_lite_typed_revision_remains_available(client, monkeypatch, tmp_path):
    monkeypatch.setenv("PODCAST_LITE", "1")
    job = job_queue.JobRecord("bodhan", str(tmp_path), "unused.pdf", {}, status="completed")
    monkeypatch.setattr(job_queue, "_current_job", job)
    started = []
    monkeypatch.setattr(job_queue, "run_job", started.append)
    response = client.post("/api/job/revise", json={"feedback": "Make the opening shorter"})
    assert response.status_code == 202
    assert started == [job]
    assert job.config["feedback"] == "Make the opening shorter"
