"""Runtime configuration, read once from environment variables (set by the Lambda in infra/api_stack.py)."""

import os
from dataclasses import dataclass
from functools import lru_cache

LOCAL_DEV_ORIGIN = "http://localhost:5173"  # Vite dev server


@dataclass(frozen=True)
class Settings:
    table_name: str
    user_pool_id: str
    region: str
    allowed_origins: tuple[str, ...]  # CORS: which websites may call the API from a browser
    enable_docs: bool  # /docs, /redoc, /openapi.json (on locally, off on AWS)


@lru_cache
def get_settings() -> Settings:
    origins = os.environ.get("ALLOWED_ORIGINS", LOCAL_DEV_ORIGIN)
    return Settings(
        table_name=os.environ.get("TABLE_NAME", "sumaat"),
        user_pool_id=os.environ.get("USER_POOL_ID", ""),
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        enable_docs=os.environ.get("ENABLE_DOCS", "1") == "1",
    )
