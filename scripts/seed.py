"""Seed the `sumaat` table (and demo owner logins) with 3 fictional Al-Ahsa restaurants.

Safe to re-run: ids are deterministic (uuid5 from the slug), items are overwritten,
order counters are only created if missing, existing owner users are reused.

Usage:
  SEED_OWNER_PASSWORD='...' uv run python scripts/seed.py            # table + owners
  uv run python scripts/seed.py --skip-owners                         # table only
  uv run python scripts/seed.py --dry-run                             # print, write nothing

Pool id defaults to outputs.json (SumaatAuth.UserPoolId).
"""

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.geo import encode  # noqa: E402
from scripts.seed_data import CATEGORIES, COUNTER_START, RESTAURANTS  # noqa: E402

NAMESPACE = uuid.UUID("5b1c1d0e-6a39-4f53-9d0e-3f1f6a0c5a11")  # fixed: same slug -> same id forever


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- item builders (these shapes are the contract the API will read) --------


def restaurant_item(r: dict, owner_sub: str | None, ts: str) -> dict:
    rid = stable_id("restaurant", r["slug"])
    item = {
        "PK": f"RESTAURANT#{rid}",
        "SK": "PROFILE",
        "type": "RESTAURANT",
        "id": rid,
        "name": r["name"],
        "nameAr": r["nameAr"],
        "description": r["description"],
        "city": r["city"],
        "district": r["district"],
        "lat": Decimal(str(r["lat"])),
        "lng": Decimal(str(r["lng"])),
        "geohash": encode(r["lat"], r["lng"], 7),
        "hours": r["hours"],
        "isPaused": False,
        "GSI1PK": f"GEO#{encode(r['lat'], r['lng'])}",
        "GSI1SK": f"RESTAURANT#{rid}",
        "createdAt": ts,
        "updatedAt": ts,
    }
    if owner_sub:
        item["ownerSub"] = owner_sub
    return item


def menu_items(r: dict, ts: str) -> list[dict]:
    rid = stable_id("restaurant", r["slug"])
    out = []
    for i in r["items"]:
        iid = stable_id("item", r["slug"], i["slug"])
        out.append(
            {
                "PK": f"RESTAURANT#{rid}",
                "SK": f"ITEM#{iid}",
                "type": "MENU_ITEM",
                "id": iid,
                "restaurantId": rid,
                "name": i["name"],
                "nameAr": i["nameAr"],
                "category": i["category"],
                "priceHalalas": i["priceHalalas"],
                "calories": i["calories"],
                "dietTags": i["dietTags"],
                "isAvailable": True,
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
    return out


# --- writers ----------------------------------------------------------------


def ensure_owner(cognito, pool_id: str, owner: dict, restaurant_id: str, password: str) -> str:
    """Create (or reuse) a confirmed owner login linked to the restaurant. Returns its sub."""
    email = owner["email"]
    try:
        user = cognito.admin_get_user(UserPoolId=pool_id, Username=email)
        attrs = user["UserAttributes"]
    except cognito.exceptions.UserNotFoundException:
        attrs = cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            MessageAction="SUPPRESS",  # no invitation email
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": owner["name"]},
                {"Name": "phone_number", "Value": owner["phone"]},  # fake demo number
                {"Name": "custom:signupRole", "Value": "owner"},
            ],
        )["User"]["Attributes"]

    cognito.admin_set_user_password(UserPoolId=pool_id, Username=email, Password=password, Permanent=True)
    cognito.admin_update_user_attributes(
        UserPoolId=pool_id,
        Username=email,
        UserAttributes=[{"Name": "custom:restaurantId", "Value": restaurant_id}],
    )
    for group in ("customer", "owner"):  # same groups a self-registered owner gets
        cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=email, GroupName=group)
    return next(a["Value"] for a in attrs if a["Name"] == "sub")


def seed(table, cognito=None, pool_id: str | None = None, password: str | None = None) -> dict:
    ts = now_iso()
    summary = {"restaurants": 0, "items": 0, "counters_created": 0, "owners": []}

    # ADD on a string set is a union: re-running never removes categories added by hand.
    table.update_item(
        Key={"PK": "CONFIG", "SK": "CATEGORIES"},
        UpdateExpression="ADD categories :c SET #t = :t",
        ExpressionAttributeNames={"#t": "type"},
        ExpressionAttributeValues={":c": set(CATEGORIES), ":t": "CONFIG"},
    )

    for r in RESTAURANTS:
        rid = stable_id("restaurant", r["slug"])
        owner_sub = None
        if cognito is not None:
            owner_sub = ensure_owner(cognito, pool_id, r["owner"], rid, password)
            summary["owners"].append({"restaurant": r["name"], "email": r["owner"]["email"]})

        table.put_item(Item=restaurant_item(r, owner_sub, ts))
        if owner_sub:
            # Same one-restaurant-per-owner lock the API writes on POST /restaurants.
            table.put_item(Item={"PK": f"OWNER#{owner_sub}", "SK": "RESTAURANT", "type": "OWNER_LOCK",
                                 "restaurantId": rid, "createdAt": ts})
        summary["restaurants"] += 1

        with table.batch_writer() as batch:
            for item in menu_items(r, ts):
                batch.put_item(Item=item)
                summary["items"] += 1

        try:
            table.put_item(
                Item={"PK": f"RESTAURANT#{rid}", "SK": "COUNTER", "type": "COUNTER", "seq": COUNTER_START},
                ConditionExpression="attribute_not_exists(PK)",  # never reset a live counter
            )
            summary["counters_created"] += 1
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            pass

    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", default="sumaat")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--pool-id", help="business user pool id (default: from outputs.json)")
    ap.add_argument("--skip-owners", action="store_true", help="don't create owner logins")
    ap.add_argument("--dry-run", action="store_true", help="print items, write nothing")
    args = ap.parse_args()

    if args.dry_run:
        ts = now_iso()
        for r in RESTAURANTS:
            print(json.dumps(restaurant_item(r, None, ts), default=str, ensure_ascii=False))
            for i in menu_items(r, ts):
                print("  ", json.dumps(i, default=str, ensure_ascii=False))
        return

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    cognito = pool_id = password = None
    if not args.skip_owners:
        password = os.environ.get("SEED_OWNER_PASSWORD")
        if not password:
            sys.exit("Set SEED_OWNER_PASSWORD (min 8 chars, upper, lower, digit, symbol) or use --skip-owners")
        pool_id = args.pool_id or json.loads((ROOT / "outputs.json").read_text())["SumaatAuth"]["UserPoolId"]
        cognito = boto3.client("cognito-idp", region_name=args.region)

    print(json.dumps(seed(table, cognito, pool_id, password), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
