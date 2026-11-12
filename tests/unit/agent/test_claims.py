"""agent/claims.py: read the caller from the (already verified) access token."""

import base64
import json

from agent.claims import caller_from


def token(claims: dict) -> str:
    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'RS256'})}.{b64(claims)}.sig"


def test_customer_from_bearer_header():
    c = caller_from({"Authorization": "Bearer " + token({"sub": "u-1", "cognito:groups": ["customer"]})})
    assert c.sub == "u-1" and c.is_customer


def test_owner_is_not_customer():
    c = caller_from({"Authorization": "Bearer " + token({"sub": "u-2", "cognito:groups": ["owner"]})})
    assert c is not None and not c.is_customer


def test_no_groups_is_not_customer():
    assert not caller_from({"Authorization": "Bearer " + token({"sub": "u-3"})}).is_customer


def test_bare_token_without_bearer_prefix():
    assert caller_from({"Authorization": token({"sub": "u-4", "cognito:groups": ["customer"]})}).sub == "u-4"


def test_missing_or_broken_token():
    assert caller_from(None) is None
    assert caller_from({}) is None
    assert caller_from({"Authorization": "Bearer nonsense"}) is None
    assert caller_from({"Authorization": "Bearer " + token({"cognito:groups": ["customer"]})}) is None  # no sub
