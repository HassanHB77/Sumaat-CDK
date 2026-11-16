"""Restaurant and dish photos: upload form, attach, replace, remove; imageUrl in public responses."""

import boto3
import pytest

from api.handler import app
from api.services import image_keys
from scripts.seed import seed
from tests.unit.api.conftest import NEW, customer_claims, owner_claims

BUCKET = "sumaat-images-test"
DISH = {"name": "Camel Burger", "nameAr": "برجر", "category": "Mains", "priceHalalas": 3900}


@pytest.fixture
def setup(ddb, make_client, monkeypatch):
    """Seeded table + images bucket + a restaurant (owner-sub-1) with one dish."""
    table, *_ = ddb
    monkeypatch.setenv("IMAGES_BUCKET", BUCKET)
    from api import aws
    from api.settings import get_settings

    get_settings.cache_clear()
    aws.s3.cache_clear()
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    seed(table)
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]
    item = owner.post(f"/restaurants/{rid}/menu", json=DISH).json()["id"]
    return {"s3": s3, "owner": owner, "rid": rid, "item": item, "public": make_client(app)}


def _upload(s, item_id=None, body=b"\xff\xd8jpeg", content_type="image/jpeg") -> str:
    """Ask for a form, then put the file where the browser would (moto doesn't run the POST policy)."""
    res = s["owner"].post(f"/restaurants/{s['rid']}/image-upload", json={"itemId": item_id} if item_id else {})
    assert res.status_code == 200, res.text
    key = res.json()["key"]
    s["s3"].put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=content_type)
    return key


def _exists(s, key) -> bool:
    return s["s3"].list_objects_v2(Bucket=BUCKET, Prefix=key).get("KeyCount", 0) == 1


# --- upload form -------------------------------------------------------------


def test_upload_form_is_a_presigned_post_for_a_new_server_made_key(setup):
    res = setup["owner"].post(f"/restaurants/{setup['rid']}/image-upload", json={})
    body = res.json()
    assert res.status_code == 200
    assert image_keys.belongs_to(body["key"], setup["rid"])
    assert body["fields"]["key"] == body["key"]
    assert body["fields"]["Content-Type"] == "image/jpeg"
    assert "policy" in body["fields"] or "Policy" in body["fields"]
    assert BUCKET in body["url"]
    assert body["maxBytes"] == 3 * 1024 * 1024


def test_upload_form_for_a_dish_uses_the_dish_folder(setup):
    res = setup["owner"].post(f"/restaurants/{setup['rid']}/image-upload", json={"itemId": setup["item"]})
    assert image_keys.belongs_to(res.json()["key"], setup["rid"], setup["item"])


def test_upload_form_for_unknown_dish_is_404(setup):
    res = setup["owner"].post(f"/restaurants/{setup['rid']}/image-upload", json={"itemId": "nope"})
    assert res.status_code == 404


def test_upload_form_only_for_the_owner(setup, make_client):
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    assert other.post(f"/restaurants/{setup['rid']}/image-upload", json={}).status_code == 403
    customer = make_client(app, customer_claims())
    assert customer.post(f"/restaurants/{setup['rid']}/image-upload", json={}).status_code == 403
    assert setup["public"].post(f"/restaurants/{setup['rid']}/image-upload", json={}).status_code == 401


def test_upload_form_rejects_unknown_fields(setup):
    res = setup["owner"].post(f"/restaurants/{setup['rid']}/image-upload", json={"key": "img/evil.jpg"})
    assert res.status_code == 422


# --- restaurant photo --------------------------------------------------------


def test_attach_restaurant_photo_shows_in_public_responses(setup):
    key = _upload(setup)
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    assert res.status_code == 200
    assert res.json()["imageUrl"] == f"/{key}"
    assert "imageKey" not in res.json()

    detail = setup["public"].get(f"/restaurants/{setup['rid']}").json()
    assert detail["imageUrl"] == f"/{key}"
    near = setup["public"].get("/restaurants", params={"lat": NEW["lat"], "lng": NEW["lng"]}).json()
    assert next(r for r in near if r["id"] == setup["rid"])["imageUrl"] == f"/{key}"


def test_no_photo_means_null_image_url(setup):
    detail = setup["public"].get(f"/restaurants/{setup['rid']}").json()
    assert detail["imageUrl"] is None
    assert detail["menu"][0]["imageUrl"] is None


def test_replace_deletes_the_old_file(setup):
    first = _upload(setup)
    setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": first})
    second = _upload(setup)
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": second})
    assert res.json()["imageUrl"] == f"/{second}"
    assert not _exists(setup, first)
    assert _exists(setup, second)


def test_remove_restaurant_photo(setup):
    key = _upload(setup)
    setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    res = setup["owner"].delete(f"/restaurants/{setup['rid']}/image")
    assert res.status_code == 200
    assert res.json()["imageUrl"] is None
    assert not _exists(setup, key)


def test_remove_without_photo_is_fine(setup):
    assert setup["owner"].delete(f"/restaurants/{setup['rid']}/image").status_code == 200


# --- dish photo --------------------------------------------------------------


def test_attach_and_remove_dish_photo(setup):
    key = _upload(setup, setup["item"])
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/menu/{setup['item']}/image", json={"key": key})
    assert res.status_code == 200
    assert res.json()["imageUrl"] == f"/{key}"
    menu = setup["public"].get(f"/restaurants/{setup['rid']}").json()["menu"]
    assert menu[0]["imageUrl"] == f"/{key}"

    res = setup["owner"].delete(f"/restaurants/{setup['rid']}/menu/{setup['item']}/image")
    assert res.json()["imageUrl"] is None
    assert not _exists(setup, key)


def test_dish_edit_keeps_the_photo(setup):
    key = _upload(setup, setup["item"])
    setup["owner"].put(f"/restaurants/{setup['rid']}/menu/{setup['item']}/image", json={"key": key})
    res = setup["owner"].patch(f"/restaurants/{setup['rid']}/menu/{setup['item']}", json={"priceHalalas": 4100})
    assert res.json()["imageUrl"] == f"/{key}"


def test_unknown_dish_photo_is_404(setup):
    key = _upload(setup)  # a valid restaurant key, but the dish doesn't exist
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/menu/nope/image", json={"key": key})
    assert res.status_code == 422  # the key isn't one made for that dish
    assert setup["owner"].delete(f"/restaurants/{setup['rid']}/menu/nope/image").status_code == 404


# --- what attach refuses -----------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "img/r/other-restaurant/0b8f7c9e-2a7c-4d8e-9a4f-1b2c3d4e5f60.jpg",
        "img/r/{rid}/../x.jpg",
        "img/r/{rid}/not-a-uuid.jpg",
        "img/r/{rid}/0b8f7c9e-2a7c-4d8e-9a4f-1b2c3d4e5f60.png",
        "img/r/{rid}/items/{item}/0b8f7c9e-2a7c-4d8e-9a4f-1b2c3d4e5f60.jpg",  # a dish key for the restaurant
        "index.html",
    ],
)
def test_attach_refuses_keys_not_made_for_this_place(setup, key):
    key = key.format(rid=setup["rid"], item=setup["item"])
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    assert res.status_code == 422


def test_attach_refuses_a_key_that_was_never_uploaded(setup):
    key = image_keys.new_key(setup["rid"])
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    assert res.status_code == 422
    assert "upload" in res.json()["detail"].lower()


def test_attach_refuses_a_non_jpeg(setup):
    key = _upload(setup, content_type="text/html")
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    assert res.status_code == 422


def test_attach_refuses_too_big(setup):
    key = _upload(setup, body=b"0" * (image_keys.MAX_BYTES + 1))
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": key})
    assert res.status_code == 422


def test_other_owner_cannot_attach_or_remove(setup, make_client):
    key = _upload(setup)
    other = make_client(app, owner_claims(sub="owner-sub-2"))
    assert other.put(f"/restaurants/{setup['rid']}/image", json={"key": key}).status_code == 403
    assert other.delete(f"/restaurants/{setup['rid']}/image").status_code == 403
    assert other.delete(f"/restaurants/{setup['rid']}/menu/{setup['item']}/image").status_code == 403


# --- key helpers -------------------------------------------------------------


def test_keys_and_urls():
    k = image_keys.new_key("r1")
    assert k.startswith("img/r/r1/") and k.endswith(".jpg")
    assert image_keys.belongs_to(k, "r1")
    assert not image_keys.belongs_to(k, "r1", "i1")
    d = image_keys.new_key("r1", "i1")
    assert image_keys.belongs_to(d, "r1", "i1")
    assert not image_keys.belongs_to(d, "r1")
    assert image_keys.public_url({"imageKey": k}) == f"/{k}"
    assert image_keys.public_url({}) is None


def test_attach_missing_upload_is_422_even_when_s3_says_403(setup, monkeypatch):
    """Live S3 answers a missing key with 403 when the caller can't list the bucket (moto says 404)."""
    from botocore.exceptions import ClientError

    from api import aws

    def forbidden(**_):
        raise ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject")

    monkeypatch.setattr(aws.s3(), "head_object", forbidden)
    res = setup["owner"].put(f"/restaurants/{setup['rid']}/image", json={"key": image_keys.new_key(setup["rid"])})
    assert res.status_code == 422
