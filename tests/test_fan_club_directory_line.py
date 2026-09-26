"""The tool directory's Fan Club line promises paid memberships only while
a fan can pay.

The line read "Paid monthly memberships through Stripe with a
members-only drops area, wired into the Fan CRM." on every account, while
paid joins wait on the owner's online-sales switch (sales_switch, off by
default) and on Stripe. Until both hold, the line says what is true:
the club can be set up now and joins open when online sales are on.
"""
import uuid

import app as appmod
import command_center as cc
import db as store
import sales_switch

PW = "club-line-12345"


def _client():
    email = "clubline-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Club Line", "email": email, "password": PW})
    c.post("/login", data={"email": email, "password": PW})
    return c


def _line(modules):
    return next(m[2] for m in modules if m[0] == "/fan-club")


def test_with_online_sales_off_the_line_says_set_up_now(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    before = store.get_kv(sales_switch.KEY)
    sales_switch.set_on(False)
    try:
        assert _line(cc.directory()) == cc.FAN_CLUB_SETUP
        body = _client().get("/all-tools").get_data(as_text=True)
        assert "paid joins open when online sales are switched on" in body
        assert "Paid monthly memberships through Stripe" not in body
    finally:
        store.set_kv(sales_switch.KEY, before or "off")


def test_without_stripe_the_line_says_set_up_now_even_with_sales_on(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    before = store.get_kv(sales_switch.KEY)
    sales_switch.set_on(True)
    try:
        assert _line(cc.directory()) == cc.FAN_CLUB_SETUP
    finally:
        store.set_kv(sales_switch.KEY, before or "off")


def test_once_joins_are_open_the_original_line_is_true_again(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    before = store.get_kv(sales_switch.KEY)
    sales_switch.set_on(True)
    try:
        assert _line(cc.directory()) == cc.FAN_CLUB_OPEN
        assert "Paid monthly memberships through Stripe" in cc.FAN_CLUB_OPEN
    finally:
        store.set_kv(sales_switch.KEY, before or "off")
    # the registry itself is untouched: preview routes and the lookup read it
    assert _line(cc.MODULES) == cc.FAN_CLUB_OPEN
