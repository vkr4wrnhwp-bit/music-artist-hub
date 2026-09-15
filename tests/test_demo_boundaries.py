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
    fresh = _fresh(app_obj)
    fresh.post("/plan/switch", data={"plan": "pro"})      # /overview is a Pro page; an Artist plan gets the upgrade card
    r = fresh.get("/overview")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for seeded in ("Recent Payouts", "Royalty Health Score", "$250.00"):
        assert seeded not in body, seeded
    # and no zero dollars standing in for a figure nobody measured
    assert "$0.00" not in body and "Nothing tracked yet" in body and "Sample data below" not in body
    showcase = _showcase(app_obj).get("/overview").get_data(as_text=True)
    for seeded in ("Recent Payouts", "Royalty Health Score"):
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
    # the public kit of a fresh account, opened by a stranger, says the same
    import re
    fresh = _fresh(app_obj)
    editor = fresh.get("/epk").get_data(as_text=True)
    slug = re.search(r'href="(/epk/[a-z0-9-]+)"', editor).group(1)
    public = app_obj.test_client().get(slug).get_data(as_text=True)
    assert "Not measured" in public and "Midnight Drive" not in public


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


def test_a_granted_plan_is_announced_by_email_and_in_the_app(monkeypatch):
    """Owner, 2026-09-14: "we do need it to send a email saying they have
    access now to a plan". The mail goes through the one mailer, names
    the plan, carries the plan's own feature list and a sign-in link,
    and replies go to the owner. The page says "on its way" only when
    the service accepted it; unconfigured, it says so instead."""
    import email_provider as emailer
    app_obj = create_app()
    owner = _fresh(app_obj)
    target = _fresh(app_obj)
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <hello@mail.example.net>")
    sent = []
    monkeypatch.setattr(emailer, "_http", lambda url, payload, headers: sent.append(payload) or {"id": "em1"})
    r = owner.post("/admin/plan", data={"email": target._email, "plan": "pro"})
    assert "granted=pro" in r.headers["Location"] and "emailed=1" in r.headers["Location"]
    assert len(sent) == 1
    mail = sent[0]
    assert mail["to"] == [target._email] and mail["reply_to"] == owner._email
    assert mail["subject"] == "You have Street Banker Pro access"
    assert "Pro</strong> plan" in mail["html"] and "/login" in mail["html"]
    assert "Royalty Sweep: statements, recovery, catalog" in mail["html"]
    assert "No card was charged" in mail["html"]
    with app_obj.app_context():
        notes = store.list_notifications(store.get_user_by_email(target._email)["id"])
    assert any(n["title"] == "You have Pro access" for n in notes)
    body = owner.get("/settings?granted=pro&to=%s&emailed=1" % target._email).get_data(as_text=True)
    assert "An email telling them is on its way" in body

    # the service refuses: the page says so, the grant stands
    def refuse(url, payload, headers):
        raise RuntimeError("domain not verified")
    monkeypatch.setattr(emailer, "_http", refuse)
    r = owner.post("/admin/plan", data={"email": target._email, "plan": "label"})
    assert "emailed=0" in r.headers["Location"]
    with app_obj.app_context():
        assert store.get_user_by_email(target._email)["plan"] == "label"
    body = owner.get("/settings?granted=label&to=%s&emailed=0&why=domain%%20not%%20verified" % target._email).get_data(as_text=True)
    assert "could not be delivered: domain not verified" in body

    # nothing configured (staging): no attempt, and the page says so
    monkeypatch.delenv("RESEND_API_KEY")
    monkeypatch.setattr(emailer, "_http", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not send")))
    r = owner.post("/admin/plan", data={"email": target._email, "plan": "artist"})
    assert "emailed=off" in r.headers["Location"]
    body = owner.get("/settings?granted=artist&to=%s&emailed=off" % target._email).get_data(as_text=True)
    assert "Email is not set up on this deployment" in body
