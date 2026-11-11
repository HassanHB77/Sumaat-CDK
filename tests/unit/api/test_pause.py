from datetime import datetime

import pytest

from api.handler import app
from api.hours import RIYADH
from api.services.staff import cashier_key
from tests.unit.api.conftest import customer_claims, owner_claims
from tests.unit.api.test_restaurants import NEW


@pytest.fixture
def fixed_time(monkeypatch):
    """Thursday 18:00 in Riyadh: inside NEW's hours (16:00-02:00)."""
    monkeypatch.setattr("api.hours.riyadh_now", lambda: datetime(2026, 11, 12, 18, 0, tzinfo=RIYADH))


@pytest.fixture
def setup(ddb, make_client, fixed_time):
    table, *_ = ddb
    owner = make_client(app, owner_claims())
    rid = owner.post("/restaurants", json=NEW).json()["id"]
    return table, owner, rid


def _cashier(make_client, table, rid, sub="cashier-sub-1", status="active", claim_rid=None):
    table.put_item(Item={**cashier_key(rid, sub), "type": "CASHIER", "sub": sub, "status": status})
    return make_client(app, owner_claims(sub=sub, groups="cashier", restaurant_id=claim_rid or rid))


def test_new_restaurant_is_open_inside_hours(setup, make_client):
    _, owner, rid = setup
    body = make_client(app).get(f"/restaurants/{rid}").json()
    assert body["isPaused"] is False
    assert body["openNow"] is True


def test_closed_outside_hours(setup, make_client, monkeypatch):
    _, _, rid = setup
    monkeypatch.setattr("api.hours.riyadh_now", lambda: datetime(2026, 11, 12, 10, 0, tzinfo=RIYADH))
    assert make_client(app).get(f"/restaurants/{rid}").json()["openNow"] is False


def test_owner_pause_and_resume(setup, make_client):
    _, owner, rid = setup
    r = owner.post(f"/restaurants/{rid}/pause")
    assert r.status_code == 200
    assert r.json()["isPaused"] is True and r.json()["openNow"] is False
    near = make_client(app).get("/restaurants", params={"lat": NEW["lat"], "lng": NEW["lng"]}).json()
    assert [x["openNow"] for x in near if x["id"] == rid] == [False]  # still listed, shown as closed

    r = owner.post(f"/restaurants/{rid}/resume")
    assert r.json()["isPaused"] is False and r.json()["openNow"] is True


def test_active_cashier_can_pause(setup, make_client):
    table, _, rid = setup
    cashier = _cashier(make_client, table, rid)
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 200
    assert cashier.post(f"/restaurants/{rid}/resume").status_code == 200


def test_disabled_cashier_cannot_pause(setup, make_client):
    table, _, rid = setup
    cashier = _cashier(make_client, table, rid, status="disabled")
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 403


def test_cashier_without_record_cannot_pause(setup, make_client):
    _, _, rid = setup
    ghost = make_client(app, owner_claims(sub="cashier-sub-1", groups="cashier", restaurant_id=rid))
    assert ghost.post(f"/restaurants/{rid}/pause").status_code == 403


def test_cashier_of_other_restaurant_cannot_pause(setup, make_client):
    table, _, rid = setup
    # Has a record here, but the token says they work somewhere else.
    cashier = _cashier(make_client, table, rid, claim_rid="other-restaurant")
    assert cashier.post(f"/restaurants/{rid}/pause").status_code == 403


@pytest.mark.parametrize(
    "claims, code",
    [
        (None, 401),
        (customer_claims(), 403),
        (owner_claims(sub="owner-sub-2"), 403),  # another restaurant's owner
    ],
)
def test_others_cannot_pause(setup, make_client, claims, code):
    _, _, rid = setup
    assert make_client(app, claims).post(f"/restaurants/{rid}/pause").status_code == code


def test_pause_unknown_restaurant_is_404(setup):
    _, owner, _ = setup
    assert owner.post("/restaurants/nope/pause").status_code == 404
