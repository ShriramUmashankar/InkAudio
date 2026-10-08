import json
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .graph import (
    build_graph,
    build_revision_graph,
    merge_edits,
    run_revision,
    run_section,
)
from .evaluator import evaluate_questions
from .ingest import convert_questions_pdf, md_path_for
from .llm_client import LLMClient
from .tts import synthesize_all, synthesize_turns
from .stitch import stitch
from .translation import translate_turns, validate_language_config


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_scripts(english, settings, check_cancel=None, on_progress=None):
    """Translate completely before replacing either published script."""
    spoken = translate_turns(english, settings, check_cancel, on_progress)
    if check_cancel:
        check_cancel()
    _publish_scripts(english, spoken, settings)
    return spoken


def save_revision_scripts(original, spoken, edits, settings, check_cancel=None, on_progress=None):
    """Translate only changed source turns, preserving untouched spoken text."""
    english = merge_edits(original, edits)
    edited = changed_turns(original, english)
    if not edited:
        return spoken
    translated = translate_turns(edited, settings, check_cancel, on_progress)
    updated = merge_edits(spoken, translated)
    if check_cancel:
        check_cancel()
    _publish_scripts(english, updated, settings)
    print(f"[revise] {len(edited)} English turn(s) edited; "
          f"{len(changed_turns(spoken, updated))} spoken turn(s) to synthesize")
    return updated


def _publish_scripts(english, spoken, settings):
    base = Path(settings.pipeline.content_dir)
    if settings.tts.mode == "bodhan":
        _write_json(base / "script_english.json", english)
        _write_json(base / "script_metadata.json", {
            "tts_mode": "bodhan", "podcast_language": settings.tts.podcast_language,
        })
    _write_json(base / "script.json", spoken)
    if settings.tts.mode != "bodhan":
        # A new Qwen script supersedes the previous Bodhan generation.
        (base / "script_english.json").unlink(missing_ok=True)
        (base / "script_metadata.json").unlink(missing_ok=True)


def load_script_pair(settings):
    base = Path(settings.pipeline.content_dir)
    script = base / "script.json"
    if not script.exists():
        raise RuntimeError(f"{script} not found; run generation first.")
    spoken = json.loads(script.read_text(encoding="utf-8"))
    metadata = base / "script_metadata.json"
    if metadata.exists():
        language = json.loads(metadata.read_text(encoding="utf-8"))["podcast_language"]
        if settings.tts.mode != "bodhan" and language != "en":
            raise ValueError("An Indic Bodhan script requires Bodhan; generate a new Qwen script")
        if settings.tts.mode == "bodhan" and language != settings.tts.podcast_language:
            raise ValueError("Podcast language cannot change during revision/audio regeneration; generate a new script")
    if settings.tts.mode != "bodhan":
        return spoken, spoken
    english_path = base / "script_english.json"
    if not english_path.exists():
        if settings.tts.podcast_language != "en":
            raise ValueError("English source script missing; generate a new multilingual podcast")
        return spoken, spoken
    english = json.loads(english_path.read_text(encoding="utf-8"))
    if [(t["turn_id"], t["speaker"]) for t in english] != [(t["turn_id"], t["speaker"]) for t in spoken]:
        raise ValueError("English and spoken scripts are not aligned; generate a new podcast")
    return english, spoken


def changed_turns(previous, updated):
    before = {t["turn_id"]: t["text"] for t in previous}
    return [t for t in updated if before.get(t["turn_id"]) != t["text"]]


def validate_bodhan_settings(settings, require_tts=True, require_translation=True):
    validate_language_config(settings.tts.mode, {}, settings.tts.podcast_language)
    if settings.tts.mode == "bodhan":
        if require_translation and settings.tts.podcast_language != "en" and not settings.tts.bodhan_translation_api_key:
            raise RuntimeError("Bodhan translation credential is missing; configure BODHAN_TRANSLATION")
        if require_tts and not settings.tts.bodhan_api_key:
            raise RuntimeError("Bodhan TTS credential is missing; configure BODHAN_TTS")


def _renumber(turns: List[Dict[str, str]], counter: int) -> (List[Dict[str, str]], int):
    out = []
    for t in turns:
        counter += 1
        out.append({"turn_id": f"{counter:04d}", "speaker": t["speaker"], "text": t["text"]})
    return out, counter


def _write_questions_files(
    result: Dict, content_dir: str
) -> str:
    base = Path(content_dir)
    answerable = result.get("answerable", [])
    unanswerable = result.get("unanswerable", [])

    if answerable:
        lines = []
        for q in answerable:
            lines.append(f"Q{q['question_number']}: {q['question']}")
        (base / "questions_to_answer.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    if unanswerable:
        lines = []
        for q in unanswerable:
            flag = q.get("flag", "content not there")
            lines.append(f"Q{q['question_number']}: {q['question']}  [{flag}]")
        (base / "questions_unanswerable.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    return "\n".join(
        f"{q['question']}" for q in answerable
    )


def generate_script(
    markdown: str,
    settings: Settings,
    do_stitch: bool = True,
    actor_client: LLMClient = None,
    no_tts: bool = False,
) -> List[Dict[str, str]]:
    validate_bodhan_settings(settings, require_tts=not no_tts)
    log_path = settings.pipeline.log_path
    if actor_client is None:
        actor_client = LLMClient(
            settings.actor.base_url, settings.actor.api_key, settings.actor.model,
            log_path=log_path,
        )

    questions_pdf = Path(settings.pipeline.questions_pdf_path)
    if questions_pdf.exists():
        convert_questions_pdf(str(questions_pdf), settings.pipeline.content_dir)

    questions_context = ""
    questions_md_path = Path(settings.pipeline.content_dir) / "questions.md"
    if questions_md_path.exists():
        content_md_path = Path(settings.pipeline.content_dir) / f"{Path(settings.pipeline.pdf_path).stem}.md"
        content_md = content_md_path.read_text(encoding="utf-8")
        questions_md = questions_md_path.read_text(encoding="utf-8")

        eval_client = LLMClient(
            settings.actor.base_url, settings.actor.api_key, settings.actor.model,
            log_path=log_path,
        )
        result = evaluate_questions(questions_md, content_md, eval_client)
        questions_context = _write_questions_files(result, settings.pipeline.content_dir)

    graph = build_graph(actor_client, settings.pipeline.max_loops, english_only=settings.tts.mode == "bodhan")
    turns = run_section(graph, markdown, questions_context)
    turns, counter = _renumber(turns, 0)

    turns = save_scripts(turns, settings)
    out_path = Path(settings.pipeline.content_dir) / "script.json"
    print(f"[script] wrote {len(turns)} turns -> {out_path}")

    if not no_tts:
        synthesize_all(turns, settings)
        if do_stitch:
            stitch(settings, turns if settings.tts.mode == "bodhan" else None)
    return turns


def revise_script(settings: Settings, feedback_text: str) -> List[Dict[str, str]]:
    validate_bodhan_settings(settings)
    turns, spoken = load_script_pair(settings)

    client = LLMClient(
        settings.actor.base_url, settings.actor.api_key, settings.actor.model,
        log_path=settings.pipeline.log_path,
    )
    graph = build_revision_graph(client, settings.pipeline.max_loops, english_only=settings.tts.mode == "bodhan")

    edits = run_revision(graph, turns, feedback_text)
    if not edits:
        print("[revise] no turns changed")
        return spoken

    updated = save_revision_scripts(turns, spoken, edits, settings)
    changed = changed_turns(spoken, updated)
    if changed:
        synthesize_turns(changed, settings)
        if not stitch(settings, updated if settings.tts.mode == "bodhan" else None):
            raise RuntimeError("Revised podcast audio could not be stitched")
    return updated


def regenerate_audio(settings: Settings, do_stitch: bool = True) -> List[Dict[str, str]]:
    validate_bodhan_settings(settings, require_translation=False)
    _, turns = load_script_pair(settings)
    print(f"[script] regenerating audio for {len(turns)} existing turns")
    synthesize_all(turns, settings)
    if do_stitch:
        stitch(settings, turns if settings.tts.mode == "bodhan" else None)
    return turns
