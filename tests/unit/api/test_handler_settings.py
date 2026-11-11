import pytest
from fastapi.testclient import TestClient

from api.handler import create_app
from api.settings import get_settings


def _client(monkeypatch, **env) -> TestClient:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_cors_allows_local_dev_origin(monkeypatch):
    r = _client(monkeypatch).get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_ignores_other_origins(monkeypatch):
    r = _client(monkeypatch).get("/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200  # the request works, but the browser won't let evil.example read it
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_from_env(monkeypatch):
    c = _client(monkeypatch, ALLOWED_ORIGINS="http://localhost:5173, https://d123.cloudfront.net")
    r = c.get("/health", headers={"Origin": "https://d123.cloudfront.net"})
    assert r.headers["access-control-allow-origin"] == "https://d123.cloudfront.net"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_on_by_default(monkeypatch, path):
    assert _client(monkeypatch).get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_off_on_aws(monkeypatch, path):
    assert _client(monkeypatch, ENABLE_DOCS="0").get(path).status_code == 404
