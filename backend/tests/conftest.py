import sys
from pathlib import Path

import pytest


backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


@pytest.fixture(autouse=True)
def _reset_checkpointer_singleton():
    from app.core.checkpointer import reset_checkpointer

    reset_checkpointer()
    yield
    reset_checkpointer()
