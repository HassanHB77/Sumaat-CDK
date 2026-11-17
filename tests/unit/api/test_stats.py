"""Order statistics: periods, what counts, prep time, best/slow dishes, busiest times, rejections, loader privacy."""

from datetime import datetime

import boto3
import pytest
from moto import mock_aws

from api.hours import RIYADH, period_bounds, previous_period
from api.services import stats
from tests.ddb import create_table

TUE = datetime(2026, 11, 17, 15, 30, tzinfo=RIYADH)  # a Tuesday afternoon


def order(status, created="2026-11-17T10:00:00Z", total=1000, items=(("a", "Kabsa", 1, 1000),), accepted=None,
          ready=None, reason=None, business="2026-11-17", **extra):
    history = [{"status": "PLACED", "at": created}]
    if accepted:
        history.append({"status": "ACCEPTED", "at": accepted})
    if ready:
        history.append({"status": "READY_FOR_PICKUP", "at": ready})
    if status in ("SERVED",):
        history.append({"status": "SERVED", "at": ready or created})
    if status == "REJECTED":
        history.append({"status": "REJECTED", "at": created, **({"reason": reason} if reason else {})})
    return {
        "id": f"o-{created}-{status}", "status": status, "createdAt": created, "businessDate": business,
        "totalHalalas": total, "statusHistory": history,
        "items": [{"itemId": i, "name": n, "nameAr": n, "qty": q, "lineTotalHalalas": t} for i, n, q, t in items],
        **extra,
    }


# --- periods ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, first, last",
    [
        ("today", "2026-11-17", "2026-11-17"),
        ("yesterday", "2026-11-16", "2026-11-16"),
        ("this_week", "2026-11-15", "2026-11-17"),  # Saudi week starts Sunday
        ("last_week", "2026-11-08", "2026-11-14"),
        ("this_month", "2026-11-01", "2026-11-17"),
        ("last_month", "2026-10-01", "2026-10-31"),
    ],
)
def test_periods(kind, first, last):
    p = period_bounds(kind, TUE)
    assert (p.first_day.isoformat(), p.last_day.isoformat()) == (first, last)


def test_running_periods_end_now_and_are_compared_at_the_same_point():
    week = period_bounds("this_week", TUE)
    assert week.start == "2026-11-15T01:00:00Z" and week.end == "2026-11-17T12:30:00Z" and week.to_date
    prev = previous_period(week, TUE)
    assert (prev.start, prev.end) == ("2026-11-08T01:00:00Z", "2026-11-10T12:30:00Z")
    full = previous_period(period_bounds("last_week", TUE), TUE)
    assert (full.start, full.end) == ("2026-11-01T01:00:00Z", "2026-11-08T01:00:00Z")


def test_business_day_starts_at_4am():
    before = datetime(2026, 11, 15, 3, 59, tzinfo=RIYADH)  # Sunday 03:59 still belongs to Saturday
    after = datetime(2026, 11, 15, 4, 0, tzinfo=RIYADH)
    assert period_bounds("this_week", before).first_day.isoformat() == "2026-11-08"
    assert period_bounds("this_week", after).first_day.isoformat() == "2026-11-15"


def test_month_change():
    first = datetime(2026, 12, 1, 4, 30, tzinfo=RIYADH)
    assert period_bounds("last_month", first).first_day.isoformat() == "2026-11-01"
    assert period_bounds("this_month", datetime(2026, 12, 1, 3, 0, tzinfo=RIYADH)).first_day.isoformat() == "2026-11-01"


# --- what counts -------------------------------------------------------------------------------------------------


def test_sales_count_served_orders_only():
    orders = [order("SERVED", total=2000), order("SERVED", total=1000), order("REJECTED", total=5000),
              order("CANCELLED", total=7000), order("ACCEPTED", total=900)]
    s = stats.summary(orders)
    assert s == {"orders": 5, "served": 2, "open": 1, "rejected": 1, "cancelled": 1,
                 "salesHalalas": 3000, "avgOrderHalalas": 1500}


def test_dish_sales_and_best_and_slow():
    orders = [
        order("SERVED", items=(("a", "Kabsa", 2, 4000), ("b", "Laban", 1, 500))),
        order("SERVED", items=(("a", "Kabsa", 1, 2000),)),
        order("REJECTED", items=(("c", "Harees", 9, 9000),)),  # not a sale
    ]
    menu = [{"id": "a", "name": "Kabsa"}, {"id": "b", "name": "Laban"}, {"id": "c", "name": "Harees"},
            {"id": "d", "name": "Hidden", "isAvailable": False}]
    sold = stats.dish_sales(orders)
    assert sold["a"]["qty"] == 3 and sold["a"]["salesHalalas"] == 6000 and "c" not in sold
    result = stats.best_and_slow(orders, menu, top=2)
    assert [d["name"] for d in result["best"]] == ["Kabsa", "Laban"]
    assert [(d["name"], d["qty"]) for d in result["slow"]] == [("Harees", 0), ("Laban", 1)]  # hidden left out


def test_prep_time_is_accept_to_ready():
    orders = [
        order("SERVED", accepted="2026-11-17T10:00:00Z", ready="2026-11-17T10:10:00Z"),
        order("SERVED", accepted="2026-11-17T11:00:00Z", ready="2026-11-17T11:20:00Z"),
        order("SERVED", accepted="2026-11-17T12:00:00Z", ready="2026-11-17T12:30:00Z"),
        order("REJECTED"),
    ]
    assert stats.prep_summary(orders) == {"count": 3, "avgMinutes": 20.0, "medianMinutes": 20.0,
                                          "fastestMinutes": 10.0, "slowestMinutes": 30.0}
    assert stats.prep_summary([order("REJECTED")]) == {"count": 0}


def test_busiest_uses_riyadh_hours_and_skips_rejected():
    orders = [order("SERVED", created="2026-11-17T17:10:00Z"), order("SERVED", created="2026-11-17T17:40:00Z"),
              order("SERVED", created="2026-11-17T10:00:00Z"), order("REJECTED", created="2026-11-17T09:00:00Z")]
    b = stats.busiest(orders)
    assert b["byHour"][0] == {"hour": "20:00", "orders": 2}  # 17:xx UTC = 20:xx Riyadh
    assert {"hour": "12:00", "orders": 0} not in b["byHour"] and len(b["byHour"]) == 2
    assert b["byWeekday"] == [{"day": "Tuesday", "orders": 3}]


def test_rejections_with_reasons():
    orders = [order("REJECTED", reason="Too busy"), order("REJECTED", reason="Too busy"), order("REJECTED"),
              order("CANCELLED"), order("SERVED")]
    assert stats.rejections(orders) == {
        "rejected": 3, "cancelledByCustomer": 1,
        "rejectReasons": [{"reason": "Too busy", "count": 2}, {"reason": "No reason given", "count": 1}],
    }


def test_change_percent():
    assert stats.change(120, 100) == 20.0
    assert stats.change(50, 100) == -50.0
    assert stats.change(5, 0) is None


# --- loader ------------------------------------------------------------------------------------------------------


def test_loader_reads_only_non_personal_fields_and_skips_excluded():
    with mock_aws():
        table = create_table(boto3.resource("dynamodb", region_name="us-east-1"))
        base = {"SK": "ORDER", "GSI1PK": "RORDERS#r1", "customerName": "Sara", "customerPhone": "+966500000001",
                "customerEmail": "s@example.com", "note": "hi"}
        keep = order("SERVED", created="2026-11-17T10:00:00Z")
        old = order("SERVED", created="2026-11-17T11:00:00Z", statsExcluded=True)
        late = order("SERVED", created="2026-11-17T12:30:00Z")  # == end -> outside [start, end)
        for i, o in enumerate((keep, old, late)):
            table.put_item(Item={**base, **o, "PK": f"ORDER#{i}", "GSI1SK": o["createdAt"]})
        rows = stats.load_orders("r1", "2026-11-17T01:00:00Z", "2026-11-17T12:30:00Z", table=table)
        assert [r["createdAt"] for r in rows] == ["2026-11-17T10:00:00Z"]
        assert not {"customerName", "customerPhone", "customerEmail", "note"} & set(rows[0])
