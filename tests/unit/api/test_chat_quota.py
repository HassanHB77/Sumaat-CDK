"""api/services/chat_quota.py: AI-chat messages per account per business day (04:00 -> 04:00 Riyadh).

The default is 50 (customers and owners); these tests pin CHAT_DAILY_LIMIT=10 to check the mechanics with small numbers.
"""

from datetime import datetime

import pytest

from api.hours import RIYADH
from api.services import chat_quota
from api.services.chat_quota import QuotaExceeded

SARA, OMAR = "customer-sub-1", "customer-sub-2"


def at(day, h, m=0):
    return datetime(2026, 11, day, h, m, tzinfo=RIYADH)


@pytest.fixture
def table(ddb, clock, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "10")
    return ddb[0]


def test_default_is_50_a_day(monkeypatch):
    monkeypatch.delenv("CHAT_DAILY_LIMIT", raising=False)
    assert chat_quota.daily_limit() == 50


def row(table, sub, day):
    return table.get_item(Key={"PK": f"CHATQUOTA#{sub}", "SK": f"DAY#2026-11-{day:02d}"}).get("Item")


def test_ten_allowed_then_refused(table):
    assert chat_quota.peek(SARA) == 10
    assert [chat_quota.use_one(SARA) for _ in range(10)] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    with pytest.raises(QuotaExceeded) as e:
        chat_quota.use_one(SARA)
    assert e.value.status_code == 429
    assert chat_quota.peek(SARA) == 0
    assert row(table, SARA, 12)["n"] == 10  # the refused one didn't count


def test_customers_have_their_own_allowance(table):
    for _ in range(10):
        chat_quota.use_one(SARA)
    assert chat_quota.use_one(OMAR) == 9


def test_new_day_starts_at_4am_riyadh(table, clock):
    clock.set(at(13, 3, 59))  # still Thursday 12th's business day
    for _ in range(10):
        chat_quota.use_one(SARA)
    clock.set(at(13, 0, 30))
    with pytest.raises(QuotaExceeded):
        chat_quota.use_one(SARA)
    clock.set(at(13, 4, 0))  # Friday's allowance
    assert chat_quota.peek(SARA) == 10
    assert chat_quota.use_one(SARA) == 9


def test_give_back(table):
    chat_quota.use_one(SARA)
    chat_quota.use_one(SARA)
    chat_quota.give_back(SARA)
    assert chat_quota.peek(SARA) == 9
    chat_quota.give_back(SARA)
    chat_quota.give_back(SARA)  # never below zero
    assert row(table, SARA, 12)["n"] == 0 and chat_quota.peek(SARA) == 10


def test_give_back_with_nothing_used_is_a_no_op(table):
    chat_quota.give_back(SARA)
    assert row(table, SARA, 12) is None


def test_row_expires_two_days_after_its_business_day(table):
    chat_quota.use_one(SARA)
    # Business day 12 Nov ends 13 Nov 04:00 Riyadh; + 2 days = 15 Nov 04:00 Riyadh = 15 Nov 01:00 UTC.
    assert row(table, SARA, 12)["expiresAt"] == int(at(15, 4).timestamp())


def test_limit_from_environment(table, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT", "2")
    assert chat_quota.use_one(SARA) == 1
    assert chat_quota.use_one(SARA) == 0
    with pytest.raises(QuotaExceeded):
        chat_quota.use_one(SARA)


# --- GET /me/chat-quota ------------------------------------------------------

from api.handler import app  # noqa: E402
from tests.unit.api.conftest import owner_claims, sara  # noqa: E402

CASHIER = {"sub": "cashier-sub-1", "cognito:username": "cashier-sub-1", "name": "Ali", "cognito:groups": "cashier"}


def test_quota_route_for_customer(table, make_client):
    chat_quota.use_one(SARA)
    r = make_client(app, sara()).get("/me/chat-quota")
    assert r.status_code == 200 and r.json() == {"left": 9, "limit": 10}


def test_quota_route_for_owner_too(table, make_client):
    r = make_client(app, owner_claims()).get("/me/chat-quota")
    assert r.status_code == 200 and r.json() == {"left": 10, "limit": 10}


def test_quota_route_not_for_cashiers_or_guests(table, make_client):
    assert make_client(app, CASHIER).get("/me/chat-quota").status_code == 403  # cashiers have no assistant
    assert make_client(app, None).get("/me/chat-quota").status_code == 401
