"""Restaurant routes. Browsing is public; changes need an owner token."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from api.auth import Principal, require_groups
from api.models import (
    MAX_RADIUS_KM,
    Lat,
    Lng,
    NearbyRestaurant,
    RestaurantCreate,
    RestaurantDetail,
    RestaurantOut,
    RestaurantUpdate,
)
from api.services import restaurants

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

Owner = Annotated[Principal, Depends(require_groups("owner"))]


@router.get("", response_model=list[NearbyRestaurant])
def list_near(
    lat: Annotated[Lat, Query()],
    lng: Annotated[Lng, Query()],
    radiusKm: Annotated[float, Query(gt=0, le=MAX_RADIUS_KM)] = 3.0,
):
    return restaurants.near(lat, lng, radiusKm)


@router.get("/{restaurant_id}", response_model=RestaurantDetail)
def get_one(restaurant_id: str):
    return restaurants.get(restaurant_id)


@router.post("", response_model=RestaurantOut, status_code=status.HTTP_201_CREATED)
def create(body: RestaurantCreate, owner: Owner):
    return restaurants.create(owner, body)


@router.patch("/{restaurant_id}", response_model=RestaurantOut)
def update(restaurant_id: str, body: RestaurantUpdate, owner: Owner):
    return restaurants.update(owner, restaurant_id, body)
