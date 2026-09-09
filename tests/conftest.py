import pytest

from src.api import job_queue
from src.api.job_queue import TEMP_ROOT, _cleanup_dir
from src.api.model_manager import get_model_manager


@pytest.fixture(autouse=True)
def reset_state():
    mgr = get_model_manager()
    mgr._models = {}
    mgr._current_mode = None
    _cleanup_dir(str(TEMP_ROOT))
    job_queue._current_job = None
    yield
    job_queue._current_job = None