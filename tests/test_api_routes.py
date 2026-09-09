import json
from unittest.mock import patch
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
