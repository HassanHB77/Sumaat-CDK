"""The owner assistant's look-ups (agent/owner_catalog.py) on a small, hand-made order history.

The clock is Thu 12 Nov 2026 18:00 Riyadh: this_week = Sun 8 - Thu 12 (so far), last week cut at the same point.
"""

import json
from datetime import datetime, timedelta

from agent import owner_catalog as oc
from agent.owner_tools import build_owner_tools
from agent.session import ChatSession

FMT = "%Y-%m-%dT%H:%M:%SZ"
N = [0]


def put(shop, created, status="SERVED", lines=(), prep=10, reason=None, day=None):
    """One order with real-shaped fields, including personal ones the owner assistant must never return."""
    N[0] += 1
    t = datetime.strptime(created, FMT)
    hist = [{"status": "PLACED", "at": created}]
    if status == "SERVED":
        hist += [{"status": "ACCEPTED", "at": created},
                 {"status": "READY_FOR_PICKUP", "at": (t + timedelta(minutes=prep)).strftime(FMT)},
                 {"status": "SERVED", "at": (t + timedelta(minutes=prep + 2)).strftime(FMT)}]
    if status == "REJECTED":
        hist.append({"status": "REJECTED", "at": created, **({"reason": reason} if reason else {})})
    if status == "CANCELLED":
        hist.append({"status": "CANCELLED", "at": created})
    items = [{"itemId": shop[k], "name": n, "nameAr": n, "qty": q, "unitPriceHalalas": p, "lineTotalHalalas": p * q}
             for k, n, q, p in lines]
    shop["table"].put_item(Item={
        "PK": f"ORDER#oc{N[0]}", "SK": "ORDER", "id": f"oc{N[0]}", "status": status, "createdAt": created,
        "businessDate": day or (t + timedelta(hours=3) - timedelta(hours=4)).date().isoformat(),
        "totalHalalas": sum(i["lineTotalHalalas"] for i in items), "items": items, "statusHistory": hist,
        "GSI1PK": f"RORDERS#{shop['rid']}", "GSI1SK": created,
        "customerName": "Sara", "customerPhone": "+966500000001", "customerEmail": "s@example.com", "note": "hi",
    })


BURGER = ("burger", "Smash Burger", 1, 2500)
FRIES = ("fries", "Fries", 1, 900)


def history(shop):
    # this week (Sun 8 .. Thu 12, before 18:00 Thu)
    put(shop, "2026-11-08T10:00:00Z", lines=(BURGER, FRIES), prep=10)
    put(shop, "2026-11-10T17:00:00Z", lines=(("burger", "Smash Burger", 2, 2500),), prep=20)
    put(shop, "2026-11-12T09:00:00Z", lines=(FRIES,), prep=12)
    put(shop, "2026-11-12T10:00:00Z", status="REJECTED", lines=(BURGER,), reason="Too busy")
    put(shop, "2026-11-12T11:00:00Z", status="CANCELLED", lines=(FRIES,))
    # last week, before the same point (Sun 1 .. Thu 5 18:00)
    put(shop, "2026-11-02T10:00:00Z", lines=(BURGER,), prep=30)
    # last week, after the same point (Fri 6): not in the comparison
    put(shop, "2026-11-06T10:00:00Z", lines=(BURGER, BURGER), prep=30)


def test_order_summary_with_comparison(shop):
    history(shop)
    r = oc.order_summary(shop["rid"], "this_week")
    assert r["period"] == {"name": "this_week", "from": "2026-11-08", "to": "2026-11-12", "soFar": True}
    assert (r["orders"], r["served"], r["rejected"], r["cancelled"]) == (5, 3, 1, 1)
    assert r["salesSar"] == "93.00"  # served only: 34 + 50 + 9
    assert r["previous"]["period"]["to"] == "2026-11-05"  # cut at the same point last week
    assert (r["previous"]["served"], r["previous"]["salesSar"]) == (1, "25.00")
    assert r["changePercent"]["sales"] == 272.0  # 93 vs 25


def test_dish_sales_by_partial_english_or_arabic_name(shop):
    history(shop)
    r = oc.dish_sales(shop["rid"], "burger", "this_week")
    (d,) = r["dishes"]
    assert (d["name"], d["qtySold"], d["salesSar"], d["previousQtySold"]) == ("Smash Burger", 3, "75.00", 1)
    assert oc.dish_sales(shop["rid"], "برجر", "this_week")["dishes"][0]["name"] == "Smash Burger"
    missing = oc.dish_sales(shop["rid"], "pizza", "this_week")
    assert missing["error"] == "dish_not_found" and "Fries" in missing["menu"]


def test_best_and_slow_sellers(shop):
    history(shop)
    r = oc.best_sellers(shop["rid"], "this_week", limit=5)
    assert [(d["name"], d["qtySold"]) for d in r["best"]] == [("Smash Burger", 3), ("Fries", 2)]
    assert r["slow"][0]["name"] == "Fries"


def test_prep_time(shop):
    history(shop)
    r = oc.prep_time(shop["rid"], "this_week")
    assert (r["count"], r["avgMinutes"], r["medianMinutes"]) == (3, 14.0, 12.0)
    assert r["previous"]["avgMinutes"] == 30.0


def test_busiest_and_rejections(shop):
    history(shop)
    b = oc.busiest_times(shop["rid"], "this_week")
    assert b["byHour"][0]["orders"] >= 1 and {d["day"] for d in b["byWeekday"]} == {"Sunday", "Tuesday", "Thursday"}
    r = oc.rejections(shop["rid"], "this_week")
    assert (r["rejected"], r["cancelledByCustomer"]) == (1, 1)
    assert r["rejectReasons"] == [{"reason": "Too busy", "count": 1}]


def test_unknown_period_lists_the_allowed_ones(shop):
    r = oc.order_summary(shop["rid"], "next_year")
    assert r["error"] == "unknown_period" and "this_month" in r["allowed"]
    assert oc.order_summary(shop["rid"], "This Week")["period"]["name"] == "this_week"  # forgiving spelling


def test_no_personal_data_in_any_answer(shop):
    history(shop)
    rid = shop["rid"]
    answers = [oc.order_summary(rid, "this_week"), oc.dish_sales(rid, "fries", "this_week"),
               oc.best_sellers(rid, "this_week"), oc.prep_time(rid, "this_week"),
               oc.busiest_times(rid, "this_week"), oc.rejections(rid, "this_week")]
    text = json.dumps(answers, ensure_ascii=False)
    for secret in ("Sara", "+966500000001", "s@example.com", "customer"):
        assert secret not in text


def test_tools_always_use_the_sessions_restaurant(shop):
    history(shop)
    session = ChatSession(sub="owner-sub-1", mode="owner", restaurant_id=shop["rid"])
    tools = {t.tool_name: t for t in build_owner_tools(session)}
    assert set(tools) == {"order_summary", "dish_sales", "best_sellers", "prep_time", "busiest_times", "rejections"}
    # no tool lets the model choose a restaurant
    for t in tools.values():
        assert "restaurant" not in json.dumps(t.tool_spec["inputSchema"]).lower()


def test_arabic_prefixes_and_word_order_dont_matter():
    from agent.owner_catalog import _matches

    assert _matches("شاي الهيل", "شاي بالهيل")
    assert _matches("الكبسة", "كبسة لحم")
    assert _matches("cardamom tea", "Cardamom Tea") and _matches("tea", "Cardamom Tea")
    assert not _matches("pizza", "Cardamom Tea")


def test_dish_answer_says_clearly_what_the_counts_mean(shop):
    history(shop)
    d = oc.dish_sales(shop["rid"], "burger", "this_week")
    assert "servedOrdersContainingIt" in d["dishes"][0] and "inOrders" not in d["dishes"][0]
    assert "open orders" in d["note"]
