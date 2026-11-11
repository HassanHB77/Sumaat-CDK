"""Opening hours in Riyadh time.

Hours are stored as "HH:MM-HH:MM" (e.g. "12:00-23:30"). Special cases:
  "13:00-01:00"  closes after midnight (open 13:00 until 01:00 the next day)
  "00:00-00:00"  open 24 hours
The opening minute counts as open, the closing minute as closed.

Saudi Arabia is UTC+3 all year (no daylight saving), so a fixed offset is used instead of a time-zone
database. Simpler, and nothing to install on Lambda.
"""

from datetime import UTC, date, datetime, time, timedelta, timezone

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


# The business day starts at 04:00 Riyadh, not midnight: a restaurant open 13:00-01:00 keeps one day
# (one order numbering, one "today" list) for the whole night. Orders 00:00-03:59 belong to the day before.
DAY_START_HOUR = 4


def business_date(now: datetime | None = None) -> date:
    """The business day an order placed at `now` belongs to."""
    local = (now or riyadh_now()).astimezone(RIYADH)
    return (local - timedelta(hours=DAY_START_HOUR)).date()


def day_bounds_utc(day: date) -> tuple[str, str]:
    """[start, end) of a business day (04:00 -> 04:00 Riyadh) as UTC ISO strings, same format as createdAt."""
    start = datetime.combine(day, time(DAY_START_HOUR, 0), RIYADH).astimezone(UTC)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)
