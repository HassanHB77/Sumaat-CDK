import pytest
from fastapi import Depends, FastAPI

from api.auth import Principal, parse_groups, require_business, require_customer
from api.handler import app as real_app
from tests.unit.api.conftest import ISS, customer_claims, owner_claims

probe = FastAPI()


@probe.get("/owner-only")
def owner_only(p: Principal = Depends(require_business("owner"))):
    return {"sub": p.sub, "pool": p.pool, "groups": sorted(p.groups), "restaurantId": p.restaurant_id}


@probe.get("/staff")
def staff(p: Principal = Depends(require_business("owner", "cashier"))):
    return {"sub": p.sub}


@probe.get("/customer-only")
def customer_only(p: Principal = Depends(require_customer())):
    return {"sub": p.sub, "pool": p.pool}


def test_health_is_public(make_client):
    r = make_client(real_app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/owner-only", "/customer-only"])
def test_no_claims_is_401(make_client, path):
    assert make_client(probe).get(path).status_code == 401


def test_unknown_issuer_is_401(make_client):
    claims = {**owner_claims(), "iss": ISS.format("us-east-1_SOMEONEELSE")}
    assert make_client(probe, claims).get("/owner-only").status_code == 401


def test_owner_passes_and_claims_are_read(make_client):
    r = make_client(probe, owner_claims(restaurant_id="r-1")).get("/owner-only")
    assert r.status_code == 200
    assert r.json() == {"sub": "owner-sub-1", "pool": "business", "groups": ["owner"], "restaurantId": "r-1"}


def test_cashier_blocked_from_owner_route_but_allowed_on_staff(make_client):
    cashier = owner_claims(sub="c-1", groups="cashier")
    assert make_client(probe, cashier).get("/owner-only").status_code == 403
    assert make_client(probe, cashier).get("/staff").status_code == 200


def test_business_user_without_group_is_403(make_client):
    assert make_client(probe, owner_claims(groups=None)).get("/owner-only").status_code == 403


def test_customer_token_cannot_use_business_route(make_client):
    # Both pools pass the shared API Gateway authorizer; the pool check must stop this.
    claims = {**customer_claims(), "cognito:groups": "owner"}
    assert make_client(probe, claims).get("/owner-only").status_code == 403


def test_business_token_cannot_use_customer_route(make_client):
    assert make_client(probe, owner_claims()).get("/customer-only").status_code == 403


def test_customer_passes(make_client):
    r = make_client(probe, customer_claims()).get("/customer-only")
    assert r.json() == {"sub": "customer-sub-1", "pool": "customer"}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, set()),
        ("", set()),
        ("owner", {"owner"}),
        ("owner,cashier", {"owner", "cashier"}),
        ("[owner cashier]", {"owner", "cashier"}),
        (["owner", "cashier"], {"owner", "cashier"}),
    ],
)
def test_parse_groups(raw, expected):
    assert parse_groups(raw) == expected
