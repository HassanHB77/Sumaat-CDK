"""Text sent to the API is trimmed (spaces / tabs / new lines at both ends) before it is validated and saved.
Passwords are the exception: kept exactly as typed."""

import pytest

from api.handler import app
from api.models import CashierCreate, PasswordReset
from tests.unit.api.conftest import NEW, order_body, sara  # fixtures: clock, shop, customer, make_client

PAD = "  \n\t"


def test_restaurant_and_menu_text_saved_trimmed(shop):
    owner, rid = shop["owner"], shop["rid"]
    r = owner.patch(f"/restaurants/{rid}", json={"name": f"{PAD}Hofuf Burger Lab{PAD}", "description": "\nSmash burgers.\n\n"})
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["description"]) == ("Hofuf Burger Lab", "Smash burgers.")
    stored = shop["table"].get_item(Key={"PK": f"RESTAURANT#{rid}", "SK": "PROFILE"})["Item"]
    assert stored["name"] == "Hofuf Burger Lab"  # same text in the database, not only in the response

    item = owner.post(
        f"/restaurants/{rid}/menu",
        json={"name": f"{PAD}Kabsa{PAD}", "nameAr": " كبسة\n", "category": " Mains ", "priceHalalas": 3000},
    )
    assert item.status_code == 201, item.text
    assert (item.json()["name"], item.json()["nameAr"], item.json()["category"]) == ("Kabsa", "كبسة", "Mains")


def test_blank_text_counts_as_empty(shop):
    owner, rid = shop["owner"], shop["rid"]
    assert owner.patch(f"/restaurants/{rid}", json={"name": " \n "}).status_code == 422


def test_order_note_and_reject_reason_trimmed(shop, customer):
    o = customer.post("/orders", json=order_body(shop, note=f"{PAD}No onions please{PAD}")).json()
    assert o["note"] == "No onions please"
    r = shop["owner"].post(f"/orders/{o['id']}/reject", json={"reason": f"{PAD}Kitchen closing{PAD}"})
    assert r.status_code == 200, r.text
    assert r.json()["statusHistory"][-1]["reason"] == "Kitchen closing"


def test_names_from_the_login_token_are_trimmed(shop, make_client):
    padded = make_client(app, {**sara(), "name": " Sara \n", "phone_number": " +966500000001 "})
    o = padded.post("/orders", json=order_body(shop)).json()
    assert (o["customerName"], o["customerPhone"]) == ("Sara", "+966500000001")


def test_cashier_fields_trimmed_but_password_kept():
    c = CashierCreate(name=" Fahad\n", email=" fahad@example.com ", phone=" +966500000201\n", password=" Cash#2026 ")
    assert (c.name, c.email, c.phone) == ("Fahad", "fahad@example.com", "+966500000201")
    assert c.password == " Cash#2026 "
    assert PasswordReset(password=" Cash#2026 ").password == " Cash#2026 "


@pytest.mark.parametrize("field", list(NEW))
def test_every_restaurant_text_field_is_trimmed_on_create(field, ddb, make_client):
    from tests.unit.api.conftest import owner_claims

    value = NEW[field]
    body = {**NEW, field: f"{PAD}{value}{PAD}" if isinstance(value, str) else value}
    r = make_client(app, owner_claims()).post("/restaurants", json=body)
    assert r.status_code == 201, r.text
    assert r.json()[field] == value
