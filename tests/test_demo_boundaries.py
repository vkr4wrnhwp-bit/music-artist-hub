"""Showcase treatment reaches the four seeded logins and nobody else.

The rule used to be a wildcard - demo-*@streetbanker.io - stated in
three files, and /signup accepts any address. So a stranger could
register demo-anything@streetbanker.io and take the Label plan free
while Stripe was live. And a fresh account's Overview showed five paid
payouts, an action feed and a health gauge that were the showcase's
seed; its press kit listed five recordings belonging to nobody.

Asked for on 2026-09-14: "anyone new sees no data as well". This file
holds the boundary: what the showcase keeps, what a new account never
sees, and the owner's one card-free way to put a demo login on a plan.
"""
import uuid

import pytest

import app as appmod
import db as store
import demo_accounts
from app import create_app

PW = "boundary-12345"


def _fresh(app_obj, email=None):
    client = app_obj.test_client()
    email = email or ("new-%s@example.net" % uuid.uuid4().hex[:8])
    client.post("/signup", data={"name": "Brand New", "email": email, "password": PW})
    client._email = email
    return client


def _showcase(app_obj):
    client = app_obj.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def test_the_showcase_set_is_exact_not_a_pattern():
    assert demo_accounts.is_demo_email("demo@streetbanker.io")
    assert demo_accounts.is_demo_email("  DEMO-PRO@streetbanker.io ")
    assert not demo_accounts.is_demo_email("demo-x@streetbanker.io")
    assert not demo_accounts.is_demo_email("demo-hack@streetbanker.io")
    assert not demo_accounts.is_demo_email("demo@streetbanker.io.evil.net")
    assert not demo_accounts.is_demo_email("")
    assert not demo_accounts.is_demo_email(None)
    assert len(demo_accounts.ACCOUNTS) == 4 and len(demo_accounts.EMAILS) == 4


def test_a_lookalike_address_cannot_take_a_paid_plan_free(monkeypatch):
    app_obj = create_app()
    client = _fresh(app_obj, "demo-hack-%s@streetbanker.io" % uuid.uuid4().hex[:6])
    monkeypatch.setattr(appmod.stripe_billing, "configured", lambda: True)
    r = client.post("/plan/switch", data={"plan": "label"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/billing")
    with app_obj.app_context():
        assert store.get_user_by_email(client._email)["plan"] != "label"


def test_a_new_account_sees_none_of_the_seeded_overview_sections():
    app_obj = create_app()
    body = _fresh(app_obj).get("/overview").get_data(as_text=True)
    for seeded in ("Recent Payouts", "Royalty Health Score", "Action Center", "$250.00"):
        assert seeded not in body, seeded
    showcase = _showcase(app_obj).get("/overview").get_data(as_text=True)
    for seeded in ("Recent Payouts", "Royalty Health Score", "Action Center"):
        assert seeded in showcase, seeded


def test_a_new_account_press_kit_carries_nothing_seeded():
    app_obj = create_app()
    body = _fresh(app_obj).get("/epk").get_data(as_text=True)
    assert "Sample figures" not in body
    for song in ("Midnight Drive", "Neon Dreams", "City Lights"):
        assert song not in body, song
    assert "Not measured" in body
    assert "Strongest platform" not in body
    showcase = _showcase(app_obj).get("/epk").get_data(as_text=True)
    assert "Midnight Drive" in showcase


def test_a_new_account_links_page_does_not_call_its_empty_list_examples():
    app_obj = create_app()
    body = _fresh(app_obj).get("/links").get_data(as_text=True)
    assert "demo examples" not in body


def test_the_owner_grants_a_plan_by_address_and_nobody_else_can(monkeypatch):
    app_obj = create_app()
    owner = _fresh(app_obj)
    target = _fresh(app_obj)
    # not an owner yet: the control is absent and the route is a 404
    assert 'id="grant-plan"' not in owner.get("/settings").get_data(as_text=True)
    assert owner.post("/admin/plan", data={"email": target._email, "plan": "label"}).status_code == 404
    with app_obj.app_context():
        assert store.get_user_by_email(target._email)["plan"] != "label"

    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    assert 'id="grant-plan"' in owner.get("/settings").get_data(as_text=True)
    r = owner.post("/admin/plan", data={"email": target._email.upper(), "plan": "label"})
    assert r.status_code == 302 and "granted=label" in r.headers["Location"]
    with app_obj.app_context():
        assert store.get_user_by_email(target._email)["plan"] == "label"
    body = owner.get("/settings?granted=label&to=%s" % target._email).get_data(as_text=True)
    assert "is on the label plan" in body

    r = owner.post("/admin/plan", data={"email": "nobody@example.net", "plan": "pro"})
    assert "granted=unknown" in r.headers["Location"]
    r = owner.post("/admin/plan", data={"email": target._email, "plan": "platinum"})
    assert "granted=badplan" in r.headers["Location"]
    with app_obj.app_context():
        assert store.get_user_by_email(target._email)["plan"] == "label"
