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

# Same rules as the Cognito pool (infra/auth_stack.py), checked here first for a clear 422.
Password = Annotated[str, Field(min_length=8, max_length=128)]
Phone = Annotated[str, Field(pattern=r"^\+[1-9]\d{7,14}$", examples=["+966500000001"])]  # E.164
# name@domain.tld; no spaces, commas, semicolons or brackets (a pasted "a@b.com," was accepted before).
Email = Annotated[str, Field(pattern=r"^[^@\s,;<>()\[\]]+@[^@\s,;<>()\[\]]+\.[A-Za-z]{2,}$", max_length=254)]


def check_password_rules(password: str) -> str:
    missing = [
        label
        for label, ok in (
            ("an uppercase letter", any(c.isupper() for c in password)),
            ("a lowercase letter", any(c.islower() for c in password)),
            ("a digit", any(c.isdigit() for c in password)),
            ("a symbol", any(not c.isalnum() and not c.isspace() for c in password)),
        )
        if not ok
    ]
    if missing:
        raise ValueError("Password needs " + ", ".join(missing))
    return password


StrongPassword = Annotated[Password, AfterValidator(check_password_rules)]

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


class RestaurantUpdate(_In):
    name: Name | None = None
    nameAr: Name | None = None
    description: Annotated[str, Field(max_length=500)] | None = None
    city: Name | None = None
    district: Name | None = None
    lat: Lat | None = None
    lng: Lng | None = None
    hours: Hours | None = None


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
    isPaused: bool = False  # staff pressed "Pause" (stop new orders now)
    openNow: bool  # taking orders right now: not paused AND inside hours (Riyadh time)
    createdAt: str
    updatedAt: str


class NearbyRestaurant(RestaurantOut):
    distanceKm: float


class RestaurantDetail(RestaurantOut):
    menu: list[MenuItemOut]


class CashierCreate(_In):
    name: Name
    email: Email
    phone: Phone
    password: StrongPassword


class PasswordReset(_In):
    password: StrongPassword


class CashierOut(BaseModel):
    sub: str
    name: str
    email: str
    phone: str
    status: Literal["active", "disabled"]
    createdAt: str
    updatedAt: str


# --- orders ------------------------------------------------------------------

OrderStatus = Literal["PLACED", "ACCEPTED", "READY_FOR_PICKUP", "SERVED", "REJECTED", "CANCELLED"]


class OrderLineIn(_In):
    itemId: Annotated[str, Field(min_length=1, max_length=64)]
    qty: Annotated[int, Field(strict=True, ge=1, le=20)]


def _no_duplicate_items(lines: list[OrderLineIn]) -> list[OrderLineIn]:
    ids = [line.itemId for line in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("Each item may appear only once; use qty instead")
    return lines


class OrderCreate(_In):
    """No prices here on purpose: the API takes prices from the menu in the database."""

    restaurantId: Annotated[str, Field(min_length=1, max_length=64)]
    items: Annotated[list[OrderLineIn], Field(min_length=1, max_length=20), AfterValidator(_no_duplicate_items)]
    note: Annotated[str, Field(max_length=200)] | None = None


class OrderLine(BaseModel):
    itemId: str
    name: str
    nameAr: str
    unitPriceHalalas: int
    qty: int
    lineTotalHalalas: int


class StatusChange(BaseModel):
    status: OrderStatus
    at: str
    by: str
    role: Literal["customer", "owner", "cashier"]
    reason: str | None = None


class OrderOut(BaseModel):
    """What customers and staff see. customerEmail is never returned (kept only for the pickup email)."""

    id: str
    orderNumber: int
    businessDate: str  # business day (04:00-04:00 Riyadh); numbers restart at #1 every business day
    restaurantId: str
    restaurantName: str
    restaurantNameAr: str | None = None  # orders placed before Step 7 don't have it
    customerName: str | None = None
    customerPhone: str | None = None
    items: list[OrderLine]
    totalHalalas: int  # VAT included
    note: str | None = None
    status: OrderStatus
    statusHistory: list[StatusChange]
    createdAt: str
    updatedAt: str


class RejectBody(_In):
    reason: Annotated[str, Field(max_length=200)] | None = None
