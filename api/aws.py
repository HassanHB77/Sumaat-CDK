"""boto3 handles, created lazily and reused across warm Lambda invocations.

Tests call `table.cache_clear()` / `cognito.cache_clear()` inside `mock_aws` so each test gets fresh mocks.
"""

from functools import lru_cache

import boto3

from api.settings import get_settings


@lru_cache
def table():
    s = get_settings()
    return boto3.resource("dynamodb", region_name=s.region).Table(s.table_name)


@lru_cache
def cognito():
    return boto3.client("cognito-idp", region_name=get_settings().region)
