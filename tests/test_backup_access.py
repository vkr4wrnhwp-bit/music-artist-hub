"""The full-database export is gated on identity, not on plan.

/backup and /backup/run hand out a zip of the whole SQLite database —
every account's name, email and data. That was gated on plan == "label",
which is not an identity: /plan/switch calls store.set_user_plan directly
for any tier in plans.TIER_RANK whenever Stripe is not configured, so on a
keyless deployment any signed-up artist was one POST away from qualifying.

This test walks that exact path rather than setting the plan by hand, so
it fails if the self-serve tier switch ever becomes a route to the zip
again.
"""
import uuid

from app import create_app
import db as store
import stripe_provider as stripe_billing


PASSWORD = "backuppw12345"


def _signup(app_obj, email):
    client = app_obj.test_client()
    r = client.post("/signup", data={"name": "Backup Test",
                                     "email": email, "password": PASSWORD})
    assert r.status_code == 302, "signup failed for %s" % email
    return client


def test_label_plan_alone_does_not_open_the_backup(monkeypatch):
    monkeypatch.delenv("OWNER_EMAILS", raising=False)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    app_obj = create_app()
    email = "plain-%s@example.net" % uuid.uuid4().hex[:8]
    client = _signup(app_obj, email)

    # The precondition the bug depended on: without Stripe keys the tier
    # switch is free. If this ever stops being true the test still holds,
    # but the escalation it models is gone.
    assert not stripe_billing.configured(), \
        "Stripe is configured in this test run; the free tier switch is not reachable"
    assert client.post("/plan/switch", data={"plan": "label"}).status_code == 302
    assert store.get_user_by_email(email)["plan"] == "label"

    # Top tier, and still refused.
    assert client.get("/backup").status_code == 404
    assert client.post("/backup/run").status_code == 404
    # And /settings does not dangle a button that would 404.
    settings = client.get("/settings").get_data(as_text=True)
    assert "Download backup" not in settings
    assert "/backup" not in settings


def test_owner_email_still_gets_the_backup(monkeypatch):
    email = "backup-owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    app_obj = create_app()
    client = _signup(app_obj, email)

    assert client.get("/backup").status_code == 200
    assert "Download backup" in client.get("/settings").get_data(as_text=True)
