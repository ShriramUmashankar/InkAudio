import pytest
from unittest.mock import patch, MagicMock
from src.api.model_manager import ModelManager


def test_singleton():
    from src.api.model_manager import get_model_manager
    m1 = get_model_manager()
    m2 = get_model_manager()
    assert m1 is m2


def test_get_model_custom_voice():
    mgr = ModelManager()
    with patch("src.api.model_manager._load_qwen_model") as mock_load:
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        model = mgr.get_model("custom_voice")
        assert model is mock_model
        mock_load.assert_called_once()


def test_model_cached():
    mgr = ModelManager()
    with patch("src.api.model_manager._load_qwen_model") as mock_load:
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        mgr.get_model("custom_voice")
        mgr.get_model("custom_voice")
        assert mock_load.call_count == 1


def test_bodhan_returns_none():
    mgr = ModelManager()
    model = mgr.get_model("bodhan")
    assert model is None


def test_unload():
    mgr = ModelManager()
    with patch("src.api.model_manager._load_qwen_model") as mock_load:
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        mgr.get_model("custom_voice")
    with patch("src.api.model_manager.torch.cuda.empty_cache"):
        mgr.unload("custom_voice")
    assert "custom_voice" not in mgr._models


def test_unload_all():
    mgr = ModelManager()
    with patch("src.api.model_manager._load_qwen_model"):
        mgr.get_model("custom_voice")
        mgr.get_model("voice_design")
    with patch("src.api.model_manager.torch.cuda.empty_cache"):
        mgr.unload_all()
    assert len(mgr._models) == 0


def test_mode_switch():
    mgr = ModelManager()
    with patch("src.api.model_manager._load_qwen_model") as mock_load:
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        mgr.get_model("custom_voice")
        mgr.get_model("voice_design")
        assert mock_load.call_count == 2
        assert "custom_voice" not in mgr._models
        assert "voice_design" in mgr._models
