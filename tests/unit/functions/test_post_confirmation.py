import boto3
import pytest
from moto import mock_aws

from .conftest import load_handler

USER = "user-uuid-1"


@pytest.fixture
def pool():
    with mock_aws():
        client = boto3.client("cognito-idp", region_name="us-east-1")
        pool_id = client.create_user_pool(PoolName="sumaat-users")["UserPool"]["Id"]
        for group in ("customer", "owner", "cashier"):
            client.create_group(UserPoolId=pool_id, GroupName=group)
        client.admin_create_user(UserPoolId=pool_id, Username=USER)
        yield client, pool_id


def _event(pool_id: str, source: str, role: str | None = None) -> dict:
    attrs = {"sub": "abc-123", "email": "someone@example.com"}
    if role is not None:
        attrs["custom:signupRole"] = role
    return {
        "triggerSource": source,
        "userPoolId": pool_id,
        "userName": USER,
        "request": {"userAttributes": attrs},
        "response": {},
    }


def _groups(client, pool_id):
    resp = client.admin_list_groups_for_user(UserPoolId=pool_id, Username=USER)
    return sorted(g["GroupName"] for g in resp["Groups"])


def test_customer_signup_joins_customer_only(pool):
    client, pool_id = pool
    fn = load_handler("post_confirmation")
    event = _event(pool_id, "PostConfirmation_ConfirmSignUp", "customer")
    assert fn.handler(event, None) is event
    assert _groups(client, pool_id) == ["customer"]


def test_owner_signup_joins_owner_only(pool):
    # One role per account: an owner orders food with a separate customer account.
    client, pool_id = pool
    load_handler("post_confirmation").handler(_event(pool_id, "PostConfirmation_ConfirmSignUp", "owner"), None)
    assert _groups(client, pool_id) == ["owner"]


@pytest.mark.parametrize("role", [None, "", "cashier", "admin", "OWNER"])
def test_missing_or_unknown_role_is_customer_only(pool, role):
    # Nobody can make themselves a cashier (or anything else) from the sign-up form.
    client, pool_id = pool
    load_handler("post_confirmation").handler(_event(pool_id, "PostConfirmation_ConfirmSignUp", role), None)
    assert _groups(client, pool_id) == ["customer"]


def test_forgot_password_adds_nothing(pool):
    client, pool_id = pool
    load_handler("post_confirmation").handler(
        _event(pool_id, "PostConfirmation_ConfirmForgotPassword", "owner"), None
    )
    assert _groups(client, pool_id) == []
