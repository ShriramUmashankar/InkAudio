import json
import os
import tempfile

from src.config import PipelineConfig, Settings, STTConfig
from src.stitch import _turn_id, stitch
from pydub import AudioSegment


def _make_settings(audio_dir: str) -> Settings:
    return Settings(
        actor=None,
        critic=None,
        tts=None,
        stt=STTConfig(device="cpu", compute_type="int8", model="small.en"),
        pipeline=PipelineConfig(
            pdf_path="x.pdf",
            content_dir="Content",
            audio_dir=audio_dir,
            max_loops=3,
            silence_ms=500,
            heading_level=2,
            questions_pdf_path="Content/questions.pdf",
            log_path="",
        ),
    )


def _write_silent(path: str, ms: int = 100):
    AudioSegment.silent(duration=ms).export(path, format="wav")


def test_turn_id_sort_key():
    assert _turn_id("0003_Host 1.wav") == 3
    assert _turn_id("0010_Host 2.wav") == 10


def test_stitch_orders_and_adds_gaps():
    with tempfile.TemporaryDirectory() as d:
        # write out of order to prove sorting
        _write_silent(os.path.join(d, "0002_Host 2.wav"), 100)
        _write_silent(os.path.join(d, "0001_Host 1.wav"), 100)
        settings = _make_settings(d)
        out = stitch(settings)
        assert out and out.endswith("final_podcast.mp3")
        # 100 + gap(500) + 100 = 700ms total
        result = AudioSegment.from_file(out)
        assert abs(len(result) - 700) <= 30


def test_stitch_no_files_returns_none():
    with tempfile.TemporaryDirectory() as d:
        settings = _make_settings(d)
        assert stitch(settings) is None


def test_stitch_writes_timeline():
    with tempfile.TemporaryDirectory() as d:
        _write_silent(os.path.join(d, "0001_Host 1.wav"), 100)
        _write_silent(os.path.join(d, "0002_Host 2.wav"), 100)
        settings = _make_settings(d)
        stitch(settings)
        timeline = json.loads(open(os.path.join(d, "timeline.json")).read())
        assert timeline == [
            {"turn_id": 1, "speaker": "Host 1", "start_ms": 0, "end_ms": 100},
            {"turn_id": 2, "speaker": "Host 2", "start_ms": 600, "end_ms": 700},
        ]
