"""What the AI assistant can look up and do (Step 9). Piece 2 exposes these as Strands tools.

All read-only except `draft_cart`, which only BUILDS a draft: nothing is saved and no order is placed. The
customer sees the draft, adds it to their cart and places the order themselves (normal checkout, normal checks).

Rules:
- Reuse the API's services (same data, same opening-hours logic); never call the API over HTTP.
- Return small, JSON-safe dicts (no DynamoDB keys, no Decimals, no owner ids) - the model sees all of it.
- Problems come back as data ({"error": ...}) so the model can explain them; nothing here raises to the model.
- Prices always come from the database. Shown to the model in SAR with VAT included ("25.00").
"""

from dataclasses import dataclass
from typing import Any, get_args

from api import hours
from api.errors import NotFound
from api.models import MAX_RADIUS_KM, Cuisine, DietTag
from api.services import categories, restaurants

MIN_RADIUS_KM = 0.5
MAX_MENU_ITEMS = 60  # keeps the model's input small; real menus are far smaller
MAX_SEARCH_DISHES = 30
MAX_QTY = 20  # same limits as the web cart (web/src/cart/cartLogic.ts) and the order API
MAX_LINES = 20
DIET_TAGS: tuple[str, ...] = get_args(DietTag)
CUISINES: tuple[str, ...] = get_args(Cuisine)


@dataclass(frozen=True)
class Spot:
    """Where the customer is searching from (sent by the browser; the model never invents coordinates)."""

    lat: float
    lng: float


def _sar(halalas: int) -> str:
    return f"{halalas / 100:.2f}"


def _status(r: dict) -> dict[str, Any]:
    if r.get("isPaused"):
        return {"status": "paused"}  # staff stopped new orders for now; no known reopening time
    if r["openNow"]:
        return {"status": "open"}
    return {"status": "closed", "opensAt": hours.opens_at(r["hours"])}


def _restaurant(r: dict) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "nameAr": r["nameAr"],
        "cuisines": list(r.get("cuisines", [])),
        "description": r.get("description", ""),
        "descriptionAr": r.get("descriptionAr", ""),
        "district": r.get("district", ""),
        "city": r.get("city", ""),
        "hours": r["hours"],
        **_status(r),
    }


def _item(i: dict) -> dict[str, Any]:
    calories = int(i.get("calories", 0))
    return {
        "id": i["id"],
        "name": i["name"],
        "nameAr": i["nameAr"],
        "category": i["category"],
        "priceSar": _sar(int(i["priceHalalas"])),
        "calories": calories or None,  # 0 = the owner didn't say
        "dietTags": list(i.get("dietTags", [])),
    }


def _check_cuisine(cuisine: str | None) -> tuple[str | None, dict | None]:
    """Normalised cuisine, or an error listing the real ones (like _check_category)."""
    if not cuisine or not cuisine.strip():
        return None, None
    c = cuisine.strip().lower()
    if c in CUISINES:
        return c, None
    return None, {"error": "unknown_cuisine", "unknown": cuisine, "allowed": list(CUISINES)}


def find_restaurants(
    spot: Spot, radius_km: float = MAX_RADIUS_KM, open_now_only: bool = False, cuisine: str | None = None
) -> dict:
    """Restaurants near the customer's spot, nearest first, each marked open / paused / closed."""
    wanted, err = _check_cuisine(cuisine)
    if err:
        return err
    radius = min(max(float(radius_km), MIN_RADIUS_KM), MAX_RADIUS_KM)
    found = restaurants.near(spot.lat, spot.lng, radius)
    out = [{**_restaurant(r), "distanceKm": float(r["distanceKm"])} for r in found]
    if open_now_only:
        out = [r for r in out if r["status"] == "open"]
    if wanted:
        out = [r for r in out if wanted in r["cuisines"]]
    return {"radiusKm": radius, "count": len(out), "restaurants": out}


def list_categories() -> dict:
    return {"categories": categories.ordered()}


def _load(restaurant_id: str) -> dict | None:
    try:
        return restaurants.get(str(restaurant_id))
    except NotFound:
        return None


def _check_tags(diet_tags: list[str] | None) -> tuple[list[str], dict | None]:
    tags = [t.strip().lower() for t in (diet_tags or []) if t and t.strip()]
    unknown = [t for t in tags if t not in DIET_TAGS]
    if unknown:
        return tags, {"error": "unknown_diet_tags", "unknown": unknown, "allowed": list(DIET_TAGS)}
    return tags, None


def _check_category(category: str | None) -> dict | None:
    """An unknown category is an error listing the real ones (the model often guesses e.g. "Desserts")."""
    if not category or not category.strip():
        return None
    allowed = categories.ordered()
    if category.strip().lower() in {c.lower() for c in allowed}:
        return None
    return {"error": "unknown_category", "unknown": category, "allowed": allowed}


def _matching(
    menu: list[dict],
    category: str | None,
    tags: list[str],
    max_calories: int | None,
    max_price_sar: float | None,
) -> list[dict]:
    """Available dishes that pass every given filter."""
    items = [i for i in menu if i.get("isAvailable", True)]
    if category:
        items = [i for i in items if i["category"].lower() == category.strip().lower()]
    if tags:
        items = [i for i in items if set(tags) <= set(i.get("dietTags", []))]
    if max_calories is not None:
        # Unknown calories (0) can't be shown to fit a calorie limit, so they are left out.
        items = [i for i in items if 0 < int(i.get("calories", 0)) <= max_calories]
    if max_price_sar is not None:
        items = [i for i in items if int(i["priceHalalas"]) <= round(max_price_sar * 100)]
    return items


def get_menu(
    restaurant_id: str,
    category: str | None = None,
    diet_tags: list[str] | None = None,
    max_calories: int | None = None,
    max_price_sar: float | None = None,
) -> dict:
    """The restaurant's available dishes, optionally filtered. All filters must match."""
    r = _load(restaurant_id)
    if r is None:
        return {"error": "restaurant_not_found"}
    tags, err = _check_tags(diet_tags)
    err = err or _check_category(category)
    if err:
        return err
    items = _matching(r["menu"], category, tags, max_calories, max_price_sar)
    return {
        "restaurant": _restaurant(r),
        "count": len(items),
        "truncated": len(items) > MAX_MENU_ITEMS,
        "items": [_item(i) for i in items[:MAX_MENU_ITEMS]],
    }


def search_dishes(
    spot: Spot,
    category: str | None = None,
    diet_tags: list[str] | None = None,
    max_calories: int | None = None,
    max_price_sar: float | None = None,
    open_now_only: bool = False,
    radius_km: float = MAX_RADIUS_KM,
    cuisine: str | None = None,
) -> dict:
    """Matching dishes from EVERY restaurant near the spot, in one call (nearest restaurant first, then cheapest).

    One call instead of find_restaurants + get_menu per restaurant: fewer model round trips, faster replies.
    """
    tags, err = _check_tags(diet_tags)
    err = err or _check_category(category)
    if err:
        return err
    nearby = find_restaurants(spot, radius_km, open_now_only, cuisine)
    if "error" in nearby:
        return nearby
    dishes: list[dict] = []
    for summary in nearby["restaurants"]:
        r = _load(summary["id"])
        if r is None:  # removed between the two reads
            continue
        place = {k: summary[k] for k in ("id", "name", "nameAr", "distanceKm", "status")}
        if "opensAt" in summary:
            place["opensAt"] = summary["opensAt"]
        matches = sorted(_matching(r["menu"], category, tags, max_calories, max_price_sar), key=lambda i: int(i["priceHalalas"]))
        dishes += [{**_item(i), "restaurant": place} for i in matches]
    out = {
        "radiusKm": nearby["radiusKm"],
        "restaurantsSearched": nearby["count"],
        "count": len(dishes),
        "truncated": len(dishes) > MAX_SEARCH_DISHES,
        "dishes": dishes[:MAX_SEARCH_DISHES],
    }
    if not dishes and category and category.strip():
        # The model often turns "lunch"/"dinner" into a category (e.g. Mains) and then finds nothing.
        out["hint"] = "Nothing in this category. Search again WITHOUT category before saying nothing was found."
    return out


def _wanted(items: list[dict]) -> tuple[dict[str, int], list[Any]]:
    """{itemId: total qty} keeping first-seen order, plus any lines that aren't {itemId, qty>=1 int}."""
    wanted: dict[str, int] = {}
    bad: list[Any] = []
    for line in items or []:
        if not isinstance(line, dict):
            bad.append(line)
            continue
        item_id = line.get("itemId") or line.get("item_id")
        qty = line.get("qty", 1)
        if not isinstance(item_id, str) or not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            bad.append(line)
            continue
        wanted[item_id] = wanted.get(item_id, 0) + qty
    return wanted, bad


def draft_cart(restaurant_id: str, items: list[dict]) -> dict:
    """Check a proposed cart against the database and build a draft for the customer to review.

    Refused (with a reason) if the restaurant is unknown, paused or closed, or any line is wrong.
    """
    wanted, bad = _wanted(items)
    if bad:
        return {"error": "invalid_lines", "lines": bad, "hint": "each line is {itemId: string, qty: integer >= 1}"}
    if not wanted:
        return {"error": "empty"}
    if len(wanted) > MAX_LINES:
        return {"error": "too_many_lines", "max": MAX_LINES}
    too_many = [i for i, q in wanted.items() if q > MAX_QTY]
    if too_many:
        return {"error": "qty_too_high", "itemIds": too_many, "maxQty": MAX_QTY}

    r = _load(restaurant_id)
    if r is None:
        return {"error": "restaurant_not_found"}
    status = _status(r)
    if status["status"] != "open":
        return {"error": status["status"], "restaurant": r["name"], "restaurantAr": r["nameAr"], **status}

    menu = {i["id"]: i for i in r["menu"]}
    unknown = [i for i in wanted if i not in menu]
    if unknown:
        return {"error": "unknown_items", "itemIds": unknown}
    unavailable = [menu[i]["name"] for i in wanted if not menu[i].get("isAvailable", True)]
    if unavailable:
        return {"error": "unavailable_items", "items": unavailable}

    lines = [
        {
            "itemId": i,
            "name": menu[i]["name"],
            "nameAr": menu[i]["nameAr"],
            "priceHalalas": int(menu[i]["priceHalalas"]),
            "qty": q,
        }
        for i, q in wanted.items()
    ]
    total = sum(line["priceHalalas"] * line["qty"] for line in lines)
    return {
        "draft": {
            "restaurant": {"id": r["id"], "name": r["name"], "nameAr": r["nameAr"]},
            "lines": lines,
            "totalHalalas": total,
        },
        "totalSar": _sar(total),
        "note": "Draft only: the customer must review it, add it to the cart and place the order.",
    }
