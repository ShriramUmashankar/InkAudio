import pytest
from src.api.models import (
    BodhanConfig, CustomVoiceConfig, VoiceDesignConfig,
    PipelineConfig, GenerateRequest, GenerateResponse,
    JobResult, JobInfo,
    RevisionRequest, FinishRequest, TranscriptResponse,
    SSEEvent,
)

def test_bodhan_config_defaults():
    cfg = BodhanConfig(host1={"voice": "Parth"}, host2={"voice": "Suhani"})
    assert cfg.host1["voice"] == "Parth"
    assert cfg.host2["voice"] == "Suhani"

def test_custom_voice_config():
    cfg = CustomVoiceConfig(host1={"speaker": "ryan", "instruct": "test"}, host2={"speaker": "dylan"})
    assert cfg.host1["speaker"] == "ryan"

def test_voice_design_config():
    cfg = VoiceDesignConfig(host1={"instruct": "A young male"}, host2={"instruct": "A young female"})
    assert cfg.host1["instruct"] == "A young male"

def test_pipeline_config_no_silence_ms():
    cfg = PipelineConfig(max_loops=3)
    assert cfg.max_loops == 3
    assert not hasattr(cfg, "silence_ms")

def test_generate_request_accepts_optional_fields():
    req = GenerateRequest(content_pdf="test.pdf", config=PipelineConfig(max_loops=5))
    assert req.content_pdf == "test.pdf"
    assert req.config.max_loops == 5

def test_generate_request_requires_content_pdf():
    with pytest.raises(ValueError):
        GenerateRequest(content_pdf="")

def test_generate_response_has_job_id():
    resp = GenerateResponse(job_id="abc-123", status="queued", tts_mode="bodhan")
    assert resp.job_id == "abc-123"
    assert resp.status == "queued"

def test_job_info_result_structure():
    info = JobInfo(
        job_id="abc", tts_mode="bodhan", status="completed",
        created_at="2026-09-09T12:00:00Z", completed_at="2026-09-09T12:05:00Z",
        result={"mp3_url": "/api/files/Audio/final_podcast.mp3", "script_url": "/api/files/Content/script.json"},
        error=None,
    )
    assert info.result["mp3_url"] == "/api/files/Audio/final_podcast.mp3"

def test_revision_request():
    req = RevisionRequest(feedback="Speak more slowly")
    assert req.feedback == "Speak more slowly"

def test_finish_request():
    req = FinishRequest()
    assert req == FinishRequest()

def test_sse_event_model():
    from pydantic import BaseModel
    import json
    event = SSEEvent(event="stage_start", data=json.dumps({"stage": "ingest"}))
    assert event.event == "stage_start"

def test_stt_transcript_response():
    from src.api.models import TranscriptResponse
    resp = TranscriptResponse(transcript="hello world")
    assert resp.transcript == "hello world"
