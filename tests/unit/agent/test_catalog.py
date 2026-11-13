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
    assert set(r) == {"id", "name", "nameAr", "cuisines", "description", "descriptionAr", "district", "city", "hours", "status", "distanceKm"}
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
    res = catalog.get_menu(shop["rid"], diet_tags=["paleo"])
    assert res["error"] == "unknown_diet_tags" and res["unknown"] == ["paleo"] and "vegan" in res["allowed"]


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


# --- search_dishes -----------------------------------------------------------


def test_search_dishes_across_restaurants(shop):
    res = catalog.search_dishes(HERE, max_price_sar=20)
    assert res["restaurantsSearched"] >= 2
    places = {d["restaurant"]["name"] for d in res["dishes"]}
    assert NEW["name"] in places and len(places) >= 2  # the shop + seeded restaurants nearby
    assert all(float(d["priceSar"]) <= 20 for d in res["dishes"])
    fries = next(d for d in res["dishes"] if d["id"] == shop["fries"])
    assert fries["restaurant"] == {"id": shop["rid"], "name": NEW["name"], "nameAr": NEW["nameAr"],
                                   "distanceKm": 0.0, "status": "open"}
    dists = [d["restaurant"]["distanceKm"] for d in res["dishes"]]
    assert dists == sorted(dists)  # nearest restaurant first
    json.dumps(res)


def test_search_dishes_cheapest_first_within_a_restaurant(shop):
    mine_only = [d for d in catalog.search_dishes(HERE)["dishes"] if d["restaurant"]["id"] == shop["rid"]]
    assert [d["id"] for d in mine_only] == [shop["fries"], shop["burger"]]


def test_search_dishes_marks_closed_and_open_now_only(shop, clock):
    clock.set(at(11))  # shop opens 16:00
    fries = next(d for d in catalog.search_dishes(HERE)["dishes"] if d["id"] == shop["fries"])
    assert fries["restaurant"]["status"] == "closed" and fries["restaurant"]["opensAt"] == "16:00"
    assert shop["fries"] not in [d["id"] for d in catalog.search_dishes(HERE, open_now_only=True)["dishes"]]


def test_search_dishes_filters_and_hidden(shop):
    shop["owner"].patch(f"/restaurants/{shop['rid']}/menu/{shop['fries']}", json={"isAvailable": False})
    ids = [d["id"] for d in catalog.search_dishes(HERE, category="Sides")["dishes"]]
    assert shop["fries"] not in ids
    assert catalog.search_dishes(HERE, diet_tags=["paleo"])["error"] == "unknown_diet_tags"
    veg = catalog.search_dishes(HERE, diet_tags=["vegetarian"])["dishes"]
    assert veg and all("vegetarian" in d["dietTags"] for d in veg)


def test_search_dishes_is_capped(shop, monkeypatch):
    monkeypatch.setattr(catalog, "MAX_SEARCH_DISHES", 2)
    res = catalog.search_dishes(HERE)
    assert len(res["dishes"]) == 2 and res["truncated"] is True and res["count"] > 2


def test_search_dishes_nothing_far_away(shop):
    assert catalog.search_dishes(Spot(24.7136, 46.6753))["dishes"] == []


@pytest.mark.parametrize("call", ["menu", "search"])
def test_unknown_category_lists_the_real_ones(shop, call):
    res = catalog.get_menu(shop["rid"], category="Desserts") if call == "menu" else catalog.search_dishes(HERE, category="Desserts")
    assert res["error"] == "unknown_category" and res["unknown"] == "Desserts" and "Sweets" in res["allowed"]


def test_category_match_ignores_case(shop):
    assert "error" not in catalog.search_dishes(HERE, category="sweets")


# --- cuisines ------------------------------------------------------------------


def test_cuisine_filter_on_restaurants_and_dishes(shop):
    shop["owner"].patch(f"/restaurants/{shop['rid']}", json={"cuisines": ["burgers"], "descriptionAr": "برجر سماش."})
    burgers = catalog.find_restaurants(HERE, cuisine=" Burgers ")
    assert shop["rid"] in [r["id"] for r in burgers["restaurants"]]
    assert all("burgers" in r["cuisines"] for r in burgers["restaurants"])
    assert mine(burgers, shop)["descriptionAr"] == "برجر سماش."
    assert shop["rid"] not in [r["id"] for r in catalog.find_restaurants(HERE, cuisine="indian")["restaurants"]]
    dishes = catalog.search_dishes(HERE, cuisine="burgers")["dishes"]
    assert {shop["fries"], shop["burger"]} <= {d["id"] for d in dishes}


@pytest.mark.parametrize("call", ["find", "search"])
def test_unknown_cuisine_lists_the_real_ones(shop, call):
    res = catalog.find_restaurants(HERE, cuisine="mexican") if call == "find" else catalog.search_dishes(HERE, cuisine="mexican")
    assert res["error"] == "unknown_cuisine" and "pizza" in res["allowed"]


def test_new_diet_tags_are_accepted(shop):
    add_dish(shop, name="Keto Bowl", nameAr="وعاء كيتو", category="Bowls", priceHalalas=3200, dietTags=["keto", "low_carb"])
    found = catalog.search_dishes(HERE, diet_tags=["keto"])["dishes"]
    assert "Keto Bowl" in [d["name"] for d in found]


def test_empty_search_with_a_category_hints_to_retry_without_it(shop):
    res = catalog.search_dishes(HERE, category="Mains", diet_tags=["contains_seafood"], max_price_sar=1)
    assert res["count"] == 0 and "WITHOUT category" in res["hint"]
    assert "hint" not in catalog.search_dishes(HERE, diet_tags=["contains_seafood"], max_price_sar=1)
