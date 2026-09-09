from pydantic import BaseModel, Field


class RevisionRequest(BaseModel):
    feedback: str = Field(..., min_length=1)


class TranscriptResponse(BaseModel):
    transcript: str