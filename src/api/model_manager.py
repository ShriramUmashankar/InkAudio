import torch
from typing import Dict, Optional

from src.config import load_settings

_model_manager_instance = None


def _load_qwen_model(mode: str, settings) -> object:
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

    if mode == "custom_voice":
        local_path = settings.tts.local_model_path
        hf_repo = settings.tts.hf_repo_id
    elif mode == "voice_design":
        local_path = settings.tts.voice_design_model_path
        hf_repo = settings.tts.voice_design_hf_repo_id
    else:
        raise ValueError(f"Unknown TTS mode: {mode}")

    try:
        print(f"[model_manager] loaded {mode} from local path {local_path}")
        return Qwen3TTSModel.from_pretrained(
            local_path, device_map=device, quantization_config=quant
        )
    except Exception as e:
        print(f"[model_manager] local load failed ({e}); falling back to {hf_repo}")
        return Qwen3TTSModel.from_pretrained(
            hf_repo, device_map=device, quantization_config=quant
        )


class ModelManager:
    def __new__(cls):
        global _model_manager_instance
        if _model_manager_instance is None:
            _model_manager_instance = super().__new__(cls)
            _model_manager_instance._models = {}
            _model_manager_instance._current_mode = None
        return _model_manager_instance

    def get_model(self, mode: str, settings=None):
        if mode == "bodhan":
            return None
        if settings is None:
            settings = load_settings()
        if mode not in self._models:
            self._models[mode] = _load_qwen_model(mode, settings)
        if self._current_mode is not None and self._current_mode != mode:
            self.unload(self._current_mode)
        self._current_mode = mode
        return self._models[mode]

    def unload(self, mode: str):
        if mode in self._models:
            del self._models[mode]
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if self._current_mode == mode:
                self._current_mode = None

    def unload_all(self):
        self._models.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._current_mode = None

    @property
    def loaded_modes(self) -> list:
        return list(self._models.keys())


def get_model_manager() -> ModelManager:
    return ModelManager()
