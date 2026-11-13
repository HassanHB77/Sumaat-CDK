"""Daily AI-chat message allowance per customer (Step 9).

Each customer may send CHAT_DAILY_LIMIT (default 10) chat messages per business day (04:00 -> 04:00 Riyadh,
the same day boundary as order numbers). Shared by the agent (counts each message) and the API (shows how many
are left before the first message).

Item: PK=CHATQUOTA#<sub>  SK=DAY#<YYYY-MM-DD>  n (messages used)  expiresAt (epoch seconds; DynamoDB TTL
deletes the row 2 days after its business day ends)

Counting is one conditional update (ADD n 1 only while n < limit), so two messages sent at the same moment
can never both take the last one.
"""

import os
from datetime import datetime, time, timedelta

from botocore.exceptions import ClientError

from api import aws, hours
from api.errors import TooMany

DEFAULT_LIMIT = 10
KEEP_DAYS = 2  # after the business day ends


class QuotaExceeded(TooMany):
    pass


def daily_limit() -> int:
    return int(os.environ.get("CHAT_DAILY_LIMIT", DEFAULT_LIMIT))


def _key(sub: str, now: datetime | None = None) -> dict:
    return {"PK": f"CHATQUOTA#{sub}", "SK": f"DAY#{hours.business_date(now).isoformat()}"}


def _expires_at(now: datetime | None = None) -> int:
    day = hours.business_date(now)
    day_end = datetime.combine(day + timedelta(days=1), time(hours.DAY_START_HOUR), hours.RIYADH)
    return int((day_end + timedelta(days=KEEP_DAYS)).timestamp())


def peek(sub: str, limit: int | None = None) -> int:
    """Messages left today (never below 0)."""
    limit = daily_limit() if limit is None else limit
    item = aws.table().get_item(Key=_key(sub)).get("Item") or {}
    return max(0, limit - int(item.get("n", 0)))


def use_one(sub: str, limit: int | None = None) -> int:
    """Take one message from today's allowance and return how many are left. QuotaExceeded when none are left."""
    limit = daily_limit() if limit is None else limit
    now = hours.riyadh_now()  # one clock reading, so key and expiry agree at 04:00
    try:
        res = aws.table().update_item(
            Key=_key(sub, now),
            UpdateExpression="ADD n :one SET expiresAt = :exp",
            ConditionExpression="attribute_not_exists(n) OR n < :limit",
            ExpressionAttributeValues={":one": 1, ":limit": limit, ":exp": _expires_at(now)},
            ReturnValues="UPDATED_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise QuotaExceeded("No chat messages left today") from e
        raise
    return max(0, limit - int(res["Attributes"]["n"]))


def give_back(sub: str) -> None:
    """Return one message (our side failed). Never goes below 0; a no-op if nothing was used today."""
    try:
        aws.table().update_item(
            Key=_key(sub),
            UpdateExpression="ADD n :minus",
            ConditionExpression="n > :zero",
            ExpressionAttributeValues={":minus": -1, ":zero": 0},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
