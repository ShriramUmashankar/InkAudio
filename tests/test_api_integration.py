from fastapi.testclient import TestClient
from src.api.main import app
from src.api.job_queue import job_queue, JobRecord
from unittest.mock import patch, MagicMock
import json


def test_full_generation_flow():
    """Test that a job can be submitted, status checked, and finished."""
    client = TestClient(app)

    with patch("src.api.job_queue.get_worker") as mock_worker, \
         patch("src.api.model_manager.get_model_manager") as mock_mm:
        mock_worker_instance = MagicMock()

        def fake_add_job(tts_mode, content_pdf_path, questions_pdf_path=None, config=None):
            job = JobRecord(
                job_id="integration-test-id",
                tts_mode=tts_mode,
                content_pdf_path=content_pdf_path,
                questions_pdf_path=questions_pdf_path,
                config=config or {},
            )
            job_queue.append(job)
            return job.job_id

        mock_worker_instance.add_job.side_effect = fake_add_job
        mock_worker.return_value = mock_worker_instance

        # Submit job
        response = client.post(
            "/api/jobs/bodhan",
            files={"content_pdf": ("test.pdf", b"%PDF", "application/pdf")},
            data={"config": json.dumps({"bodhan": {"host1": {"voice": "Parth"}}, "pipeline": {"max_loops": 3}})},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert job_id == "integration-test-id"

        # Check status
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["tts_mode"] == "bodhan"

        # Finish
        response = client.post(f"/api/jobs/{job_id}/finish")
        assert response.status_code == 200
        assert response.json()["status"] == "cleaned_up"

        job_queue.clear()

    import os
    for path in ("Content/test.pdf",):
        if os.path.exists(path):
            os.remove(path)