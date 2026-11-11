import importlib.util
from pathlib import Path

import pytest

FUNCTIONS = Path(__file__).resolve().parents[3] / "functions"


def load_handler(folder: str):
    """Load functions/<folder>/handler.py as its own module (every Lambda file is named handler.py)."""
    spec = importlib.util.spec_from_file_location(f"fn_{folder}", FUNCTIONS / folder / "handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Fake credentials so nothing can ever reach real AWS from a unit test."""
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(key, value)
