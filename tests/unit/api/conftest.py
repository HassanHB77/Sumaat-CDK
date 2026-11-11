import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from api import aws
from api.settings import get_settings
from tests.ddb import create_table

USER_POOL = "us-east-1_TESTPOOL"
ISS = "https://cognito-idp.us-east-1.amazonaws.com/{}"


@pytest.fixture(autouse=True)
def api_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "sumaat")
    monkeypatch.setenv("USER_POOL_ID", USER_POOL)
    for cached in (get_settings, aws.table, aws.cognito):
        cached.cache_clear()
    yield
    for cached in (get_settings, aws.table, aws.cognito):
        getattr(cached, "cache_clear", lambda: None)()  # a test may have monkeypatched it


def owner_claims(sub="owner-sub-1", groups="owner", restaurant_id=None) -> dict:
    # No "iss" here: with_claims() adds our pool's issuer at request time (the `ddb` fixture swaps in
    # moto's generated pool id). cognito:username == sub here; in the real pool the username is also a UUID.
    claims = {
        "sub": sub,
        "cognito:username": sub,
        "name": "Test Owner",
        "cognito:groups": groups,
    }
    if restaurant_id:
        claims["custom:restaurantId"] = restaurant_id
    return claims


def customer_claims(sub="customer-sub-1") -> dict:
    return {
        "sub": sub,
        "cognito:username": sub,
        "name": "Sara",
        "phone_number": "+966500000001",
        "cognito:groups": "customer",
    }


def with_claims(app, claims: dict | None):
    """Wrap an ASGI app so each request looks like it came through API Gateway + Mangum."""

    async def wrapped(scope, receive, send):
        if scope["type"] == "http" and claims is not None:
            full = {"iss": ISS.format(os.environ["USER_POOL_ID"]), **claims}  # explicit iss wins
            scope = {**scope, "aws.event": {"requestContext": {"authorizer": {"claims": full}}}}
        await app(scope, receive, send)

    return wrapped


@pytest.fixture
def make_client():
    """make_client(app, claims=None) -> TestClient that sends those Cognito claims."""

    def _make(app, claims: dict | None = None) -> TestClient:
        return TestClient(with_claims(app, claims))

    return _make


@pytest.fixture
def ddb(monkeypatch):
    """moto table `sumaat` + moto user pool with users owner-sub-1, owner-sub-2 (owners), cashier-sub-1."""
    with mock_aws():
        table = create_table(boto3.resource("dynamodb", region_name="us-east-1"))
        cognito = boto3.client("cognito-idp", region_name="us-east-1")
        pool_id = cognito.create_user_pool(
            PoolName="sumaat-users",
            Schema=[{"Name": "restaurantId", "AttributeDataType": "String", "Mutable": True}],
        )["UserPool"]["Id"]
        for group in ("customer", "owner", "cashier"):
            cognito.create_group(UserPoolId=pool_id, GroupName=group)
        for username in ("owner-sub-1", "owner-sub-2", "cashier-sub-1"):
            cognito.admin_create_user(UserPoolId=pool_id, Username=username, MessageAction="SUPPRESS")

        monkeypatch.setenv("USER_POOL_ID", pool_id)
        for cached in (get_settings, aws.table, aws.cognito):
            cached.cache_clear()
        yield table, cognito, pool_id
