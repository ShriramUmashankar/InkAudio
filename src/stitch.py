import json
import re
from glob import glob
from pathlib import Path

from pydub import AudioSegment

from .config import Settings


def _turn_id(path: str) -> int:
    name = Path(path).stem
    m = re.match(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def stitch(settings: Settings) -> str | None:
    audio_dir = Path(settings.pipeline.audio_dir)
    files = sorted(glob(str(audio_dir / "*.wav")), key=_turn_id)
    if not files:
        print("[stitch] no .wav files found, skipping")
        return None

    print(f"[stitch] stitching {len(files)} files in order")
    master: AudioSegment | None = None
    gap = AudioSegment.silent(duration=settings.pipeline.silence_ms)
    timeline = []
    cursor = 0
    for f in files:
        seg = AudioSegment.from_wav(f)
        stem = Path(f).stem
        start = cursor
        timeline.append({
            "turn_id": _turn_id(f),
            "speaker": stem.split("_", 1)[1] if "_" in stem else "",
            "start_ms": start,
            "end_ms": start + len(seg),
        })
        cursor = start + len(seg) + settings.pipeline.silence_ms
        master = seg if master is None else master + gap + seg

    out = audio_dir / "final_podcast.mp3"
    master.export(str(out), format="mp3")
    (audio_dir / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stitch] wrote {out}")
    return str(out)
