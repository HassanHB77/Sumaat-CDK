"""Request/response shapes. Field names are camelCase to match the DynamoDB items and the React app.

Money is always an int in halalas (100 halalas = 1 SAR). Never floats for money.
lat/lng are floats in JSON; services convert them to Decimal for DynamoDB (boto3 rejects floats).
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

DietTag = Literal["vegetarian", "vegan", "gluten_free", "dairy_free", "high_protein", "spicy"]

Name = Annotated[str, Field(min_length=1, max_length=80)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lng = Annotated[float, Field(ge=-180, le=180)]
Hours = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$", examples=["12:00-23:30"])]

Category = Annotated[str, Field(min_length=1, max_length=40)]
# strict=True: JSON 1500 is accepted, but 15.5 and "1500" are rejected (money is never a float or a string).
Halalas = Annotated[int, Field(strict=True, ge=1, le=1_000_000)]
Calories = Annotated[int, Field(strict=True, ge=0, le=10_000)]
DietTags = Annotated[list[DietTag], Field(max_length=6), AfterValidator(lambda tags: list(dict.fromkeys(tags)))]

# The 3x3 geohash block always covers at least ~4.4 km around the caller (see api/geo.cells_around).
MAX_RADIUS_KM = 4.4


class _In(BaseModel):
    # Unknown fields -> 422. A client can never sneak in ownerSub, PK, GSI1PK, ...
    model_config = ConfigDict(extra="forbid")


class RestaurantCreate(_In):
    name: Name
    nameAr: Name
    description: Annotated[str, Field(max_length=500)] = ""
    city: Name
    district: Name
    lat: Lat
    lng: Lng
    hours: Hours
    isOpen: bool = True


class RestaurantUpdate(_In):
    name: Name | None = None
    nameAr: Name | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    city: Name | None = None
    district: Name | None = None
    lat: Lat | None = None
    lng: Lng | None = None
    hours: Hours | None = None
    isOpen: bool | None = None


class MenuItemCreate(_In):
    name: Name
    nameAr: Name
    category: Category
    priceHalalas: Halalas
    calories: Calories = 0
    dietTags: DietTags = []
    isAvailable: bool = True


class MenuItemUpdate(_In):
    name: Name | None = None
    nameAr: Name | None = None
    category: Category | None = None
    priceHalalas: Halalas | None = None
    calories: Calories | None = None
    dietTags: DietTags | None = None
    isAvailable: bool | None = None


class CategoriesOut(BaseModel):
    categories: list[str]


class MenuItemOut(BaseModel):
    id: str
    restaurantId: str
    name: str
    nameAr: str
    category: str
    priceHalalas: int
    calories: int
    dietTags: list[str] = []
    isAvailable: bool


class RestaurantOut(BaseModel):
    id: str
    name: str
    nameAr: str
    description: str = ""
    city: str
    district: str
    lat: float
    lng: float
    hours: str
    isOpen: bool
    createdAt: str
    updatedAt: str


class NearbyRestaurant(RestaurantOut):
    distanceKm: float


class RestaurantDetail(RestaurantOut):
    menu: list[MenuItemOut]
