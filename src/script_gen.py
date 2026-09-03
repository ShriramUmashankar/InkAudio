import json
from pathlib import Path
from typing import Dict, List

from .config import Settings
from .graph import (
    build_graph,
    build_revision_graph,
    run_revision,
    run_section,
)
from .evaluator import evaluate_questions
from .ingest import convert_questions_pdf, md_path_for
from .llm_client import LLMClient
from .tts import synthesize_all, synthesize_turns
from .stitch import stitch


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

    graph = build_graph(actor_client, settings.pipeline.max_loops)
    turns = run_section(graph, markdown, questions_context)
    turns, counter = _renumber(turns, 0)

    out_path = Path(settings.pipeline.content_dir) / "script.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[script] wrote {len(turns)} turns -> {out_path}")

    if not no_tts:
        synthesize_all(turns, settings)
        if do_stitch:
            stitch(settings)
    return turns


def merge_edits(turns: List[Dict[str, str]], edits: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_id = {t["turn_id"]: dict(t) for t in turns}
    for e in edits:
        if e["turn_id"] in by_id:
            by_id[e["turn_id"]]["text"] = e["text"]
    return list(by_id.values())


def revise_script(settings: Settings, feedback_text: str) -> List[Dict[str, str]]:
    script_path = Path(settings.pipeline.content_dir) / "script.json"
    if not script_path.exists():
        raise RuntimeError(f"{script_path} not found; run generation first.")
    turns = json.loads(script_path.read_text(encoding="utf-8"))

    client = LLMClient(
        settings.actor.base_url, settings.actor.api_key, settings.actor.model,
        log_path=settings.pipeline.log_path,
    )
    graph = build_revision_graph(client, settings.pipeline.max_loops)

    edits = run_revision(graph, turns, feedback_text)
    if not edits:
        print("[revise] no turns changed")
        return turns

    updated = merge_edits(turns, edits)
    script_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[revise] applied {len(edits)} turn edit(s) -> {script_path}")

    synthesize_turns(edits, settings)
    stitch(settings)
    return updated


def regenerate_audio(settings: Settings, do_stitch: bool = True) -> List[Dict[str, str]]:
    script_path = Path(settings.pipeline.content_dir) / "script.json"
    if not script_path.exists():
        raise RuntimeError(f"{script_path} not found; run generation or --revise first.")
    turns = json.loads(script_path.read_text(encoding="utf-8"))
    print(f"[script] regenerating audio for {len(turns)} existing turns")
    synthesize_all(turns, settings)
    if do_stitch:
        stitch(settings)
    return turns