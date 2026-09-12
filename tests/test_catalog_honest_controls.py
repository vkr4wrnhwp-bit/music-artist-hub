"""Buttons on the Catalog and Billing pages that could not do anything.

Found by scanning every template for <button> elements outside any form
with no handler (2026-09-12). The Catalog page was a demo-era shell:
"Add Release" opened a modal that announced '"X" created' and stored
nothing; the drawer offered Edit Metadata / Register Track / Edit
Release / Add Track / Register Missing with no handlers; every row had a
"..." menu that opened nothing. Billing's "Choose <plan>" on a keyless
deployment was a plain button.

Now: each control either does the thing or is a link to where the thing
is done. Nothing announces a result that did not happen.
"""
import uuid

import pytest

from app import create_app

PW = "catalog-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "cat-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Cat", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    return client


def test_the_catalog_no_longer_fakes_a_release(artist):
    body = artist.get("/catalog").get_data(as_text=True)
    assert "add-release-modal" not in body
    assert "created. Add tracks" not in body
    assert "Add a track" in body and 'href="/catalog?view=passports"' in body


def test_the_drawer_and_rows_carry_no_dead_buttons(artist):
    body = artist.get("/catalog").get_data(as_text=True)
    for dead in ("Edit Metadata", "Register Track", "Edit Release", "Register Missing",
                 "row-menu", 'aria-label="Track actions"', ">···<"):
        assert dead not in body, dead
    assert "Open passport" in body


def test_billing_choose_is_a_real_plan_switch(artist):
    body = artist.get("/billing").get_data(as_text=True)
    assert 'action="/plan/switch"' in body
    assert 'name="plan" value="label"' in body
    assert 'name="plan" value="artist"' in body, "free maps to the artist tier"
    r = artist.post("/plan/switch", data={"plan": "label"})
    assert r.status_code == 302
    assert "Current" in artist.get("/billing").get_data(as_text=True)
