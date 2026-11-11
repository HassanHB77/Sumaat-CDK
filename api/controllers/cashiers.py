"""Cashier management. Only the owner of the restaurant (checked in the service)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from api.auth import Principal, require_groups
from api.models import CashierCreate, CashierOut, PasswordReset
from api.services import cashiers

router = APIRouter(prefix="/restaurants/{restaurant_id}/cashiers", tags=["cashiers"])

Owner = Annotated[Principal, Depends(require_groups("owner"))]


@router.post("", response_model=CashierOut, status_code=status.HTTP_201_CREATED)
def create(restaurant_id: str, body: CashierCreate, owner: Owner):
    return cashiers.create(owner, restaurant_id, body)


@router.get("", response_model=list[CashierOut])
def list_all(restaurant_id: str, owner: Owner):
    return cashiers.list_for(owner, restaurant_id)


@router.post("/{sub}/disable", response_model=CashierOut)
def disable(restaurant_id: str, sub: str, owner: Owner):
    return cashiers.disable(owner, restaurant_id, sub)


@router.post("/{sub}/enable", response_model=CashierOut)
def enable(restaurant_id: str, sub: str, owner: Owner):
    return cashiers.enable(owner, restaurant_id, sub)


@router.post("/{sub}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(restaurant_id: str, sub: str, body: PasswordReset, owner: Owner):
    cashiers.reset_password(owner, restaurant_id, sub, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
