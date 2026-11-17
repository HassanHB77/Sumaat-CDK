"""Order statistics for one restaurant: owner numbers, the owner AI, "usually ready in" and "Popular".

Rules (decided with the product owner):
- Sales (money, dish quantities) count SERVED orders only: that is money actually taken at the counter.
- Order counts also report open, rejected and cancelled orders separately.
- Prep time = ACCEPTED -> READY_FOR_PICKUP, in minutes.
- Orders marked `statsExcluded` (old smoke-test orders) are ignored.

Privacy: `load_orders` asks DynamoDB for non-personal fields only (no customer name, phone, email or note), so
nothing here can leak customer data. The owner AI's IAM role is limited to the same field list.
"""

import time as _time
from collections import Counter
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any

from boto3.dynamodb.conditions import Key

from api import aws
from api import hours as _hours
from api.hours import RIYADH

# The only order fields stats ever read (the owner AI's IAM policy allows exactly these on GSI1).
STATS_FIELDS = ("id", "status", "createdAt", "businessDate", "totalHalalas", "items", "statusHistory",
                "statsExcluded", "GSI1PK", "GSI1SK")
OPEN = ("PLACED", "ACCEPTED", "READY_FOR_PICKUP")


def load_orders(rid: str, start: str, end: str, table=None) -> list[dict]:
    """The restaurant's orders created in [start, end) (UTC ISO), non-personal fields only, without excluded ones."""
    table = table or aws.table()
    names = {f"#f{i}": f for i, f in enumerate(STATS_FIELDS)}
    kwargs: dict[str, Any] = {
        "IndexName": "GSI1",
        "KeyConditionExpression": Key("GSI1PK").eq(f"RORDERS#{rid}") & Key("GSI1SK").between(start, end),
        "ProjectionExpression": ", ".join(names),
        "ExpressionAttributeNames": names,
    }
    out: list[dict] = []
    while True:
        page = table.query(**kwargs)
        out += [o for o in page["Items"] if o["GSI1SK"] < end and not o.get("statsExcluded")]
        if "LastEvaluatedKey" not in page:
            return out
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _served(orders: list[dict]) -> list[dict]:
    return [o for o in orders if o["status"] == "SERVED"]


def _at(order: dict, status: str) -> datetime | None:
    entry = next((h for h in order.get("statusHistory", []) if h.get("status") == status), None)
    return datetime.fromisoformat(entry["at"].replace("Z", "+00:00")) if entry else None


def summary(orders: list[dict]) -> dict:
    by_status = Counter(o["status"] for o in orders)
    served = _served(orders)
    sales = sum(int(o["totalHalalas"]) for o in served)
    return {
        "orders": len(orders),
        "served": by_status["SERVED"],
        "open": sum(by_status[s] for s in OPEN),
        "rejected": by_status["REJECTED"],
        "cancelled": by_status["CANCELLED"],
        "salesHalalas": sales,
        "avgOrderHalalas": round(sales / len(served)) if served else 0,
    }


def dish_sales(orders: list[dict]) -> dict[str, dict]:
    """itemId -> {name, nameAr, qty, salesHalalas, orders} over SERVED orders."""
    out: dict[str, dict] = {}
    for o in _served(orders):
        for line in o.get("items", []):
            d = out.setdefault(line["itemId"], {"itemId": line["itemId"], "name": line["name"],
                                                "nameAr": line.get("nameAr", ""), "qty": 0, "salesHalalas": 0,
                                                "orders": 0})
            d["qty"] += int(line["qty"])
            d["salesHalalas"] += int(line["lineTotalHalalas"])
            d["orders"] += 1
    return out


def best_and_slow(orders: list[dict], menu: list[dict], top: int = 5) -> dict:
    """Best sellers by quantity, and the visible dishes that sold least (0 included)."""
    sold = dish_sales(orders)
    best = sorted(sold.values(), key=lambda d: (-d["qty"], -d["salesHalalas"], d["name"]))[:top]
    visible = [m for m in menu if m.get("isAvailable", True)]
    slow = sorted(
        ({"itemId": m["id"], "name": m["name"], "nameAr": m.get("nameAr", ""),
          "qty": sold.get(m["id"], {}).get("qty", 0)} for m in visible),
        key=lambda d: (d["qty"], d["name"]),
    )[:top]
    return {"best": best, "slow": slow}


def prep_minutes(orders: list[dict]) -> list[float]:
    """Minutes from ACCEPTED to READY_FOR_PICKUP for every order that got that far."""
    out = []
    for o in orders:
        accepted, ready = _at(o, "ACCEPTED"), _at(o, "READY_FOR_PICKUP")
        if accepted and ready and ready >= accepted:
            out.append((ready - accepted).total_seconds() / 60)
    return out


def prep_summary(orders: list[dict]) -> dict:
    mins = prep_minutes(orders)
    if not mins:
        return {"count": 0}
    return {
        "count": len(mins),
        "avgMinutes": round(mean(mins), 1),
        "medianMinutes": round(median(mins), 1),
        "fastestMinutes": round(min(mins), 1),
        "slowestMinutes": round(max(mins), 1),
    }


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def busiest(orders: list[dict], days: list | None = None) -> dict:
    """Orders (not rejected/cancelled) by Riyadh hour of day and by weekday (business day), busiest first.

    Weekdays are ranked by the AVERAGE per day when `days` (the period's business days) is given: a month with
    three Sundays and two Fridays must not make Sunday look busier just because it happened more often.
    """
    kept = [o for o in orders if o["status"] not in ("REJECTED", "CANCELLED")]
    hours = Counter(datetime.fromisoformat(o["createdAt"].replace("Z", "+00:00")).astimezone(RIYADH).hour for o in kept)
    counts = Counter(WEEKDAYS[datetime.fromisoformat(o["businessDate"]).weekday()] for o in kept if o.get("businessDate"))
    occurrences = Counter(WEEKDAYS[d.weekday()] for d in days) if days else Counter()
    by_day = []
    for name, n in counts.items():
        k = occurrences.get(name) or 1
        by_day.append({"day": name, "orders": n, "daysInPeriod": occurrences.get(name, 0) or None,
                       "avgOrdersPerDay": round(n / k, 1)})
    by_day.sort(key=lambda d: (-d["avgOrdersPerDay"], -d["orders"]))
    return {"byHour": [{"hour": f"{h:02d}:00", "orders": n} for h, n in hours.most_common()], "byWeekday": by_day}


def rejections(orders: list[dict]) -> dict:
    rejected = [o for o in orders if o["status"] == "REJECTED"]
    reasons = Counter(
        (next((h.get("reason") for h in o.get("statusHistory", []) if h.get("status") == "REJECTED"), None)
         or "No reason given")
        for o in rejected
    )
    return {
        "rejected": len(rejected),
        "cancelledByCustomer": sum(1 for o in orders if o["status"] == "CANCELLED"),
        "rejectReasons": [{"reason": r, "count": n} for r, n in reasons.most_common()],
    }


def change(cur: float, prev: float) -> float | None:
    """% change from prev to cur (None when there is nothing to compare with)."""
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


# --- what the website shows ---------------------------------------------------------------------------------------

INSIGHT_DAYS = 30
INSIGHT_TTL_SECONDS = 300  # "usually ready in" and "Popular" change slowly; one query per restaurant per 5 min
MIN_PREP_SAMPLES = 5
POPULAR_TOP = 3
POPULAR_MIN_QTY = 3
_insights_cache: dict[str, tuple[float, dict]] = {}


def _days_start(days: int, now=None) -> str:
    first = _hours.business_date(now) - timedelta(days=days - 1)
    return _hours.day_bounds_utc(first)[0]


def _now_utc(now=None) -> str:
    return _hours._utc((now or _hours.riyadh_now()))


def public_insights(rid: str, now=None) -> dict:
    """For customers (last 30 days): typicalReadyMinutes (median prep, rounded to 5; None if < 5 orders) and the
    ids of the restaurant's top dishes. Cached in the Lambda for 5 minutes."""
    hit = _insights_cache.get(rid)
    if hit and hit[0] > _time.monotonic():
        return hit[1]
    orders = load_orders(rid, _days_start(INSIGHT_DAYS, now), _now_utc(now))
    mins = prep_minutes(orders)
    ready = max(5, int(5 * round(median(mins) / 5))) if len(mins) >= MIN_PREP_SAMPLES else None
    sold = sorted(dish_sales(orders).values(), key=lambda d: (-d["qty"], d["itemId"]))
    popular = [d["itemId"] for d in sold[:POPULAR_TOP] if d["qty"] >= POPULAR_MIN_QTY]
    result = {"typicalReadyMinutes": ready, "popularItemIds": popular}
    _insights_cache[rid] = (_time.monotonic() + INSIGHT_TTL_SECONDS, result)
    return result


def owner_overview(rid: str, now=None) -> dict:
    """Owner page: today's numbers + served orders and sales for each of the last 7 business days."""
    days = _hours.last_n_days(7, now)
    orders = load_orders(rid, _hours.day_bounds_utc(days[0])[0], _now_utc(now))
    today_key = days[-1].isoformat()
    today = [o for o in orders if o.get("businessDate") == today_key]
    sold = sorted(dish_sales(today).values(), key=lambda d: (-d["qty"], -d["salesHalalas"], d["name"]))
    prep = prep_summary(today)
    last7 = []
    for d in days:
        day_orders = _served([o for o in orders if o.get("businessDate") == d.isoformat()])
        last7.append({"date": d.isoformat(), "servedOrders": len(day_orders),
                      "salesHalalas": sum(int(o["totalHalalas"]) for o in day_orders)})
    return {
        "today": {
            **summary(today),
            "avgPrepMinutes": prep.get("avgMinutes"),
            "bestSeller": ({k: sold[0][k] for k in ("itemId", "name", "nameAr", "qty")} if sold else None),
        },
        "last7": last7,
    }
