import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import job_queue
from src.api.job_queue import JobBusyError, JobRecord
from src.api.main import app


def _job(tmp_path, status="running", **kw):
    return JobRecord(
        tts_mode=kw.get("tts_mode", "bodhan"),
        temp_dir=str(tmp_path),
        content_pdf_path=str(tmp_path / "content.pdf"),
        questions_pdf_path=str(tmp_path / "questions.pdf"),
        config={},
        status=status,
    )


def test_generate_starts_job(tmp_path, monkeypatch):
    fake = _job(tmp_path)
    monkeypatch.setattr(job_queue, "create_job", lambda mode, cfg: fake)
    started = {}
    monkeypatch.setattr(job_queue, "run_job", lambda job: started.update(job=job))
    client = TestClient(app)
    r = client.post("/api/job/bodhan", files={"content_pdf": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 202
    assert r.json() == {"status": "running", "tts_mode": "bodhan"}
    assert started["job"] is fake
    assert (tmp_path / "content.pdf").read_bytes() == b"%PDF"


def test_generate_409_when_busy(tmp_path, monkeypatch):
    def busy(mode, cfg):
        raise JobBusyError("generation already in progress")
    monkeypatch.setattr(job_queue, "create_job", busy)
    client = TestClient(app)
    r = client.post("/api/job/bodhan", files={"content_pdf": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 409


def test_generate_unknown_mode():
    client = TestClient(app)
    r = client.post("/api/job/nonsense", files={"content_pdf": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 404


def test_generate_invalid_config():
    client = TestClient(app)
    r = client.post(
        "/api/job/bodhan",
        files={"content_pdf": ("a.pdf", b"%PDF", "application/pdf")},
        data={"config": "{not json"},
    )
    assert r.status_code == 400


def test_status_idle():
    client = TestClient(app)
    r = client.get("/api/job")
    assert r.status_code == 200
    assert r.json() == {"status": "idle"}


def test_status_running(tmp_path):
    job_queue._current_job = _job(tmp_path, status="running")
    client = TestClient(app)
    r = client.get("/api/job")
    assert r.json()["status"] == "running"
    assert r.json()["tts_mode"] == "bodhan"
    job_queue._current_job = None


def test_result_not_ready(tmp_path):
    job_queue._current_job = _job(tmp_path, status="completed")
    client = TestClient(app)
    r = client.get("/api/job/result")
    assert r.status_code == 404
    job_queue._current_job = None


def test_result_serves_mp3(tmp_path):
    job = _job(tmp_path, status="completed")
    mp3 = tmp_path / "final_podcast.mp3"
    mp3.write_bytes(b"ID3fake")
    job_queue._current_job = job
    client = TestClient(app)
    r = client.get("/api/job/result")
    assert r.status_code == 200
    assert r.content == b"ID3fake"
    job_queue._current_job = None


def test_script_serves_json(tmp_path):
    job = _job(tmp_path, status="completed")
    (tmp_path / "script.json").write_text('{"turns": []}', encoding="utf-8")
    job_queue._current_job = job
    client = TestClient(app)
    r = client.get("/api/job/script")
    assert r.status_code == 200
    assert r.json() == {"turns": []}
    job_queue._current_job = None


def test_questions_404_without_report(tmp_path):
    job_queue._current_job = _job(tmp_path, status="completed")
    client = TestClient(app)
    r = client.get("/api/job/questions")
    assert r.status_code == 404
    job_queue._current_job = None


def test_questions_serves_report(tmp_path):
    job = _job(tmp_path, status="completed")
    job.questions_report = {"answerable": [{"question_number": 1, "question": "A?"}], "unanswerable": []}
    job_queue._current_job = job
    client = TestClient(app)
    r = client.get("/api/job/questions")
    assert r.status_code == 200
    assert r.json()["answerable"][0]["question"] == "A?"
    job_queue._current_job = None


def test_finish_refuses_while_running(tmp_path):
    job_queue._current_job = _job(tmp_path, status="running")
    client = TestClient(app)
    r = client.post("/api/job/finish")
    assert r.status_code == 400
    job_queue._current_job = None


def test_finish_cleans_completed(tmp_path):
    job_queue._current_job = _job(tmp_path, status="completed")
    with patch("src.api.job_queue.get_model_manager_instance") as mm, \
         patch("src.api.job_queue.shutil.rmtree"):
        client = TestClient(app)
        r = client.post("/api/job/finish")
    assert r.status_code == 200
    assert r.json() == {"status": "cleaned_up"}
    assert job_queue.get_current_job() is None


def test_terminate_sets_cancel_flag(tmp_path):
    job = _job(tmp_path, status="running")
    job_queue._current_job = job
    client = TestClient(app)
    r = client.post("/api/job/terminate")
    assert r.status_code == 200
    assert job.cancel_requested is True
    assert r.json()["status"] == "terminating"
    job_queue._current_job = None


def test_terminate_refuses_when_idle():
    client = TestClient(app)
    r = client.post("/api/job/terminate")
    assert r.status_code == 400


def test_revise_refuses_unless_completed(tmp_path):
    job_queue._current_job = _job(tmp_path, status="running")
    client = TestClient(app)
    r = client.post("/api/job/revise", json={"feedback": "faster"})
    assert r.status_code == 400
    job_queue._current_job = None


def test_revise_restarts_completed_job(tmp_path, monkeypatch):
    job = _job(tmp_path, status="completed")
    job_queue._current_job = job
    started = {}
    monkeypatch.setattr(job_queue, "run_job", lambda j: started.update(job=j))
    client = TestClient(app)
    r = client.post("/api/job/revise", json={"feedback": "faster please"})
    assert r.status_code == 202
    assert started["job"] is job
    assert job.config["revision"] is True
    assert job.config["feedback"] == "faster please"
    assert job.status == "running"
    job_queue._current_job = None