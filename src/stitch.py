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
    for f in files:
        seg = AudioSegment.from_wav(f)
        master = seg if master is None else master + gap + seg

    out = audio_dir / "final_podcast.mp3"
    master.export(str(out), format="mp3")
    print(f"[stitch] wrote {out}")
    return str(out)
