"""Opening hours in Riyadh time.

Hours are stored as "HH:MM-HH:MM" (e.g. "12:00-23:30"). Special cases:
  "13:00-01:00"  closes after midnight (open 13:00 until 01:00 the next day)
  "00:00-00:00"  open 24 hours
The opening minute counts as open, the closing minute as closed.

Saudi Arabia is UTC+3 all year (no daylight saving), so a fixed offset is used instead of a time-zone
database. Simpler, and nothing to install on Lambda.
"""

from datetime import UTC, datetime, timedelta, timezone

RIYADH = timezone(timedelta(hours=3), "Asia/Riyadh")


def riyadh_now() -> datetime:
    return datetime.now(UTC).astimezone(RIYADH)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_within_hours(hours: str, now: datetime | None = None) -> bool:
    now = (now or riyadh_now()).astimezone(RIYADH)
    start_s, end_s = hours.split("-")
    start, end, cur = _minutes(start_s), _minutes(end_s), now.hour * 60 + now.minute
    if start == end:
        return True  # 24 hours
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end  # past midnight


def open_now(restaurant: dict, now: datetime | None = None) -> bool:
    """Taking orders right now = not paused AND inside opening hours."""
    return not restaurant.get("isPaused", False) and is_within_hours(restaurant["hours"], now)
