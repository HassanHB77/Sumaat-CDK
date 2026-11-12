"""Run the CloudFront Functions in Node (same JavaScript as CloudFront executes) with sample requests."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FUNCTIONS = Path(__file__).resolve().parents[2] / "infra" / "cf_functions"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(file: str, uri: str) -> str:
    script = (
        FUNCTIONS.joinpath(file).read_text()
        + f"\nconsole.log(JSON.stringify(handler({{request: {{uri: {json.dumps(uri)}, querystring: {{}}}}}})));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["uri"]


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("/api/health", "/health"),
        ("/api/orders/mine", "/orders/mine"),
        ("/api/restaurants/abc/menu/xyz", "/restaurants/abc/menu/xyz"),
        ("/api", "/"),
        ("/api/", "/"),
        ("/apiary/x", "/apiary/x"),  # only the exact /api prefix is removed
    ],
)
def test_strip_api_prefix(uri, expected):
    assert run("strip_api_prefix.js", uri) == expected


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("/", "/index.html"),
        ("/orders/123", "/index.html"),
        ("/owner/menu/", "/index.html"),
        ("/index.html", "/index.html"),
        ("/assets/app-1a2b.js", "/assets/app-1a2b.js"),
        ("/favicon.ico", "/favicon.ico"),
    ],
)
def test_spa_index(uri, expected):
    assert run("spa_index.js", uri) == expected


ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/sumaat_agent-abc123"


def run_agent(uri: str, method: str = "POST") -> dict:
    code = FUNCTIONS.joinpath("agent_rewrite.js").read_text().replace("__RUNTIME_ARN__", ARN)
    req = json.dumps({"uri": uri, "method": method, "querystring": {}})
    script = code + f"\nconsole.log(JSON.stringify(handler({{request: {req}}})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_agent_rewrite_to_runtime_invocations():
    out = run_agent("/agent/chat")
    assert out["uri"] == (
        "/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A123456789012%3Aruntime%2Fsumaat_agent-abc123"
        "/invocations"
    )
    assert out["querystring"] == {"qualifier": {"value": "DEFAULT"}}


@pytest.mark.parametrize("uri, method", [("/agent/chat", "GET"), ("/agent/other", "POST"), ("/agent/", "POST")])
def test_agent_rewrite_refuses_anything_else(uri, method):
    assert run_agent(uri, method)["statusCode"] == 404
