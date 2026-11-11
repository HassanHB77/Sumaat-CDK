from datetime import datetime

import pytest
from botocore.exceptions import ClientError

from api.handler import app
from api.hours import RIYADH
from tests.unit.api.conftest import customer_claims, owner_claims
from tests.unit.api.test_restaurants import NEW

CASHIER = {"name": "Fahad Cashier", "email": "cashier.one@example.com", "phone": "+966500000201", "password": "Cash#2026"}


@pytest.fixture
def setup(ddb, make_client, monkeypatch):
    monkeypatch.setattr("api.hours.riyadh_now", lambda: datetime(2026, 11, 12, 18, 0, tzinfo=RIYADH))
    table, cognito, pool_id = ddb
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]
    return table, cognito, pool_id, owner, rid


def _cashier_client(make_client, sub, rid):
    """What the cashier's own token looks like after login."""
    return make_client(app, owner_claims(sub=sub, groups="cashier", restaurant_id=rid))


@pytest.fixture
def created(setup):
    table, cognito, pool_id, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/cashiers", json=CASHIER)
    assert r.status_code == 201, r.text
    return r.json()


# --- create ------------------------------------------------------------------


def test_create_makes_login_group_and_record(setup, created):
    table, cognito, pool_id, owner, rid = setup
    assert created["status"] == "active" and created["name"] == CASHIER["name"]
    assert "password" not in created

    user = cognito.admin_get_user(UserPoolId=pool_id, Username=CASHIER["email"])
    attrs = {a["Name"]: a["Value"] for a in user["UserAttributes"]}
    assert attrs["custom:restaurantId"] == rid
    assert attrs["phone_number"] == CASHIER["phone"]
    assert attrs["email_verified"] == "true"
    assert user["UserStatus"] == "CONFIRMED"  # password set: ready to log in, no email sent
    groups = cognito.admin_list_groups_for_user(UserPoolId=pool_id, Username=CASHIER["email"])["Groups"]
    assert [g["GroupName"] for g in groups] == ["cashier"]  # one role only


def test_new_cashier_can_pause_right_away(setup, created, make_client):
    *_, rid = setup
    cashier = _cashier_client(make_client, created["sub"], rid)
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 200


def test_list(setup, created):
    *_, owner, rid = setup
    owner.post(f"/restaurants/{rid}/cashiers", json={**CASHIER, "name": "Amal", "email": "amal@example.com"})
    names = [c["name"] for c in owner.get(f"/restaurants/{rid}/cashiers").json()]
    assert names == ["Amal", "Fahad Cashier"]


def test_duplicate_email_is_409(setup, created):
    *_, owner, rid = setup
    assert owner.post(f"/restaurants/{rid}/cashiers", json=CASHIER).status_code == 409


def test_customer_email_cannot_be_taken_over(setup):
    table, cognito, pool_id, owner, rid = setup
    cognito.admin_create_user(UserPoolId=pool_id, Username="sara@example.com", MessageAction="SUPPRESS")
    r = owner.post(f"/restaurants/{rid}/cashiers", json={**CASHIER, "email": "sara@example.com"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    "password, missing",
    [
        ("short#1A", None),  # ok length 8 -> accepted (control case)
        ("Short#1", "at least 8"),
        ("nouppercase#1", "uppercase"),
        ("NOLOWERCASE#1", "lowercase"),
        ("NoDigits#here", "digit"),
        ("NoSymbol123", "symbol"),
    ],
)
def test_password_rules(setup, password, missing):
    *_, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/cashiers", json={**CASHIER, "email": f"{abs(hash(password))}@example.com", "password": password})
    if missing is None:
        assert r.status_code == 201
    else:
        assert r.status_code == 422
        assert missing in r.text or "at least 8" in r.text


@pytest.mark.parametrize("phone", ["0500000201", "966500000201", "+96650", "+9665000002011234567"])
def test_bad_phone_is_422(setup, phone):
    *_, owner, rid = setup
    assert owner.post(f"/restaurants/{rid}/cashiers", json={**CASHIER, "phone": phone}).status_code == 422


@pytest.mark.parametrize(
    "claims, code",
    [
        (None, 401),
        (customer_claims(), 403),
        (owner_claims(sub="owner-sub-2"), 403),  # owner of another restaurant
    ],
)
def test_only_this_owner_manages_cashiers(setup, make_client, claims, code):
    *_, rid = setup
    c = make_client(app, claims)
    assert c.post(f"/restaurants/{rid}/cashiers", json=CASHIER).status_code == code
    assert c.get(f"/restaurants/{rid}/cashiers").status_code == code


def test_cashier_cannot_create_cashiers(setup, created, make_client):
    *_, rid = setup
    cashier = _cashier_client(make_client, created["sub"], rid)
    assert cashier.post(f"/restaurants/{rid}/cashiers", json={**CASHIER, "email": "x@example.com"}).status_code == 403


def test_unknown_restaurant_is_404(setup):
    *_, owner, _ = setup
    assert owner.post("/restaurants/nope/cashiers", json=CASHIER).status_code == 404


def test_failed_setup_removes_half_made_user(setup, monkeypatch):
    table, cognito, pool_id, owner, rid = setup
    from api import aws

    real = aws.cognito()

    class Flaky:
        def __getattr__(self, name):
            return getattr(real, name)

        def admin_add_user_to_group(self, **kw):
            raise ClientError({"Error": {"Code": "InternalErrorException", "Message": "boom"}}, "AdminAddUserToGroup")

    monkeypatch.setattr(aws, "cognito", lambda: Flaky())
    with pytest.raises(ClientError):
        owner.post(f"/restaurants/{rid}/cashiers", json=CASHIER)
    with pytest.raises(cognito.exceptions.UserNotFoundException):
        cognito.admin_get_user(UserPoolId=pool_id, Username=CASHIER["email"])
    assert not [i for i in table.scan()["Items"] if i["SK"].startswith("CASHIER#")]


# --- disable / enable --------------------------------------------------------


def test_disable_blocks_same_token_immediately_then_enable(setup, created, make_client):
    table, cognito, pool_id, owner, rid = setup
    cashier = _cashier_client(make_client, created["sub"], rid)  # token issued BEFORE disable

    r = owner.post(f"/restaurants/{rid}/cashiers/{created['sub']}/disable")
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert cognito.admin_get_user(UserPoolId=pool_id, Username=CASHIER["email"])["Enabled"] is False
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 403

    r = owner.post(f"/restaurants/{rid}/cashiers/{created['sub']}/enable")
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert cognito.admin_get_user(UserPoolId=pool_id, Username=CASHIER["email"])["Enabled"] is True
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 200


def test_cannot_manage_another_restaurants_cashier(setup, created, make_client):
    # owner-sub-2 creates their own restaurant, then tries to touch our cashier through it.
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    other_rid = other.post("/restaurants", json={**NEW, "name": "Other"}).json()["id"]
    for action in ("disable", "enable"):
        assert other.post(f"/restaurants/{other_rid}/cashiers/{created['sub']}/{action}").status_code == 404
    assert other.post(f"/restaurants/{other_rid}/cashiers/{created['sub']}/password", json={"password": "New#Pass1"}).status_code == 404


def test_unknown_cashier_is_404(setup):
    *_, owner, rid = setup
    assert owner.post(f"/restaurants/{rid}/cashiers/nope/disable").status_code == 404


# --- password reset ----------------------------------------------------------


def _login(cognito, pool_id, password):
    client_id = cognito.create_user_pool_client(
        UserPoolId=pool_id, ClientName="t", ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
    )["UserPoolClient"]["ClientId"]
    return cognito.initiate_auth(
        ClientId=client_id, AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": CASHIER["email"], "PASSWORD": password},
    )


def test_reset_password(setup, created):
    table, cognito, pool_id, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/cashiers/{created['sub']}/password", json={"password": "New#Pass1"})
    assert r.status_code == 204
    assert "AuthenticationResult" in _login(cognito, pool_id, "New#Pass1")
    with pytest.raises(cognito.exceptions.NotAuthorizedException):
        _login(cognito, pool_id, CASHIER["password"])


def test_reset_password_weak_is_422(setup, created):
    *_, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/cashiers/{created['sub']}/password", json={"password": "weak"})
    assert r.status_code == 422
