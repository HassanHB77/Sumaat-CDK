"""Restaurant and dish photos (owner only).

Upload in three steps, so photo bytes never pass through the Lambda:
  1. upload_form()  -> a short-lived presigned S3 POST for a NEW key the server picks (JPEG, max 3 MB).
  2. the browser POSTs the (already shrunk) JPEG straight to S3.
  3. attach()       -> checks the key is ours and the file really is there, saves `imageKey`, removes the old photo.
remove() clears `imageKey` and deletes the file. Orders don't keep photos, so deleting a file never breaks one.
"""

import logging

from botocore.exceptions import ClientError

from api import aws
from api.auth import Principal
from api.clock import now_iso
from api.errors import Forbidden, Invalid, NotFound
from api.services import image_keys
from api.services.restaurants import load_owned, with_status
from api.settings import get_settings

logger = logging.getLogger(__name__)

UPLOAD_SECONDS = 300
LONG_CACHE = "public, max-age=31536000, immutable"  # a key's content never changes (new upload = new key)


def _profile_key(rid: str) -> dict:
    return {"PK": f"RESTAURANT#{rid}", "SK": "PROFILE"}


def _item_key(rid: str, item_id: str) -> dict:
    return {"PK": f"RESTAURANT#{rid}", "SK": f"ITEM#{item_id}"}


def _load_item(rid: str, item_id: str) -> dict:
    item = aws.table().get_item(Key=_item_key(rid, item_id)).get("Item")
    if item is None:
        raise NotFound("Menu item not found")
    return item


def upload_form(owner: Principal, rid: str, item_id: str | None) -> dict:
    load_owned(owner, rid)
    if item_id:
        _load_item(rid, item_id)
    key = image_keys.new_key(rid, item_id)
    post = aws.s3().generate_presigned_post(
        Bucket=get_settings().images_bucket,
        Key=key,
        Fields={"Content-Type": image_keys.CONTENT_TYPE, "Cache-Control": LONG_CACHE},
        Conditions=[
            {"Content-Type": image_keys.CONTENT_TYPE},
            {"Cache-Control": LONG_CACHE},
            ["content-length-range", 1, image_keys.MAX_BYTES],
        ],
        ExpiresIn=UPLOAD_SECONDS,
    )
    return {"url": post["url"], "fields": post["fields"], "key": key, "maxBytes": image_keys.MAX_BYTES}


def _check_uploaded(key: str) -> None:
    try:
        head = aws.s3().head_object(Bucket=get_settings().images_bucket, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            raise Invalid("Photo not found: upload it first") from e
        raise
    if head.get("ContentType") != image_keys.CONTENT_TYPE or head.get("ContentLength", 0) > image_keys.MAX_BYTES:
        raise Invalid("Photo must be a JPEG of at most 3 MB")


def _delete_file(key: str | None) -> None:
    """Best effort: a file left behind costs fractions of a cent; it must never fail the request."""
    if not key:
        return
    try:
        aws.s3().delete_object(Bucket=get_settings().images_bucket, Key=key)
    except ClientError as e:
        logger.warning("Could not delete an old photo: %s", e.response["Error"]["Code"])


def _set_key(db_key: dict, image_key: str | None, condition: str, values: dict) -> dict:
    expr_values = {":t": now_iso(), **values}
    if image_key:
        update = "SET imageKey = :k, updatedAt = :t"
        expr_values[":k"] = image_key
    else:
        update = "REMOVE imageKey SET updatedAt = :t"
    try:
        res = aws.table().update_item(
            Key=db_key,
            UpdateExpression=update,
            ConditionExpression=condition,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Forbidden("Not your restaurant") from e
        raise
    return res["Attributes"]


def _save(owner: Principal, rid: str, item_id: str | None, image_key: str | None) -> dict:
    """Write (or clear) imageKey on the profile or the dish, then delete the replaced file. Returns the new row."""
    profile = load_owned(owner, rid)
    if item_id:
        old = _load_item(rid, item_id).get("imageKey")
        row = _set_key(_item_key(rid, item_id), image_key, "attribute_exists(PK)", {})
        result = image_keys.with_image_url(row)
    else:
        old = profile.get("imageKey")
        # Re-check ownership atomically (load_owned above only gives a clear 404/403).
        row = _set_key(_profile_key(rid), image_key, "attribute_exists(PK) AND ownerSub = :sub", {":sub": owner.sub})
        result = with_status(row)
    if old != image_key:
        _delete_file(old)
    return result


def attach(owner: Principal, rid: str, item_id: str | None, key: str) -> dict:
    if not image_keys.belongs_to(key, rid, item_id):
        raise Invalid("This photo does not belong here")
    load_owned(owner, rid)  # 404/403 before touching S3
    _check_uploaded(key)
    return _save(owner, rid, item_id, key)


def remove(owner: Principal, rid: str, item_id: str | None) -> dict:
    return _save(owner, rid, item_id, None)
