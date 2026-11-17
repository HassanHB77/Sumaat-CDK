"""Demo order history: realistic, fictional, clearly marked, and shaped exactly like real orders."""

from datetime import date, timedelta

from api.hours import day_bounds_utc
from scripts.seed import stable_id
from scripts.seed_history import CUSTOMER_SUB, generate_day, open_minutes, to_item
from scripts.seed_restaurants import RESTAURANTS

NAKHLA = next(r for r in RESTAURANTS if r["slug"] == "nakhla-kitchen")
DAY = date(2026, 11, 12)  # a Thursday


def test_same_orders_every_run():
    assert generate_day(NAKHLA, DAY, 3) == generate_day(NAKHLA, DAY, 3)


def test_orders_inside_opening_hours_and_business_day():
    start, end = day_bounds_utc(DAY)
    for r in RESTAURANTS:
        for o in generate_day(r, DAY, 0):
            row = to_item(r, DAY, o, 1)
            assert start <= row["createdAt"] < end
            assert row["createdAt"] <= row["statusHistory"][-1]["at"]


def test_open_minutes_follow_hours():
    assert len(open_minutes("00:00-00:00")) == 24 * 12  # 24 h
    assert open_minutes("12:00-23:30")[0] == 8 * 60  # 12:00 = 8 h after the 04:00 day start
    assert max(open_minutes("13:00-01:00")) < 21 * 60 + 1  # closes 01:00 = 21 h after 04:00


def test_row_shape_matches_real_orders_and_is_marked():
    o = generate_day(NAKHLA, DAY, 0)[0]
    row = to_item(NAKHLA, DAY, o, 7)
    rid = stable_id("restaurant", NAKHLA["slug"])
    assert row["demoHistory"] is True and row["customerSub"] == CUSTOMER_SUB and "customerEmail" not in row
    assert row["GSI1PK"] == f"RORDERS#{rid}" and row["GSI1SK"] == row["createdAt"] and row["orderNumber"] == 7
    assert row["totalHalalas"] == sum(line["lineTotalHalalas"] for line in row["items"])
    assert row["status"] in ("SERVED", "REJECTED", "CANCELLED")  # never an open order (no locks needed)
    menu_ids = {stable_id("item", NAKHLA["slug"], d["slug"]) for d in NAKHLA["items"]}
    assert {line["itemId"] for line in row["items"]} <= menu_ids


def test_mix_of_statuses_and_realistic_prep():
    rows = [to_item(NAKHLA, DAY + timedelta(days=k), o, 1)
            for k in range(30) for o in generate_day(NAKHLA, DAY + timedelta(days=k), k)]
    served = [r for r in rows if r["status"] == "SERVED"]
    assert 0.8 < len(served) / len(rows) < 0.95
    assert any(r["status"] == "REJECTED" for r in rows) and any(r["status"] == "CANCELLED" for r in rows)
    rejected = [r for r in rows if r["status"] == "REJECTED"]
    assert all(r["statusHistory"][-1].get("reason") for r in rejected)
    for r in served:
        steps = [h["status"] for h in r["statusHistory"]]
        assert steps == ["PLACED", "ACCEPTED", "READY_FOR_PICKUP", "SERVED"]


def test_trend_uses_a_fixed_date_so_reruns_add_nothing():
    # Same day -> same orders, whatever window the run covers (the trend no longer depends on the run's start).
    assert generate_day(NAKHLA, DAY) == generate_day(NAKHLA, DAY)
    assert len(generate_day(NAKHLA, date(2026, 11, 16))) >= 1
