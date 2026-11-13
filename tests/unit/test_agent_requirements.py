"""agent/requirements.txt (what the agent container installs) must match uv.lock (what the tests run with)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORT = "uv export --only-group agent --no-hashes --no-emit-project -o agent/requirements.txt"


def _pins() -> dict[str, str]:
    text = (ROOT / "agent" / "requirements.txt").read_text()
    return {m[1].lower(): m[2] for m in re.finditer(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", text, re.M)}


def _locked() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return {p["name"].lower(): p["version"] for p in lock["package"] if "version" in p}


def test_agent_deps_are_pinned():
    pins = _pins()
    for name in ("strands-agents", "bedrock-agentcore", "fastapi", "pydantic", "boto3"):
        assert name in pins, f"{name} missing from agent/requirements.txt"


def test_agent_requirements_match_lock():
    locked = _locked()
    stale = {n: (v, locked.get(n)) for n, v in _pins().items() if locked.get(n) != v}
    assert not stale, f"agent/requirements.txt is out of date {stale}. Run: {EXPORT}"
