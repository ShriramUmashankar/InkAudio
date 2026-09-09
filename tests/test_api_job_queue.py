import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from src.api.job_queue import JobRecord, JobWorker, job_queue, get_worker


def test_job_record_creation():
    record = JobRecord(
        job_id="test-123",
        tts_mode="bodhan",
        content_pdf_path="/tmp/test.pdf",
        config={"max_loops": 3},
    )
    assert record.job_id == "test-123"
    assert record.tts_mode == "bodhan"
    assert record.status == "queued"
    assert record.result is None
    assert record.error is None


def test_job_record_status_transitions():
    record = JobRecord(job_id="1", tts_mode="custom_voice", content_pdf_path="/tmp/a.pdf")
    assert record.status == "queued"
    record.status = "running"
    assert record.status == "running"
    record.status = "completed"
    assert record.status == "completed"


def test_job_queue_is_list():
    assert isinstance(job_queue, list)


def test_worker_singleton():
    w1 = get_worker()
    w2 = get_worker()
    assert w1 is w2


def test_worker_has_queue():
    worker = get_worker()
    assert hasattr(worker, "queue")
    assert hasattr(worker, "worker_task")


@patch("src.api.job_queue.ModelManager")
@patch("src.api.job_queue.load_settings")
def test_worker_add_job(mock_settings, mock_model_mgr):
    mock_settings.return_value = MagicMock()
    worker = get_worker()
    job_id = worker.add_job(tts_mode="bodhan", content_pdf_path="/tmp/test.pdf", questions_pdf_path=None, config={})
    assert job_id is not None
    assert len(job_queue) == 1


@patch("src.api.job_queue.ModelManager")
@patch("src.api.job_queue.load_settings")
def test_worker_process_bodhan_job(mock_settings, mock_model_mgr):
    mock_settings.return_value = MagicMock()
    mock_model_mgr.get_model.return_value = None
    with patch("src.api.job_queue.convert_pdf") as mock_convert, \
         patch("src.api.job_queue.generate_script") as mock_gen, \
         patch("src.api.job_queue.stitch") as mock_stitch:
        mock_convert.return_value = "/tmp/test.md"
        mock_gen.return_value = [{"turn_id": "0001", "speaker": "Host 1", "text": "hello"}]
        worker = get_worker()
        worker.add_job(tts_mode="bodhan", content_pdf_path="/tmp/test.pdf", config={})
        import asyncio
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
        assert len(job_queue) == 0