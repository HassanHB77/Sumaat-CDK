"""Timestamps: always UTC ISO-8601 with a Z (same format as scripts/seed.py). "Today" (Asia/Riyadh) comes later."""

from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
