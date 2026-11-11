import boto3
import pytest
from moto import mock_aws

from .conftest import load_handler


@pytest.fixture
def pool():
    with mock_aws():
        client = boto3.client("cognito-idp", region_name="us-east-1")
        pool_id = client.create_user_pool(PoolName="sumaat-business")["UserPool"]["Id"]
        client.create_group(UserPoolId=pool_id, GroupName="owner")
        client.admin_create_user(UserPoolId=pool_id, Username="owner@example.com")
        yield client, pool_id


def _event(pool_id: str, source: str) -> dict:
    return {
        "triggerSource": source,
        "userPoolId": pool_id,
        "userName": "owner@example.com",
        "request": {"userAttributes": {"sub": "abc-123", "email": "owner@example.com"}},
        "response": {},
    }


def _groups(client, pool_id):
    resp = client.admin_list_groups_for_user(UserPoolId=pool_id, Username="owner@example.com")
    return [g["GroupName"] for g in resp["Groups"]]


def test_sign_up_adds_owner(pool):
    client, pool_id = pool
    fn = load_handler("post_confirmation")
    event = _event(pool_id, "PostConfirmation_ConfirmSignUp")
    assert fn.handler(event, None) is event
    assert _groups(client, pool_id) == ["owner"]


def test_forgot_password_does_not_add_owner(pool):
    client, pool_id = pool
    fn = load_handler("post_confirmation")
    fn.handler(_event(pool_id, "PostConfirmation_ConfirmForgotPassword"), None)
    assert _groups(client, pool_id) == []
