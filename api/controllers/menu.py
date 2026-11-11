"""Menu routes (owner) and the public category list."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.auth import Principal, require_business
from api.models import CategoriesOut, MenuItemCreate, MenuItemOut, MenuItemUpdate
from api.services import categories, menu

router = APIRouter(tags=["menu"])

Owner = Annotated[Principal, Depends(require_business("owner"))]


@router.get("/categories", response_model=CategoriesOut)
def list_categories():
    return {"categories": sorted(categories.allowed())}


@router.post("/restaurants/{restaurant_id}/menu", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
def create_item(restaurant_id: str, body: MenuItemCreate, owner: Owner):
    return menu.create(owner, restaurant_id, body)


@router.patch("/restaurants/{restaurant_id}/menu/{item_id}", response_model=MenuItemOut)
def update_item(restaurant_id: str, item_id: str, body: MenuItemUpdate, owner: Owner):
    return menu.update(owner, restaurant_id, item_id, body)
