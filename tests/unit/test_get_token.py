import boto3
import pytest
from moto import mock_aws

from scripts.get_token import get_access_token, get_id_token

PASSWORD = "Test#Pass2026"


@pytest.fixture
def pool():
    with mock_aws():
        cognito = boto3.client("cognito-idp", region_name="us-east-1")
        pool_id = cognito.create_user_pool(PoolName="sumaat-users", UsernameAttributes=["email"])["UserPool"]["Id"]
        client_id = cognito.create_user_pool_client(
            UserPoolId=pool_id, ClientName="web", ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
        )["UserPoolClient"]["ClientId"]
        cognito.admin_create_user(UserPoolId=pool_id, Username="owner@example.com", MessageAction="SUPPRESS")
        cognito.admin_set_user_password(UserPoolId=pool_id, Username="owner@example.com", Password=PASSWORD, Permanent=True)
        yield cognito, client_id


def test_returns_id_token(pool):
    cognito, client_id = pool
    token = get_id_token(cognito, client_id, "owner@example.com", PASSWORD)
    assert token.count(".") == 2  # a JWT: header.payload.signature


def test_wrong_password(pool):
    cognito, client_id = pool
    with pytest.raises(cognito.exceptions.NotAuthorizedException):
        get_id_token(cognito, client_id, "owner@example.com", "Wrong#Pass1")


def test_returns_access_token(pool):
    cognito, client_id = pool
    access = get_access_token(cognito, client_id, "owner@example.com", PASSWORD)
    assert access.count(".") == 2
    assert access != get_id_token(cognito, client_id, "owner@example.com", PASSWORD)
