import torch
from typing import Dict, Optional

from dataclasses import replace

from src.config import load_settings
from src.tts import _load_model as _load_qwen_model

_model_manager_instance = None


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
            settings_copy = replace(settings, tts=replace(settings.tts, mode=mode))
            self._models[mode] = _load_qwen_model(settings_copy)
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