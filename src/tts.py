import os
import random
import numpy as np
from pathlib import Path
from typing import Dict, List

import soundfile as sf
import torch
import yaml

from .config import Settings


def set_determinism(seed: int):
    """Force deterministic behavior across all libraries."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _load_model(settings: Settings):
    from qwen_tts import Qwen3TTSModel
    from transformers import BitsAndBytesConfig

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=dtype,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        llm_int8_skip_modules=["lm_head"],
    )

    mode = settings.tts.mode
    if mode == "custom_voice":
        local_path = settings.tts.local_model_path
        hf_repo = settings.tts.hf_repo_id
    elif mode == "voice_design":
        local_path = settings.tts.voice_design_model_path
        hf_repo = settings.tts.voice_design_hf_repo_id
    else:
        raise ValueError(f"Unknown TTS mode: {mode}")

    try:
        print(f"[tts] loading {mode} from local path {local_path}")
        return Qwen3TTSModel.from_pretrained(
            local_path,
            device_map=device,
            quantization_config=quant
        )
    except Exception as e:
        print(f"[tts] local load failed ({e}); falling back to {hf_repo}")
        return Qwen3TTSModel.from_pretrained(
            hf_repo,
            device_map=device,
            quantization_config=quant
        )


def _load_template(settings: Settings) -> Dict:
    req_dir = Path(__file__).parent / "tts_requirements"
    mode = settings.tts.mode
    if mode == "custom_voice":
        path = req_dir / "custom_voice.yaml"
    elif mode == "voice_design":
        path = req_dir / "voice_design.yaml"
    else:
        raise ValueError(f"Unknown TTS mode: {mode}")

    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _synth_one(model, turn: Dict[str, str], settings: Settings, template: Dict) -> None:
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    generator = torch.Generator(device=device).manual_seed(settings.tts.seed)

    out = Path(settings.pipeline.audio_dir) / f"{turn['turn_id']}_{turn['speaker']}.wav"
    mode = settings.tts.mode

    try:
        if mode == "custom_voice":
            host_cfg = template.get("host1") if turn["speaker"] == "Host 1" else template.get("host2")
            voice = host_cfg.get("speaker") if host_cfg else "ryan"
            instruct = host_cfg.get("instruct") if host_cfg else ""
            wavs, sr = model.generate_custom_voice(
                text=turn["text"],
                language=settings.tts.language,
                speaker=voice,
                instruct=instruct,
                generator=generator,
            )
        elif mode == "voice_design":
            host_cfg = template.get("host1") if turn["speaker"] == "Host 1" else template.get("host2")
            instruct = host_cfg.get("instruct") if host_cfg else ""
            wavs, sr = model.generate_voice_design(
                text=turn["text"],
                language=settings.tts.language,
                instruct=instruct,
                generator=generator,
            )
        else:
            raise ValueError(f"Unknown TTS mode: {mode}")

        sf.write(str(out), wavs[0], sr)
        print(f"[tts] {out.name}")
    except Exception as e:
        print(f"[tts] FAILED {out.name}: {e}")


def synthesize_turns(turns: List[Dict[str, str]], settings: Settings) -> None:
    if not turns:
        print("[tts] no turns to synthesize")
        return

    model = _load_model(settings)
    template = _load_template(settings)

    if hasattr(model, "get_supported_speakers"):
        print("Available voices:", model.get_supported_speakers())

    Path(settings.pipeline.audio_dir).mkdir(parents=True, exist_ok=True)

    for turn in turns:
        _synth_one(model, turn, settings, template)


def synthesize_all(turns: List[Dict[str, str]], settings: Settings) -> None:
    synthesize_turns(turns, settings)


def synthesize_turn(turn: Dict[str, str], settings: Settings) -> None:
    synthesize_turns([turn], settings)