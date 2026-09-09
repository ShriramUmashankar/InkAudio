import pytest
from src.api.models import RevisionRequest, TranscriptResponse


def test_revision_request():
    req = RevisionRequest(feedback="Speak more slowly")
    assert req.feedback == "Speak more slowly"


def test_revision_request_requires_feedback():
    with pytest.raises(Exception):
        RevisionRequest(feedback="")


def test_stt_transcript_response():
    resp = TranscriptResponse(transcript="hello world")
    assert resp.transcript == "hello world"