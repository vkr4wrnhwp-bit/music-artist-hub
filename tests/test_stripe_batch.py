"""Stripe, before a real card goes through it (2026-09-19).

Found by the 2026-09-18 launch check, each of these took or kept money
wrongly, or would have:

  a member changing plan opened a SECOND subscription; the old one kept
  billing, unseen by the app
  a checkout that completed unpaid still granted the plan, and a delayed
  payment method could complete that way
  nothing heard a subscription change in Stripe, so past-due and unpaid
  members kept their plan, and a portal or dashboard change was missed
  any subscription ending dropped the account to Fan, even an old one
  the referral paid the referrer $9 on a free first month; the owner's offer
  is 50% off the new artist's first month and 50% off the referrer's next,
  once the new artist has actually paid
"""
import hashlib
import hmac
import json
import time
import uuid

import pytest

import app as appmod
import db as store
import stripe_provider as sb

SECRET = "whsec_batchtest"
PW = "stripe-batch-1"


def _sig(payload):
    t = str(int(time.time()))
    v1 = hmac.new(SECRET.encode(), ("%s.%s" % (t, payload)).encode(), hashlib.sha256).hexdigest()
    return {"Stripe-Signature": "t=%s,v1=%s" % (t, v1)}


def _hook(event_type, obj):
    payload = json.dumps({"type": event_type, "data": {"object": obj}})
    return appmod.app.test_client().post("/webhooks/stripe", data=payload, headers=_sig(payload),
                                         content_type="application/json")


@pytest.fixture
def stripe_on(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_batch")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("SANDBOX", raising=False)
    calls = []
    state = {"sub": {"id": "sub_1", "status": "active",
                     "items": {"data": [{"id": "si_1", "price": {"unit_amount": 2900}}]}},
             "update": {"id": "sub_1", "status": "active"}}

    def fake_http(path, fields):
        calls.append((path, dict(fields)))
        if path == "/v1/products":
            return {"id": "prod_" + fields["name"].split()[-1].lower()}
        if path == "/v1/coupons":
            return {"id": "coup_half"}
        if path == "/v1/checkout/sessions":
            return {"id": "cs_1", "url": "https://checkout.stripe.com/c/1"}
        if path.startswith("/v1/subscriptions/"):
            return dict(state["update"])
        return {"id": "cbt_1"}

    monkeypatch.setattr(sb, "_http", fake_http)
    monkeypatch.setattr(sb, "_http_get", lambda path: dict(state["sub"]))
    for key in ("stripe_product_artist", "stripe_product_pro", "stripe_product_label", "stripe_ref_coupon_50"):
        store.set_kv(key, "")
    return calls, state


def _member(plan="artist", sub="sub_1", customer=None):
    email = "member-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Member", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    store.set_stripe_ids(uid, customer or ("cus_" + uid[:8]), sub)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


# --- one subscription, whatever the plan changes to -------------------------

def test_an_upgrade_changes_the_subscription_it_has(stripe_on):
    calls, _state = stripe_on
    c, uid = _member("artist")
    page = c.get("/billing").get_data(as_text=True)
    assert "Switch to Pro: $79/mo" in page
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/billing?changed=pro")
    assert not [p for p, f in calls if p == "/v1/checkout/sessions"], "no second subscription"
    change = [f for p, f in calls if p == "/v1/subscriptions/sub_1" and "items[0][id]" in f][0]
    assert change["items[0][id]"] == "si_1"
    assert change["items[0][price_data][unit_amount]"] == "7900"
    assert change["proration_behavior"] == "always_invoice"
    assert change["payment_behavior"] == "pending_if_incomplete"
    assert store.get_user(uid)["plan"] == "pro"


def test_an_upgrade_waiting_on_payment_keeps_the_old_plan(stripe_on):
    _calls, state = stripe_on
    state["update"] = {"id": "sub_1", "status": "active", "pending_update": {"expires_at": 1}}
    c, uid = _member("artist")
    r = c.post("/billing/checkout", data={"plan": "label"})
    assert r.headers["Location"].endswith("/billing?changed=pending")
    assert store.get_user(uid)["plan"] == "artist"
    assert "Waiting on the payment" in c.get("/billing?changed=pending").get_data(as_text=True)


def test_a_downgrade_takes_effect_with_a_credit_not_a_charge(stripe_on):
    calls, state = stripe_on
    state["sub"]["items"]["data"][0]["price"]["unit_amount"] = 19900
    c, uid = _member("label")
    c.post("/billing/checkout", data={"plan": "artist"})
    change = [f for p, f in calls if p == "/v1/subscriptions/sub_1" and "items[0][id]" in f][0]
    assert change["proration_behavior"] == "create_prorations" and "payment_behavior" not in change
    assert store.get_user(uid)["plan"] == "artist"


def test_a_cancelled_subscription_checks_out_again_as_the_same_customer(stripe_on):
    calls, state = stripe_on
    state["sub"]["status"] = "canceled"
    c, uid = _member("artist", customer="cus_known")
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 303
    sess = [f for p, f in calls if p == "/v1/checkout/sessions"][-1]
    assert sess["customer"] == "cus_known" and "customer_email" not in sess
    assert sess["payment_method_types[0]"] == "card"


def test_a_new_member_checks_out_by_card_only(stripe_on):
    calls, _state = stripe_on
    c, uid = _member("artist", sub=None, customer=None)
    store.set_stripe_ids(uid, None, None)
    c.post("/billing/checkout", data={"plan": "artist"})
    sess = [f for p, f in calls if p == "/v1/checkout/sessions"][-1]
    assert sess["payment_method_types[0]"] == "card" and sess["customer_email"]


# --- a plan follows money, and follows Stripe --------------------------------

def test_an_unpaid_checkout_grants_nothing(stripe_on):
    _c, uid = _member("fan", sub=None)
    store.set_stripe_ids(uid, None, None)
    _hook("checkout.session.completed", {"client_reference_id": uid, "customer": "cus_u",
                                         "subscription": "sub_u", "payment_status": "unpaid",
                                         "metadata": {"plan": "label"}})
    assert store.get_user(uid)["plan"] == "fan"
    _hook("checkout.session.completed", {"client_reference_id": uid, "customer": "cus_u",
                                         "subscription": "sub_u", "payment_status": "paid",
                                         "metadata": {"plan": "label"}})
    assert store.get_user(uid)["plan"] == "label"


def _sub(sid, customer, status, cents):
    return {"id": sid, "customer": customer, "status": status,
            "items": {"data": [{"id": "si", "price": {"unit_amount": cents}}]}}


def test_a_change_made_in_stripe_is_followed_here(stripe_on):
    _c, uid = _member("artist", sub="sub_s", customer="cus_s")
    _hook("customer.subscription.updated", _sub("sub_s", "cus_s", "active", 7900))
    assert store.get_user(uid)["plan"] == "pro"


def test_past_due_keeps_the_plan_while_stripe_retries_and_unpaid_ends_it(stripe_on):
    _c, uid = _member("pro", sub="sub_p", customer="cus_p")
    _hook("customer.subscription.updated", _sub("sub_p", "cus_p", "past_due", 7900))
    assert store.get_user(uid)["plan"] == "pro"
    assert any("past due" in n["title"].lower() for n in store.list_notifications(uid))
    _hook("customer.subscription.updated", _sub("sub_p", "cus_p", "unpaid", 7900))
    assert store.get_user(uid)["plan"] == "fan"


def test_another_subscription_of_the_same_customer_changes_nothing(stripe_on):
    _c, uid = _member("pro", sub="sub_now", customer="cus_two")
    _hook("customer.subscription.updated", _sub("sub_old", "cus_two", "unpaid", 2900))
    _hook("customer.subscription.deleted", {"id": "sub_old", "customer": "cus_two"})
    assert store.get_user(uid)["plan"] == "pro", "an old subscription ending drops nobody"
    _hook("customer.subscription.deleted", {"id": "sub_now", "customer": "cus_two"})
    assert store.get_user(uid)["plan"] == "fan"


# --- the referral: 50% each way, on money ------------------------------------

def _referred(referrer_id):
    code = store.ensure_ref_code(referrer_id)
    friend = appmod.app.test_client()
    friend.get("/signup?ref=" + code)
    email = "friend-%s@example.net" % uuid.uuid4().hex[:10]
    friend.post("/signup", data={"name": "Friend", "email": email, "password": PW})
    fid = store.get_user_by_email(email)["id"]
    assert store.get_user(fid)["referred_by"] == referrer_id
    return friend, fid


def test_the_new_artist_gets_half_off_their_first_month(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("artist")
    friend, fid = _referred(rid)
    friend.post("/login", data={"email": store.get_user(fid)["email"], "password": PW})
    friend.post("/billing/checkout", data={"plan": "pro"})
    coupon = [f for p, f in calls if p == "/v1/coupons"][-1]
    assert coupon["percent_off"] == "50" and coupon["duration"] == "once"
    assert [f for p, f in calls if p == "/v1/checkout/sessions"][-1]["discounts[0][coupon]"] == "coup_half"


def test_the_referrer_gets_half_their_own_month_once_the_friend_has_paid(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("artist", customer="cus_ref")
    _f, fid = _referred(rid)
    store.set_stripe_ids(fid, "cus_friend", "sub_friend")
    _hook("invoice.paid", {"customer": "cus_friend", "amount_paid": 0})
    assert store.get_user(fid)["ref_credited"] == 0, "nothing on a $0 invoice"
    _hook("invoice.paid", {"customer": "cus_friend", "amount_paid": 3950})
    assert store.get_user(fid)["ref_credited"] == 1
    credit = [(p, f) for p, f in calls if "balance_transactions" in p][-1]
    assert "cus_ref" in credit[0] and credit[1]["amount"] == "-1450"  # half of $29
    _hook("invoice.paid", {"customer": "cus_friend", "amount_paid": 3950})
    assert len([p for p, f in calls if "balance_transactions" in p]) == 1, "credited once"


def test_a_referrer_not_yet_paying_is_credited_on_their_first_bill(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("fan", sub=None, customer=None)
    store.set_stripe_ids(rid, None, None)
    _f, fid = _referred(rid)
    store.set_stripe_ids(fid, "cus_f2", "sub_f2")
    _hook("invoice.paid", {"customer": "cus_f2", "amount_paid": 3950})
    assert store.get_user(fid)["ref_credited"] == 0
    assert not [p for p, f in calls if "balance_transactions" in p]
    # The referrer subscribes to Pro and pays their first bill.
    store.set_user_plan(rid, "pro")
    store.set_stripe_ids(rid, "cus_r2", "sub_r2")
    _hook("invoice.paid", {"customer": "cus_r2", "amount_paid": 7900})
    credit = [(p, f) for p, f in calls if "balance_transactions" in p][-1]
    assert "cus_r2" in credit[0] and credit[1]["amount"] == "-3950"  # half of $79
    assert store.get_user(fid)["ref_credited"] == 1


# --- the webhook hears the new events ----------------------------------------

def test_the_webhook_listens_for_changes_and_payments():
    assert "customer.subscription.updated" in sb.WEBHOOK_EVENTS
    assert "invoice.paid" in sb.WEBHOOK_EVENTS


def test_an_endpoint_set_up_before_the_new_events_is_offered_an_update(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    store.set_kv("stripe_webhook_events", "checkout.session.completed")
    assert sb.webhook_events_current() is False
    store.set_kv("stripe_webhook_events", ",".join(sb.WEBHOOK_EVENTS))
    assert sb.webhook_events_current() is True
