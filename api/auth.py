"""Who is calling? Read the Cognito claims that API Gateway already verified.

API Gateway (REST, Cognito authorizer) checks the JWT signature and expiry BEFORE Lambda runs and
puts the decoded claims in event.requestContext.authorizer.claims. Mangum exposes the raw event as
request.scope["aws.event"]. We trust those claims and never re-verify the JWT here.

One pool (sumaat-users) for everyone; Cognito groups decide what a user may do.
One role per account: customer, owner, or cashier.
We still check `iss` is our pool, as a defence against a misconfigured authorizer.
"""

import re
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from api.settings import get_settings


@dataclass(frozen=True)
class Principal:
    sub: str
    username: str  # Cognito username (an internal UUID; users sign in with their email)
    name: str | None
    email: str | None  # personal data: store where needed, never log
    phone: str | None
    groups: frozenset[str]
    restaurant_id: str | None


def parse_groups(raw) -> frozenset[str]:
    """REST authorizer flattens claims to strings: "owner", "owner,cashier" or "[owner cashier]"."""
    if not raw:
        return frozenset()
    if isinstance(raw, list):
        return frozenset(str(g) for g in raw)
    return frozenset(g for g in re.split(r"[\s,\[\]]+", str(raw)) if g)


def claims_from(request: Request) -> dict | None:
    event = request.scope.get("aws.event") or {}
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get("claims")
    return claims or None


def principal_from(request: Request) -> Principal:
    claims = claims_from(request)
    if not claims or not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    pool_id = get_settings().user_pool_id
    if not pool_id or not str(claims.get("iss", "")).endswith(f"/{pool_id}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown token issuer")
    return Principal(
        sub=claims["sub"],
        username=claims.get("cognito:username") or claims["sub"],
        name=claims.get("name"),
        email=claims.get("email"),
        phone=claims.get("phone_number"),
        groups=parse_groups(claims.get("cognito:groups")),
        restaurant_id=claims.get("custom:restaurantId") or None,
    )


def require_user():
    """Dependency: any signed-in user, whatever their role (the service decides what they may see)."""

    def dep(request: Request) -> Principal:
        return principal_from(request)

    return dep


def require_groups(*groups: str):
    """Dependency: signed-in user in at least one of `groups`."""
    if not groups:
        raise ValueError("require_groups needs at least one group; use require_user() for any user")

    def dep(request: Request) -> Principal:
        p = principal_from(request)
        if not (p.groups & set(groups)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires group: {' or '.join(groups)}")
        return p

    return dep


def require_customer():
    """Dependency: a customer account (owners and cashiers use separate customer accounts to order)."""
    return require_groups("customer")
