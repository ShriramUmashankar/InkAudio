import asyncio
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from src.config import load_settings
from src.api.model_manager import get_model_manager, ModelManager
from src.ingest import convert_pdf, convert_questions_pdf
from src.script_gen import revise_script, generate_script, _renumber
from src.stitch import stitch


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobRecord:
    job_id: str
    tts_mode: str
    content_pdf_path: str
    questions_pdf_path: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.QUEUED.value
    created_at: str = ""
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    _sse_listeners: List = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


job_queue: List[JobRecord] = []
_model_manager: Optional[ModelManager] = None
_worker_instance: Optional["JobWorker"] = None


def get_model_manager_instance() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = get_model_manager()
    return _model_manager


class JobWorker:
    def __init__(self):
        self.queue: List[JobRecord] = job_queue
        self.worker_task: Optional[asyncio.Task] = None
        self._start_worker()

    def _start_worker(self):
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.ensure_future(self._run_loop())

    async def _run_loop(self):
        while True:
            if not self.queue:
                await asyncio.sleep(0.1)
                continue
            job = self.queue.pop(0)
            job.status = JobStatus.RUNNING.value
            try:
                await self._process_job(job)
            except Exception as e:
                job.status = JobStatus.FAILED.value
                job.error = str(e)
            job.completed_at = datetime.now(timezone.utc).isoformat()

    async def _process_job(self, job: JobRecord):
        settings = load_settings()
        mm = get_model_manager_instance()
        from src.tts import synthesize_all, set_determinism
        from src.graph import build_graph, run_section
        from src.llm_client import LLMClient
        from pathlib import Path as _Path

        set_determinism(settings.tts.seed)

        await self._emit_sse(job, "stage_start", {"stage": "ingest", "progress": 0})

        md_path = convert_pdf(job.content_pdf_path, settings.pipeline.content_dir)
        if job.questions_pdf_path:
            convert_questions_pdf(job.questions_pdf_path, settings.pipeline.content_dir)
            questions_md_path = f"{settings.pipeline.content_dir}/questions.md"
        else:
            questions_md_path = None

        await self._emit_sse(job, "stage_complete", {"stage": "ingest", "progress": 10})
        await self._emit_sse(job, "stage_start", {"stage": "script_gen", "progress": 10})

        markdown = open(md_path, encoding="utf-8").read()
        questions_context = ""
        if questions_md_path and _Path(questions_md_path).exists():
            questions_context = _Path(questions_md_path).read_text(encoding="utf-8")

        actor_client = LLMClient(settings.actor.base_url, settings.actor.api_key, settings.actor.model)
        graph = build_graph(actor_client, settings.pipeline.max_loops)
        turns = run_section(graph, markdown, questions_context)
        turns, _ = _renumber(turns, 0)

        script_path = _Path(settings.pipeline.content_dir) / "script.json"
        script_path.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")

        await self._emit_sse(job, "stage_complete", {"stage": "script_gen", "progress": 40})
        await self._emit_sse(job, "stage_start", {"stage": "tts", "progress": 40})

        model = mm.get_model(job.tts_mode, settings)
        if job.tts_mode != "bodhan" and model is not None:
            await self._emit_sse(job, "model_loading", {"model": settings.tts.local_model_path})

        for turn in turns:
            set_determinism(settings.tts.seed)
            synthesize_all([turn], settings)
            await self._emit_sse(job, "turn_synthesized", {
                "turn_id": turn["turn_id"],
                "speaker": turn["speaker"],
                "progress": 50 + (turns.index(turn) / len(turns)) * 35,
            })

        await self._emit_sse(job, "stage_complete", {"stage": "tts", "progress": 85})
        await self._emit_sse(job, "stage_start", {"stage": "stitch", "progress": 85})

        stitch(settings)

        mp3_path = _Path(settings.pipeline.audio_dir) / "final_podcast.mp3"
        script_url = f"/api/files/Content/script.json"
        mp3_url = f"/api/files/Audio/final_podcast.mp3"
        turn_urls = []
        for turn in turns:
            wav_path = f"/api/files/Audio/{turn['turn_id']}_{turn['speaker']}.wav"
            turn_urls.append({"turn_id": turn["turn_id"], "speaker": turn["speaker"], "text": turn["text"], "wav_url": wav_path})

        job.result = {
            "mp3_url": mp3_url,
            "script_url": script_url,
            "turns": turn_urls,
        }
        job.status = JobStatus.COMPLETED.value
        await self._emit_sse(job, "complete", job.result)

    async def _emit_sse(self, job: JobRecord, event_type: str, data: Dict[str, Any]):
        payload = json.dumps({"event": event_type, "data": json.dumps(data)})
        for listener in job._sse_listeners:
            try:
                listener.put_nowait(payload)
            except Exception:
                pass
        job._sse_listeners = [l for l in job._sse_listeners if not l._queue.empty()]

    def add_job(self, tts_mode: str, content_pdf_path: str, questions_pdf_path: Optional[str] = None, config: Dict[str, Any] = None) -> str:
        if config is None:
            config = {}
        job_id = str(uuid.uuid4())
        job = JobRecord(
            job_id=job_id,
            tts_mode=tts_mode,
            content_pdf_path=content_pdf_path,
            questions_pdf_path=questions_pdf_path,
            config=config,
        )
        self.queue.append(job)
        return job_id


def get_job_queue() -> List[JobRecord]:
    return job_queue


def get_worker() -> JobWorker:
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = JobWorker()
    return _worker_instance