import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app


def test_generate_bodhan_endpoint():
    client = TestClient(app)
    with patch("src.api.job_queue.get_worker") as mock_worker:
        mock_worker.return_value.add_job.return_value = "test-job-id"
        response = client.post(
            "/api/jobs/bodhan",
            files={"content_pdf": ("test.pdf", b"pdf_content", "application/pdf")},
            data={"config": json.dumps({"bodhan": {"host1": {"voice": "Parth"}}, "pipeline": {"max_loops": 3}})},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["tts_mode"] == "bodhan"
    assert data["status"] == "queued"


def test_generate_custom_voice_endpoint():
    client = TestClient(app)
    with patch("src.api.job_queue.get_worker") as mock_worker:
        mock_worker.return_value.add_job.return_value = "cv-job-id"
        response = client.post(
            "/api/jobs/custom_voice",
            files={"content_pdf": ("test.pdf", b"pdf_content", "application/pdf")},
            data={"config": json.dumps({"custom_voice": {"host1": {"speaker": "ryan"}}, "pipeline": {"max_loops": 3}})},
        )
    assert response.status_code == 202
    assert response.json()["tts_mode"] == "custom_voice"


def test_generate_voice_design_endpoint():
    client = TestClient(app)
    with patch("src.api.job_queue.get_worker") as mock_worker:
        mock_worker.return_value.add_job.return_value = "vd-job-id"
        response = client.post(
            "/api/jobs/voice_design",
            files={"content_pdf": ("test.pdf", b"pdf_content", "application/pdf")},
            data={"config": json.dumps({"voice_design": {"host1": {"instruct": "test"}}, "pipeline": {"max_loops": 3}})},
        )
    assert response.status_code == 202
    assert response.json()["tts_mode"] == "voice_design"


def test_generate_missing_content_pdf():
    client = TestClient(app)
    response = client.post(
        "/api/jobs/bodhan",
        files={},
    )
    assert response.status_code == 422


def test_generate_invalid_mode():
    client = TestClient(app)
    response = client.post(
        "/api/jobs/invalid_mode",
        files={"content_pdf": ("test.pdf", b"pdf_content", "application/pdf")},
    )
    assert response.status_code == 404


def test_get_job_status():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_job = MagicMock()
        mock_job.job_id = "test-job"
        mock_job.tts_mode = "bodhan"
        mock_job.status = "completed"
        mock_job.created_at = "2026-09-09T12:00:00Z"
        mock_job.completed_at = "2026-09-09T12:05:00Z"
        mock_job.result = {"mp3_url": "/api/files/Audio/final_podcast.mp3"}
        mock_job.error = None
        mock_queue.return_value = [mock_job]
        response = client.get("/api/jobs/test-job")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job"
    assert data["status"] == "completed"


def test_get_job_not_found():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_queue.return_value = []
        response = client.get("/api/jobs/nonexistent")
    assert response.status_code == 404


def test_sse_events_stream():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_job = MagicMock()
        mock_job.job_id = "test-job"
        mock_job._sse_listeners = []
        mock_queue.return_value = [mock_job]
        response = client.get("/api/jobs/test-job/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_revision_on_job():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_job = MagicMock()
        mock_job.job_id = "test-job"
        mock_job.tts_mode = "bodhan"
        mock_job.status = "completed"
        mock_queue.return_value = [mock_job]
        with patch("src.api.routes.revise.revise_script"):
            response = client.post(
                "/api/jobs/test-job/revise",
                json={"feedback": "Speak more slowly"},
            )
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "test-job"
    assert data["status"] == "completed"


def test_revision_on_nonexistent_job():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_queue.return_value = []
        response = client.post("/api/jobs/nonexistent/revise", json={"feedback": "test"})
    assert response.status_code == 404


def test_revision_on_failed_job():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_job = MagicMock()
        mock_job.job_id = "failed-job"
        mock_job.tts_mode = "bodhan"
        mock_job.status = "failed"
        mock_queue.return_value = [mock_job]
        response = client.post("/api/jobs/failed-job/revise", json={"feedback": "test"})
    assert response.status_code == 400


def test_finish_job():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue, \
         patch("src.api.model_manager.get_model_manager") as mock_mm:
        mock_job = MagicMock()
        mock_job.job_id = "test-job"
        mock_job.tts_mode = "bodhan"
        mock_queue.return_value = [mock_job]
        mock_mm_instance = MagicMock()
        mock_mm_instance.unload_all.return_value = None
        mock_mm.return_value = mock_mm_instance
        response = client.post("/api/jobs/test-job/finish")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleaned_up"
    assert data["model_unloaded"] is True


def test_finish_nonexistent_job():
    client = TestClient(app)
    with patch("src.api.job_queue.get_job_queue") as mock_queue:
        mock_queue.return_value = []
        response = client.post("/api/jobs/nonexistent/finish")
    assert response.status_code == 404
