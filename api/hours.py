"""Opening hours in Riyadh time.

Hours are stored as "HH:MM-HH:MM" (e.g. "12:00-23:30"). Special cases:
  "13:00-01:00"  closes after midnight (open 13:00 until 01:00 the next day)
  "00:00-00:00"  open 24 hours
The opening minute counts as open, the closing minute as closed.

Saudi Arabia is UTC+3 all year (no daylight saving), so a fixed offset is used instead of a time-zone
database. Simpler, and nothing to install on Lambda.
"""

from dataclasses import dataclass
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


def opens_at(hours: str) -> str:
    """The opening time "HH:MM" of "HH:MM-HH:MM" (what to tell a customer when the restaurant is closed)."""
    return hours.split("-")[0]


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


# --- periods for stats (owner numbers, owner AI) --------------------------------------------------------------

PERIODS = ("today", "yesterday", "this_week", "last_week", "this_month", "last_month")


def _first_of_previous_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def _period_days(kind: str, today: date) -> tuple[date, date]:
    """[first day, day after the last day) in business days. Weeks start on Sunday (Saudi week)."""
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)  # Mon=0 .. Sun=6 -> back to Sunday
    month_start = today.replace(day=1)
    match kind:
        case "today":
            return today, today + timedelta(days=1)
        case "yesterday":
            return today - timedelta(days=1), today
        case "this_week":
            return week_start, today + timedelta(days=1)
        case "last_week":
            return week_start - timedelta(days=7), week_start
        case "this_month":
            return month_start, today + timedelta(days=1)
        case "last_month":
            return _first_of_previous_month(today), month_start
    raise ValueError(f"unknown period {kind!r}")


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time(DAY_START_HOUR, 0), RIYADH)


@dataclass(frozen=True)
class Period:
    kind: str
    first_day: date  # business days, inclusive
    last_day: date
    start: str  # UTC ISO [start, end), same format as createdAt
    end: str
    to_date: bool  # still running (ends now), so it is compared "to date"


def period_bounds(kind: str, now: datetime | None = None) -> Period:
    now = (now or riyadh_now()).astimezone(RIYADH)
    first, after = _period_days(kind, business_date(now))
    end = min(_day_start(after), now)
    return Period(kind, first, after - timedelta(days=1), _utc(_day_start(first)), _utc(end), end == now)


def previous_period(p: Period, now: datetime | None = None) -> Period:
    """The period before `p`, cut at the same point if `p` is still running (a fair "vs last week")."""
    now = (now or riyadh_now()).astimezone(RIYADH)
    length = (p.last_day - p.first_day).days + 1
    if p.kind in ("this_month", "last_month"):
        first = _first_of_previous_month(p.first_day)
        after = p.first_day
    else:
        first = p.first_day - timedelta(days=length if p.kind not in ("this_week", "last_week") else 7)
        after = first + timedelta(days=length if p.kind not in ("this_week", "last_week") else 7)
    start = _day_start(first)
    end = _day_start(after)
    if p.to_date:
        elapsed = now - _day_start(p.first_day)
        end = min(end, start + elapsed)
    last = business_date(end - timedelta(seconds=1))
    return Period(f"before_{p.kind}", first, last, _utc(start), _utc(end), p.to_date)


def last_n_days(n: int, now: datetime | None = None) -> list[date]:
    """The last n business days, oldest first, ending today."""
    today = business_date(now)
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
