import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.api.model_manager import ModelManager, get_model_manager
from src.config import load_settings
from src.evaluator import evaluate_questions
from src.graph import build_graph, build_revision_graph, run_revision, run_section
from src.ingest import convert_pdf, convert_questions_pdf
from src.llm_client import LLMClient
from src.script_gen import (
    _renumber, save_scripts, save_revision_scripts, load_script_pair, changed_turns,
    validate_bodhan_settings,
)
from src.stitch import stitch
from src.translation import validate_language_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = _REPO_ROOT / ".api_tmp"


class JobBusyError(Exception):
    pass


class _JobCancelled(Exception):
    pass


@dataclass
class JobRecord:
    tts_mode: str
    temp_dir: str
    content_pdf_path: str
    config: Dict[str, Any]
    questions_pdf_path: Optional[str] = None
    status: str = "running"
    created_at: str = ""
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    questions_report: Optional[Dict[str, Any]] = None
    cancel_requested: bool = False
    stage: str = "ingest"
    progress: float = 0
    _sse_listeners: List = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


_current_job: Optional[JobRecord] = None
_model_manager: Optional[ModelManager] = None


def get_model_manager_instance() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = get_model_manager()
    return _model_manager


def get_current_job() -> Optional[JobRecord]:
    return _current_job


def _merge_template_overrides(template: Dict, config: Dict) -> Dict:
    for host in ("host1", "host2"):
        overrides = (config or {}).get(host)
        if overrides:
            merged = dict(template.get(host) or {})
            merged.update(overrides)
            template[host] = merged
    return template


def create_job(tts_mode: str, config: Dict[str, Any]) -> JobRecord:
    global _current_job
    if _current_job is not None and _current_job.status == "running":
        raise JobBusyError("generation already in progress")
    if _current_job is not None:
        get_model_manager_instance().unload(_current_job.tts_mode)
        _cleanup_dir(_current_job.temp_dir)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    job = JobRecord(
        tts_mode=tts_mode,
        temp_dir=str(TEMP_ROOT),
        content_pdf_path=str(TEMP_ROOT / "content.pdf"),
        questions_pdf_path=str(TEMP_ROOT / "questions.pdf"),
        config=config,
    )
    _current_job = job
    return job


def abandon(job: JobRecord):
    global _current_job
    if _current_job is job:
        _current_job = None
    _cleanup_dir(job.temp_dir)


def finish_job(job: JobRecord):
    global _current_job
    if _current_job is not job:
        return
    _current_job = None
    get_model_manager_instance().unload(job.tts_mode)
    _cleanup_dir(job.temp_dir)


def _cleanup_dir(path: str):
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def cleanup_on_shutdown():
    global _current_job
    if _current_job is not None:
        _current_job.cancel_requested = True
        _current_job = None
    _cleanup_dir(str(TEMP_ROOT))


def run_job(job: JobRecord):
    asyncio.ensure_future(_run_job(job))


async def _run_job(job: JobRecord):
    try:
        await asyncio.to_thread(_process_job_sync, job)
        _check_cancel(job)
    except _JobCancelled:
        job.status = "terminated"
        job.error = "terminated by user"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        _emit_sse(job, "terminated", {"status": "terminated"})
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc).isoformat()
        _emit_sse(job, "failed", {"error": str(e)})
    else:
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        _emit_sse(job, "complete", job.result or {})
    # Keep terminal status available after refresh; release files only after
    # the worker has stopped, and only if it still owns the shared directory.
    if job.status in {"failed", "terminated"} and _current_job is job:
        get_model_manager_instance().unload(job.tts_mode)
        _cleanup_dir(job.temp_dir)


def _check_cancel(job: JobRecord):
    # ponytail: cooperative cancel; a mid-flight LLM/TTS call finishes before the flag lands
    if job.cancel_requested:
        raise _JobCancelled()


def _process_job_sync(job: JobRecord):
    from pathlib import Path as _Path
    from src.tts import _load_template, _synth_one, set_determinism

    settings = load_settings()
    settings.tts.mode = job.tts_mode
    settings.tts.podcast_language = validate_language_config(
        job.tts_mode, job.config, settings.tts.podcast_language,
    )
    validate_bodhan_settings(settings)
    settings.pipeline.content_dir = job.temp_dir
    settings.pipeline.audio_dir = job.temp_dir
    log_path = str(Path(job.temp_dir) / "llm_log.md")
    settings.pipeline.log_path = log_path
    set_determinism(settings.tts.seed)
    mm = get_model_manager_instance()

    _check_cancel(job)

    if job.config.get("revision"):
        _process_revision_sync(job, settings, mm)
        return

    _emit_sse(job, "stage_start", {"stage": "ingest", "progress": 0})
    md_path = convert_pdf(job.content_pdf_path, settings.pipeline.content_dir)
    questions_report = None
    questions_context = ""
    if job.questions_pdf_path and _Path(job.questions_pdf_path).exists():
        convert_questions_pdf(job.questions_pdf_path, settings.pipeline.content_dir)
        questions_md_path = _Path(settings.pipeline.content_dir) / "questions.md"
        if questions_md_path.exists():
            content_md = _Path(md_path).read_text(encoding="utf-8")
            questions_md = questions_md_path.read_text(encoding="utf-8")
            eval_client = LLMClient(
                settings.actor.base_url, settings.actor.api_key, settings.actor.model,
                log_path=log_path,
            )
            report = evaluate_questions(questions_md, content_md, eval_client)
            questions_report = report
            job.questions_report = report
            questions_context = "\n".join(q["question"] for q in report.get("answerable", []))

    _check_cancel(job)
    _emit_sse(job, "stage_complete", {"stage": "ingest", "progress": 10})
    _emit_sse(job, "stage_start", {"stage": "script_gen", "progress": 10})

    markdown = _Path(md_path).read_text(encoding="utf-8")
    actor_client = LLMClient(
        settings.actor.base_url, settings.actor.api_key, settings.actor.model,
        log_path=log_path,
    )
    graph = build_graph(actor_client, job.config.get("max_loops", settings.pipeline.max_loops),
                        english_only=job.tts_mode == "bodhan")
    turns = run_section(graph, markdown, questions_context)
    turns, _ = _renumber(turns, 0)

    _check_cancel(job)
    _emit_sse(job, "stage_complete", {"stage": "script_gen", "progress": 40})
    turns = _save_job_scripts(job, settings, turns)
    _emit_sse(job, "stage_start", {"stage": "tts", "progress": 50})

    if job.tts_mode != "bodhan":
        _emit_sse(job, "model_loading", {"model": settings.tts.local_model_path})
    template = _merge_template_overrides(_load_template(settings), job.config)
    model = mm.get_model(job.tts_mode, settings)

    for idx, turn in enumerate(turns):
        _check_cancel(job)
        set_determinism(settings.tts.seed)
        _synth_one(model, turn, settings, template, check_cancel=lambda: _check_cancel(job), raise_on_error=True)
        _emit_sse(job, "turn_synthesized", {
            "turn_id": turn["turn_id"],
            "speaker": turn["speaker"],
            "progress": 50 + (idx / len(turns)) * 35,
        })

    _check_cancel(job)
    _emit_sse(job, "stage_complete", {"stage": "tts", "progress": 85})
    _emit_sse(job, "stage_start", {"stage": "stitch", "progress": 85})

    if not stitch(settings, turns):
        raise RuntimeError("Podcast audio could not be stitched")
    _check_cancel(job)
    _emit_sse(job, "stage_complete", {"stage": "stitch", "progress": 100})

    job.result = _result_payload(job, turns)


def _process_revision_sync(job: JobRecord, settings, mm):
    from src.tts import _load_template, _synth_one, set_determinism

    _emit_sse(job, "stage_start", {"stage": "revision", "progress": 30})
    turns, spoken = load_script_pair(settings)

    client = LLMClient(
        settings.actor.base_url, settings.actor.api_key, settings.actor.model,
        log_path=str(Path(settings.pipeline.content_dir) / "llm_log.md"),
    )
    graph = build_revision_graph(client, job.config.get("max_loops", settings.pipeline.max_loops),
                                 english_only=job.tts_mode == "bodhan")
    edits = run_revision(graph, turns, job.config.get("feedback", ""))

    updated = spoken
    if edits:
        _check_cancel(job)
        updated = _save_job_scripts(job, settings, turns, previous_spoken=spoken, edits=edits)
        changed = changed_turns(spoken, updated)

        if changed:
            template = _merge_template_overrides(_load_template(settings), job.config)
            model = mm.get_model(job.tts_mode, settings)
            _emit_sse(job, "stage_start", {"stage": "tts", "progress": 50})
            for edit in changed:
                _check_cancel(job)
                set_determinism(settings.tts.seed)
                _synth_one(model, edit, settings, template, check_cancel=lambda: _check_cancel(job), raise_on_error=True)
            _check_cancel(job)
            _emit_sse(job, "stage_start", {"stage": "stitch", "progress": 85})
            if not stitch(settings, updated):
                raise RuntimeError("Revised podcast audio could not be stitched")

    _check_cancel(job)

    _emit_sse(job, "revision_complete", {"progress": 90})
    job.result = _result_payload(job, updated)


def _save_job_scripts(job, settings, english, previous_spoken=None, edits=None):
    translating = job.tts_mode == "bodhan" and settings.tts.podcast_language != "en"
    if translating:
        _emit_sse(job, "stage_start", {"stage": "translation", "progress": 40})
    callbacks = dict(
        check_cancel=lambda: _check_cancel(job),
        on_progress=lambda completed, total: _emit_sse(job, "translation_progress", {
            "completed_turns": completed, "total_turns": total,
            "progress": 40 + completed / total * 10,
        }),
    )
    if previous_spoken is None:
        spoken = save_scripts(english, settings, **callbacks)
    else:
        spoken = save_revision_scripts(english, previous_spoken, edits, settings, **callbacks)
    if translating:
        _emit_sse(job, "stage_complete", {"stage": "translation", "progress": 50})
    return spoken


def _result_payload(job: JobRecord, turns: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "tts_mode": job.tts_mode,
        "podcast_language": job.config.get("podcast_language", "en"),
        "mp3_url": "/api/job/result",
        "script_url": "/api/job/script",
        "questions": job.questions_report,
        "turns": [
            {"turn_id": t["turn_id"], "speaker": t["speaker"], "text": t["text"]}
            for t in turns
        ],
    }


def _emit_sse(job: JobRecord, event_type: str, data: Dict[str, Any]):
    if "stage" in data:
        job.stage = data["stage"]
    if "progress" in data:
        job.progress = data["progress"]
    payload = json.dumps({"event": event_type, "data": json.dumps(data)})
    for listener, loop in list(job._sse_listeners):
        try:
            loop.call_soon_threadsafe(listener.put_nowait, payload)
        except Exception:
            pass
