import json

from src.graph import REVISION_SYSTEM_PROMPT, build_revision_graph, run_revision
from src.script_gen import merge_edits


class FakeRevClient:
    def __init__(self, approved: bool = True):
        self.approved = approved

    def chat(self, system_prompt: str, user_prompt: str, **kwargs):
        if system_prompt == REVISION_SYSTEM_PROMPT:
            return json.dumps(
                [{"turn_id": "0001", "speaker": "Host 1", "text": "uhh, revised line with hmm"}]
            )
        return json.dumps(
            {"is_approved": self.approved, "feedback": "" if self.approved else "still off"}
        )


def _settings(max_loops: int = 3):
    from src.config import PipelineConfig, Settings

    return Settings(
        actor=None, critic=None, tts=None,
        pipeline=PipelineConfig(
            pdf_path="x.pdf", content_dir="Content", audio_dir="Audio",
            max_loops=max_loops, silence_ms=500, heading_level=2,
            questions_pdf_path="Content/questions.pdf", log_path="",
        ),
    )


def test_revision_returns_edits():
    g = build_revision_graph(FakeRevClient(approved=True), max_loops=3)
    edits = run_revision(
        g, [{"turn_id": "0001", "speaker": "Host 1", "text": "old"}], "make it casual"
    )
    assert len(edits) == 1
    assert edits[0]["turn_id"] == "0001"


def test_revision_caps_when_rejected():
    g = build_revision_graph(FakeRevClient(approved=False), max_loops=2)
    edits = run_revision(
        g, [{"turn_id": "0001", "speaker": "Host 1", "text": "old"}], "fix it"
    )
    assert len(edits) == 1


def test_merge_edits_replaces_and_preserves_order():
    turns = [
        {"turn_id": "0001", "speaker": "Host 1", "text": "a"},
        {"turn_id": "0002", "speaker": "Host 2", "text": "b"},
    ]
    edits = [{"turn_id": "0001", "speaker": "Host 1", "text": "A"}]
    out = merge_edits(turns, edits)
    assert [t["turn_id"] for t in out] == ["0001", "0002"]
    assert out[0]["text"] == "A"
    assert out[1]["text"] == "b"


def test_merge_edits_ignores_unknown_id():
    turns = [{"turn_id": "0001", "speaker": "Host 1", "text": "a"}]
    edits = [{"turn_id": "9999", "speaker": "Host 1", "text": "x"}]
    out = merge_edits(turns, edits)
    assert out[0]["text"] == "a"
