"""Stripe, second review (2026-09-19), before the owner's real-card test.

Each test here failed on the code after the first round of fixes:

  an account holding sandbox ids could never check out under the live key,
  and the owner's card said the webhook was active when live mode had none
  a paid checkout whose webhook had not landed could still become a second
  one, and a late first delivery of an old checkout overwrote the plan
  a plan change was applied from a stale snapshot when Stripe could not be
  read, a grant made by hand in Settings was undone at every renewal, and a
  member Stripe stopped charging kept a paid plan for ever
  the referral paid half of the tier the app shows, not the one billed; a
  credit Stripe did not answer about was paid again later; a refund or a
  dispute left the credit in place unseen; a deleted account could earn the
  referral again
  Sync took any $29/$79/$199 subscription, a fan club included, for a tier
  a partner-seated artist could not open Manage Billing to cancel
"""
import hashlib
import hmac
import io
import json
import time
import urllib.error
import uuid

import pytest

import app as appmod
import db as store
import stripe_provider as sb

SECRET = "whsec_round2"
PW = "stripe-round-2"


def _sig(payload, secret=SECRET):
    t = str(int(time.time()))
    v1 = hmac.new(secret.encode(), ("%s.%s" % (t, payload)).encode(), hashlib.sha256).hexdigest()
    return {"Stripe-Signature": "t=%s,v1=%s" % (t, v1)}


def _hook(event_type, obj, secret=SECRET):
    payload = json.dumps({"type": event_type, "data": {"object": obj}})
    return appmod.app.test_client().post("/webhooks/stripe", data=payload,
                                         headers=_sig(payload, secret),
                                         content_type="application/json")


def _http_error(code):
    return urllib.error.HTTPError("https://api.stripe.com/x", code, "err", {}, io.BytesIO(b"{}"))


def _sub(sid, status="active", cents=2900, plan="artist"):
    return {"id": sid, "status": status, "metadata": {"plan": plan},
            "items": {"data": [{"id": "si_" + sid, "price": {"unit_amount": cents}}]}}


@pytest.fixture
def stripe_on(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_round2")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("SANDBOX", raising=False)
    calls = []
    # routes: path prefix -> value, or an exception to raise
    routes = {}

    def lookup(path):
        for prefix in sorted(routes, key=len, reverse=True):
            if path.startswith(prefix):
                out = routes[prefix]
                if isinstance(out, BaseException):
                    raise out
                return json.loads(json.dumps(out))
        return {"id": "x", "data": []}

    def fake_http(path, fields):
        calls.append((path, dict(fields)))
        if path == "/v1/checkout/sessions":
            return {"id": "cs_new", "url": "https://checkout.stripe.com/c/new"}
        if path.endswith("/balance_transactions") and "credit_post" in routes:
            out = routes["credit_post"]
            if isinstance(out, BaseException):
                raise out
            return out
        if path == "/v1/coupons":
            return {"id": "coup_half"}
        if path == "/v1/billing_portal/sessions":
            return {"id": "bps_1", "url": "https://billing.stripe.com/p/1"}
        return {"id": "ok_1"}

    def fake_get(path):
        calls.append(("GET " + path, {}))
        return lookup(path)

    monkeypatch.setattr(sb, "_http", fake_http)
    monkeypatch.setattr(sb, "_http_get", fake_get)
    store.set_kv(sb._kv_key("ref_coupon_50"), "")
    return calls, routes


def _member(plan="artist", sub=None, customer=None):
    email = "r2-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Member", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    store.set_stripe_ids(uid, customer, sub)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _owner(monkeypatch):
    email = "r2-owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    c.post("/login", data={"email": email, "password": PW})
    return c, store.get_user_by_email(email)["id"]


def _titles(uid):
    return [n["title"] for n in store.list_notifications(uid)]


def _checkouts(calls):
    return [f for p, f in calls if p == "/v1/checkout/sessions"]


# --- modes -------------------------------------------------------------------

def test_sandbox_ids_are_dropped_under_a_key_that_does_not_know_them(stripe_on):
    calls, routes = stripe_on
    routes["/v1/customers/"] = _http_error(404)
    c, uid = _member("fan", sub="sub_sandbox", customer="cus_sandbox")
    r = c.post("/billing/checkout", data={"plan": "artist"})
    assert r.status_code == 303
    sess = _checkouts(calls)[-1]
    assert "customer" not in sess and sess["customer_email"]
    u = store.get_user(uid)
    assert u["stripe_customer_id"] is None and u["stripe_subscription_id"] is None


def test_stripe_unreachable_starts_nothing(stripe_on):
    calls, routes = stripe_on
    routes["/v1/customers/"] = _http_error(500)
    c, _uid = _member("fan", customer="cus_known")
    r = c.post("/billing/checkout", data={"plan": "artist"})
    assert r.status_code == 502 and not _checkouts(calls)


def test_the_webhook_secret_is_kept_per_mode(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_round2")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("SANDBOX", raising=False)
    store.set_kv(sb._kv_key("webhook_secret"), "")
    store.set_kv(sb._kv_key("webhook_events"), "")
    store.set_kv("stripe_webhook_secret", "whsec_from_the_sandbox")
    try:
        assert not sb.webhook_configured(), "live mode has no endpoint of its own"
        assert sb.webhook_accepts(), "old deliveries still verify"
        payload = json.dumps({"type": "noop", "data": {"object": {}}})
        assert sb.verify_webhook(_sig(payload, "whsec_from_the_sandbox")["Stripe-Signature"], payload)
        assert not sb.webhook_events_current(), "the owner's card offers the update"
    finally:
        store.set_kv("stripe_webhook_secret", "")


def test_a_hand_made_endpoint_is_offered_the_update_too(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_round2")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_by_hand")
    store.set_kv(sb._kv_key("webhook_events"), "")
    assert sb.webhook_configured() and not sb.webhook_events_current()


def test_setting_up_the_webhook_retires_the_old_secret(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_round2")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("SANDBOX", raising=False)
    store.set_kv(sb._kv_key("webhook_secret"), "")
    store.set_kv("stripe_webhook_secret", "whsec_old")
    monkeypatch.setattr(sb, "_http_get", lambda path: {"data": []})
    monkeypatch.setattr(sb, "_http", lambda path, fields: {"id": "we_live", "secret": "whsec_live"})
    try:
        assert sb.setup_webhook_endpoint("https://x.test")
        assert store.get_kv(sb._kv_key("webhook_secret")) == "whsec_live"
        assert not store.get_kv("stripe_webhook_secret")
        assert sb.webhook_configured() and sb.webhook_events_current()
    finally:
        store.set_kv(sb._kv_key("webhook_secret"), "")
        store.set_kv(sb._kv_key("webhook_events"), "")


# --- one subscription ----------------------------------------------------------

def test_a_paid_checkout_whose_webhook_has_not_landed_is_claimed_not_doubled(stripe_on):
    calls, routes = stripe_on
    c, uid = _member("fan")
    store.set_kv("stripe_open_checkout:" + uid, "cs_paid")
    routes["/v1/checkout/sessions/"] = {
        "id": "cs_paid", "status": "complete", "payment_status": "paid",
        "client_reference_id": uid, "customer": "cus_paid", "subscription": "sub_paid",
        "metadata": {"plan": "pro"}}
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.headers["Location"].endswith("/billing?upgraded=1")
    assert not _checkouts(calls), "no second checkout"
    u = store.get_user(uid)
    assert u["plan"] == "pro" and u["stripe_subscription_id"] == "sub_paid"
    assert not store.get_kv("stripe_open_checkout:" + uid)


def test_an_open_checkout_stripe_cannot_describe_blocks_a_second(stripe_on):
    calls, routes = stripe_on
    c, uid = _member("fan")
    store.set_kv("stripe_open_checkout:" + uid, "cs_mystery")
    routes["/v1/checkout/sessions/"] = _http_error(500)
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 502 and not _checkouts(calls)
    assert store.get_kv("stripe_open_checkout:" + uid) == "cs_mystery"


def test_the_webhook_clears_only_its_own_open_checkout(stripe_on):
    _calls, _routes = stripe_on
    _c, uid = _member("fan")
    store.set_kv("stripe_open_checkout:" + uid, "cs_newer")
    _hook("checkout.session.completed", {"id": "cs_older", "client_reference_id": uid,
                                         "customer": "cus_o", "subscription": "sub_o",
                                         "payment_status": "paid", "metadata": {"plan": "artist"}})
    assert store.get_kv("stripe_open_checkout:" + uid) == "cs_newer"


def test_a_past_due_subscription_is_settled_first_not_doubled(stripe_on):
    calls, routes = stripe_on
    routes["/v1/subscriptions?"] = {"data": [_sub("sub_owed", "past_due", 7900, "pro")]}
    c, uid = _member("pro", customer="cus_owes")
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 502 and "bill waiting" in r.get_data(as_text=True)
    assert not _checkouts(calls)
    assert store.get_user(uid)["stripe_subscription_id"] == "sub_owed"


def test_a_late_old_checkout_does_not_replace_the_live_subscription(stripe_on, monkeypatch):
    _calls, routes = stripe_on
    _o, oid = _owner(monkeypatch)
    _c, uid = _member("pro", sub="sub_live", customer="cus_late")
    routes["/v1/subscriptions/sub_live"] = _sub("sub_live", "active", 7900, "pro")
    _hook("checkout.session.completed", {"id": "cs_old_" + uid[:6], "client_reference_id": uid,
                                         "customer": "cus_late", "subscription": "sub_old",
                                         "payment_status": "paid", "metadata": {"plan": "artist"}})
    u = store.get_user(uid)
    assert u["plan"] == "pro" and u["stripe_subscription_id"] == "sub_live"
    assert "Two subscriptions on one account" in _titles(oid)


def test_a_checkout_that_failed_half_way_is_run_again(stripe_on, monkeypatch):
    _c, uid = _member("fan")
    obj = {"id": "cs_half_" + uid[:6], "client_reference_id": uid, "customer": "cus_h",
           "subscription": "sub_h", "payment_status": "paid", "metadata": {"plan": "artist"}}
    real = store.notify
    boom = {"on": True}

    def flaky(*a, **k):
        if boom["on"]:
            raise RuntimeError("database is locked")
        return real(*a, **k)

    monkeypatch.setattr(store, "notify", flaky)
    try:
        assert _hook("checkout.session.completed", obj).status_code == 500
    except RuntimeError:
        pass                        # the test client may raise it instead
    assert not store.get_kv("stripe_cs_done:" + obj["id"]), "not marked done"
    boom["on"] = False
    _hook("checkout.session.completed", obj)
    assert store.get_user(uid)["stripe_subscription_id"] == "sub_h"
    assert store.get_kv("stripe_cs_done:" + obj["id"]) == "1"


# --- a plan follows Stripe only when Stripe can be read ----------------------------

def test_a_change_is_not_applied_from_a_stale_snapshot(stripe_on):
    _calls, routes = stripe_on
    _c, uid = _member("pro", sub="sub_snap", customer="cus_snap")
    routes["/v1/subscriptions/"] = RuntimeError("timed out")
    r = _hook("customer.subscription.updated", dict(_sub("sub_snap", "active", 2900), customer="cus_snap"))
    assert r.status_code == 503, "Stripe sends it again"
    assert store.get_user(uid)["plan"] == "pro"


def test_a_plan_the_owner_granted_survives_renewal(stripe_on, monkeypatch):
    _calls, routes = stripe_on
    owner, _oid = _owner(monkeypatch)
    _c, uid = _member("artist", sub="sub_grant", customer="cus_grant")
    email = store.get_user(uid)["email"]
    owner.post("/admin/plan", data={"email": email, "plan": "label"})
    routes["/v1/subscriptions/"] = _sub("sub_grant", "active", 2900)
    _hook("customer.subscription.updated", dict(_sub("sub_grant", "active", 2900), customer="cus_grant"))
    assert store.get_user(uid)["plan"] == "label"
    owner.post("/admin/plan", data={"email": email, "plan": "fan"})
    _hook("customer.subscription.updated", dict(_sub("sub_grant", "active", 2900), customer="cus_grant"))
    assert store.get_user(uid)["plan"] == "artist", "a free grant hands it back to the subscription"


def test_stripe_giving_up_ends_the_paid_plan(stripe_on):
    _c, uid = _member("pro", sub="sub_fail", customer="cus_fail")
    _hook("invoice.payment_failed", {"customer": "cus_fail", "subscription": "sub_fail",
                                     "next_payment_attempt": int(time.time()) + 86400})
    assert store.get_user(uid)["plan"] == "pro", "still retrying"
    _hook("invoice.payment_failed", {"customer": "cus_fail",
                                     "parent": {"subscription_details": {"subscription": "sub_fail"}},
                                     "next_payment_attempt": None})
    assert store.get_user(uid)["plan"] == "fan"
    assert "Plan paused" in _titles(uid)


def test_another_subscriptions_failure_ends_nothing(stripe_on):
    _c, uid = _member("pro", sub="sub_mine", customer="cus_mine")
    _hook("invoice.payment_failed", {"customer": "cus_mine", "subscription": "sub_other",
                                     "next_payment_attempt": None})
    assert store.get_user(uid)["plan"] == "pro"


# --- the referral ------------------------------------------------------------------

def _referred(referrer_id):
    code = store.ensure_ref_code(referrer_id)
    friend = appmod.app.test_client()
    friend.get("/signup?ref=" + code)
    email = "r2-friend-%s@example.net" % uuid.uuid4().hex[:10]
    friend.post("/signup", data={"name": "Friend", "email": email, "password": PW})
    fid = store.get_user_by_email(email)["id"]
    return friend, fid, email


def test_the_credit_is_half_of_what_the_referrer_is_billed(stripe_on):
    calls, routes = stripe_on
    _r, rid = _member("label", sub="sub_ref", customer="cus_ref_b")   # shown Label
    routes["/v1/subscriptions/sub_ref"] = _sub("sub_ref", "active", 2900)  # billed Artist
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_friend_b", "sub_friend_b")
    _hook("invoice.paid", {"customer": "cus_friend_b", "amount_paid": 7900})
    credit = [f for p, f in calls if p.endswith("/balance_transactions")][-1]
    assert credit["amount"] == "-1450", "half of the $29 billed, not of Label"


def test_a_credit_stripe_did_not_answer_about_is_never_paid_twice(stripe_on, monkeypatch):
    calls, routes = stripe_on
    _o, oid = _owner(monkeypatch)
    _r, rid = _member("artist", sub="sub_r3", customer="cus_r3")
    routes["/v1/subscriptions/sub_r3"] = _sub("sub_r3", "active", 2900)
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_f3", "sub_f3")
    routes["credit_post"] = RuntimeError("read timed out")
    routes["/v1/customers/cus_r3/balance_transactions"] = {"data": []}
    _hook("invoice.paid", {"customer": "cus_f3", "amount_paid": 1450})
    assert store.get_user(fid)["ref_credited"] == 1, "the claim is kept"
    assert "Check a referral credit" in _titles(oid)
    posts = len([p for p, f in calls if p.endswith("/balance_transactions")])
    _hook("invoice.paid", {"customer": "cus_f3", "amount_paid": 2900})
    assert len([p for p, f in calls if p.endswith("/balance_transactions")]) == posts


def test_a_credit_found_on_the_balance_counts_as_paid(stripe_on):
    _calls, routes = stripe_on
    _r, rid = _member("artist", sub="sub_r4", customer="cus_r4")
    routes["/v1/subscriptions/sub_r4"] = _sub("sub_r4", "active", 2900)
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_f4", "sub_f4")
    routes["credit_post"] = RuntimeError("read timed out")
    routes["/v1/customers/cus_r4/balance_transactions"] = {"data": [{"metadata": {"sb_ref_friend": fid}}]}
    _hook("invoice.paid", {"customer": "cus_f4", "amount_paid": 1450})
    assert "Referral credit applied" in _titles(rid)


def test_a_refunded_friend_is_reported_to_the_owner(stripe_on, monkeypatch):
    _calls, routes = stripe_on
    _o, oid = _owner(monkeypatch)
    _r, rid = _member("artist", sub="sub_r5", customer="cus_r5")
    routes["/v1/subscriptions/sub_r5"] = _sub("sub_r5", "active", 2900)
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_f5", "sub_f5")
    _hook("invoice.paid", {"customer": "cus_f5", "amount_paid": 1450})
    assert store.get_user(fid)["ref_credited"] == 1
    _hook("charge.refunded", {"customer": "cus_f5", "amount_refunded": 1450})
    assert "Referral credit on a refunded payment" in _titles(oid)


def test_a_refund_before_the_credit_means_no_credit(stripe_on):
    calls, routes = stripe_on
    _r, rid = _member("fan")                                  # not paying yet
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_f6", "sub_f6")
    _hook("invoice.paid", {"customer": "cus_f6", "amount_paid": 1450})
    _hook("charge.refunded", {"customer": "cus_f6", "amount_refunded": 1450})
    # The referrer starts paying: the refunded referral earns nothing.
    store.set_user_plan(rid, "artist")
    store.set_stripe_ids(rid, "cus_r6", "sub_r6")
    routes["/v1/subscriptions/sub_r6"] = _sub("sub_r6", "active", 2900)
    _hook("invoice.paid", {"customer": "cus_r6", "amount_paid": 2900})
    assert not [p for p, f in calls if p.endswith("/balance_transactions")]


def test_a_dispute_is_traced_to_its_customer(stripe_on, monkeypatch):
    _calls, routes = stripe_on
    _o, oid = _owner(monkeypatch)
    _r, rid = _member("artist", sub="sub_r7", customer="cus_r7")
    routes["/v1/subscriptions/sub_r7"] = _sub("sub_r7", "active", 2900)
    _f, fid, _e = _referred(rid)
    store.set_stripe_ids(fid, "cus_f7", "sub_f7")
    _hook("invoice.paid", {"customer": "cus_f7", "amount_paid": 1450})
    routes["/v1/charges/"] = {"id": "ch_7", "customer": "cus_f7"}
    _hook("charge.dispute.created", {"charge": "ch_7", "amount": 1450})
    assert "Referral credit on a disputed payment" in _titles(oid)


def test_deleting_and_rejoining_does_not_earn_the_referral_again(stripe_on):
    _r, rid = _member("artist", customer="cus_r8")
    friend, fid, email = _referred(rid)
    assert store.get_user(fid)["referred_by"] == rid
    friend.post("/login", data={"email": email, "password": PW})
    friend.post("/account/delete", data={"confirm": email})
    assert store.get_user(fid) is None
    again = appmod.app.test_client()
    again.get("/signup?ref=" + store.ensure_ref_code(rid))
    again.post("/signup", data={"name": "Friend", "email": email, "password": PW})
    assert not store.get_user_by_email(email)["referred_by"]


# --- Sync and the portal -----------------------------------------------------------

def test_sync_does_not_take_a_fan_club_for_a_tier(stripe_on):
    _calls, routes = stripe_on
    c, uid = _member("fan")
    routes["/v1/customers?"] = {"data": [{"id": "cus_fanclub"}]}
    routes["/v1/subscriptions?"] = {"data": [{"id": "sub_club", "status": "active",
                                              "items": {"data": [{"price": {"unit_amount": 7900}}]}}]}
    r = c.post("/billing/sync")
    assert r.headers["Location"].endswith("?sync=none")
    assert store.get_user(uid)["plan"] == "fan"
    routes["/v1/subscriptions?"] = {"data": [_sub("sub_mine", "active", 7900, "pro")]}
    c.post("/billing/sync")
    assert store.get_user(uid)["plan"] == "pro"


def test_a_partner_seated_artist_can_still_cancel_their_own_subscription(stripe_on):
    _calls, routes = stripe_on
    c, uid = _member("artist", sub="sub_own", customer="cus_own")
    with store.get_db() as db:
        db.execute("UPDATE users SET partner_id = ? WHERE id = ?", ("partner-x", uid))
    routes["/v1/customers/"] = {"id": "cus_own"}
    r = c.post("/billing/portal")
    assert r.status_code == 303
