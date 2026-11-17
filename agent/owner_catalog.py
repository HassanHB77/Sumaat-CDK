"""What the OWNER assistant can look up: numbers about the owner's OWN restaurant (Piece 3 of the owner-AI plan).

- The restaurant id always comes from the server (the owner's login), never from the model.
- Everything is read-only and built on api/services/stats.py, which reads non-personal order fields only
  (no customer names, phones, emails or notes). The agent's IAM role is limited to the same fields.
- Sales and dish quantities = SERVED orders (money actually taken). Order counts also report open/rejected/cancelled.
- Every answer carries the period's dates and, where it helps, the previous period (cut at the same point
  when the period is still running) and the % change, so the model never has to do maths.
- Problems come back as {"error": ...} so the model can explain them.
"""

import re
from datetime import datetime, timedelta
from typing import Any

from api import hours
from api.errors import NotFound
from api.services import restaurants, stats

PERIODS = hours.PERIODS  # today, yesterday, this_week, last_week, this_month, last_month


def _sar(halalas: int) -> str:
    return f"{halalas / 100:.2f}"


def _check_period(period: str | None) -> tuple[str | None, dict | None]:
    p = (period or "").strip().lower().replace(" ", "_").replace("-", "_")
    if p in PERIODS:
        return p, None
    return None, {"error": "unknown_period", "unknown": period, "allowed": list(PERIODS)}


def _describe(p: hours.Period) -> dict[str, Any]:
    out: dict[str, Any] = {"name": p.kind, "from": p.first_day.isoformat(), "to": p.last_day.isoformat()}
    if p.to_date:
        out["soFar"] = True  # still running: numbers up to now
    return out


def _orders(rid: str, p: hours.Period) -> list[dict]:
    return stats.load_orders(rid, p.start, p.end)


def _periods(period: str, now: datetime | None) -> tuple[hours.Period, hours.Period]:
    cur = hours.period_bounds(period, now)
    return cur, hours.previous_period(cur, now)


def _money_summary(s: dict) -> dict:
    return {
        "orders": s["orders"],
        "served": s["served"],
        "open": s["open"],
        "rejected": s["rejected"],
        "cancelled": s["cancelled"],
        "salesSar": _sar(s["salesHalalas"]),
        "avgOrderSar": _sar(s["avgOrderHalalas"]),
    }


def order_summary(rid: str, period: str, now: datetime | None = None) -> dict:
    """Orders and sales for a period, with the previous period and % change."""
    period, err = _check_period(period)
    if err:
        return err
    cur_p, prev_p = _periods(period, now)
    cur, prev = stats.summary(_orders(rid, cur_p)), stats.summary(_orders(rid, prev_p))
    return {
        "period": _describe(cur_p),
        **_money_summary(cur),
        "previous": {"period": _describe(prev_p), **_money_summary(prev)},
        "changePercent": {
            "orders": stats.change(cur["orders"], prev["orders"]),
            "served": stats.change(cur["served"], prev["served"]),
            "sales": stats.change(cur["salesHalalas"], prev["salesHalalas"]),
        },
        "note": "Sales count served orders only.",
    }


def _normalise(text: str) -> str:
    """Same idea as the website's dish search: case, Arabic vowel marks, alef/ta marbuta/ya forms."""
    t = text.lower()
    t = re.sub(r"[ً-ٰٟـ]", "", t)
    t = re.sub(r"[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", t).strip()


_AR_PREFIX = re.compile(r"^(وبال|بال|وال|فال|كال|لل|ال|و|ب)(?=..)")


def _words(text: str) -> list[str]:
    """Normalised words without punctuation or common Arabic prefixes: "شاي الهيل" ~ "شاي بالهيل"."""
    words = re.findall(r"\w+", _normalise(text))
    return [_AR_PREFIX.sub("", w) for w in words if len(w) > 1 or w.isdigit()]


def _matches(query: str, name: str) -> bool:
    """Every word of the query appears in (a word of) the name, ignoring case, marks and Arabic prefixes."""
    q, n = _words(query), _words(name)
    return bool(q) and all(any(qw in nw or nw in qw for nw in n if len(nw) > 1) for qw in q)


def _menu(rid: str) -> list[dict]:
    try:
        return restaurants.get(rid)["menu"]
    except NotFound:
        return []


def dish_sales(rid: str, dish: str, period: str, now: datetime | None = None) -> dict:
    """How much of a dish (matched by English or Arabic name) sold in a period, vs the previous period."""
    period, err = _check_period(period)
    if err:
        return err
    if not _words(dish or ""):
        return {"error": "no_dish_name"}
    menu = _menu(rid)
    matches = [m for m in menu if _matches(dish, m["name"]) or _matches(dish, m.get("nameAr", ""))]
    if not matches:
        return {"error": "dish_not_found", "dish": dish, "menu": [m["name"] for m in menu][:60]}
    cur_p, prev_p = _periods(period, now)
    cur, prev = stats.dish_sales(_orders(rid, cur_p)), stats.dish_sales(_orders(rid, prev_p))
    out = []
    for m in matches[:5]:
        c, p = cur.get(m["id"], {}), prev.get(m["id"], {})
        out.append({
            "name": m["name"],
            "nameAr": m.get("nameAr", ""),
            "qtySold": c.get("qty", 0),
            "salesSar": _sar(c.get("salesHalalas", 0)),
            "servedOrdersContainingIt": c.get("orders", 0),
            "previousQtySold": p.get("qty", 0),
            "changePercent": stats.change(c.get("qty", 0), p.get("qty", 0)),
        })
    return {"period": _describe(cur_p), "previousPeriod": _describe(prev_p), "dishes": out,
            "note": "qtySold = portions sold in SERVED orders; servedOrdersContainingIt = how many served orders had "
                    "this dish. Neither is about open orders."}


def best_sellers(rid: str, period: str, limit: int = 5, now: datetime | None = None) -> dict:
    """Top dishes by quantity, and the visible dishes that sold least (slow dishes, 0 included)."""
    period, err = _check_period(period)
    if err:
        return err
    limit = min(max(int(limit or 5), 1), 10)
    cur_p = hours.period_bounds(period, now)
    result = stats.best_and_slow(_orders(rid, cur_p), _menu(rid), top=limit)
    return {
        "period": _describe(cur_p),
        "best": [{"name": d["name"], "nameAr": d["nameAr"], "qtySold": d["qty"], "salesSar": _sar(d["salesHalalas"])}
                 for d in result["best"]],
        "slow": [{"name": d["name"], "nameAr": d["nameAr"], "qtySold": d["qty"]} for d in result["slow"]],
        "note": "Quantities count served orders only; slow dishes are visible dishes that sold least.",
    }


def prep_time(rid: str, period: str, now: datetime | None = None) -> dict:
    """Minutes from ACCEPTED to READY: average, median, fastest, slowest, vs the previous period."""
    period, err = _check_period(period)
    if err:
        return err
    cur_p, prev_p = _periods(period, now)
    cur, prev = stats.prep_summary(_orders(rid, cur_p)), stats.prep_summary(_orders(rid, prev_p))
    return {
        "period": _describe(cur_p),
        **cur,
        "previous": {"period": _describe(prev_p), **prev},
        "changePercentAvg": stats.change(cur.get("avgMinutes") or 0, prev.get("avgMinutes") or 0),
        "note": "From the moment an order is accepted until it is marked ready. count = orders measured.",
    }


def busiest_times(rid: str, period: str, now: datetime | None = None) -> dict:
    """Orders by hour of day (Riyadh time) and by weekday, busiest first (rejected/cancelled left out)."""
    period, err = _check_period(period)
    if err:
        return err
    cur_p = hours.period_bounds(period, now)
    days = [cur_p.first_day + timedelta(days=i) for i in range((cur_p.last_day - cur_p.first_day).days + 1)]
    b = stats.busiest(_orders(rid, cur_p), days)
    return {"period": _describe(cur_p), "byHour": b["byHour"][:6], "byWeekday": b["byWeekday"],
            "note": "Weekdays are ranked by average orders per day (avgOrdersPerDay), not raw totals."}


def rejections(rid: str, period: str, now: datetime | None = None) -> dict:
    """Rejected orders with reasons, and orders cancelled by customers, vs the previous period."""
    period, err = _check_period(period)
    if err:
        return err
    cur_p, prev_p = _periods(period, now)
    cur_orders = _orders(rid, cur_p)
    cur, prev = stats.rejections(cur_orders), stats.rejections(_orders(rid, prev_p))
    return {
        "period": _describe(cur_p),
        "ordersInPeriod": len(cur_orders),
        **cur,
        "previous": {"period": _describe(prev_p), "rejected": prev["rejected"],
                     "cancelledByCustomer": prev["cancelledByCustomer"]},
    }
