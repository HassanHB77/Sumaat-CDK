"""Order routes. Placing an order: customers only. Reading: the customer, or staff of that restaurant."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from api.auth import Principal, require_customer, require_user
from api.models import OrderCreate, OrderOut, OrderStatus
from api.services import orders

router = APIRouter(tags=["orders"])

Customer = Annotated[Principal, Depends(require_customer())]
User = Annotated[Principal, Depends(require_user())]  # the service checks customer-or-staff


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def place(body: OrderCreate, customer: Customer):
    return orders.place(customer, body)


# Declared before /orders/{order_id} so "mine" is not read as an order id.
@router.get("/orders/mine", response_model=list[OrderOut])
def my_orders(customer: Customer):
    return orders.mine(customer)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, user: User):
    return orders.get_for(user, order_id)


@router.get("/restaurants/{restaurant_id}/orders", response_model=list[OrderOut])
def restaurant_orders(
    restaurant_id: str,
    user: User,
    day: Annotated[date | None, Query(alias="date", description="Riyadh date YYYY-MM-DD (default: today)")] = None,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
):
    return orders.for_restaurant(user, restaurant_id, day, order_status)
