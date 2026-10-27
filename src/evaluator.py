"""Classify questions by whether the supplied source content can answer them."""

from typing import Dict, List

from .graph import EVALUATOR_SYSTEM_PROMPT
from .llm_client import LLMClient, extract_json


def evaluate_questions(
    questions_md: str,
    content_md: str,
    client: LLMClient,
) -> Dict[str, List[Dict]]:
    """Ask the LLM to classify questions against the content and return both categories.

    Treat statuses other than answerable as unanswerable flags; invalid top-level
    responses produce empty categories and non-object entries are ignored.
    """
    user = (
        f"QUESTIONS:\n<<<\n{questions_md}\n>>>\n\n"
        f"CONTENT:\n<<<\n{content_md}\n>>>\n\n"
        "Classify each question based on whether the content can answer it."
    )
    raw = client.chat(EVALUATOR_SYSTEM_PROMPT, user, node_label="evaluator")
    parsed = extract_json(raw)
    if not isinstance(parsed, list):
        return {"answerable": [], "unanswerable": []}

    answerable: List[Dict] = []
    unanswerable: List[Dict] = []

    for item in parsed:
        if not isinstance(item, dict):
            continue
        status = item.get("status", "")
        entry = {
            "question_number": item.get("question_number"),
            "question": item.get("question", ""),
        }
        if status == "answerable":
            answerable.append(entry)
        else:
            entry["flag"] = status
            unanswerable.append(entry)

    return {"answerable": answerable, "unanswerable": unanswerable}