"""agent/catalog.py: what the AI assistant can look up, and how it drafts a cart."""

import json
from datetime import datetime

import pytest

from agent import catalog
from agent.catalog import Spot
from api.hours import RIYADH
from tests.unit.api.conftest import NEW

HERE = Spot(NEW["lat"], NEW["lng"])  # the shop's own location


def at(h, m=0, day=12):
    return datetime(2026, 11, day, h, m, tzinfo=RIYADH)


def mine(result, shop):
    return next(r for r in result["restaurants"] if r["id"] == shop["rid"])


def add_dish(shop, **dish):
    return shop["owner"].post(f"/restaurants/{shop['rid']}/menu", json=dish).json()["id"]


# --- find_restaurants --------------------------------------------------------


def test_find_marks_open_restaurant(shop):
    res = catalog.find_restaurants(HERE)
    r = mine(res, shop)
    assert r["status"] == "open" and "opensAt" not in r
    assert r["distanceKm"] == 0.0 and r["name"] == NEW["name"] and r["nameAr"] == NEW["nameAr"]
    assert res["radiusKm"] == 4.0
    dists = [x["distanceKm"] for x in res["restaurants"]]
    assert dists == sorted(dists)


def test_find_shows_closed_with_opening_time(shop, clock):
    clock.set(at(11))  # shop opens 16:00
    r = mine(catalog.find_restaurants(HERE), shop)
    assert r["status"] == "closed" and r["opensAt"] == "16:00"


def test_find_marks_paused(shop):
    shop["owner"].post(f"/restaurants/{shop['rid']}/pause")
    r = mine(catalog.find_restaurants(HERE), shop)
    assert r == {**r, "status": "paused"} and "opensAt" not in r


def test_find_open_now_only(shop, clock):
    clock.set(at(11))
    res = catalog.find_restaurants(HERE, open_now_only=True)
    assert shop["rid"] not in [r["id"] for r in res["restaurants"]]
    assert all(r["status"] == "open" for r in res["restaurants"])
    assert res["count"] == len(res["restaurants"])


@pytest.mark.parametrize("asked, used", [(10, 4.0), (0, 0.5), (-3, 0.5), (2.5, 2.5)])
def test_find_radius_is_kept_in_range(shop, asked, used):
    assert catalog.find_restaurants(HERE, radius_km=asked)["radiusKm"] == used


def test_find_nothing_far_away(shop):
    assert catalog.find_restaurants(Spot(24.7136, 46.6753)) == {"radiusKm": 4.0, "count": 0, "restaurants": []}


def test_find_hides_internal_fields_and_is_json(shop):
    r = mine(catalog.find_restaurants(HERE), shop)
    assert set(r) == {"id", "name", "nameAr", "district", "city", "hours", "status", "distanceKm"}
    json.dumps(catalog.find_restaurants(HERE))  # no Decimals


# --- get_menu ----------------------------------------------------------------


def test_menu_lists_available_items_in_sar(shop):
    res = catalog.get_menu(shop["rid"])
    assert res["restaurant"]["id"] == shop["rid"] and res["restaurant"]["status"] == "open"
    burger = next(i for i in res["items"] if i["id"] == shop["burger"])
    assert burger == {
        "id": shop["burger"],
        "name": "Smash Burger",
        "nameAr": "برجر",
        "category": "Mains",
        "priceSar": "25.00",
        "calories": None,  # not given by the owner
        "dietTags": [],
    }
    assert res["count"] == 2 and res["truncated"] is False
    json.dumps(res)


def test_menu_hides_unavailable(shop):
    shop["owner"].patch(f"/restaurants/{shop['rid']}/menu/{shop['fries']}", json={"isAvailable": False})
    assert [i["id"] for i in catalog.get_menu(shop["rid"])["items"]] == [shop["burger"]]


def test_menu_unknown_restaurant(shop):
    assert catalog.get_menu("nope") == {"error": "restaurant_not_found"}


def test_menu_filters(shop):
    salad = add_dish(shop, name="Green Salad", nameAr="سلطة", category="Sides", priceHalalas=1500,
                     calories=180, dietTags=["vegetarian", "vegan"])
    halloumi = add_dish(shop, name="Halloumi Wrap", nameAr="لفافة حلوم", category="Mains", priceHalalas=2200,
                        calories=520, dietTags=["vegetarian"])

    def ids(**f):
        return [i["id"] for i in catalog.get_menu(shop["rid"], **f)["items"]]

    assert set(ids(diet_tags=["vegetarian"])) == {salad, halloumi}
    assert ids(diet_tags=["Vegetarian", "vegan"]) == [salad]  # all tags must match; case-insensitive
    assert set(ids(category="mains")) == {shop["burger"], halloumi}
    assert set(ids(max_price_sar=22)) == {shop["fries"], salad, halloumi}  # 22.00 SAR included
    assert ids(max_price_sar=8.99) == []
    assert ids(max_calories=500) == [salad]  # unknown calories (burger, fries) left out
    assert ids(category="Mains", diet_tags=["vegetarian"], max_price_sar=30) == [halloumi]


def test_menu_unknown_diet_tag(shop):
    res = catalog.get_menu(shop["rid"], diet_tags=["keto"])
    assert res["error"] == "unknown_diet_tags" and res["unknown"] == ["keto"] and "vegan" in res["allowed"]


def test_menu_is_capped(shop, monkeypatch):
    monkeypatch.setattr(catalog, "MAX_MENU_ITEMS", 1)
    res = catalog.get_menu(shop["rid"])
    assert res["count"] == 2 and res["truncated"] is True and len(res["items"]) == 1


def test_list_categories(shop):
    cats = catalog.list_categories()["categories"]
    assert "Mains" in cats and "Sides" in cats


# --- draft_cart --------------------------------------------------------------


def test_draft_uses_database_prices_and_merges_repeats(shop):
    res = catalog.draft_cart(
        shop["rid"],
        [{"itemId": shop["burger"], "qty": 2}, {"itemId": shop["fries"], "qty": 1}, {"item_id": shop["burger"]}],
    )
    draft = res["draft"]
    assert draft["restaurant"] == {"id": shop["rid"], "name": NEW["name"], "nameAr": NEW["nameAr"]}
    assert draft["lines"] == [
        {"itemId": shop["burger"], "name": "Smash Burger", "nameAr": "برجر", "priceHalalas": 2500, "qty": 3},
        {"itemId": shop["fries"], "name": "Fries", "nameAr": "بطاطس", "priceHalalas": 900, "qty": 1},
    ]
    assert draft["totalHalalas"] == 3 * 2500 + 900 and res["totalSar"] == "84.00"
    json.dumps(res)


def test_draft_refused_when_closed(shop, clock):
    clock.set(at(11))
    res = catalog.draft_cart(shop["rid"], [{"itemId": shop["burger"], "qty": 1}])
    assert res == {"error": "closed", "status": "closed", "opensAt": "16:00",
                   "restaurant": NEW["name"], "restaurantAr": NEW["nameAr"]}


@pytest.mark.parametrize("when, ok", [(at(1, 59, 13), True), (at(2, 0, 13), False), (at(16, 0), True)])
def test_draft_follows_past_midnight_hours(shop, clock, when, ok):
    clock.set(when)  # 16:00-02:00
    res = catalog.draft_cart(shop["rid"], [{"itemId": shop["burger"], "qty": 1}])
    assert ("draft" in res) is ok


def test_draft_refused_when_paused(shop):
    shop["owner"].post(f"/restaurants/{shop['rid']}/pause")
    res = catalog.draft_cart(shop["rid"], [{"itemId": shop["burger"], "qty": 1}])
    assert res["error"] == "paused" and "opensAt" not in res


def test_draft_refusals(shop):
    rid, burger = shop["rid"], shop["burger"]
    assert catalog.draft_cart("nope", [{"itemId": burger, "qty": 1}]) == {"error": "restaurant_not_found"}
    assert catalog.draft_cart(rid, []) == {"error": "empty"}
    assert catalog.draft_cart(rid, [{"itemId": "x", "qty": 1}]) == {"error": "unknown_items", "itemIds": ["x"]}
    assert catalog.draft_cart(rid, [{"itemId": burger, "qty": 21}])["error"] == "qty_too_high"
    assert catalog.draft_cart(rid, [{"itemId": burger, "qty": 15}, {"itemId": burger, "qty": 6}])["error"] == (
        "qty_too_high"  # 21 after merging
    )
    for bad in ({"itemId": burger, "qty": 0}, {"itemId": burger, "qty": "2"}, {"itemId": burger, "qty": True},
                {"qty": 1}, "burger"):
        assert catalog.draft_cart(rid, [bad])["error"] == "invalid_lines"
    many = [{"itemId": f"i{n}", "qty": 1} for n in range(21)]
    assert catalog.draft_cart(rid, many) == {"error": "too_many_lines", "max": 20}


def test_draft_refuses_hidden_dish(shop):
    shop["owner"].patch(f"/restaurants/{shop['rid']}/menu/{shop['fries']}", json={"isAvailable": False})
    res = catalog.draft_cart(shop["rid"], [{"itemId": shop["fries"], "qty": 1}])
    assert res == {"error": "unavailable_items", "items": ["Fries"]}


def test_dish_from_another_restaurant_is_unknown(shop):
    nearby = catalog.find_restaurants(HERE)["restaurants"]
    nakhla = next(r for r in nearby if r["name"] == "Nakhla Kitchen")  # seeded, open 12:00-23:30
    assert nakhla["status"] == "open"
    res = catalog.draft_cart(nakhla["id"], [{"itemId": shop["burger"], "qty": 1}])
    assert res == {"error": "unknown_items", "itemIds": [shop["burger"]]}
