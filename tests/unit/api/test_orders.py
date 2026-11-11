from datetime import datetime

import pytest

from api.handler import app
from api.hours import RIYADH
from api.services.orders import open_lock_key
from api.services.staff import cashier_key
from tests.unit.api.conftest import NEW, DISH, order_body, owner_claims, sara  # fixtures: clock, shop, customer

# --- place -------------------------------------------------------------------


def test_place_order(shop, customer):
    r = customer.post("/orders", json=order_body(shop, note="No onions please"))
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["orderNumber"] == 1
    assert o["businessDate"] == "2026-11-12"
    assert o["status"] == "PLACED"
    assert o["totalHalalas"] == 2 * 2500 + 900  # from the DATABASE prices
    assert [(line["name"], line["qty"], line["lineTotalHalalas"]) for line in o["items"]] == [
        ("Smash Burger", 2, 5000),
        ("Fries", 1, 900),
    ]
    assert o["customerName"] == "Sara" and o["customerPhone"] == "+966500000001"  # from the token
    assert (o["restaurantName"], o["restaurantNameAr"]) == ("Hofuf Burger Lab", "مختبر برجر الهفوف")
    assert o["note"] == "No onions please"
    assert [h["status"] for h in o["statusHistory"]] == ["PLACED"]
    assert "customerEmail" not in o  # stored, never returned

    stored = shop["table"].get_item(Key={"PK": f"ORDER#{o['id']}", "SK": "ORDER"})["Item"]
    assert stored["customerEmail"] == "sara@example.com"
    assert stored["GSI1PK"] == f"RORDERS#{shop['rid']}" and stored["GSI2PK"] == "CORDERS#customer-sub-1"


def test_numbers_count_up_and_reset_daily(shop, make_client, clock):
    n = lambda c: c.post("/orders", json=order_body(shop)).json()["orderNumber"]  # noqa: E731
    assert n(make_client(app, sara("c1"))) == 1
    assert n(make_client(app, sara("c2"))) == 2
    clock.set(datetime(2026, 11, 13, 18, 0, tzinfo=RIYADH))  # next Riyadh day
    assert n(make_client(app, sara("c3"))) == 1


def test_one_open_order_per_restaurant(shop, customer):
    assert customer.post("/orders", json=order_body(shop)).status_code == 201
    r = customer.post("/orders", json=order_body(shop))
    assert r.status_code == 409
    assert "#1" in r.json()["detail"]
    counter = shop["table"].get_item(Key={"PK": f"RESTAURANT#{shop['rid']}", "SK": "COUNTER#2026-11-12"})["Item"]
    assert counter["seq"] == 1  # the refused order did not use up a number


def test_can_order_again_once_lock_is_released(shop, customer):
    # 5.4 deletes the lock when the order is SERVED / REJECTED / CANCELLED; simulate that here.
    assert customer.post("/orders", json=order_body(shop)).status_code == 201
    shop["table"].delete_item(Key=open_lock_key("customer-sub-1", shop["rid"]))
    r = customer.post("/orders", json=order_body(shop))
    assert r.status_code == 201 and r.json()["orderNumber"] == 2


def test_open_order_elsewhere_does_not_block(shop, customer, make_client):
    other_owner = make_client(app, owner_claims(sub="owner-sub-2"))
    rid2 = other_owner.post("/restaurants", json={**NEW, "name": "Second Shop"}).json()["id"]
    item2 = other_owner.post(f"/restaurants/{rid2}/menu", json=DISH).json()["id"]
    assert customer.post("/orders", json=order_body(shop)).status_code == 201
    r = customer.post("/orders", json={"restaurantId": rid2, "items": [{"itemId": item2, "qty": 1}]})
    assert r.status_code == 201 and r.json()["orderNumber"] == 1  # each restaurant has its own numbers


def test_closed_when_paused(shop, customer):
    shop["owner"].post(f"/restaurants/{shop['rid']}/pause")
    r = customer.post("/orders", json=order_body(shop))
    assert r.status_code == 409 and r.json()["detail"] == "Restaurant is closed"


def test_closed_outside_hours(shop, customer, clock):
    clock.set(datetime(2026, 11, 12, 10, 0, tzinfo=RIYADH))
    assert customer.post("/orders", json=order_body(shop)).status_code == 409


def test_hidden_item_is_422(shop, customer):
    shop["owner"].patch(f"/restaurants/{shop['rid']}/menu/{shop['fries']}", json={"isAvailable": False})
    r = customer.post("/orders", json=order_body(shop))
    assert r.status_code == 422 and "Fries" in r.json()["detail"]


def test_unknown_restaurant_is_404(shop, customer):
    assert customer.post("/orders", json={**order_body(shop), "restaurantId": "nope"}).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"items": []},
        {"items": [{"itemId": "x", "qty": 0}]},
        {"items": [{"itemId": "x", "qty": 21}]},
        {"items": [{"itemId": "x", "qty": 1.5}]},
        {"items": [{"itemId": "x", "qty": 1}, {"itemId": "x", "qty": 2}]},  # duplicate line
        {"items": [{"itemId": f"i{n}", "qty": 1} for n in range(21)]},  # too many lines
        {"items": [{"itemId": "x", "qty": 1, "priceHalalas": 1}]},  # client can't send prices
        {"totalHalalas": 1},
        {"note": "x" * 201},
    ],
)
def test_validation(shop, customer, change):
    assert customer.post("/orders", json={**order_body(shop), **change}).status_code == 422


def test_unknown_item_is_422(shop, customer):
    r = customer.post("/orders", json={"restaurantId": shop["rid"], "items": [{"itemId": "ghost", "qty": 1}]})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "claims, code",
    [
        (None, 401),
        (owner_claims(), 403),  # one role per account: owners order with a customer account
        (owner_claims(sub="cashier-sub-1", groups="cashier"), 403),
    ],
)
def test_only_customers_place_orders(shop, make_client, claims, code):
    assert make_client(app, claims).post("/orders", json=order_body(shop)).status_code == code


# --- read --------------------------------------------------------------------


@pytest.fixture
def placed(shop, customer):
    return customer.post("/orders", json=order_body(shop)).json()


def test_my_orders_newest_first_and_only_mine(shop, customer, make_client, clock, placed):
    shop["table"].delete_item(Key=open_lock_key("customer-sub-1", shop["rid"]))
    clock.set(datetime(2026, 11, 12, 19, 0, tzinfo=RIYADH))
    second = customer.post("/orders", json=order_body(shop)).json()
    make_client(app, sara("someone-else")).post("/orders", json=order_body(shop))

    mine = customer.get("/orders/mine").json()
    assert [o["id"] for o in mine] == [second["id"], placed["id"]]
    assert all("customerEmail" not in o for o in mine)


def test_get_order_customer_and_staff(shop, customer, placed, make_client):
    assert customer.get(f"/orders/{placed['id']}").status_code == 200
    assert shop["owner"].get(f"/orders/{placed['id']}").status_code == 200

    shop["table"].put_item(Item={**cashier_key(shop["rid"], "cashier-sub-1"), "status": "active"})
    cashier = make_client(app, owner_claims(sub="cashier-sub-1", groups="cashier", restaurant_id=shop["rid"]))
    r = cashier.get(f"/orders/{placed['id']}")
    assert r.status_code == 200 and r.json()["customerPhone"] == "+966500000001"
    assert "customerEmail" not in r.json()


@pytest.mark.parametrize(
    "claims",
    [
        sara("another-customer"),
        owner_claims(sub="owner-sub-2"),  # other restaurant's owner
        owner_claims(sub="cashier-sub-9", groups="cashier", restaurant_id="other"),
    ],
)
def test_get_order_others_see_404(shop, placed, make_client, claims):
    assert make_client(app, claims).get(f"/orders/{placed['id']}").status_code == 404


def test_disabled_cashier_cannot_read(shop, placed, make_client):
    shop["table"].put_item(Item={**cashier_key(shop["rid"], "cashier-sub-1"), "status": "disabled"})
    cashier = make_client(app, owner_claims(sub="cashier-sub-1", groups="cashier", restaurant_id=shop["rid"]))
    assert cashier.get(f"/orders/{placed['id']}").status_code == 404


def test_unknown_order_is_404(shop, customer):
    assert customer.get("/orders/nope").status_code == 404


def test_staff_list_today_date_and_status(shop, placed, make_client, clock):
    owner, rid = shop["owner"], shop["rid"]
    clock.set(datetime(2026, 11, 13, 18, 0, tzinfo=RIYADH))  # tomorrow
    make_client(app, sara("tomorrow-customer")).post("/orders", json=order_body(shop))

    today = owner.get(f"/restaurants/{rid}/orders").json()  # "today" is now the 13th
    assert [o["businessDate"] for o in today] == ["2026-11-13"]
    yesterday = owner.get(f"/restaurants/{rid}/orders", params={"date": "2026-11-12"}).json()
    assert [o["id"] for o in yesterday] == [placed["id"]]
    assert owner.get(f"/restaurants/{rid}/orders", params={"date": "2026-11-12", "status": "SERVED"}).json() == []
    assert owner.get(f"/restaurants/{rid}/orders", params={"status": "NOPE"}).status_code == 422


def test_the_night_stays_one_business_day_until_4am(shop, make_client, clock):
    owner, rid = shop["owner"], shop["rid"]
    clock.set(datetime(2026, 11, 12, 23, 30, tzinfo=RIYADH))
    o1 = make_client(app, sara("night-1")).post("/orders", json=order_body(shop)).json()
    clock.set(datetime(2026, 11, 13, 0, 30, tzinfo=RIYADH))  # after midnight, before 04:00 -> still the 12th
    o2 = make_client(app, sara("night-2")).post("/orders", json=order_body(shop)).json()
    assert (o1["businessDate"], o1["orderNumber"]) == ("2026-11-12", 1)
    assert (o2["businessDate"], o2["orderNumber"]) == ("2026-11-12", 2)  # numbering continues
    # The counter's "today" at 00:30 still shows the whole night.
    assert [x["id"] for x in owner.get(f"/restaurants/{rid}/orders").json()] == [o2["id"], o1["id"]]

    clock.set(datetime(2026, 11, 13, 16, 0, tzinfo=RIYADH))  # next afternoon: new business day
    o3 = make_client(app, sara("day-2")).post("/orders", json=order_body(shop)).json()
    assert (o3["businessDate"], o3["orderNumber"]) == ("2026-11-13", 1)
    assert [x["id"] for x in owner.get(f"/restaurants/{rid}/orders", params={"date": "2026-11-12"}).json()] == [o2["id"], o1["id"]]


@pytest.mark.parametrize("claims", [sara(), owner_claims(sub="owner-sub-2")])
def test_staff_list_forbidden_for_others(shop, make_client, claims):
    assert make_client(app, claims).get(f"/restaurants/{shop['rid']}/orders").status_code == 403
