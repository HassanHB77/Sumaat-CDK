"""boto3 handles, created lazily and reused across warm Lambda invocations.

Tests call `table.cache_clear()` / `cognito.cache_clear()` / `s3.cache_clear()` inside `mock_aws` so each test gets
fresh mocks.
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


@lru_cache
def s3():
    # Regional endpoint + SigV4: presigned POSTs must go to the bucket's own region (us-east-1).
    from botocore.config import Config

    region = get_settings().region
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
