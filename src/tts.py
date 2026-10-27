"""Synthesize turn WAVs with local Qwen models or chunked Bodhan speech requests."""

import json
import io
import gc
import os
import random
import re
import textwrap
import numpy as np
from pathlib import Path
from typing import Dict, List

from pydub import AudioSegment
import soundfile as sf
import torch
import yaml

from .config import Settings
from .bodhan import post_bodhan


def _bodhan_chunks(text):
    """Yield sentence-aware chunks and flags indicating where inter-sentence silence belongs.

    Wrap at 250 characters without splitting words; callers reject oversized tokens.
    """
    # Conservative size: the API recommends a sentence or two / ~30s per call.
    for sentence_index, sentence in enumerate(re.split(r"(?<=[.!?।॥])\s+", text.strip())):
        for chunk_index, chunk in enumerate(textwrap.wrap(
            sentence, width=250, break_long_words=False, break_on_hyphens=False,
        )):
            yield chunk, sentence_index > 0 and chunk_index == 0


def set_determinism(seed: int):
    """Seed Python, NumPy, and PyTorch and configure deterministic cuDNN behavior."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _load_model(settings: Settings):
    """Load the selected quantized Qwen model locally, falling back to its Hugging Face repository.

    Use CUDA with BF16 when available, otherwise CPU with FP32. Return None for Bodhan.
    """
    mode = settings.tts.mode
    if mode == "bodhan":
        return None

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
            dtype=dtype,
            quantization_config=quant
        )
    except Exception as e:
        print(f"[tts] local load failed ({e}); falling back to {hf_repo}")
        return Qwen3TTSModel.from_pretrained(
            hf_repo,
            device_map=device,
            dtype=dtype,
            quantization_config=quant
        )


def _load_template(settings: Settings) -> Dict:
    """Read host voice settings from the YAML template for the selected synthesis mode."""
    req_dir = Path(__file__).parent / "tts_requirements"
    mode = settings.tts.mode
    if mode == "custom_voice":
        path = req_dir / "custom_voice.yaml"
    elif mode == "voice_design":
        path = req_dir / "voice_design.yaml"
    elif mode == "bodhan":
        path = req_dir / "bodhan.yaml"
    else:
        raise ValueError(f"Unknown TTS mode: {mode}")

    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _synth_one(model, turn: Dict[str, str], settings: Settings, template: Dict, check_cancel=None, raise_on_error=False) -> None:
    """Synthesize one turn to its numbered host WAV, combining chunks for Bodhan.

    Qwen retries CUDA OOM once with its attention cache offloaded to RAM, restoring
    sampling state before retry and the original cache setting afterward. Qwen
    failures are logged and suppressed unless raise_on_error is set; Bodhan errors
    propagate and cancellation is checked between provider calls and before saving.
    """
    out = Path(settings.pipeline.audio_dir) / f"{turn['turn_id']}_{turn['speaker']}.wav"
    mode = settings.tts.mode

    if mode == "bodhan":
        host_cfg = template.get("host1" if turn["speaker"] == "Host 1" else "host2") or {}
        instructions = {"lang": settings.tts.podcast_language}
        if host_cfg.get("style"):
            instructions["style"] = host_cfg["style"]
        chunks = list(_bodhan_chunks(turn["text"]))
        if not chunks or any(len(chunk) > 250 for chunk, _ in chunks):
            raise ValueError(f"Turn {turn['turn_id']} has empty text or a token too long for Bodhan TTS")
        audio = AudioSegment.empty()
        for chunk, sentence_start in chunks:
            resp = post_bodhan("/v1/audio/speech", settings.tts.bodhan_api_key, {
                "model": "indic-speak", "input": chunk,
                "voice": host_cfg.get("voice", ""),
                "instructions": json.dumps(instructions),
            }, check_cancel=check_cancel, default_rpm=3)
            segment = AudioSegment.from_wav(io.BytesIO(resp.content))
            if len(segment) == 0:
                raise RuntimeError(f"Bodhan returned empty audio for turn {turn['turn_id']}")
            if sentence_start:
                audio += AudioSegment.silent(duration=250, frame_rate=segment.frame_rate)
            audio += segment
        if check_cancel:
            check_cancel()
        temporary = out.with_suffix(".wav.tmp")
        audio.export(str(temporary), format="wav")
        temporary.replace(out)
        print(f"[tts] {out.name}")
        return

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    generator = torch.Generator(device=device).manual_seed(settings.tts.seed)

    try:
        host_cfg = template.get("host1" if turn["speaker"] == "Host 1" else "host2") or {}
        kwargs = dict(text=turn["text"], language=settings.tts.language,
                      instruct=host_cfg.get("instruct", ""), generator=generator)
        if mode == "custom_voice":
            generate = model.generate_custom_voice
            kwargs["speaker"] = host_cfg.get("speaker", "ryan")
        elif mode == "voice_design":
            generate = model.generate_voice_design
        else:
            raise ValueError(f"Unknown TTS mode: {mode}")

        # Qwen currently drops the generator kwarg internally, so also preserve
        # the global sampling state when restarting a failed turn.
        cpu_rng = torch.get_rng_state()
        cuda_rng = torch.cuda.get_rng_state(device) if device.startswith("cuda") else None
        oom = False
        try:
            wavs, sr = generate(**kwargs)
        except torch.cuda.OutOfMemoryError:
            oom = True

        if oom:
            # Retry OUTSIDE the except block: its traceback otherwise keeps the
            # failed generation's tensors alive, defeating empty_cache().
            gc.collect()
            torch.cuda.empty_cache()
            if check_cancel:
                check_cancel()
            print(f"[tts] CUDA OOM for turn {turn['turn_id']}; retrying with attention cache in RAM")
            torch.set_rng_state(cpu_rng)
            if cuda_rng is not None:
                torch.cuda.set_rng_state(cuda_rng, device)
            generator.manual_seed(settings.tts.seed)
            # Qwen's wrapper drops cache_implementation from generation kwargs.
            config = model.model.talker.generation_config
            original_cache = config.cache_implementation
            try:
                config.cache_implementation = "offloaded"
                wavs, sr = generate(**kwargs)
            finally:
                config.cache_implementation = original_cache

        if len(wavs) == 0 or len(wavs[0]) == 0:
            raise RuntimeError(f"Qwen returned empty audio for turn {turn['turn_id']}")
        sf.write(str(out), wavs[0], sr)
        print(f"[tts] {out.name}")
    except Exception as e:
        print(f"[tts] FAILED {out.name}: {e}")
        if raise_on_error:
            raise


def synthesize_turns(turns: List[Dict[str, str]], settings: Settings) -> None:
    """Load the configured model and template once, then synthesize the supplied turns in order."""
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
    """Synthesize audio for every turn in the supplied script."""
    synthesize_turns(turns, settings)


def synthesize_turn(turn: Dict[str, str], settings: Settings) -> None:
    """Synthesize a single turn using the configured model and host template."""
    synthesize_turns([turn], settings)
