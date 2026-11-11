import importlib.util
from pathlib import Path

FUNCTIONS = Path(__file__).resolve().parents[3] / "functions"


def load_handler(folder: str):
    """Load functions/<folder>/handler.py as its own module (every Lambda file is named handler.py)."""
    spec = importlib.util.spec_from_file_location(f"fn_{folder}", FUNCTIONS / folder / "handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
