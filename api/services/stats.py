"""Order statistics for one restaurant: owner numbers, the owner AI, "usually ready in" and "Popular".

Rules (decided with the product owner):
- Sales (money, dish quantities) count SERVED orders only: that is money actually taken at the counter.
- Order counts also report open, rejected and cancelled orders separately.
- Prep time = ACCEPTED -> READY_FOR_PICKUP, in minutes.
- Orders marked `statsExcluded` (old smoke-test orders) are ignored.

Privacy: `load_orders` asks DynamoDB for non-personal fields only (no customer name, phone, email or note), so
nothing here can leak customer data. The owner AI's IAM role is limited to the same field list.
"""

from collections import Counter
from datetime import datetime
from statistics import mean, median
from typing import Any

from boto3.dynamodb.conditions import Key

from api import aws
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


def busiest(orders: list[dict]) -> dict:
    """Orders (not rejected/cancelled) by Riyadh hour of day and by weekday (business day), busiest first."""
    kept = [o for o in orders if o["status"] not in ("REJECTED", "CANCELLED")]
    hours = Counter(datetime.fromisoformat(o["createdAt"].replace("Z", "+00:00")).astimezone(RIYADH).hour for o in kept)
    days = Counter(WEEKDAYS[datetime.fromisoformat(o["businessDate"]).weekday()] for o in kept if o.get("businessDate"))
    return {
        "byHour": [{"hour": f"{h:02d}:00", "orders": n} for h, n in hours.most_common()],
        "byWeekday": [{"day": d, "orders": n} for d, n in days.most_common()],
    }


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
