"""Order routes. Placing an order: customers only. Reading: the customer, or staff of that restaurant."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from api.auth import Principal, require_customer, require_user
from api.models import OrderCreate, OrderOut, OrderStatus, RejectBody
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
    day: Annotated[date | None, Query(alias="date", description="Business day YYYY-MM-DD (04:00-04:00 Riyadh; default: the current one)")] = None,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
):
    return orders.for_restaurant(user, restaurant_id, day, order_status)


# --- status changes (forward only; the frontend shows a short "Undo" countdown BEFORE calling these) ---


@router.post("/orders/{order_id}/accept", response_model=OrderOut)
def accept(order_id: str, user: User):
    return orders.change_status(user, order_id, "accept")


@router.post("/orders/{order_id}/ready", response_model=OrderOut)
def ready(order_id: str, user: User):
    return orders.change_status(user, order_id, "ready")


@router.post("/orders/{order_id}/served", response_model=OrderOut)
def served(order_id: str, user: User):
    return orders.change_status(user, order_id, "served")


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
def reject(order_id: str, user: User, body: Annotated[RejectBody | None, Body()] = None):
    return orders.change_status(user, order_id, "reject", body.reason if body else None)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: str, customer: Customer):
    return orders.change_status(customer, order_id, "cancel")
