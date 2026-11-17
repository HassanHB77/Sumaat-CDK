"""Owner numbers (GET /restaurants/{rid}/stats) and the public "usually ready in" + "Popular" fields."""

from datetime import datetime, timedelta

from api.handler import app
from api.hours import day_bounds_utc
from tests.unit.api.conftest import THU_18, customer_claims, owner_claims


def _put_order(table, rid, created, status="SERVED", items=(), prep_min=10, day="2026-11-12", excluded=False, n=[0]):
    """A stored order (only the fields stats read, plus a customer name that must never be read)."""
    n[0] += 1
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    hist = [{"status": "PLACED", "at": created}]
    if status == "SERVED":
        a = datetime.strptime(created, fmt)
        hist += [{"status": "ACCEPTED", "at": created},
                 {"status": "READY_FOR_PICKUP", "at": (a + timedelta(minutes=prep_min)).strftime(fmt)},
                 {"status": "SERVED", "at": (a + timedelta(minutes=prep_min + 3)).strftime(fmt)}]
    lines = [{"itemId": i, "name": nm, "nameAr": nm, "qty": q, "unitPriceHalalas": p, "lineTotalHalalas": p * q}
             for i, nm, q, p in items]
    table.put_item(Item={
        "PK": f"ORDER#t{n[0]}", "SK": "ORDER", "id": f"t{n[0]}", "status": status, "createdAt": created,
        "businessDate": day, "totalHalalas": sum(x["lineTotalHalalas"] for x in lines), "items": lines,
        "statusHistory": hist, "GSI1PK": f"RORDERS#{rid}", "GSI1SK": created, "customerName": "Sara",
        **({"statsExcluded": True} if excluded else {}),
    })


def test_owner_stats_today_and_last7(shop):
    table, rid, burger, fries = shop["table"], shop["rid"], shop["burger"], shop["fries"]
    start = day_bounds_utc(THU_18.date())[0]  # Thu 12 Nov 04:00 Riyadh
    t = start.replace("T01:", "T10:")
    _put_order(table, rid, t, items=((burger, "Smash Burger", 2, 2500),), prep_min=10)
    _put_order(table, rid, t.replace("T10:", "T11:"), items=((burger, "Smash Burger", 1, 2500), (fries, "Fries", 1, 900)),
               prep_min=20)
    _put_order(table, rid, t.replace("T10:", "T12:"), status="REJECTED")
    _put_order(table, rid, t.replace("T10:", "T13:"), items=((fries, "Fries", 9, 900),), excluded=True)  # smoke test
    _put_order(table, rid, "2026-11-10T12:00:00Z", items=((fries, "Fries", 1, 900),), day="2026-11-10")

    res = shop["owner"].get(f"/restaurants/{rid}/stats")
    assert res.status_code == 200, res.text
    body = res.json()
    today = body["today"]
    assert (today["orders"], today["served"], today["rejected"]) == (3, 2, 1)
    assert today["salesHalalas"] == 5000 + 3400
    assert today["avgPrepMinutes"] == 15.0
    assert today["bestSeller"]["name"] == "Smash Burger" and today["bestSeller"]["qty"] == 3
    assert [d["date"] for d in body["last7"]] == [f"2026-11-{d:02d}" for d in range(6, 13)]
    assert {d["date"]: d["servedOrders"] for d in body["last7"]}["2026-11-10"] == 1
    assert body["last7"][-1]["salesHalalas"] == 8400


def test_owner_stats_only_for_this_owner(shop, make_client):
    rid = shop["rid"]
    assert make_client(app, owner_claims(sub="owner-sub-2")).get(f"/restaurants/{rid}/stats").status_code == 403
    assert make_client(app, customer_claims()).get(f"/restaurants/{rid}/stats").status_code == 403
    assert make_client(app).get(f"/restaurants/{rid}/stats").status_code == 401


def test_empty_day_has_zero_numbers(shop):
    body = shop["owner"].get(f"/restaurants/{shop['rid']}/stats").json()
    assert body["today"]["orders"] == 0 and body["today"]["bestSeller"] is None
    assert body["today"]["avgPrepMinutes"] is None and len(body["last7"]) == 7


def test_public_ready_time_and_popular(shop, make_client):
    table, rid, burger, fries = shop["table"], shop["rid"], shop["burger"], shop["fries"]
    for k, prep in enumerate((12, 14, 15, 16, 30)):
        _put_order(table, rid, f"2026-11-{k + 5:02d}T12:00:00Z", items=((burger, "Smash Burger", 1, 2500),),
                   prep_min=prep, day=f"2026-11-{k + 5:02d}")
    _put_order(table, rid, "2026-11-11T13:00:00Z", items=((fries, "Fries", 2, 900),))

    body = make_client(app).get(f"/restaurants/{rid}").json()
    assert body["typicalReadyMinutes"] == 15  # median 15, rounded to 5
    by_id = {m["id"]: m for m in body["menu"]}
    assert by_id[burger]["popular"] is True  # 5 sold
    assert by_id[fries]["popular"] is False  # only 2 sold (needs 3)


def test_too_few_orders_means_no_ready_time(shop, make_client):
    body = make_client(app).get(f"/restaurants/{shop['rid']}").json()
    assert body["typicalReadyMinutes"] is None
    assert not any(m["popular"] for m in body["menu"])


def test_insights_are_cached(shop, make_client, monkeypatch):
    from api.services import stats

    calls = []
    real = stats.load_orders
    monkeypatch.setattr(stats, "load_orders", lambda *a, **k: calls.append(1) or real(*a, **k))
    client = make_client(app)
    client.get(f"/restaurants/{shop['rid']}")
    client.get(f"/restaurants/{shop['rid']}")
    assert len(calls) == 1
