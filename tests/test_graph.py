from src.config import PipelineConfig, Settings
from src.graph import ACTOR_SYSTEM_PROMPT, build_graph, run_section


class FakeClient:
    """Returns valid actor JSON; critic controlled by approved flag."""

    def __init__(self, approved: bool = True):
        self.approved = approved

    def chat(self, system_prompt: str, user_prompt: str, **kwargs):
        if system_prompt == ACTOR_SYSTEM_PROMPT:
            import json

            return json.dumps(
                [
                    {"speaker": "Host 1", "text": "uhh, so this is the topic"},
                    {"speaker": "Host 2", "text": "— wait, no, I think—"},
                ]
            )
        # critic
        import json

        return json.dumps(
            {"is_approved": self.approved, "feedback": "needs more fillers" if not self.approved else "good"}
        )


def _settings(max_loops: int = 3) -> Settings:
    return Settings(
        actor=None,
        critic=None,
        tts=None,
        pipeline=PipelineConfig(
            pdf_path="x.pdf", content_dir="Content", audio_dir="Audio",
            max_loops=max_loops, silence_ms=500, heading_level=2,
            questions_pdf_path="Content/questions.pdf", log_path="",
        ),
    )


def test_graph_approves_first_pass():
    g = build_graph(FakeClient(approved=True), max_loops=3)
    turns = run_section(g, "The mitochondria is the powerhouse.")
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Host 1"


def test_graph_caps_retries_when_rejected():
    g = build_graph(FakeClient(approved=False), max_loops=2)
    turns = run_section(g, "Photosynthesis converts light to sugar.")
    # still returns last draft even though never approved
    assert len(turns) == 2
