import asyncio

import pytest
from unittest.mock import patch

from src.api import job_queue
from src.api.job_queue import JobBusyError, JobRecord


def test_job_record_defaults():
    job = JobRecord(tts_mode="bodhan", temp_dir="/tmp/x", content_pdf_path="/tmp/x/content.pdf", config={})
    assert job.status == "running"
    assert job.result is None
    assert job.error is None
    assert job.created_at


def test_create_job_and_finish():
    from src.api.job_queue import TEMP_ROOT
    job = job_queue.create_job("bodhan", {})
    assert job.temp_dir == str(TEMP_ROOT)
    assert job.content_pdf_path == str(TEMP_ROOT / "content.pdf")
    assert job_queue.get_current_job() is job
    with patch("src.api.job_queue.get_model_manager_instance") as mm, \
         patch("src.api.job_queue.shutil.rmtree") as rmtree:
        job_queue.finish_job(job)
    rmtree.assert_called_once_with(str(TEMP_ROOT), ignore_errors=True)
    mm.return_value.unload.assert_called_once_with("bodhan")
    assert job_queue.get_current_job() is None


def test_create_job_busy_raises():
    job = JobRecord(tts_mode="bodhan", temp_dir="/tmp", content_pdf_path="/tmp/x", config={}, status="running")
    job_queue._current_job = job
    with pytest.raises(JobBusyError):
        job_queue.create_job("bodhan", {})
    job_queue._current_job = None


def test_create_job_replaces_completed(tmp_path):
    from src.api.job_queue import TEMP_ROOT
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    old = JobRecord(tts_mode="custom_voice", temp_dir=str(old_dir), content_pdf_path=str(old_dir / "x.pdf"), config={}, status="completed")
    job_queue._current_job = old
    with patch("src.api.job_queue.get_model_manager_instance") as mm, \
         patch("src.api.job_queue.shutil.rmtree") as rmtree:
        job = job_queue.create_job("bodhan", {})
    assert job.temp_dir == str(TEMP_ROOT)
    rmtree.assert_called_once_with(str(old_dir), ignore_errors=True)
    mm.return_value.unload.assert_called_once_with("custom_voice")


def test_abandon_clears():
    job = job_queue.create_job("bodhan", {})
    with patch("src.api.job_queue.shutil.rmtree"):
        job_queue.abandon(job)
    assert job_queue.get_current_job() is None


def test_run_job_marks_failed_and_cleans(monkeypatch):
    def boom(job):
        raise RuntimeError("boom")
    monkeypatch.setattr(job_queue, "_process_job_sync", boom)
    job = job_queue.create_job("bodhan", {})
    with patch("src.api.job_queue.get_model_manager_instance") as mm, \
         patch("src.api.job_queue.shutil.rmtree"):
        asyncio.run(job_queue._run_job(job))
    assert job.status == "failed"
    assert job.error == "boom"
    assert job_queue.get_current_job() is None


def test_run_job_terminates_on_cancel(monkeypatch):
    def throw_cancel(job):
        raise job_queue._JobCancelled()
    monkeypatch.setattr(job_queue, "_process_job_sync", throw_cancel)
    job = job_queue.create_job("bodhan", {})
    with patch("src.api.job_queue.get_model_manager_instance") as mm, \
         patch("src.api.job_queue.shutil.rmtree"):
        asyncio.run(job_queue._run_job(job))
    assert job.status == "terminated"
    assert job_queue.get_current_job() is None


def test_merge_template_overrides_partial():
    from src.api.job_queue import _merge_template_overrides
    template = {"host1": {"speaker": "ryan", "instruct": "A"}, "host2": {"speaker": "dylan", "instruct": "B"}}
    merged = _merge_template_overrides(template, {"host1": {"speaker": "sarah"}, "max_loops": 5})
    assert merged["host1"] == {"speaker": "sarah", "instruct": "A"}
    assert merged["host2"] == {"speaker": "dylan", "instruct": "B"}


def test_merge_template_overrides_empty_config_unchanged():
    from src.api.job_queue import _merge_template_overrides
    template = {"host1": {"speaker": "ryan"}}
    merged = _merge_template_overrides(template, {})
    assert merged == template


def test_cleanup_on_shutdown():
    from src.api.job_queue import TEMP_ROOT
    job = job_queue.create_job("bodhan", {})
    with patch("src.api.job_queue.shutil.rmtree") as rmtree:
        job_queue.cleanup_on_shutdown()
    assert job.cancel_requested is True
    assert job_queue.get_current_job() is None
    rmtree.assert_called_once_with(str(TEMP_ROOT), ignore_errors=True)


def test_emit_sse_delivers_to_listener():
    job = JobRecord(tts_mode="bodhan", temp_dir="/tmp/x", content_pdf_path="/tmp/x/content.pdf", config={}, status="running")
    loop = asyncio.new_event_loop()
    listener = asyncio.Queue()
    job._sse_listeners.append((listener, loop))
    try:
        loop.run_until_complete(asyncio.sleep(0))
        job_queue._emit_sse(job, "stage_start", {"stage": "ingest"})
        payload = loop.run_until_complete(listener.get())
    finally:
        loop.close()
    assert "stage_start" in payload
    assert "ingest" in payload