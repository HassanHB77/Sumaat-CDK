from datetime import UTC, date, datetime

import pytest

from api.hours import RIYADH, business_date, day_bounds_utc, is_within_hours, open_now


def at(hh: int, mm: int = 0) -> datetime:
    return datetime(2026, 11, 12, hh, mm, tzinfo=RIYADH)


@pytest.mark.parametrize(
    "hours, now, expected",
    [
        ("12:00-23:30", at(11, 59), False),
        ("12:00-23:30", at(12, 0), True),  # opening minute is open
        ("12:00-23:30", at(18, 0), True),
        ("12:00-23:30", at(23, 29), True),
        ("12:00-23:30", at(23, 30), False),  # closing minute is closed
        ("13:00-01:00", at(0, 30), True),  # past midnight (Qaisariya)
        ("13:00-01:00", at(1, 0), False),
        ("13:00-01:00", at(12, 59), False),
        ("13:00-01:00", at(23, 0), True),
        ("00:00-00:00", at(4, 0), True),  # 24 hours
        ("07:00-23:00", at(6, 59), False),
    ],
)
def test_is_within_hours(hours, now, expected):
    assert is_within_hours(hours, now) is expected


def test_utc_time_is_converted_to_riyadh():
    # 09:30 UTC = 12:30 in Riyadh -> open for 12:00-23:30
    assert is_within_hours("12:00-23:30", datetime(2026, 11, 12, 9, 30, tzinfo=UTC)) is True
    # 08:30 UTC = 11:30 in Riyadh -> still closed
    assert is_within_hours("12:00-23:30", datetime(2026, 11, 12, 8, 30, tzinfo=UTC)) is False


def test_open_now_respects_pause():
    r = {"hours": "00:00-00:00"}
    assert open_now(r, at(10)) is True
    assert open_now({**r, "isPaused": False}, at(10)) is True
    assert open_now({**r, "isPaused": True}, at(10)) is False


@pytest.mark.parametrize(
    "hh, mm, expected",
    [
        (4, 0, date(2026, 11, 12)),  # the business day starts at 04:00
        (18, 0, date(2026, 11, 12)),
        (23, 59, date(2026, 11, 12)),
        (0, 30, date(2026, 11, 11)),  # after midnight: still the previous business day
        (3, 59, date(2026, 11, 11)),
    ],
)
def test_business_date_rolls_over_at_4am(hh, mm, expected):
    assert business_date(at(hh, mm)) == expected


def test_day_bounds_are_4am_to_4am_riyadh_in_utc():
    # 04:00 Riyadh = 01:00 UTC
    assert day_bounds_utc(date(2026, 11, 12)) == ("2026-11-12T01:00:00Z", "2026-11-13T01:00:00Z")
