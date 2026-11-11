import pytest

from api.handler import app
from scripts.seed import seed, stable_id
from tests.unit.api.conftest import customer_claims, owner_claims

NAKHLA = {"lat": 25.3797, "lng": 49.5867}
NAKHLA_ID = stable_id("restaurant", "nakhla-kitchen")

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


@pytest.fixture
def seeded(ddb):
    table, *_ = ddb
    seed(table)  # 3 demo restaurants, no owners (seed only links owners when given cognito)
    return ddb


@pytest.fixture
def public(make_client):
    return make_client(app)


@pytest.fixture
def owner(make_client):
    return make_client(app, owner_claims())


# --- GET /restaurants (near me, public) --------------------------------------


def test_near_me_sorted_nearest_first(seeded, public):
    r = public.get("/restaurants", params={**NAKHLA, "radiusKm": 2})
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert names == ["Nakhla Kitchen", "Qaisariya Grill"]
    assert r.json()[0]["distanceKm"] == 0


def test_near_me_reaches_into_neighbouring_cell(seeded, public):
    r = public.get("/restaurants", params={**NAKHLA, "radiusKm": 4})
    assert [x["name"] for x in r.json()] == ["Nakhla Kitchen", "Qaisariya Grill", "Mubarraz Dates & Coffee"]


def test_near_me_far_away_is_empty(seeded, public):
    r = public.get("/restaurants", params={"lat": 24.7136, "lng": 46.6753})  # Riyadh
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {**NAKHLA, "radiusKm": 4.5},
        {**NAKHLA, "radiusKm": 0},
        {"lat": 200, "lng": 49.5},
        {"lng": 49.5},
    ],
)
def test_near_me_validation(seeded, public, params):
    assert public.get("/restaurants", params=params).status_code == 422


def test_near_me_hides_internal_fields(seeded, public):
    r = public.get("/restaurants", params=NAKHLA)
    for key in ("PK", "SK", "GSI1PK", "ownerSub", "geohash"):
        assert key not in r.json()[0]


# --- GET /restaurants/{id} (public) ------------------------------------------


def test_get_seeded_restaurant_contract(seeded, public):
    """Contract: what scripts/seed.py writes is exactly what the API can read."""
    r = public.get(f"/restaurants/{NAKHLA_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Nakhla Kitchen"
    assert body["lat"] == 25.3797
    assert len(body["menu"]) == 6
    assert all(isinstance(i["priceHalalas"], int) for i in body["menu"])
    assert [i["category"] for i in body["menu"]] == sorted(i["category"] for i in body["menu"])
    assert "ownerSub" not in body and "seq" not in body


def test_get_unknown_is_404(seeded, public):
    assert public.get("/restaurants/does-not-exist").status_code == 404


# --- POST /restaurants (owner) -----------------------------------------------


def test_create_writes_profile_lock_and_cognito_attr(ddb, owner, public):
    table, cognito, pool_id = ddb
    r = owner.post("/restaurants", json=NEW)
    assert r.status_code == 201
    rid = r.json()["id"]
    assert r.json()["isPaused"] is False
    assert isinstance(r.json()["openNow"], bool)

    pk = f"RESTAURANT#{rid}"
    profile = table.get_item(Key={"PK": pk, "SK": "PROFILE"})["Item"]
    assert profile["ownerSub"] == "owner-sub-1"
    assert profile["GSI1PK"] == "GEO#the22"
    assert "Item" not in table.get_item(Key={"PK": pk, "SK": "COUNTER"})  # daily counters are created by orders
    assert table.get_item(Key={"PK": "OWNER#owner-sub-1", "SK": "RESTAURANT"})["Item"]["restaurantId"] == rid

    attrs = cognito.admin_get_user(UserPoolId=pool_id, Username="owner-sub-1")["UserAttributes"]
    assert {"Name": "custom:restaurantId", "Value": rid} in attrs

    # Shows up for customers straight away.
    near = public.get("/restaurants", params={"lat": NEW["lat"], "lng": NEW["lng"]}).json()
    assert rid in [x["id"] for x in near]


def test_second_restaurant_for_same_owner_is_409(ddb, owner):
    assert owner.post("/restaurants", json=NEW).status_code == 201
    r = owner.post("/restaurants", json={**NEW, "name": "Second"})
    assert r.status_code == 409
    table, *_ = ddb
    assert sum(1 for i in table.scan()["Items"] if i["SK"] == "PROFILE") == 1  # nothing half-written


def test_create_survives_cognito_failure(ddb, make_client):
    # A business user that doesn't exist in the pool: Cognito update fails, restaurant is still created.
    r = make_client(app, owner_claims(sub="ghost-owner")).post("/restaurants", json=NEW)
    assert r.status_code == 201


@pytest.mark.parametrize(
    "claims, code",
    [
        (None, 401),
        (customer_claims(), 403),
    ],
)
def test_create_requires_owner(ddb, make_client, claims, code):
    assert make_client(app, claims).post("/restaurants", json=NEW).status_code == code


def test_cashier_cannot_create(ddb, make_client):
    r = make_client(app, owner_claims(sub="cashier-sub-1", groups="cashier")).post("/restaurants", json=NEW)
    assert r.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {**NEW, "ownerSub": "someone-else"},  # unknown field
        {**NEW, "hours": "9-5"},
        {**NEW, "name": ""},
        {**NEW, "lat": 91},
        {k: v for k, v in NEW.items() if k != "city"},
    ],
)
def test_create_validation(ddb, owner, body):
    assert owner.post("/restaurants", json=body).status_code == 422


# --- PATCH /restaurants/{id} (owner who owns it) ------------------------------


@pytest.fixture
def created(ddb, owner):
    return owner.post("/restaurants", json=NEW).json()


def test_owner_can_rename_and_change_hours(created, owner, monkeypatch):
    monkeypatch.setattr("api.services.restaurants.now_iso", lambda: "2099-01-01T00:00:00Z")
    r = owner.patch(f"/restaurants/{created['id']}", json={"name": "Renamed", "hours": "10:00-22:00"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["hours"] == "10:00-22:00"
    assert r.json()["updatedAt"] == "2099-01-01T00:00:00Z"
    assert r.json()["createdAt"] == created["createdAt"]
    assert r.json()["nameAr"] == NEW["nameAr"]  # untouched


def test_other_owner_gets_403(created, make_client):
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    assert other.patch(f"/restaurants/{created['id']}", json={"name": "Mine now"}).status_code == 403


def test_patch_unknown_is_404(created, owner):
    assert owner.patch("/restaurants/nope", json={"name": "x"}).status_code == 404


def test_patch_empty_body_is_422(created, owner):
    assert owner.patch(f"/restaurants/{created['id']}", json={}).status_code == 422


def test_patch_cannot_set_owner(created, owner):
    assert owner.patch(f"/restaurants/{created['id']}", json={"ownerSub": "x"}).status_code == 422


def test_moving_restaurant_updates_geo_index(ddb, created, owner, public):
    table, *_ = ddb
    rid = created["id"]
    # Move to Al-Mubarraz (neighbouring cell).
    r = owner.patch(f"/restaurants/{rid}", json={"lat": 25.4086, "lng": 49.5823})
    assert r.status_code == 200
    profile = table.get_item(Key={"PK": f"RESTAURANT#{rid}", "SK": "PROFILE"})["Item"]
    assert profile["GSI1PK"] == "GEO#the28"
    assert profile["geohash"].startswith("the28")
    near = public.get("/restaurants", params={"lat": 25.4086, "lng": 49.5823, "radiusKm": 0.5}).json()
    assert [x["id"] for x in near] == [rid]


def test_patch_no_longer_accepts_is_open(created, owner):
    # Open/closed is now automatic (hours) + pause/resume; the old flag is rejected.
    assert owner.patch(f"/restaurants/{created['id']}", json={"isOpen": False}).status_code == 422
