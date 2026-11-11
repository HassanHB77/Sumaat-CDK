"""Runtime configuration, read once from environment variables (set by the Lambda in Step 4)."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    table_name: str
    user_pool_id: str
    region: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        table_name=os.environ.get("TABLE_NAME", "sumaat"),
        user_pool_id=os.environ.get("USER_POOL_ID", ""),
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
