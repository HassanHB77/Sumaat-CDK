"""Realistic past orders for the 15 demo restaurants, so owner numbers, the owner AI, "usually ready in" and
"Popular" have something real to show. FICTIONAL data, clearly marked: every row has `demoHistory: true`.

- About 6 weeks of business days up to yesterday (add --today for today's orders up to now; run it again on demo
  morning). Busier at lunch (13-15) and dinner (19-23) and on Thu/Fri; a slow upward trend week to week.
- Each restaurant has a few favourite dishes (best sellers) and a few slow ones.
- ~88% SERVED, ~7% REJECTED (the counter's reasons), ~5% CANCELLED. Prep (accept -> ready) per restaurant 8-25 min.
- Customer = a made-up `demo-history` id with no login, so nobody's "My orders" fills up. No customer email
  (inserting orders never triggers the pickup email: that Lambda only runs on ACCEPTED -> READY changes).
- Same order ids on every run (uuid5): existing orders are skipped, so re-running adds nothing twice. Order
  numbers come from the real daily counters, so they never clash with real orders.

Usage (from the project folder):
  uv run python scripts/seed_history.py --exclude-existing   # one-off: keep old smoke-test orders out of the stats
  uv run python scripts/seed_history.py [--days 42] [--today] [--only <slug>] [--dry-run]
  uv run python scripts/seed_history.py --delete              # remove every demoHistory order
"""

import argparse
import hashlib
import random
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.hours import DAY_START_HOUR, RIYADH, business_date, riyadh_now  # noqa: E402
from scripts.seed import stable_id  # noqa: E402
from scripts.seed_restaurants import RESTAURANTS  # noqa: E402

TABLE = "sumaat"
REGION = "us-east-1"
CUSTOMER_SUB = "demo-history"
STAFF_SUB = "demo-history-staff"
REJECT_REASONS = ("Item unavailable", "Too busy", "Closing soon")
NAMESPACE = uuid.UUID("5b1f3c2e-8d4a-4f0e-9c6b-2a7d1e9f4b10")
# Relative order volume per Riyadh hour (lunch and dinner peaks; quiet mornings and late nights).
HOUR_WEIGHT = {4: 0.1, 5: 0.1, 6: 0.3, 7: 0.6, 8: 0.9, 9: 0.9, 10: 0.7, 11: 0.8, 12: 1.4, 13: 2.2, 14: 2.0, 15: 1.2,
               16: 0.9, 17: 1.0, 18: 1.5, 19: 2.3, 20: 2.6, 21: 2.4, 22: 1.8, 23: 1.1, 0: 0.6, 1: 0.3, 2: 0.2, 3: 0.1}
WEEKDAY_FACTOR = {3: 1.4, 4: 1.5, 5: 1.1}  # Thu, Fri, Sat (Mon=0)


def _seed_of(*parts: str) -> int:
    return int(hashlib.sha256("/".join(parts).encode()).hexdigest()[:12], 16)


def profile(r: dict) -> dict:
    """Stable per-restaurant traits: volume, prep time, favourite and slow dishes."""
    rnd = random.Random(_seed_of("profile", r["slug"]))
    dishes = [d["slug"] for d in r["items"]]
    rnd.shuffle(dishes)
    return {
        "daily": rnd.uniform(4, 11),
        "prep": rnd.uniform(8, 22),
        "favourites": set(dishes[:3]),
        "slow": set(dishes[-2:]),
    }


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def open_minutes(hours: str) -> list[int]:
    """Minutes after the business-day start (04:00) when the restaurant is open."""
    start_s, end_s = hours.split("-")
    start, end = _minutes(start_s), _minutes(end_s)
    out = []
    for m in range(0, 24 * 60, 5):
        clock = (DAY_START_HOUR * 60 + m) % (24 * 60)
        if start == end or (start < end and start <= clock < end) or (start > end and (clock >= start or clock < end)):
            out.append(m)
    return out


def generate_day(r: dict, day: date, day_index: int) -> list[dict]:
    """The orders of one business day (no ids/numbers yet), sorted by time. Pure: no AWS calls."""
    rnd = random.Random(_seed_of("day", r["slug"], day.isoformat()))
    prof = profile(r)
    slots = open_minutes(r["hours"])
    if not slots:
        return []
    weights = [HOUR_WEIGHT[((DAY_START_HOUR * 60 + m) // 60) % 24] for m in slots]
    trend = 1 + 0.012 * day_index  # slowly growing business
    n = max(0, round(prof["daily"] * WEEKDAY_FACTOR.get(day.weekday(), 1.0) * trend * rnd.uniform(0.7, 1.3)))
    day_start = datetime.combine(day, time(DAY_START_HOUR), RIYADH)
    menu = r["items"]
    dish_weights = [6.0 if d["slug"] in prof["favourites"] else 0.15 if d["slug"] in prof["slow"] else 1.0 for d in menu]

    orders = []
    for i in range(n):
        placed = day_start + timedelta(minutes=rnd.choices(slots, weights)[0] + rnd.uniform(0, 5))
        picked: dict[str, int] = {}
        for _ in range(rnd.choices((1, 2, 3, 4), (45, 35, 15, 5))[0]):
            d = rnd.choices(menu, dish_weights)[0]
            picked[d["slug"]] = min(picked.get(d["slug"], 0) + rnd.choices((1, 2, 3), (75, 20, 5))[0], 5)
        roll = rnd.random()
        status = "SERVED" if roll < 0.88 else "REJECTED" if roll < 0.95 else "CANCELLED"
        history = [{"status": "PLACED", "at": placed, "by": CUSTOMER_SUB, "role": "customer"}]
        if status == "CANCELLED":
            history.append({"status": "CANCELLED", "at": placed + timedelta(minutes=rnd.uniform(0.5, 3)),
                            "by": CUSTOMER_SUB, "role": "customer"})
        elif status == "REJECTED":
            history.append({"status": "REJECTED", "at": placed + timedelta(minutes=rnd.uniform(1, 5)),
                            "by": STAFF_SUB, "role": "cashier", "reason": rnd.choice(REJECT_REASONS)})
        else:
            accepted = placed + timedelta(minutes=rnd.uniform(1, 4))
            ready = accepted + timedelta(minutes=max(4.0, rnd.gauss(prof["prep"], prof["prep"] * 0.25)))
            served = ready + timedelta(minutes=rnd.uniform(2, 10))
            history += [
                {"status": "ACCEPTED", "at": accepted, "by": STAFF_SUB, "role": "cashier"},
                {"status": "READY_FOR_PICKUP", "at": ready, "by": STAFF_SUB, "role": "cashier"},
                {"status": "SERVED", "at": served, "by": STAFF_SUB, "role": "cashier"},
            ]
        orders.append({"key": f"{r['slug']}/{day.isoformat()}/{i}", "status": status, "history": history,
                       "lines": [(next(d for d in menu if d["slug"] == s), q) for s, q in picked.items()]})
    return sorted(orders, key=lambda o: o["history"][0]["at"])


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_item(r: dict, day: date, o: dict, number: int) -> dict:
    """The DynamoDB order row, same shape as api/services/orders.place writes (plus demoHistory)."""
    rid = stable_id("restaurant", r["slug"])
    order_id = str(uuid.uuid5(NAMESPACE, o["key"]))
    lines = [
        {"itemId": stable_id("item", r["slug"], d["slug"]), "name": d["name"], "nameAr": d["nameAr"],
         "unitPriceHalalas": d["priceHalalas"], "qty": q, "lineTotalHalalas": d["priceHalalas"] * q}
        for d, q in o["lines"]
    ]
    history = [{**h, "at": _iso(h["at"])} for h in o["history"]]
    created, updated = history[0]["at"], history[-1]["at"]
    return {
        "PK": f"ORDER#{order_id}", "SK": "ORDER", "type": "ORDER", "id": order_id,
        "orderNumber": number, "businessDate": day.isoformat(),
        "restaurantId": rid, "restaurantName": r["name"], "restaurantNameAr": r["nameAr"],
        "customerSub": CUSTOMER_SUB, "customerName": "Demo customer", "customerPhone": "+966500000000",
        "items": lines, "totalHalalas": sum(line["lineTotalHalalas"] for line in lines), "note": None,
        "status": o["status"], "statusHistory": history, "createdAt": created, "updatedAt": updated,
        "GSI1PK": f"RORDERS#{rid}", "GSI1SK": created, "GSI2PK": f"CORDERS#{CUSTOMER_SUB}", "GSI2SK": created,
        "demoHistory": True,
    }


# --- AWS --------------------------------------------------------------------------------------------------------


def _existing_ids(table, ids: list[str]) -> set[str]:
    found: set[str] = set()
    client = table.meta.client
    for i in range(0, len(ids), 100):
        keys = [{"PK": f"ORDER#{x}", "SK": "ORDER"} for x in ids[i:i + 100]]
        res = client.batch_get_item(RequestItems={table.name: {"Keys": keys, "ProjectionExpression": "id"}})
        found |= {it["id"] for it in res["Responses"].get(table.name, [])}
    return found


def seed(table, days: int, include_today: bool, only: str | None, dry_run: bool) -> None:
    now = riyadh_now()
    today = business_date(now)
    day_list = [today - timedelta(days=k) for k in range(days, 0, -1)] + ([today] if include_today else [])
    added = skipped = 0
    for r in RESTAURANTS:
        if only and r["slug"] != only:
            continue
        rid = stable_id("restaurant", r["slug"])
        for index, day in enumerate(day_list):
            orders = [o for o in generate_day(r, day, index) if o["history"][-1]["at"] <= now]  # nothing in the future
            ids = [str(uuid.uuid5(NAMESPACE, o["key"])) for o in orders]
            existing = set() if dry_run else _existing_ids(table, ids)
            new = [o for o, i in zip(orders, ids) if i not in existing]
            skipped += len(orders) - len(new)
            if not new or dry_run:
                added += len(new)
                continue
            # Numbers from the real daily counter, like real orders (never clash with them).
            seq = int(table.update_item(
                Key={"PK": f"RESTAURANT#{rid}", "SK": f"COUNTER#{day.isoformat()}"},
                UpdateExpression="ADD seq :n SET #t = :t", ExpressionAttributeNames={"#t": "type"},
                ExpressionAttributeValues={":n": len(new), ":t": "COUNTER"}, ReturnValues="UPDATED_NEW",
            )["Attributes"]["seq"])
            with table.batch_writer() as batch:
                for k, o in enumerate(new):
                    batch.put_item(Item=to_item(r, day, o, seq - len(new) + 1 + k))
            added += len(new)
        print(f"{r['name']:28} done")
    print(f"{'would add' if dry_run else 'added'} {added} orders, skipped {skipped} already there")


def _orders_of(table, rid: str, projection: str = "PK, SK, demoHistory, statsExcluded"):
    kwargs = {"IndexName": "GSI1", "KeyConditionExpression": "GSI1PK = :p",
              "ExpressionAttributeValues": {":p": f"RORDERS#{rid}"}, "ProjectionExpression": projection}
    while True:
        page = table.query(**kwargs)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def exclude_existing(table) -> None:
    """Mark every non-demo order as statsExcluded (old smoke-test orders). Real orders placed later still count."""
    n = 0
    for r in RESTAURANTS:
        for o in _orders_of(table, stable_id("restaurant", r["slug"])):
            if not o.get("demoHistory") and not o.get("statsExcluded"):
                table.update_item(Key={"PK": o["PK"], "SK": o["SK"]}, UpdateExpression="SET statsExcluded = :t",
                                  ExpressionAttributeValues={":t": True})
                n += 1
    print(f"marked {n} existing orders statsExcluded")


def delete_demo(table) -> None:
    n = 0
    for r in RESTAURANTS:
        with table.batch_writer() as batch:
            for o in _orders_of(table, stable_id("restaurant", r["slug"])):
                if o.get("demoHistory"):
                    batch.delete_item(Key={"PK": o["PK"], "SK": o["SK"]})
                    n += 1
    print(f"deleted {n} demo-history orders (daily counters are left as they are)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--today", action="store_true", help="also today's orders up to now")
    ap.add_argument("--only", help="one restaurant slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--exclude-existing", action="store_true")
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()

    import boto3

    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
    if args.exclude_existing:
        exclude_existing(table)
    elif args.delete:
        delete_demo(table)
    else:
        seed(table, args.days, args.today, args.only, args.dry_run)


if __name__ == "__main__":
    main()
