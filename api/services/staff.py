"""Who may run a restaurant's day-to-day work (pause/resume, handle orders)?

  owner    restaurant.ownerSub == caller's sub (checked in the database, not the token)
  cashier  in the `cashier` group, token's custom:restaurantId == this restaurant, AND the
           CASHIER#<sub> record is active. The record check makes "disable cashier" take effect
           immediately: a disabled cashier's token stays valid up to 1 hour, but this check fails.
"""

from typing import Literal

from api import aws
from api.auth import Principal
from api.errors import Forbidden, NotFound

Role = Literal["owner", "cashier"]


def cashier_key(rid: str, sub: str) -> dict:
    return {"PK": f"RESTAURANT#{rid}", "SK": f"CASHIER#{sub}"}


def require_staff(principal: Principal, rid: str) -> tuple[Role, dict]:
    """Returns (role, restaurant profile). 404 if the restaurant doesn't exist, 403 if not staff."""
    table = aws.table()
    profile = table.get_item(Key={"PK": f"RESTAURANT#{rid}", "SK": "PROFILE"}).get("Item")
    if profile is None:
        raise NotFound("Restaurant not found")
    if profile.get("ownerSub") == principal.sub:
        return "owner", profile
    if "cashier" in principal.groups and principal.restaurant_id == rid:
        record = table.get_item(Key=cashier_key(rid, principal.sub)).get("Item")
        if record and record.get("status") == "active":
            return "cashier", profile
    raise Forbidden("Not staff of this restaurant")
