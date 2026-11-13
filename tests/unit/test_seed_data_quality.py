"""The demo restaurants and menus (scripts/seed_restaurants.py) are complete, bilingual and valid.

Also keeps the fixed lists in sync with the website: diet tags, cuisines and categories each need EN + AR labels.
"""

import re
from pathlib import Path
from typing import get_args

import pytest

from api.geo import distance_km
from api.models import Cuisine, DietTag
from scripts.seed_data import CATEGORIES, RESTAURANTS

ROOT = Path(__file__).resolve().parents[2]
ARABIC = re.compile(r"[؀-ۿ]")
HOURS = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_SPOT = (25.38, 49.588)  # web/src/lib/geo.ts DEFAULT_SPOT (Al-Hofuf)
DIET_TAGS = set(get_args(DietTag))
CUISINES = set(get_args(Cuisine))
ALL_ITEMS = [(r, i) for r in RESTAURANTS for i in r["items"]]


def test_slugs_and_accounts_are_unique():
    assert len({r["slug"] for r in RESTAURANTS}) == len(RESTAURANTS)
    emails = [r[who]["email"] for r in RESTAURANTS for who in ("owner", "cashier")]
    assert len(set(emails)) == len(emails)
    phones = [r[who]["phone"] for r in RESTAURANTS for who in ("owner", "cashier")]
    assert len(set(phones)) == len(phones)
    for r in RESTAURANTS:
        slugs = [i["slug"] for i in r["items"]]
        assert len(set(slugs)) == len(slugs), r["slug"]


@pytest.mark.parametrize("r", RESTAURANTS, ids=lambda r: r["slug"])
def test_restaurant_is_complete_and_nearby(r):
    assert ARABIC.search(r["nameAr"]) and ARABIC.search(r["descriptionAr"])
    assert r["description"] and not ARABIC.search(r["description"])
    assert 1 <= len(r["cuisines"]) <= 3 and set(r["cuisines"]) <= CUISINES
    assert HOURS.match(r["hours"])
    assert distance_km(r["lat"], r["lng"], *DEFAULT_SPOT) <= 4  # shows up in "near me" without moving the map
    assert 10 <= len(r["items"]) <= 14


@pytest.mark.parametrize("pair", ALL_ITEMS, ids=lambda p: f"{p[0]['slug']}/{p[1]['slug']}")
def test_dish_is_valid(pair):
    _, i = pair
    assert i["name"] and not ARABIC.search(i["name"]) and ARABIC.search(i["nameAr"])
    assert i["category"] in CATEGORIES
    assert isinstance(i["priceHalalas"], int) and i["priceHalalas"] > 0
    assert isinstance(i["calories"], int) and 0 <= i["calories"] <= 10_000
    assert set(i["dietTags"]) <= DIET_TAGS and len(set(i["dietTags"])) == len(i["dietTags"])
    tags = set(i["dietTags"])
    assert not ({"vegan", "contains_seafood"} <= tags), "vegan dish can't contain seafood"
    assert not ({"nut_free", "contains_nuts"} <= tags)


def test_every_cuisine_category_and_tag_is_used():
    assert CUISINES == {c for r in RESTAURANTS for c in r["cuisines"]}
    assert DIET_TAGS == {t for _, i in ALL_ITEMS for t in i["dietTags"]}
    assert set(CATEGORIES) == {i["category"] for _, i in ALL_ITEMS}


def _ts_list(name: str) -> set[str]:
    text = (ROOT / "web/src/api/types.ts").read_text()
    body = re.search(rf"export const {name}\b[^=]*=\s*\[(.*?)\]", text, re.S).group(1)
    return set(re.findall(r"'([a-z_]+)'", body))


def test_web_lists_match_the_api():
    assert _ts_list("DIET_TAGS") == DIET_TAGS
    assert _ts_list("CUISINES") == CUISINES


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_web_has_labels_for_every_value(lang):
    text = (ROOT / f"web/src/i18n/{lang}.ts").read_text()
    keys = set(re.findall(r"'((?:cat|diet|cuisine)\.[A-Za-z_]+)'\s*:", text))
    wanted = {f"cat.{c}" for c in CATEGORIES} | {f"diet.{t}" for t in DIET_TAGS} | {f"cuisine.{c}" for c in CUISINES}
    assert wanted <= keys, sorted(wanted - keys)
