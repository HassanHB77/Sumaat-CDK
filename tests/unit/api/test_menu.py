import pytest

from api.handler import app
from scripts.seed import seed
from tests.unit.api.conftest import customer_claims, owner_claims
from tests.unit.api.test_restaurants import NEW

ITEM = {
    "name": "Camel Burger",
    "nameAr": "برجر لحم جمل",
    "category": "Mains",
    "priceHalalas": 3900,
    "calories": 780,
    "dietTags": ["high_protein"],
}


@pytest.fixture
def setup(ddb, make_client):
    """Seeded table (incl. categories) + a restaurant owned by owner-sub-1."""
    table, *_ = ddb
    seed(table)
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]
    return table, owner, rid


@pytest.fixture
def public(make_client):
    return make_client(app)


def _menu(public, rid):
    return public.get(f"/restaurants/{rid}").json()["menu"]


# --- GET /categories ---------------------------------------------------------


def test_categories_public_and_sorted(setup, public):
    r = public.get("/categories")
    assert r.status_code == 200
    cats = r.json()["categories"]
    assert "Mains" in cats
    assert cats == sorted(cats)


def test_categories_empty_when_not_set_up(ddb, public):
    assert public.get("/categories").json() == {"categories": []}


# --- POST /restaurants/{id}/menu ---------------------------------------------


def test_owner_adds_item_and_customers_see_it(setup, public):
    _, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/menu", json=ITEM)
    assert r.status_code == 201
    body = r.json()
    assert body["restaurantId"] == rid
    assert body["isAvailable"] is True
    assert body["priceHalalas"] == 3900

    menu = _menu(public, rid)
    assert [i["name"] for i in menu] == ["Camel Burger"]
    assert isinstance(menu[0]["priceHalalas"], int)


def test_duplicate_diet_tags_are_collapsed(setup):
    _, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/menu", json={**ITEM, "dietTags": ["spicy", "spicy", "vegan"]})
    assert r.json()["dietTags"] == ["spicy", "vegan"]


@pytest.mark.parametrize(
    "change",
    [
        {"priceHalalas": 15.5},
        {"priceHalalas": "1500"},
        {"priceHalalas": 0},
        {"calories": -1},
        {"dietTags": ["keto"]},
        {"restaurantId": "someone-else"},
        {"name": ""},
    ],
)
def test_create_validation(setup, change):
    _, owner, rid = setup
    assert owner.post(f"/restaurants/{rid}/menu", json={**ITEM, **change}).status_code == 422


def test_unknown_category_is_422_with_allowed_list(setup):
    _, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/menu", json={**ITEM, "category": "Pizza"})
    assert r.status_code == 422
    assert "Unknown category 'Pizza'" in r.json()["detail"]
    assert "Mains" in r.json()["detail"]


def test_new_category_from_cli_works_without_code_change(setup):
    table, owner, rid = setup
    assert owner.post(f"/restaurants/{rid}/menu", json={**ITEM, "category": "Soups"}).status_code == 422
    table.update_item(  # same as the aws CLI command in api/services/categories.py
        Key={"PK": "CONFIG", "SK": "CATEGORIES"},
        UpdateExpression="ADD categories :c",
        ExpressionAttributeValues={":c": {"Soups"}},
    )
    assert owner.post(f"/restaurants/{rid}/menu", json={**ITEM, "category": "Soups"}).status_code == 201


def test_categories_missing_is_clear_422(ddb, make_client):
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]  # no seed -> no CONFIG item
    r = owner.post(f"/restaurants/{rid}/menu", json=ITEM)
    assert r.status_code == 422
    assert "not set up" in r.json()["detail"]


def test_other_owner_cannot_add(setup, make_client):
    _, _, rid = setup
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    assert other.post(f"/restaurants/{rid}/menu", json=ITEM).status_code == 403


def test_add_to_unknown_restaurant_is_404(setup):
    _, owner, _ = setup
    assert owner.post("/restaurants/nope/menu", json=ITEM).status_code == 404


@pytest.mark.parametrize("claims, code", [(None, 401), (customer_claims(), 403)])
def test_add_requires_owner(setup, make_client, claims, code):
    _, _, rid = setup
    assert make_client(app, claims).post(f"/restaurants/{rid}/menu", json=ITEM).status_code == code


# --- PATCH /restaurants/{id}/menu/{itemId} -----------------------------------


@pytest.fixture
def item(setup):
    _, owner, rid = setup
    return owner.post(f"/restaurants/{rid}/menu", json=ITEM).json()


def test_hide_item_still_listed_as_unavailable(setup, item, public):
    _, owner, rid = setup
    r = owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"isAvailable": False})
    assert r.status_code == 200
    menu = _menu(public, rid)
    assert [(i["id"], i["isAvailable"]) for i in menu] == [(item["id"], False)]
    # and back again
    assert owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"isAvailable": True}).json()["isAvailable"]


def test_change_price_keeps_other_fields(setup, item, monkeypatch):
    _, owner, rid = setup
    monkeypatch.setattr("api.services.menu.now_iso", lambda: "2099-01-01T00:00:00Z")
    r = owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"priceHalalas": 4200})
    assert r.status_code == 200
    assert r.json()["priceHalalas"] == 4200
    assert r.json()["name"] == ITEM["name"]


def test_clear_diet_tags(setup, item):
    _, owner, rid = setup
    r = owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"dietTags": []})
    assert r.json()["dietTags"] == []


def test_patch_unknown_category_is_422(setup, item):
    _, owner, rid = setup
    assert owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"category": "Pizza"}).status_code == 422


def test_patch_unknown_item_is_404_and_creates_nothing(setup):
    table, owner, rid = setup
    r = owner.patch(f"/restaurants/{rid}/menu/does-not-exist", json={"priceHalalas": 100})
    assert r.status_code == 404
    assert "Item" not in table.get_item(Key={"PK": f"RESTAURANT#{rid}", "SK": "ITEM#does-not-exist"})


def test_patch_empty_is_422(setup, item):
    _, owner, rid = setup
    assert owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={}).status_code == 422


def test_patch_float_price_is_422(setup, item):
    _, owner, rid = setup
    assert owner.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"priceHalalas": 42.5}).status_code == 422


def test_other_owner_cannot_patch(setup, item, make_client):
    _, _, rid = setup
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    assert other.patch(f"/restaurants/{rid}/menu/{item['id']}", json={"priceHalalas": 1}).status_code == 403


def test_owner_can_edit_seeded_items_of_own_restaurant_only(setup, make_client, public):
    # Seeded restaurants have no ownerSub in this test (seed ran without cognito) -> nobody owns them.
    from scripts.seed import stable_id

    _, owner, _ = setup
    nakhla = stable_id("restaurant", "nakhla-kitchen")
    item_id = _menu(public, nakhla)[0]["id"]
    assert owner.patch(f"/restaurants/{nakhla}/menu/{item_id}", json={"isAvailable": False}).status_code == 403
