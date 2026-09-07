import json
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from .llm_client import LLMClient, extract_json, validate_turns


def _load_prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.txt").read_text(
        encoding="utf-8"
    ).strip()


ACTOR_SYSTEM_PROMPT = _load_prompt("actor")
CRITIC_SYSTEM_PROMPT = _load_prompt("critic")
REVISION_SYSTEM_PROMPT = _load_prompt("revision_editor")
REVISION_CRITIC_PROMPT = _load_prompt("revision_critic")
EVALUATOR_SYSTEM_PROMPT = _load_prompt("evaluator")


class GraphState(TypedDict):
    content_markdown: str
    questions_context: str
    draft: List[Dict[str, str]]
    loop_count: int
    feedback: str
    is_approved: bool


def _build_user_prompt(
    content_markdown: str, questions_context: str, feedback: str
) -> str:
    base = f"CONTENT:\n<<<\n{content_markdown}\n>>>\n\n"
    if questions_context.strip():
        base += f"\nANSWERABLE QUESTIONS:\n<<<\n{questions_context}\n>>>\n\n"
    base += "\nWrite the podcast script as a JSON array of turns."
    if feedback:
        base += f"\n\nPrevious draft was rejected. Fix this feedback:\n{feedback}"
    return base


def build_graph(client: LLMClient, max_loops: int):
    def actor(state: GraphState) -> Dict:
        user = _build_user_prompt(
            state["content_markdown"], state["questions_context"], state["feedback"]
        )
        raw = client.chat(ACTOR_SYSTEM_PROMPT, user, node_label="actor")
        parsed = extract_json(raw)
        turns = validate_turns(parsed)
        if not turns:
            return {
                **state,
                "draft": state["draft"],
                "loop_count": state["loop_count"] + 1,
                "feedback": "Return ONLY a valid JSON array of {speaker,text} objects.",
            }
        return {
            **state,
            "draft": turns,
            "loop_count": state["loop_count"] + 1,
            "feedback": "",
        }

    def critic(state: GraphState) -> Dict:
        user = f"CONTENT:\n<<<\n{state['content_markdown']}\n>>>\n\n"
        if state["questions_context"].strip():
            user += f"ANSWERABLE QUESTIONS:\n<<<\n{state['questions_context']}\n>>>\n\n"
        user += f"DRAFT:\n{json.dumps(state['draft'], ensure_ascii=False)}"
        raw = client.chat(CRITIC_SYSTEM_PROMPT, user, node_label="critic")
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            return {"is_approved": False, "feedback": "Critic returned invalid JSON; re-draft."}
        return {
            "is_approved": bool(parsed.get("is_approved")),
            "feedback": str(parsed.get("feedback", "")),
        }

    def router(state: GraphState) -> str:
        if state["is_approved"] or state["loop_count"] >= max_loops:
            return "end"
        return "actor"

    wf = StateGraph(GraphState)
    wf.add_node("actor", actor)
    wf.add_node("critic", critic)
    wf.add_edge("actor", "critic")
    wf.add_conditional_edges("critic", router, {"actor": "actor", "end": END})
    wf.set_entry_point("actor")
    return wf.compile()


def run_section(graph, content_markdown: str, questions_context: str = "") -> List[Dict[str, str]]:
    result = graph.invoke(
        {
            "content_markdown": content_markdown,
            "questions_context": questions_context,
            "draft": [],
            "loop_count": 0,
            "feedback": "",
            "is_approved": False,
        }
    )
    return result["draft"]


class RevisionState(TypedDict):
    script: List[Dict[str, str]]
    notes: str
    edits: List[Dict[str, str]]
    loop_count: int
    is_approved: bool
    critic_feedback: str


def _merge_for_critic(script: List[Dict[str, str]], edits: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_id = {t["turn_id"]: dict(t) for t in script}
    for e in edits:
        if e.get("turn_id") in by_id:
            by_id[e["turn_id"]]["text"] = e["text"]
    return list(by_id.values())


def _valid_edits(parsed: Any) -> List[Dict[str, str]]:
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        tid = item.get("turn_id")
        speaker = item.get("speaker")
        text = item.get("text")
        if not tid or speaker not in ("Host 1", "Host 2") or not isinstance(text, str) or not text.strip():
            continue
        out.append({"turn_id": str(tid), "speaker": speaker, "text": text.strip()})
    return out


def build_revision_graph(client: LLMClient, max_loops: int):
    def editor(state: RevisionState) -> Dict:
        user = (
            f"USER NOTES:\n<<<\n{state['notes']}\n>>>\n\n"
            f"FULL SCRIPT:\n{json.dumps(state['script'], ensure_ascii=False)}"
        )
        raw = client.chat(REVISION_SYSTEM_PROMPT, user, node_label="editor")
        edits = _valid_edits(extract_json(raw))
        return {"edits": edits, "loop_count": state["loop_count"] + 1}

    def critic(state: RevisionState) -> Dict:
        merged = _merge_for_critic(state["script"], state["edits"])
        user = (
            f"ORIGINAL SCRIPT:\n<<<\n{json.dumps(state['script'], ensure_ascii=False)}\n>>>\n\n"
            f"UPDATED SCRIPT:\n<<<\n{json.dumps(merged, ensure_ascii=False)}\n>>>\n\n"
            f"USER NOTES:\n<<<\n{state['notes']}\n>>>"
        )
        raw = client.chat(REVISION_CRITIC_PROMPT, user, node_label="revision_critic")
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            return {"is_approved": False, "critic_feedback": "Critic returned invalid JSON; revise again."}
        return {
            "is_approved": bool(parsed.get("is_approved")),
            "critic_feedback": str(parsed.get("feedback", "")),
        }

    def router(state: RevisionState) -> str:
        if state["is_approved"] or state["loop_count"] >= max_loops:
            return "end"
        return "editor"

    wf = StateGraph(RevisionState)
    wf.add_node("editor", editor)
    wf.add_node("critic", critic)
    wf.add_edge("editor", "critic")
    wf.add_conditional_edges("critic", router, {"editor": "editor", "end": END})
    wf.set_entry_point("editor")
    return wf.compile()


def run_revision(graph, turns: List[Dict[str, str]], notes: str) -> List[Dict[str, str]]:
    result = graph.invoke(
        {
            "script": turns,
            "notes": notes,
            "edits": [],
            "loop_count": 0,
            "is_approved": False,
            "critic_feedback": "",
        }
    )
    return result["edits"]


