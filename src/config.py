import os
from dataclasses import dataclass
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key_env: str
    api_key: str


@dataclass
class TTSConfig:
    mode: str
    local_model_path: str
    hf_repo_id: str
    voice_design_model_path: str
    voice_design_hf_repo_id: str
    device: str
    language: str
    seed: int
    bodhan_api_key: str


@dataclass
class PipelineConfig:
    pdf_path: str
    content_dir: str
    audio_dir: str
    max_loops: int
    silence_ms: int
    heading_level: int
    questions_pdf_path: str
    log_path: str


@dataclass
class STTConfig:
    device: str
    compute_type: str
    model: str


@dataclass
class Settings:
    actor: LLMConfig
    critic: LLMConfig
    tts: TTSConfig
    pipeline: PipelineConfig
    stt: STTConfig


def _resolve_key(env_name: str) -> str:
    key = os.environ.get(env_name, "")
    if not key:
        raise RuntimeError(
            f"Environment variable '{env_name}' is not set. "
            f"Add it to your .env file (see .env.example)."
        )
    return key


def _llm_from(cfg: Dict[str, Any]) -> LLMConfig:
    env_name = cfg["api_key_env"]
    return LLMConfig(
        base_url=cfg["base_url"],
        model=cfg["model"],
        api_key_env=env_name,
        api_key=_resolve_key(env_name),
    )


def _stt_from(cfg: Dict[str, Any]) -> STTConfig:
    return STTConfig(
        device=os.environ.get("STT_DEVICE", cfg.get("device", "cpu")),
        compute_type=os.environ.get("STT_COMPUTE_TYPE", cfg.get("compute_type", "int8")),
        model=os.environ.get("STT_MODEL", cfg.get("model", "small.en")),
    )


def load_settings(path: str = "config.yaml") -> Settings:
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    actor = _llm_from(raw["actor"])
    critic = _llm_from(raw["critic"])
    tts_raw = raw["tts"]
    bodhan_env = tts_raw.pop("bodhan_api_key_env", "BODHAN_TTS")
    bodhan_key = os.environ.get(bodhan_env, "")
    tts_raw["bodhan_api_key"] = bodhan_key
    tts = TTSConfig(**tts_raw)
    pipeline = PipelineConfig(**raw["pipeline"])
    stt = _stt_from(raw.get("stt", {}))
    return Settings(actor=actor, critic=critic, tts=tts, pipeline=pipeline, stt=stt)
