"""Menu items. Owners add and edit; there is no delete (hide with isAvailable=false instead).

Item: PK=RESTAURANT#<rid>  SK=ITEM#<id>  (same partition as the profile, so GET /restaurants/{id} is one Query)
"""

import uuid

from botocore.exceptions import ClientError

from api import aws
from api.auth import Principal
from api.clock import now_iso
from api.errors import Invalid, NotFound
from api.models import MenuItemCreate, MenuItemUpdate
from api.services import categories
from api.services.ddb import set_expression
from api.services.image_keys import with_image_url
from api.services.restaurants import load_owned


def _key(rid: str, item_id: str) -> dict:
    return {"PK": f"RESTAURANT#{rid}", "SK": f"ITEM#{item_id}"}


def create(owner: Principal, rid: str, data: MenuItemCreate) -> dict:
    load_owned(owner, rid)
    categories.check(data.category)
    item_id = str(uuid.uuid4())
    ts = now_iso()
    item = {
        **_key(rid, item_id),
        "type": "MENU_ITEM",
        "id": item_id,
        "restaurantId": rid,
        **data.model_dump(),
        "createdAt": ts,
        "updatedAt": ts,
    }
    aws.table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    return with_image_url(item)


def update(owner: Principal, rid: str, item_id: str, data: MenuItemUpdate) -> dict:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise Invalid("Nothing to update")
    load_owned(owner, rid)
    if "category" in changes:
        categories.check(changes["category"])
    changes["updatedAt"] = now_iso()

    try:
        res = aws.table().update_item(
            Key=_key(rid, item_id),
            ConditionExpression="attribute_exists(PK)",  # never create an item by PATCHing a wrong id
            ReturnValues="ALL_NEW",
            **set_expression(changes),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFound("Menu item not found") from e
        raise
    return with_image_url(res["Attributes"])
