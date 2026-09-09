import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.api.model_manager import ModelManager, get_model_manager
from src.config import load_settings
from src.graph import build_graph, build_revision_graph, run_revision, run_section
from src.ingest import convert_pdf, convert_questions_pdf
from src.llm_client import LLMClient
from src.script_gen import _renumber, generate_script, merge_edits
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
                await asyncio.to_thread(self._process_job_sync, job)
            except Exception as e:
                job.status = JobStatus.FAILED.value
                job.error = str(e)
            job.completed_at = datetime.now(timezone.utc).isoformat()

    def _process_job_sync(self, job: JobRecord):
        from pathlib import Path as _Path
        from src.tts import _load_template, _synth_one, set_determinism

        settings = load_settings()
        settings.tts.mode = job.tts_mode
        mm = get_model_manager_instance()

        set_determinism(settings.tts.seed)

        if job.config.get("revision"):
            self._process_revision_sync(job, settings, mm)
            return

        self._emit_sse(job, "stage_start", {"stage": "ingest", "progress": 0})

        md_path = convert_pdf(job.content_pdf_path, settings.pipeline.content_dir)
        if job.questions_pdf_path:
            convert_questions_pdf(job.questions_pdf_path, settings.pipeline.content_dir)
            questions_md_path = f"{settings.pipeline.content_dir}/questions.md"
        else:
            questions_md_path = None

        self._emit_sse(job, "stage_complete", {"stage": "ingest", "progress": 10})
        self._emit_sse(job, "stage_start", {"stage": "script_gen", "progress": 10})

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

        self._emit_sse(job, "stage_complete", {"stage": "script_gen", "progress": 40})
        self._emit_sse(job, "stage_start", {"stage": "tts", "progress": 40})

        audio_dir = _Path(settings.pipeline.audio_dir)
        audio_dir.mkdir(parents=True, exist_ok=True)
        for f in audio_dir.glob("*.wav"):
            f.unlink(missing_ok=True)

        template = _load_template(settings)
        model = mm.get_model(job.tts_mode, settings)
        if job.tts_mode != "bodhan" and model is not None:
            self._emit_sse(job, "model_loading", {"model": settings.tts.local_model_path})

        for idx, turn in enumerate(turns):
            set_determinism(settings.tts.seed)
            _synth_one(model, turn, settings, template)
            self._emit_sse(job, "turn_synthesized", {
                "turn_id": turn["turn_id"],
                "speaker": turn["speaker"],
                "progress": 50 + (idx / len(turns)) * 35,
            })

        self._emit_sse(job, "stage_complete", {"stage": "tts", "progress": 85})
        self._emit_sse(job, "stage_start", {"stage": "stitch", "progress": 85})

        stitch(settings)
        self._emit_sse(job, "stage_complete", {"stage": "stitch", "progress": 100})

        job.result = self._result_payload(turns)
        self._emit_sse(job, "complete", job.result)
        job.status = JobStatus.COMPLETED.value

    def _process_revision_sync(self, job: JobRecord, settings, mm):
        from pathlib import Path as _Path
        from src.tts import _load_template, _synth_one, set_determinism

        self._emit_sse(job, "stage_start", {"stage": "revision", "progress": 30})

        script_path = _Path(settings.pipeline.content_dir) / "script.json"
        if not script_path.exists():
            raise RuntimeError(f"{script_path} not found; run generation first.")
        turns = json.loads(script_path.read_text(encoding="utf-8"))

        client = LLMClient(
            settings.actor.base_url, settings.actor.api_key, settings.actor.model,
            log_path=settings.pipeline.log_path,
        )
        graph = build_revision_graph(client, settings.pipeline.max_loops)
        edits = run_revision(graph, turns, job.config.get("feedback", ""))

        updated = turns
        if edits:
            updated = merge_edits(turns, edits)
            script_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[revise] applied {len(edits)} turn edit(s) -> {script_path}")

            template = _load_template(settings)
            model = mm.get_model(job.tts_mode, settings)
            for edit in edits:
                set_determinism(settings.tts.seed)
                _synth_one(model, edit, settings, template)
            stitch(settings)

        self._emit_sse(job, "revision_complete", {"progress": 90})
        job.result = self._result_payload(updated)
        self._emit_sse(job, "complete", job.result)
        job.status = JobStatus.COMPLETED.value

    @staticmethod
    def _result_payload(turns):
        turn_urls = []
        for turn in turns:
            turn_urls.append({
                "turn_id": turn["turn_id"],
                "speaker": turn["speaker"],
                "text": turn["text"],
                "wav_url": f"/api/files/Audio/{turn['turn_id']}_{turn['speaker']}.wav",
            })
        return {
            "mp3_url": "/api/files/Audio/final_podcast.mp3",
            "script_url": "/api/files/Content/script.json",
            "turns": turn_urls,
        }

    def _emit_sse(self, job: JobRecord, event_type: str, data: Dict[str, Any]):
        payload = json.dumps({"event": event_type, "data": json.dumps(data)})
        for listener, loop in list(job._sse_listeners):
            try:
                loop.call_soon_threadsafe(listener.put_nowait, payload)
            except Exception:
                pass

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