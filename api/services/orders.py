"""Orders: place (customers), read (customers + staff), and move through statuses.

Items (see infra/data_stack.py):
  Order       PK=ORDER#<id>      SK=ORDER   GSI1=RORDERS#<rid>/<createdAt>  GSI2=CORDERS#<sub>/<createdAt>
  Counter     PK=RESTAURANT#<id> SK=COUNTER#<YYYY-MM-DD>  seq   (daily numbers, Riyadh date: #1, #2, ...)
  Open order  PK=CUSTOMER#<sub>  SK=OPEN#<rid>  orderId, orderNumber
              One open order per customer per restaurant; deleted when the order reaches a final status.

Personal data (customer name/phone/email) comes from the login token, is stored on the order, and is never logged.
"""

import uuid
from datetime import UTC, date, datetime

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from api import aws, hours
from api.auth import Principal
from api.errors import Conflict, Forbidden, Invalid, NotFound
from api.models import OrderCreate
from api.services import restaurants
from api.services.staff import require_staff

OPEN_STATUSES = ("PLACED", "ACCEPTED", "READY_FOR_PICKUP")
FINAL_STATUSES = ("SERVED", "REJECTED", "CANCELLED")
LIST_LIMIT = 50


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")  # same format as api/clock.now_iso


def order_key(order_id: str) -> dict:
    return {"PK": f"ORDER#{order_id}", "SK": "ORDER"}


def open_lock_key(customer_sub: str, rid: str) -> dict:
    return {"PK": f"CUSTOMER#{customer_sub}", "SK": f"OPEN#{rid}"}


# --- place -------------------------------------------------------------------


def _next_number(rid: str, day: date) -> int:
    """Atomic daily counter: the first call of a Riyadh day returns 1."""
    res = aws.table().update_item(
        Key={"PK": f"RESTAURANT#{rid}", "SK": f"COUNTER#{day.isoformat()}"},
        UpdateExpression="ADD seq :one SET #t = :t",
        ExpressionAttributeNames={"#t": "type"},
        ExpressionAttributeValues={":one": 1, ":t": "COUNTER"},
        ReturnValues="UPDATED_NEW",
    )
    return int(res["Attributes"]["seq"])


def _open_conflict(lock: dict) -> Conflict:
    return Conflict(f"You already have an open order here (#{lock['orderNumber']})")


def place(customer: Principal, data: OrderCreate) -> dict:
    table = aws.table()
    now = hours.riyadh_now()  # one clock for openNow, businessDate and createdAt

    restaurant = restaurants.get(data.restaurantId)  # profile + menu in one Query; 404 if unknown
    if not hours.open_now(restaurant, now):
        raise Conflict("Restaurant is closed")

    menu = {i["id"]: i for i in restaurant["menu"]}
    lines = []
    for line in data.items:
        item = menu.get(line.itemId)
        if item is None:
            raise Invalid(f"Unknown menu item: {line.itemId}")
        if not item.get("isAvailable", False):
            raise Invalid(f"Not available right now: {item['name']}")
        unit = int(item["priceHalalas"])  # from the database, never from the client
        lines.append(
            {
                "itemId": item["id"],
                "name": item["name"],
                "nameAr": item["nameAr"],
                "unitPriceHalalas": unit,
                "qty": line.qty,
                "lineTotalHalalas": unit * line.qty,
            }
        )

    rid = data.restaurantId
    lock_key = open_lock_key(customer.sub, rid)
    if lock := table.get_item(Key=lock_key).get("Item"):  # fail fast, before using up a number
        raise _open_conflict(lock)

    day = hours.riyadh_date(now)
    number = _next_number(rid, day)
    order_id = str(uuid.uuid4())
    ts = _iso(now)
    order = {
        **order_key(order_id),
        "type": "ORDER",
        "id": order_id,
        "orderNumber": number,
        "businessDate": day.isoformat(),
        "restaurantId": rid,
        "restaurantName": restaurant["name"],
        "customerSub": customer.sub,
        "customerName": customer.name,
        "customerPhone": customer.phone,
        "customerEmail": customer.email,  # for the Step 8 pickup email; never returned by the API
        "items": lines,
        "totalHalalas": sum(line["lineTotalHalalas"] for line in lines),
        "note": data.note,
        "status": "PLACED",
        "statusHistory": [{"status": "PLACED", "at": ts, "by": customer.sub, "role": "customer"}],
        "createdAt": ts,
        "updatedAt": ts,
        "GSI1PK": f"RORDERS#{rid}",
        "GSI1SK": ts,
        "GSI2PK": f"CORDERS#{customer.sub}",
        "GSI2SK": ts,
    }
    name = table.name
    try:
        # Both or neither: the order and the "one open order here" lock.
        table.meta.client.transact_write_items(
            TransactItems=[
                {"Put": {"TableName": name, "Item": order, "ConditionExpression": "attribute_not_exists(PK)"}},
                {
                    "Put": {
                        "TableName": name,
                        "Item": {**lock_key, "type": "OPEN_ORDER", "orderId": order_id, "orderNumber": number,
                                 "createdAt": ts},
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            if lock := table.get_item(Key=lock_key).get("Item"):  # two taps at the same moment
                raise _open_conflict(lock) from e
        raise
    return order


# --- read --------------------------------------------------------------------


def mine(customer: Principal) -> list[dict]:
    return aws.table().query(
        IndexName="GSI2",
        KeyConditionExpression=Key("GSI2PK").eq(f"CORDERS#{customer.sub}"),
        ScanIndexForward=False,  # newest first
        Limit=LIST_LIMIT,
    )["Items"]


def get_for(principal: Principal, order_id: str) -> dict:
    """The customer who placed it, or staff of that restaurant. Anyone else: 404 (don't reveal it exists)."""
    order = aws.table().get_item(Key=order_key(order_id)).get("Item")
    if order is None:
        raise NotFound("Order not found")
    if order["customerSub"] == principal.sub:
        return order
    try:
        require_staff(principal, order["restaurantId"])
    except (Forbidden, NotFound):
        raise NotFound("Order not found") from None
    return order


def for_restaurant(principal: Principal, rid: str, day: date | None = None, status: str | None = None) -> list[dict]:
    """Staff view: one Riyadh day (default today), newest first, optional status filter."""
    require_staff(principal, rid)
    start, end = hours.day_bounds_utc(day or hours.riyadh_date())
    kwargs = {
        "IndexName": "GSI1",
        "KeyConditionExpression": Key("GSI1PK").eq(f"RORDERS#{rid}") & Key("GSI1SK").between(start, end),
        "ScanIndexForward": False,
    }
    if status:
        kwargs["FilterExpression"] = Attr("status").eq(status)
    items: list[dict] = []
    while True:
        page = aws.table().query(**kwargs)
        items += [o for o in page["Items"] if o["GSI1SK"] < end]  # BETWEEN includes `end`; the day is [start, end)
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


# --- status changes ------------------------------------------------------------

# action -> (allowed from, new status, who may do it)
TRANSITIONS = {
    "accept": ("PLACED", "ACCEPTED", "staff"),
    "ready": ("ACCEPTED", "READY_FOR_PICKUP", "staff"),
    "served": ("READY_FOR_PICKUP", "SERVED", "staff"),
    "reject": ("PLACED", "REJECTED", "staff"),
    "cancel": ("PLACED", "CANCELLED", "customer"),
}


def _actor_role(principal: Principal, order: dict, who: str) -> str:
    """'customer' / 'owner' / 'cashier' if allowed; NotFound otherwise (don't reveal the order exists)."""
    if who == "customer":
        if order["customerSub"] == principal.sub:
            return "customer"
        raise NotFound("Order not found")
    try:
        role, _ = require_staff(principal, order["restaurantId"])
    except (Forbidden, NotFound):
        raise NotFound("Order not found") from None
    return role


def change_status(principal: Principal, order_id: str, action: str, reason: str | None = None) -> dict:
    """Move an order one step. Only forward, only from the expected status (409 otherwise).

    One transaction: the conditional status update, plus, for a final status, deleting the customer's
    one-open-order lock so they can order at this restaurant again.
    """
    from_status, to_status, who = TRANSITIONS[action]
    table = aws.table()
    order = table.get_item(Key=order_key(order_id)).get("Item")
    if order is None:
        raise NotFound("Order not found")
    role = _actor_role(principal, order, who)
    if order["status"] != from_status:
        raise Conflict(f"Order is {order['status']}, can't {action}")

    ts = _iso(hours.riyadh_now())
    change = {"status": to_status, "at": ts, "by": principal.sub, "role": role}
    if reason:
        change["reason"] = reason
    name = table.name
    update = {
        "Update": {
            "TableName": name,
            "Key": order_key(order_id),
            "UpdateExpression": "SET #s = :to, updatedAt = :t, statusHistory = list_append(statusHistory, :h)",
            "ConditionExpression": "#s = :from",  # someone else may have changed it a moment ago
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {":to": to_status, ":from": from_status, ":t": ts, ":h": [change]},
        }
    }
    items = [update]
    if to_status in FINAL_STATUSES:
        items.append(
            {
                "Delete": {
                    "TableName": name,
                    "Key": open_lock_key(order["customerSub"], order["restaurantId"]),
                    # Only this order's lock (never a newer one).
                    "ConditionExpression": "attribute_not_exists(PK) OR orderId = :id",
                    "ExpressionAttributeValues": {":id": order_id},
                }
            }
        )
    try:
        table.meta.client.transact_write_items(TransactItems=items)
    except ClientError as e:
        if e.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        current = table.get_item(Key=order_key(order_id))["Item"]["status"]
        raise Conflict(f"Order is {current}, can't {action}") from e
    return table.get_item(Key=order_key(order_id))["Item"]
