import os
from datetime import datetime

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from api import aws
from api.handler import app
from api.settings import get_settings
from api.hours import RIYADH
from tests.ddb import create_table

USER_POOL = "us-east-1_TESTPOOL"
ISS = "https://cognito-idp.us-east-1.amazonaws.com/{}"


@pytest.fixture(autouse=True)
def api_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "sumaat")
    monkeypatch.setenv("USER_POOL_ID", USER_POOL)
    for cached in (get_settings, aws.table, aws.cognito, aws.s3):
        cached.cache_clear()
    yield
    for cached in (get_settings, aws.table, aws.cognito, aws.s3):
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
        for cached in (get_settings, aws.table, aws.cognito, aws.s3):
            cached.cache_clear()
        yield table, cognito, pool_id


# --- shared order fixtures (test_orders.py, test_order_status.py) --------------

# A restaurant open 16:00-02:00 (Riyadh). Also used by test_restaurants.py.
NEW = {
    "name": "Hofuf Burger Lab",
    "nameAr": "مختبر برجر الهفوف",
    "description": "Smash burgers.",
    "city": "Al-Hofuf",
    "district": "Al-Kut",
    "lat": 25.3801,
    "lng": 49.5870,
    "hours": "16:00-02:00",
}
DISH = {"name": "Smash Burger", "nameAr": "برجر", "category": "Mains", "priceHalalas": 2500}
FRIES = {"name": "Fries", "nameAr": "بطاطس", "category": "Sides", "priceHalalas": 900}
THU_18 = datetime(2026, 11, 12, 18, 0, tzinfo=RIYADH)


def sara(sub="customer-sub-1") -> dict:
    return {**customer_claims(sub), "email": "sara@example.com"}


@pytest.fixture
def clock(monkeypatch):
    """Riyadh time used by the API; tests can move it with clock.set(...)."""

    class Clock:
        now = THU_18

        def set(self, dt):
            self.now = dt

    c = Clock()
    monkeypatch.setattr("api.hours.riyadh_now", lambda: c.now)
    return c


@pytest.fixture
def shop(ddb, make_client, clock):
    """A restaurant (owner-sub-1) with 2 menu items, open at 18:00."""
    table, *_ = ddb
    from scripts.seed import seed  # local import: only order tests need the seed

    seed(table)  # categories (+ the 3 demo restaurants)
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]
    burger = owner.post(f"/restaurants/{rid}/menu", json=DISH).json()["id"]
    fries = owner.post(f"/restaurants/{rid}/menu", json=FRIES).json()["id"]
    return {"table": table, "owner": owner, "rid": rid, "burger": burger, "fries": fries}


def order_body(shop, **extra):
    return {"restaurantId": shop["rid"], "items": [{"itemId": shop["burger"], "qty": 2}, {"itemId": shop["fries"], "qty": 1}], **extra}


@pytest.fixture
def customer(make_client):
    return make_client(app, sara())


