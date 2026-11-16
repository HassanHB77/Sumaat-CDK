"""Photo routes (owner only): get an upload form, then attach or remove the photo."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import Principal, require_groups
from api.models import ImageAttachIn, ImageUploadIn, ImageUploadOut, MenuItemOut, RestaurantOut
from api.services import images

router = APIRouter(prefix="/restaurants/{restaurant_id}", tags=["images"])

Owner = Annotated[Principal, Depends(require_groups("owner"))]


@router.post("/image-upload", response_model=ImageUploadOut)
def upload_form(restaurant_id: str, body: ImageUploadIn, owner: Owner):
    """A short-lived form to upload ONE JPEG straight to S3 (restaurant photo, or a dish's with itemId)."""
    return images.upload_form(owner, restaurant_id, body.itemId)


@router.put("/image", response_model=RestaurantOut)
def attach_restaurant(restaurant_id: str, body: ImageAttachIn, owner: Owner):
    return images.attach(owner, restaurant_id, None, body.key)


@router.delete("/image", response_model=RestaurantOut)
def remove_restaurant(restaurant_id: str, owner: Owner):
    return images.remove(owner, restaurant_id, None)


@router.put("/menu/{item_id}/image", response_model=MenuItemOut)
def attach_item(restaurant_id: str, item_id: str, body: ImageAttachIn, owner: Owner):
    return images.attach(owner, restaurant_id, item_id, body.key)


@router.delete("/menu/{item_id}/image", response_model=MenuItemOut)
def remove_item(restaurant_id: str, item_id: str, owner: Owner):
    return images.remove(owner, restaurant_id, item_id)
