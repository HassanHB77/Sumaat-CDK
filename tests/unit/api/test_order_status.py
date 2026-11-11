import pytest

from api.handler import app
from api.services.orders import open_lock_key
from api.services.staff import cashier_key
from tests.unit.api.conftest import order_body, owner_claims, sara  # fixtures: clock, shop, customer


@pytest.fixture
def cashier(shop, make_client):
    shop["table"].put_item(Item={**cashier_key(shop["rid"], "cashier-sub-1"), "status": "active"})
    return make_client(app, owner_claims(sub="cashier-sub-1", groups="cashier", restaurant_id=shop["rid"]))


@pytest.fixture
def order(shop, customer):
    return customer.post("/orders", json=order_body(shop)).json()


def lock_exists(shop, sub="customer-sub-1"):
    return "Item" in shop["table"].get_item(Key=open_lock_key(sub, shop["rid"]))


def test_full_path_by_cashier_and_reorder(shop, customer, cashier, order):
    oid = order["id"]
    for action, status in (("accept", "ACCEPTED"), ("ready", "READY_FOR_PICKUP")):
        r = cashier.post(f"/orders/{oid}/{action}")
        assert r.status_code == 200 and r.json()["status"] == status
        assert lock_exists(shop)  # still open

    r = cashier.post(f"/orders/{oid}/served")
    assert r.status_code == 200 and r.json()["status"] == "SERVED"
    history = r.json()["statusHistory"]
    assert [h["status"] for h in history] == ["PLACED", "ACCEPTED", "READY_FOR_PICKUP", "SERVED"]
    assert [h["role"] for h in history] == ["customer", "cashier", "cashier", "cashier"]
    assert all(h["by"] and h["at"] for h in history)
    assert "customerEmail" not in r.json()

    assert not lock_exists(shop)  # final -> free to order here again
    again = customer.post("/orders", json=order_body(shop))
    assert again.status_code == 201 and again.json()["orderNumber"] == 2


def test_owner_can_do_staff_actions(shop, order):
    assert shop["owner"].post(f"/orders/{order['id']}/accept").json()["statusHistory"][-1]["role"] == "owner"


def test_customer_sees_status_changes(shop, customer, cashier, order):
    cashier.post(f"/orders/{order['id']}/accept")
    assert customer.get("/orders/mine").json()[0]["status"] == "ACCEPTED"


@pytest.mark.parametrize(
    "steps, action, current",
    [
        ([], "ready", "PLACED"),  # ready before accept
        ([], "served", "PLACED"),
        (["accept"], "accept", "ACCEPTED"),  # double tap
        (["accept"], "reject", "ACCEPTED"),  # reject only while PLACED
        (["accept", "ready"], "accept", "READY_FOR_PICKUP"),  # no going back
        (["accept", "ready", "served"], "ready", "SERVED"),  # nothing after final
        (["reject"], "accept", "REJECTED"),
    ],
)
def test_wrong_moves_are_409(cashier, order, steps, action, current):
    for step in steps:
        assert cashier.post(f"/orders/{order['id']}/{step}").status_code == 200
    r = cashier.post(f"/orders/{order['id']}/{action}")
    assert r.status_code == 409
    assert r.json()["detail"] == f"Order is {current}, can't {action}"


def test_customer_cancels_while_placed(shop, customer, cashier, order):
    r = customer.post(f"/orders/{order['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert not lock_exists(shop)
    assert cashier.post(f"/orders/{order['id']}/accept").status_code == 409  # too late for the cashier


def test_customer_cannot_cancel_after_accept(customer, cashier, order):
    cashier.post(f"/orders/{order['id']}/accept")
    r = customer.post(f"/orders/{order['id']}/cancel")
    assert r.status_code == 409 and r.json()["detail"] == "Order is ACCEPTED, can't cancel"


@pytest.mark.parametrize("body", [{"reason": "Fries sold out"}, None, {}])
def test_reject_with_or_without_reason(shop, cashier, order, body):
    r = cashier.post(f"/orders/{order['id']}/reject", json=body) if body is not None else cashier.post(f"/orders/{order['id']}/reject")
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    assert r.json()["statusHistory"][-1].get("reason") == (body or {}).get("reason")
    assert not lock_exists(shop)


def test_reject_reason_too_long(cashier, order):
    assert cashier.post(f"/orders/{order['id']}/reject", json={"reason": "x" * 201}).status_code == 422


def test_released_lock_belongs_to_the_right_order(shop, customer, cashier, order):
    # Order 1 cancelled -> order 2 placed -> rejecting order 1 again must not delete order 2's lock.
    customer.post(f"/orders/{order['id']}/cancel")
    second = customer.post("/orders", json=order_body(shop)).json()
    assert cashier.post(f"/orders/{order['id']}/reject").status_code == 409
    lock = shop["table"].get_item(Key=open_lock_key("customer-sub-1", shop["rid"]))["Item"]
    assert lock["orderId"] == second["id"]


@pytest.mark.parametrize(
    "claims",
    [
        sara("another-customer"),
        owner_claims(sub="owner-sub-2"),  # other restaurant's owner
        owner_claims(sub="cashier-sub-9", groups="cashier", restaurant_id="other"),
    ],
)
@pytest.mark.parametrize("action", ["accept", "ready", "served", "reject"])
def test_strangers_get_404_on_staff_actions(make_client, order, claims, action):
    assert make_client(app, claims).post(f"/orders/{order['id']}/{action}").status_code == 404


def test_customer_cannot_do_staff_actions_on_own_order(customer, order):
    assert customer.post(f"/orders/{order['id']}/accept").status_code == 404


def test_disabled_cashier_gets_404(shop, cashier, order):
    shop["table"].put_item(Item={**cashier_key(shop["rid"], "cashier-sub-1"), "status": "disabled"})
    assert cashier.post(f"/orders/{order['id']}/accept").status_code == 404


def test_other_customer_cannot_cancel(make_client, order):
    assert make_client(app, sara("another-customer")).post(f"/orders/{order['id']}/cancel").status_code == 404


def test_staff_cannot_use_cancel(cashier, order):
    assert cashier.post(f"/orders/{order['id']}/cancel").status_code == 403  # customers only


def test_unknown_order_is_404(cashier):
    assert cashier.post("/orders/nope/accept").status_code == 404
