"""Who is calling? Read the Cognito claims that API Gateway already verified.

API Gateway (REST, Cognito authorizer) checks the JWT signature and expiry BEFORE Lambda runs and
puts the decoded claims in event.requestContext.authorizer.claims. Mangum exposes the raw event as
request.scope["aws.event"]. We trust those claims and never re-verify the JWT here.

One authorizer accepts BOTH pools (Step 4), so a customer token also passes API Gateway.
That's why every dependency below also checks which pool issued the token (`iss`).
"""

import re
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request, status

from api.settings import get_settings

Pool = Literal["business", "customer"]


@dataclass(frozen=True)
class Principal:
    sub: str
    username: str  # Cognito username (a UUID in the business pool, the phone in the customer pool)
    name: str | None
    pool: Pool
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


def _pool_of(iss: str) -> Pool | None:
    s = get_settings()
    if s.business_pool_id and iss.endswith(f"/{s.business_pool_id}"):
        return "business"
    if s.customer_pool_id and iss.endswith(f"/{s.customer_pool_id}"):
        return "customer"
    return None


def principal_from(request: Request) -> Principal:
    claims = claims_from(request)
    if not claims or not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    pool = _pool_of(str(claims.get("iss", "")))
    if pool is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown token issuer")
    return Principal(
        sub=claims["sub"],
        username=claims.get("cognito:username") or claims["sub"],
        name=claims.get("name"),
        pool=pool,
        groups=parse_groups(claims.get("cognito:groups")),
        restaurant_id=claims.get("custom:restaurantId") or None,
    )


def require_business(*groups: str):
    """Dependency: business-pool user in at least one of `groups` (any group if none given)."""

    def dep(request: Request) -> Principal:
        p = principal_from(request)
        if p.pool != "business":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Business account required")
        if groups and not (p.groups & set(groups)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires group: {' or '.join(groups)}")
        return p

    return dep


def require_customer():
    """Dependency: signed-in customer-pool user."""

    def dep(request: Request) -> Principal:
        p = principal_from(request)
        if p.pool != "customer":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer account required")
        return p

    return dep
