"""Clearing out the Fan accounts that registered themselves.

Owner, 2026-09-17: "delete all the bot accounts no one needs an account
now". Sign-up was open until that day, so hundreds of accounts arrived on
the fan side by themselves. The owner presses this; it is typed rather
than clicked; and it can never reach an account that has paid for
anything, a partner's account, a demo login or the owner.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import db as store

PW = "cleanup-pass-1"


@pytest.fixture
def owner(monkeypatch):
    email = "owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("SIGNUP_MODE", "open")
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    monkeypatch.setenv("OWNER_EMAILS", email)
    c.post("/login", data={"email": email, "password": PW})
    return c


def _fan(plan="fan", came_back=False, paid=False, partner=None):
    email = "f-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "F", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], plan)
    if came_back:
        with store.get_db() as db:
            db.execute("UPDATE users SET last_seen = ? WHERE id = ?",
                       ((datetime.now(timezone.utc) + timedelta(days=2)).isoformat(timespec="seconds"),
                        user["id"]))
    if paid:
        store.set_stripe_ids(user["id"], "cus_paid", "sub_paid")
    if partner:
        with store.get_db() as db:
            db.execute("UPDATE users SET partner_id = ? WHERE id = ?", (partner, user["id"]))
    return store.get_user_by_email(email)


def test_the_panel_says_when_each_account_arrived_and_whether_it_came_back(owner):
    quiet = _fan()
    page = owner.get("/settings").get_data(as_text=True)
    assert quiet["email"] in page and "never signed in" in page
    assert "Joined" in page and "Clear out Fan accounts" in page


def test_it_takes_the_quiet_ones_and_leaves_everyone_it_should(owner):
    quiet, returned = _fan(), _fan(came_back=True)
    paid, seated = _fan(paid=True), _fan(partner="p-1")
    artist = _fan(plan="artist")
    r = owner.post("/admin/accounts/clear", data={"scope": "never", "confirm": "DELETE"})
    assert r.status_code == 302
    assert store.get_user(quiet["id"]) is None, "a fan account that never came back goes"
    for kept in (returned, paid, seated, artist):
        assert store.get_user(kept["id"]) is not None, kept["email"]


def test_every_fan_takes_the_ones_that_came_back_too_but_still_not_the_protected(owner):
    quiet, returned, paid = _fan(), _fan(came_back=True), _fan(paid=True)
    owner.post("/admin/accounts/clear", data={"scope": "all", "confirm": "DELETE"})
    assert store.get_user(quiet["id"]) is None and store.get_user(returned["id"]) is None
    assert store.get_user(paid["id"]) is not None, "an account that has paid is never in a bulk clear"


def test_nothing_happens_without_the_typed_word_or_a_scope(owner):
    quiet = _fan()
    for data in ({"scope": "never"}, {"scope": "never", "confirm": "delete"},
                 {"scope": "never", "confirm": "yes"}, {"confirm": "DELETE"}):
        owner.post("/admin/accounts/clear", data=data)
        assert store.get_user(quiet["id"]) is not None, data


def test_nobody_else_can_clear_anything(owner, monkeypatch):
    quiet = _fan()
    other = appmod.app.test_client()
    email = "other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "O", "email": email, "password": PW})
    other.post("/login", data={"email": email, "password": PW})
    assert other.post("/admin/accounts/clear",
                      data={"scope": "all", "confirm": "DELETE"}).status_code == 404
    assert store.get_user(quiet["id"]) is not None
    assert "Clear out Fan accounts" not in other.get("/settings").get_data(as_text=True)
