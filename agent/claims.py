"""Who is calling the agent.

AgentCore Runtime has ALREADY verified the Cognito access token (signature, expiry, issuer = our user pool,
client_id = our web client) before our code runs. We only read the claims we need from its payload; we never
trust a token that did not come through that check (the runtime only accepts verified bearer tokens).
"""

import base64
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    sub: str
    groups: frozenset[str]

    @property
    def is_customer(self) -> bool:
        return "customer" in self.groups


def _payload(token: str) -> dict:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)  # JWTs drop base64 padding
        return json.loads(base64.urlsafe_b64decode(part))
    except (IndexError, ValueError):
        return {}


def caller_from(headers: dict[str, str] | None) -> Caller | None:
    """The caller from the forwarded `Authorization: Bearer <access token>` header, or None."""
    auth = (headers or {}).get("Authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else auth
    claims = _payload(token) if token else {}
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    groups = claims.get("cognito:groups") or []
    return Caller(sub=sub, groups=frozenset(g for g in groups if isinstance(g, str)))
