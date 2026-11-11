import pytest
from fastapi import Depends, FastAPI

from api.auth import Principal, parse_groups, require_customer, require_groups, require_user
from api.handler import app as real_app
from tests.unit.api.conftest import ISS, customer_claims, owner_claims

probe = FastAPI()


@probe.get("/owner-only")
def owner_only(p: Principal = Depends(require_groups("owner"))):
    return {"sub": p.sub, "groups": sorted(p.groups), "restaurantId": p.restaurant_id}


@probe.get("/staff")
def staff(p: Principal = Depends(require_groups("owner", "cashier"))):
    return {"sub": p.sub}


@probe.get("/customer-only")
def customer_only(p: Principal = Depends(require_customer())):
    return {"sub": p.sub}


@probe.get("/any-user")
def any_user(p: Principal = Depends(require_user())):
    return {"sub": p.sub, "name": p.name}


def test_health_is_public(make_client):
    r = make_client(real_app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/owner-only", "/any-user"])
def test_no_claims_is_401(make_client, path):
    assert make_client(probe).get(path).status_code == 401


@pytest.mark.parametrize("path", ["/owner-only", "/any-user"])
def test_other_pool_is_401(make_client, path):
    claims = {**owner_claims(), "iss": ISS.format("us-east-1_SOMEONEELSE")}
    assert make_client(probe, claims).get(path).status_code == 401


def test_owner_passes_and_claims_are_read(make_client):
    r = make_client(probe, owner_claims(restaurant_id="r-1")).get("/owner-only")
    assert r.status_code == 200
    assert r.json() == {"sub": "owner-sub-1", "groups": ["owner"], "restaurantId": "r-1"}


def test_customer_cannot_use_owner_route(make_client):
    assert make_client(probe, customer_claims()).get("/owner-only").status_code == 403


def test_cashier_blocked_from_owner_route_but_allowed_on_staff(make_client):
    cashier = owner_claims(sub="c-1", groups="cashier")
    assert make_client(probe, cashier).get("/owner-only").status_code == 403
    assert make_client(probe, cashier).get("/staff").status_code == 200


def test_user_without_groups_is_403_on_group_route(make_client):
    assert make_client(probe, owner_claims(groups=None)).get("/owner-only").status_code == 403


@pytest.mark.parametrize("claims", [customer_claims(), owner_claims(), owner_claims(groups=None)])
def test_any_signed_in_user_passes_require_user(make_client, claims):
    # require_user is for routes any role may call (the service decides what they see).
    assert make_client(probe, claims).get("/any-user").status_code == 200


def test_require_groups_needs_a_group():
    with pytest.raises(ValueError):
        require_groups()


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, set()),
        ("", set()),
        ("owner", {"owner"}),
        ("customer,owner", {"customer", "owner"}),
        ("[customer owner]", {"customer", "owner"}),
        (["owner", "cashier"], {"owner", "cashier"}),
    ],
)
def test_parse_groups(raw, expected):
    assert parse_groups(raw) == expected


def test_require_customer(make_client):
    assert make_client(probe, customer_claims()).get("/customer-only").status_code == 200
    # One role per account: owners and cashiers order with a separate customer account.
    assert make_client(probe, owner_claims()).get("/customer-only").status_code == 403
    assert make_client(probe, owner_claims(sub="c-1", groups="cashier")).get("/customer-only").status_code == 403
