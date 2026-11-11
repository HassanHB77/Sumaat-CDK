"""Run a real API Gateway REST (v1) event through the Lambda entry point, the same way Lambda will."""

import json

from fastapi import Depends, FastAPI
from mangum import Mangum

from api.auth import Principal, require_groups
from api.handler import handler
from tests.unit.api.conftest import ISS, USER_POOL, owner_claims

# Separate probe app so the real app's routes stay untouched.
probe = FastAPI()


@probe.get("/_test/whoami")
def _whoami(p: Principal = Depends(require_groups("owner"))):
    return {"sub": p.sub}


probe_handler = Mangum(probe, lifespan="off")


def rest_event(path: str, claims: dict | None = None, method: str = "GET") -> dict:
    return {
        "resource": "/{proxy+}",
        "path": path,
        "httpMethod": method,
        "headers": {"Host": "api.example.com", "X-Forwarded-Proto": "https", "X-Forwarded-Port": "443"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {"proxy": path.lstrip("/")},
        "stageVariables": None,
        "requestContext": {
            "resourcePath": "/{proxy+}",
            "httpMethod": method,
            "path": f"/prod{path}",
            "stage": "prod",
            "requestId": "test-request",
            "identity": {"sourceIp": "127.0.0.1"},
            "authorizer": {"claims": claims} if claims else None,
        },
        "body": None,
        "isBase64Encoded": False,
    }


class FakeContext:
    function_name = "sumaat-api"
    aws_request_id = "test-request"


def test_health_through_lambda_entry_point():
    resp = handler(rest_event("/health"), FakeContext())
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"status": "ok"}


def test_claims_reach_the_app_through_mangum():
    resp = probe_handler(rest_event("/_test/whoami", {**owner_claims(), "iss": ISS.format(USER_POOL)}), FakeContext())
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"sub": "owner-sub-1"}


def test_no_authorizer_claims_is_401():
    assert probe_handler(rest_event("/_test/whoami"), FakeContext())["statusCode"] == 401
