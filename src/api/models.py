"""Pydantic request and response schemas shared by revision and transcription routes."""

from pydantic import BaseModel, Field


class RevisionRequest(BaseModel):
    """Accept nonempty text feedback for revising the current completed podcast."""
    feedback: str = Field(..., min_length=1)


class TranscriptResponse(BaseModel):
    """Return recognized speech as a single transcript string."""
    transcript: str