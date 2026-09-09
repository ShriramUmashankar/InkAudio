import pytest
from src.api.model_manager import ModelManager


@pytest.fixture(autouse=True)
def reset_model_manager():
    mgr = ModelManager()
    mgr._models = {}
    mgr._current_mode = None
    yield
