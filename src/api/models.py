from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class BodhanHostConfig(BaseModel):
    voice: str = "Parth"
    lang: str = "en"
    style: str = ""

    def __getitem__(self, key):
        return getattr(self, key)


class BodhanConfig(BaseModel):
    host1: BodhanHostConfig = BodhanHostConfig()
    host2: BodhanHostConfig = BodhanHostConfig()


class CustomVoiceHostConfig(BaseModel):
    speaker: str = "ryan"
    instruct: str = ""

    def __getitem__(self, key):
        return getattr(self, key)


class CustomVoiceConfig(BaseModel):
    host1: CustomVoiceHostConfig = CustomVoiceHostConfig()
    host2: CustomVoiceHostConfig = CustomVoiceHostConfig()


class VoiceDesignHostConfig(BaseModel):
    instruct: str = ""

    def __getitem__(self, key):
        return getattr(self, key)


class VoiceDesignConfig(BaseModel):
    host1: VoiceDesignHostConfig = VoiceDesignHostConfig()
    host2: VoiceDesignHostConfig = VoiceDesignHostConfig()


class PipelineConfig(BaseModel):
    max_loops: int = Field(default=3, ge=1, le=10)


class GenerateRequest(BaseModel):
    content_pdf: str = Field(..., min_length=1)
    questions_pdf: Optional[str] = None
    config: Optional[PipelineConfig] = None


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    tts_mode: str


class SSEEvent(BaseModel):
    event: str
    data: str


class JobResult(BaseModel):
    mp3_url: str
    script_url: Optional[str] = None
    turns: List[Dict[str, Any]] = []

    def __getitem__(self, key):
        return getattr(self, key)


class JobInfo(BaseModel):
    job_id: str
    tts_mode: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None


class RevisionRequest(BaseModel):
    feedback: str = Field(..., min_length=1)


class FinishRequest(BaseModel):
    pass


class FinishResponse(BaseModel):
    status: str
    model_unloaded: bool


class TranscriptResponse(BaseModel):
    transcript: str
