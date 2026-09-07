#!/usr/bin/env python3
"""Download all 2 Qwen3-TTS model checkpoints to models/ subfolders."""
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

MODELS = {
    "Qwen3-TTS-12Hz-1.7B-CustomVoice": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen3-TTS-12Hz-1.7B-VoiceDesign": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "faster-whisper-small.en": "Systran/faster-whisper-small.en",
}

def download_model(model_name: str, hf_repo: str, out_dir: Path) -> bool:
    print(f"[download] {model_name} from {hf_repo} -> {out_dir}")
    try:
        # snapshot_download is natively idempotent; it only downloads missing or updated files.
        snapshot_download(
            repo_id=hf_repo,
            local_dir=out_dir,
            local_dir_use_symlinks=False # Ensures real files are placed in the folder, not symlinks
        )
        print(f"[download] {model_name} done")
        return True
    except Exception as e:
        print(f"[download] {model_name} failed: {e}")
        return False

def main() -> int:
    root = Path(__file__).parent
    all_ok = True
    for name, repo in MODELS.items():
        out = root / name
        if not download_model(name, repo, out):
            all_ok = False
    return 0 if all_ok else 1

if __name__ == "__main__":
    # Ensure you have the library installed: pip install huggingface_hub
    sys.exit(main())