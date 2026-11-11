"""Restaurant data access. Plain boto3, no FastAPI, raises api.errors on failure.

Items (see infra/data_stack.py):
  Profile     PK=RESTAURANT#<id>  SK=PROFILE   GSI1PK=GEO#<geohash5>  GSI1SK=RESTAURANT#<id>
  Menu item   PK=RESTAURANT#<id>  SK=ITEM#<id>
  Counter     PK=RESTAURANT#<id>  SK=COUNTER#<YYYY-MM-DD>  seq  (daily order numbers, see services/orders.py)
  Owner lock  PK=OWNER#<sub>      SK=RESTAURANT  restaurantId  (one restaurant per owner)
"""

import logging
import uuid
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from api import aws, geo, hours
from api.auth import Principal
from api.clock import now_iso
from api.errors import Conflict, Forbidden, Invalid, NotFound
from api.models import RestaurantCreate, RestaurantUpdate
from api.services.ddb import set_expression
from api.services.staff import require_staff
from api.settings import get_settings

logger = logging.getLogger(__name__)

def _pk(rid: str) -> str:
    return f"RESTAURANT#{rid}"


def _owner_lock_key(sub: str) -> dict:
    return {"PK": f"OWNER#{sub}", "SK": "RESTAURANT"}


def _geo_fields(lat: float, lng: float) -> dict:
    return {
        "lat": Decimal(str(lat)),
        "lng": Decimal(str(lng)),
        "geohash": geo.encode(lat, lng, 7),
        "GSI1PK": f"GEO#{geo.encode(lat, lng)}",
    }


def with_status(item: dict) -> dict:
    """Add the computed fields every restaurant response carries."""
    return {**item, "isPaused": item.get("isPaused", False), "openNow": hours.open_now(item)}


# --- reads (public) ----------------------------------------------------------


def near(lat: float, lng: float, radius_km: float) -> list[dict]:
    """Restaurants within radius_km, nearest first, each with distanceKm."""
    table = aws.table()
    found: dict[str, dict] = {}
    for cell in geo.cells_around(lat, lng):
        kwargs = {"IndexName": "GSI1", "KeyConditionExpression": Key("GSI1PK").eq(f"GEO#{cell}")}
        while True:
            page = table.query(**kwargs)
            for item in page["Items"]:
                found[item["id"]] = item
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    out = []
    for item in found.values():
        d = geo.distance_km(lat, lng, float(item["lat"]), float(item["lng"]))
        if d <= radius_km:
            out.append({**with_status(item), "distanceKm": round(d, 2)})
    return sorted(out, key=lambda r: r["distanceKm"])


def get(rid: str) -> dict:
    """Profile + menu (sorted by category, name). One Query on the restaurant's partition."""
    items = aws.table().query(KeyConditionExpression=Key("PK").eq(_pk(rid)))["Items"]
    profile = next((i for i in items if i["SK"] == "PROFILE"), None)
    if profile is None:
        raise NotFound("Restaurant not found")
    menu = sorted((i for i in items if i["SK"].startswith("ITEM#")), key=lambda i: (i["category"], i["name"]))
    return {**with_status(profile), "menu": menu}


# --- writes (owner) ----------------------------------------------------------


def create(owner: Principal, data: RestaurantCreate) -> dict:
    table = aws.table()
    rid = str(uuid.uuid4())
    ts = now_iso()
    profile = {
        "PK": _pk(rid),
        "SK": "PROFILE",
        "type": "RESTAURANT",
        "id": rid,
        **data.model_dump(exclude={"lat", "lng"}),
        **_geo_fields(data.lat, data.lng),
        "GSI1SK": f"RESTAURANT#{rid}",
        "ownerSub": owner.sub,
        "isPaused": False,
        "createdAt": ts,
        "updatedAt": ts,
    }
    name = table.name
    new = "attribute_not_exists(PK)"
    try:
        # Both or none: the profile and the one-restaurant-per-owner lock.
        table.meta.client.transact_write_items(
            TransactItems=[
                {"Put": {"TableName": name, "Item": profile, "ConditionExpression": new}},
                {"Put": {"TableName": name, "Item": {**_owner_lock_key(owner.sub), "type": "OWNER_LOCK",
                                                     "restaurantId": rid, "createdAt": ts},
                         "ConditionExpression": new}},
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        if "Item" in table.get_item(Key=_owner_lock_key(owner.sub)):
            raise Conflict("You already have a restaurant") from e
        raise

    # Lets cashiers/owner tokens carry the restaurant id. Ownership checks don't depend on it (they use
    # ownerSub), so a failure here is logged and the restaurant is still usable.
    try:
        aws.cognito().admin_update_user_attributes(
            UserPoolId=get_settings().user_pool_id,
            Username=owner.username,
            UserAttributes=[{"Name": "custom:restaurantId", "Value": rid}],
        )
    except ClientError as e:
        logger.warning("Could not set custom:restaurantId for new restaurant %s: %s", rid, e.response["Error"]["Code"])

    return with_status(profile)


def load_owned(owner: Principal, rid: str) -> dict:
    """The restaurant profile, if it exists (404) and the caller owns it (403)."""
    item = aws.table().get_item(Key={"PK": _pk(rid), "SK": "PROFILE"}).get("Item")
    if item is None:
        raise NotFound("Restaurant not found")
    if item.get("ownerSub") != owner.sub:
        raise Forbidden("Not your restaurant")
    return item


def update(owner: Principal, rid: str, data: RestaurantUpdate) -> dict:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise Invalid("Nothing to update")
    current = load_owned(owner, rid)

    if "lat" in changes or "lng" in changes:
        lat = changes.pop("lat", float(current["lat"]))
        lng = changes.pop("lng", float(current["lng"]))
        changes.update(_geo_fields(lat, lng))
    changes["updatedAt"] = now_iso()

    expr = set_expression(changes)
    expr["ExpressionAttributeValues"][":sub"] = owner.sub
    try:
        res = aws.table().update_item(
            Key={"PK": _pk(rid), "SK": "PROFILE"},
            # Re-check ownership atomically: the GetItem above only gives a nice 404/403.
            ConditionExpression="attribute_exists(PK) AND ownerSub = :sub",
            ReturnValues="ALL_NEW",
            **expr,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Forbidden("Not your restaurant") from e
        raise
    return with_status(res["Attributes"])


def set_paused(principal: Principal, rid: str, paused: bool) -> dict:
    """Pause (stop new orders now) or resume (follow opening hours again). Owner or active cashier."""
    require_staff(principal, rid)
    res = aws.table().update_item(
        Key={"PK": _pk(rid), "SK": "PROFILE"},
        UpdateExpression="SET isPaused = :p, updatedAt = :t",
        ConditionExpression="attribute_exists(PK)",
        ExpressionAttributeValues={":p": paused, ":t": now_iso()},
        ReturnValues="ALL_NEW",
    )
    return with_status(res["Attributes"])
