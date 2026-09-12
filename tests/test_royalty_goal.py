"""The royalty goal was a number nobody set, edited into a browser.

Every account's overview showed "of $25,000 goal" - royalty_data's
constant - and Edit Goal wrote to localStorage ("Saved on this device"),
so the figure was invented and an edit never followed the artist to
another device. The goal is the account's now: none until set, then the
same on every device, and removable.
"""
import uuid

import pytest

import db as store
from app import create_app

PW = "goal-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "goal-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "G", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})   # /overview answers 402 without a plan
    client._app, client._email = app_obj, email
    return client


def test_no_goal_until_the_artist_sets_one(artist):
    body = artist.get("/overview").get_data(as_text=True)
    assert "No goal set" in body
    assert "25,000" not in body, "royalty_data's constant is the showcase's, not this account's"
    assert "Saved on this device" not in body


def test_the_goal_is_saved_on_the_account_and_follows_them(artist):
    r = artist.post("/overview/goal", data={"amount": "30000", "kind": "yearly",
                                            "deadline": "2027-01-01"})
    assert r.status_code == 302
    body = artist.get("/overview").get_data(as_text=True)
    assert "of $30,000 goal" in body and "by 2027-01-01" in body
    # a second browser, same account
    other = artist._app.test_client()
    other.post("/login", data={"email": artist._email, "password": PW})
    assert "of $30,000 goal" in other.get("/overview").get_data(as_text=True)


def test_a_bad_amount_saves_nothing(artist):
    artist.post("/overview/goal", data={"amount": "-5"})
    artist.post("/overview/goal", data={"amount": "lots"})
    with artist._app.app_context():
        uid = store.get_user_by_email(artist._email)["id"]
        assert store.get_royalty_goal(uid) is None


def test_the_goal_can_be_removed(artist):
    artist.post("/overview/goal", data={"amount": "100"})
    artist.post("/overview/goal", data={"clear": "1"})
    assert "No goal set" in artist.get("/overview").get_data(as_text=True)
