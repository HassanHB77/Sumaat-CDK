import pytest
from fastapi.testclient import TestClient

from api import aws
from api.settings import get_settings

BUSINESS_POOL = "us-east-1_TESTBIZ"
CUSTOMER_POOL = "us-east-1_TESTCUS"
ISS = "https://cognito-idp.us-east-1.amazonaws.com/{}"


@pytest.fixture(autouse=True)
def api_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "sumaat")
    monkeypatch.setenv("BUSINESS_POOL_ID", BUSINESS_POOL)
    monkeypatch.setenv("CUSTOMER_POOL_ID", CUSTOMER_POOL)
    for cached in (get_settings, aws.table, aws.cognito):
        cached.cache_clear()
    yield
    for cached in (get_settings, aws.table, aws.cognito):
        cached.cache_clear()


def owner_claims(sub="owner-sub-1", groups="owner", restaurant_id=None) -> dict:
    claims = {"sub": sub, "iss": ISS.format(BUSINESS_POOL), "name": "Test Owner", "cognito:groups": groups}
    if restaurant_id:
        claims["custom:restaurantId"] = restaurant_id
    return claims


def customer_claims(sub="customer-sub-1") -> dict:
    return {"sub": sub, "iss": ISS.format(CUSTOMER_POOL), "name": "Sara", "phone_number": "+966500000001"}


def with_claims(app, claims: dict | None):
    """Wrap an ASGI app so each request looks like it came through API Gateway + Mangum."""

    async def wrapped(scope, receive, send):
        if scope["type"] == "http" and claims is not None:
            scope = {**scope, "aws.event": {"requestContext": {"authorizer": {"claims": claims}}}}
        await app(scope, receive, send)

    return wrapped


@pytest.fixture
def make_client():
    """make_client(app, claims=None) -> TestClient that sends those Cognito claims."""

    def _make(app, claims: dict | None = None) -> TestClient:
        return TestClient(with_claims(app, claims))

    return _make
