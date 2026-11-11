"""api/requirements.txt (what the Lambda installs) must match uv.lock (what the tests run with)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pins() -> dict[str, str]:
    text = (ROOT / "api" / "requirements.txt").read_text()
    return {m[1].lower(): m[2] for m in re.finditer(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", text, re.M)}


def _locked() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return {p["name"].lower(): p["version"] for p in lock["package"] if "version" in p}


def test_runtime_deps_are_pinned():
    pins = _pins()
    for name in ("fastapi", "mangum", "pydantic", "pydantic-core", "starlette"):
        assert name in pins, f"{name} missing from api/requirements.txt"


def test_requirements_match_lock():
    locked = _locked()
    stale = {n: (v, locked.get(n)) for n, v in _pins().items() if locked.get(n) != v}
    assert not stale, (
        f"api/requirements.txt is out of date {stale}. Run: "
        "uv export --only-group lambda --no-hashes --no-emit-project -o api/requirements.txt"
    )


def test_boto3_not_bundled():
    assert "boto3" not in _pins()  # already in the Lambda runtime
