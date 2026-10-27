"""Lazily cache Qwen TTS models and release model references and CUDA cache."""

import torch
from dataclasses import replace

from src.config import load_settings
from src.tts import _load_model as _load_qwen_model


class ModelManager:
    """Manage cached Qwen TTS models for the API; Bodhan requires no local model."""
    def __init__(self):
        """Initialize the mode-to-model cache with no active Qwen mode."""
        self._models = {}
        self._current_mode = None

    def get_model(self, mode, settings=None):
        """Return no model for Bodhan; lazily load Qwen and unload the previous mode."""
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

    def unload(self, mode):
        """Drop a cached mode, clear available CUDA cache, and reset its active marker."""
        if mode in self._models:
            del self._models[mode]
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if self._current_mode == mode:
                self._current_mode = None

    def unload_all(self):
        """Release every cached model and clear the active mode and CUDA cache."""
        self._models.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._current_mode = None

    @property
    def loaded_modes(self):
        """List the TTS modes whose models are currently cached."""
        return list(self._models.keys())


_instance = None


def get_model_manager():
    """Create the process-wide model manager on first use and return it thereafter."""
    global _instance
    if _instance is None:
        _instance = ModelManager()
    return _instance
