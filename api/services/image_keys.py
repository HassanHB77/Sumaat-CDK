"""Where restaurant and dish photos live in S3, and the address the website uses for them.

Keys are always made by the server: img/r/<rid>/<uuid>.jpg (restaurant) and img/r/<rid>/items/<itemId>/<uuid>.jpg
(dish). Every upload gets a new name, so a photo's address never changes content and can be cached forever.
CloudFront serves the bucket at /img/*, so the public address is simply "/" + key.
"""

import uuid

MAX_BYTES = 3 * 1024 * 1024  # the browser shrinks photos to ~1200 px JPEG (usually 150-400 KB) before upload
CONTENT_TYPE = "image/jpeg"


def prefix(rid: str, item_id: str | None = None) -> str:
    return f"img/r/{rid}/items/{item_id}/" if item_id else f"img/r/{rid}/"


def new_key(rid: str, item_id: str | None = None) -> str:
    return f"{prefix(rid, item_id)}{uuid.uuid4()}.jpg"


def belongs_to(key: str, rid: str, item_id: str | None = None) -> bool:
    """True if `key` is a photo name we would have made for exactly this restaurant (or this dish)."""
    p = prefix(rid, item_id)
    if not key.startswith(p) or not key.endswith(".jpg"):
        return False
    name = key[len(p) : -len(".jpg")]
    try:
        uuid.UUID(name)
    except ValueError:
        return False  # also rejects "items/<id>/<uuid>" when a restaurant photo is expected
    return True


def public_url(item: dict) -> str | None:
    key = item.get("imageKey")
    return f"/{key}" if key else None


def with_image_url(item: dict) -> dict:
    """Add `imageUrl` (the API never returns the raw `imageKey`: response models leave it out)."""
    return {**item, "imageUrl": public_url(item)}
