"""What each membership opens, and the credit wallet.

Owner, 2026-09-17: Artist ($29) is Street Banker with Royalty Sweep and
Artifacts; Pro ($79) adds REACH, Tour and Company; Label ($199) opens
everything and carries credits every month. The Room, Noise Lab and Motion
cost money each time they run, so they spend credits from one wallet: any
membership can buy a pack, included credits lapse monthly, bought ones never.
"""
import uuid

import app as appmod
import db as store
import plans
import sb_suite_sso as sso
import stripe_provider

PW = "memberships-pass-1"


def _client(plan):
    email = "mem-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "M", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], plan)
    return c, store.get_user(user["id"])


def test_prices_and_what_each_level_opens():
    assert [p[2] for p in plans.PLANS] == ["Free", "$29/mo", "$79/mo", "$199/mo"]
    assert {k: v[0] for k, v in stripe_provider.PRICES.items()} == {"artist": 2900, "pro": 7900, "label": 19900}
    # Royalty Sweep came down to Artist.
    assert plans.required_tier("/royalties") == plans.required_tier("/recovery") == "artist"
    assert plans.suite_open("artist", "royalty-sweep") and plans.suite_open("artist", "artifacts")
    for key in ("reach", "tour", "company"):
        assert not plans.suite_open("artist", key) and plans.suite_open("pro", key), key
    for key in ("the-room", "noise-lab", "motion"):
        assert not plans.suite_open("pro", key), key
        assert plans.suite_open("pro", key, credits=1), "a pack opens the creation suites"
        assert plans.suite_open("label", key), key


def test_the_suite_door_refuses_and_says_why(monkeypatch):
    monkeypatch.delenv("SUITE_SSO_SECRET", raising=False)
    artist, _ = _client("artist")
    r = artist.get("/suites/go/reach")
    assert r.status_code == 402 and "REACH opens with Pro" in r.get_data(as_text=True)
    r = artist.get("/suites/go/the-room")
    body = r.get_data(as_text=True)
    # Credit packs are off sale (owner, 2026-09-18), so the page no longer
    # sends anyone to buy one; Label is the way in.
    assert r.status_code == 402 and "The Room runs on credits" in body
    assert "The Label membership includes credits every month" in body and "buy a credit pack" not in body
    pro, _ = _client("pro")
    assert pro.get("/suites/go/reach").status_code == 302
    assert artist.get("/royalties").status_code == 200


def test_credits_open_the_door_and_the_strip_shows_the_lock(monkeypatch):
    monkeypatch.delenv("SUITE_SSO_SECRET", raising=False)
    c, user = _client("artist")
    page = c.get("/billing").get_data(as_text=True)
    assert 'title="Opens with credits or the Label membership"' in page
    assert 'title="Opens with the Pro membership"' in page
    store.add_credits(user["id"], 50, "pack", note="test pack", ref="t:" + uuid.uuid4().hex)
    assert c.get("/suites/go/the-room").status_code == 302
    assert "Opens with credits" not in c.get("/billing").get_data(as_text=True)


def test_wallet_spends_included_first_and_a_ref_counts_once():
    _, user = _client("label")
    uid = user["id"]
    assert store.add_credits(uid, 100, "monthly", bucket="monthly", ref="m:" + uid, expires="2999-01-01T00:00:00+00:00")
    assert not store.add_credits(uid, 100, "monthly", bucket="monthly", ref="m:" + uid, expires="2999-01-01T00:00:00+00:00")
    store.add_credits(uid, 40, "pack", ref="p:" + uid)
    after = store.spend_credits(uid, 120, "the-room", ref="job-1")
    assert (after["monthly"], after["bought"]) == (0, 20)
    assert store.spend_credits(uid, 120, "the-room", ref="job-1") == after, "a replayed spend takes nothing"
    assert store.spend_credits(uid, 21, "motion", ref="job-2") is None
    assert store.credit_balances(uid)["total"] == 20


def test_included_credits_lapse_and_bought_do_not():
    _, user = _client("label")
    uid = user["id"]
    store.add_credits(uid, 100, "monthly", bucket="monthly", ref="old:" + uid, expires="2026-01-01T00:00:00+00:00")
    store.add_credits(uid, 30, "pack", ref="keep:" + uid)
    have = store.credit_balances(uid)
    assert (have["monthly"], have["bought"], have["total"]) == (0, 30, 30)


def test_label_is_given_the_month_once():
    c, user = _client("label")
    c.get("/billing")
    c.get("/billing")
    have = store.credit_balances(user["id"])
    assert have["monthly"] == plans.LABEL_MONTHLY_CREDITS and have["monthly_expires"]


def test_a_suite_spends_only_with_the_shared_secret(monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", "credits-test-secret")
    c, user = _client("artist")
    store.add_credits(user["id"], 10, "pack", ref="s:" + user["id"])
    anon = appmod.app.test_client()
    assert anon.post("/api/suites/credits", json={"token": "nonsense"}).status_code == 401
    # A sign-in hand-off token is not a spend.
    assert anon.post("/api/suites/credits", json={"token": sso.issue(user, "the-room")}).status_code == 401
    call = {"op": "spend", "email": user["email"], "suite": "the-room", "amount": 4, "ref": "render-9"}
    r = anon.post("/api/suites/credits", json={"token": sso.issue_credit_call(call)})
    assert r.status_code == 200 and r.get_json()["balance"]["total"] == 6
    r = anon.post("/api/suites/credits", json={"token": sso.issue_credit_call(dict(call, amount=50, ref="render-10"))})
    assert r.status_code == 402 and r.get_json()["balance"]["total"] == 6
    # REACH does not spend credits.
    r = anon.post("/api/suites/credits", json={"token": sso.issue_credit_call(dict(call, suite="reach"))})
    assert r.status_code == 404
