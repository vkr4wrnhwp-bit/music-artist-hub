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
        if path == "/v1/prices":
            return {"id": "price_" + fields["product"].split("_")[-1]}
        if state.get("raise_on") and path.startswith(state["raise_on"]):
            raise RuntimeError("Stripe timed out")
        if path == "/v1/coupons":
            return {"id": "coup_half"}
        if path == "/v1/checkout/sessions":
            return {"id": "cs_1", "url": "https://checkout.stripe.com/c/1"}
        if path.startswith("/v1/subscriptions/"):
            return dict(state["update"])
        return {"id": "cbt_1"}

    monkeypatch.setattr(sb, "_http", fake_http)
    monkeypatch.setattr(sb, "_http_get", lambda path: dict(state["sub"]))
    for name in ("product_artist", "product_pro", "product_label",
                 "price_artist", "price_pro", "price_label", "ref_coupon_50"):
        store.set_kv(sb._kv_key(name), "")
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
    # A reusable Price, which a pending update accepts; not inline price_data.
    assert change["items[0][price]"] == "price_pro" and not any("price_data" in k for k in change)
    price = [f for p, f in calls if p == "/v1/prices"][0]
    assert price["unit_amount"] == "7900" and price["recurring[interval]"] == "month"
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


def test_a_change_made_in_stripe_is_followed_here(stripe_on, monkeypatch):
    _c, uid = _member("artist", sub="sub_s", customer="cus_s")
    # The handler re-reads the subscription; Stripe now bills Pro.
    monkeypatch.setattr(sb, "_http_get", lambda path: _sub("sub_s", "cus_s", "active", 7900))
    _hook("customer.subscription.updated", _sub("sub_s", "cus_s", "active", 7900))
    assert store.get_user(uid)["plan"] == "pro"


def test_past_due_keeps_the_plan_while_stripe_retries_and_unpaid_ends_it(stripe_on, monkeypatch):
    _c, uid = _member("pro", sub="sub_p", customer="cus_p")
    now = {"status": "past_due"}
    monkeypatch.setattr(sb, "_http_get", lambda path: _sub("sub_p", "cus_p", now["status"], 7900))
    _hook("customer.subscription.updated", _sub("sub_p", "cus_p", "past_due", 7900))
    assert store.get_user(uid)["plan"] == "pro"
    assert any("past due" in n["title"].lower() for n in store.list_notifications(uid))
    now["status"] = "unpaid"
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



# --- 2026-09-19 review: what must never happen ---------------------------------

def test_a_failed_change_never_opens_a_second_checkout(stripe_on):
    calls, state = stripe_on
    state["raise_on"] = "/v1/subscriptions/sub_1"       # the update times out
    c, uid = _member("artist")
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 502 and "Nothing new was started" in r.get_data(as_text=True)
    assert not [p for p, f in calls if p == "/v1/checkout/sessions"]
    assert store.get_user(uid)["plan"] == "artist"
    assert store.get_user(uid)["stripe_subscription_id"] == "sub_1"


def test_an_unpaid_subscription_is_settled_first_not_doubled(stripe_on):
    calls, state = stripe_on
    state["sub"]["status"] = "unpaid"
    c, _uid = _member("artist")
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.status_code == 502 and "bill waiting" in r.get_data(as_text=True)
    assert not [p for p, f in calls if p == "/v1/checkout/sessions"]


def test_two_clicks_do_not_open_two_checkouts(stripe_on):
    calls, _state = stripe_on
    c, uid = _member("artist", sub=None, customer=None)
    store.set_stripe_ids(uid, None, None)
    store.set_kv("stripe_open_checkout:" + uid, "")
    c.post("/billing/checkout", data={"plan": "artist"})
    c.post("/billing/checkout", data={"plan": "artist"})
    expired = [p for p, f in calls if p.endswith("/expire")]
    assert expired == ["/v1/checkout/sessions/cs_1/expire"], "the first is closed before the second"


def test_a_member_who_already_pays_is_not_sold_a_second_subscription(stripe_on, monkeypatch):
    calls, _state = stripe_on
    monkeypatch.setattr(sb, "_http_get", lambda path: {"data": [
        {"id": "sub_live", "status": "active", "items": {"data": [{"id": "si", "price": {"unit_amount": 7900}}]}}]})
    c, uid = _member("fan", sub=None, customer="cus_paying")
    store.set_stripe_ids(uid, "cus_paying", None)
    r = c.post("/billing/checkout", data={"plan": "pro"})
    assert r.headers["Location"].endswith("/billing?sync=found")
    assert not [p for p, f in calls if p == "/v1/checkout/sessions"]
    u = store.get_user(uid)
    assert u["plan"] == "pro" and u["stripe_subscription_id"] == "sub_live"


def test_the_coupon_is_for_a_first_subscription_only(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("artist")
    friend, fid = _referred(rid)
    friend.post("/login", data={"email": store.get_user(fid)["email"], "password": PW})
    store.set_stripe_ids(fid, "cus_before", None)          # billed before, then cancelled
    friend.post("/billing/checkout", data={"plan": "artist"})
    sess = [f for p, f in calls if p == "/v1/checkout/sessions"][-1]
    assert "discounts[0][coupon]" not in sess


def test_the_coupon_name_fits_stripes_limit():
    assert len(sb.REFERRAL_COUPON_NAME) <= 40


def test_a_referral_settles_on_the_checkout_itself_when_invoice_paid_came_first(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("artist", customer="cus_early_ref")
    _f, fid = _referred(rid)
    store.set_stripe_ids(fid, None, None)
    # invoice.paid first: the customer is not linked yet, so nothing happens.
    _hook("invoice.paid", {"customer": "cus_new_friend", "amount_paid": 1450})
    assert store.get_user(fid)["ref_credited"] == 0
    _hook("checkout.session.completed", {"id": "cs_early", "client_reference_id": fid,
                                         "customer": "cus_new_friend", "subscription": "sub_nf",
                                         "payment_status": "paid", "amount_total": 1450,
                                         "metadata": {"plan": "artist"}})
    assert store.get_user(fid)["ref_credited"] == 1
    credit = [f for p, f in calls if "balance_transactions" in p][-1]
    assert credit["amount"] == "-1450" and credit[sb.IDEMPOTENCY_FIELD] == "sb-ref-credit-" + fid


def test_a_credit_is_never_more_than_the_friend_paid(stripe_on):
    calls, _state = stripe_on
    _r, rid = _member("label", customer="cus_label_ref")
    _f, fid = _referred(rid)
    store.set_stripe_ids(fid, "cus_small", "sub_small")
    _hook("invoice.paid", {"customer": "cus_small", "amount_paid": 1450})
    credit = [f for p, f in calls if "balance_transactions" in p][-1]
    assert credit["amount"] == "-1450", "not $99.50 for a $14.50 payment"


def test_a_referral_is_claimed_once_even_if_asked_twice_at_once(stripe_on):
    _calls, _state = stripe_on
    _r, rid = _member("artist")
    _f, fid = _referred(rid)
    assert store.claim_ref_credit(fid) is True
    assert store.claim_ref_credit(fid) is False, "the second worker gets nothing"


def test_a_replayed_checkout_is_handled_once(stripe_on):
    _c, uid = _member("pro", sub="sub_now", customer="cus_rp")
    obj = {"id": "cs_old", "client_reference_id": uid, "customer": "cus_rp", "subscription": "sub_old",
           "payment_status": "paid", "metadata": {"plan": "artist"}}
    store.set_kv("stripe_cs_done:cs_old", "1")                 # handled long ago
    _hook("checkout.session.completed", obj)
    u = store.get_user(uid)
    assert u["plan"] == "pro" and u["stripe_subscription_id"] == "sub_now"


def test_a_late_event_is_checked_against_stripe_before_it_changes_a_plan(stripe_on, monkeypatch):
    _c, uid = _member("pro", sub="sub_cur", customer="cus_late")
    monkeypatch.setattr(sb, "_http_get", lambda path: _sub("sub_cur", "cus_late", "active", 7900))
    # A stale snapshot says Artist; Stripe now says Pro.
    _hook("customer.subscription.updated", _sub("sub_cur", "cus_late", "active", 2900))
    assert store.get_user(uid)["plan"] == "pro"


def test_the_owner_and_partner_seats_are_never_moved_by_stripe(stripe_on, monkeypatch):
    email = "owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    oid = store.get_user_by_email(email)["id"]
    store.set_user_plan(oid, "label")
    store.set_stripe_ids(oid, "cus_owner", "sub_owner")
    monkeypatch.setattr(sb, "_http_get", lambda path: _sub("sub_owner", "cus_owner", "active", 2900))
    _hook("customer.subscription.updated", _sub("sub_owner", "cus_owner", "active", 2900))
    _hook("customer.subscription.deleted", {"id": "sub_owner", "customer": "cus_owner"})
    assert store.get_user(oid)["plan"] == "label"


def test_partner_staff_acting_as_an_artist_cannot_charge_their_card(stripe_on):
    calls, _state = stripe_on
    c, uid = _member("artist")
    with c.session_transaction() as sess:
        sess["acting_as"] = uid
    import partner_os
    orig = partner_os.acting_context
    partner_os.acting_context = lambda staff, subject: store.get_user(subject)
    try:
        r = c.post("/billing/checkout", data={"plan": "label"})
    finally:
        partner_os.acting_context = orig
    assert r.status_code == 302 and r.headers["Location"].endswith("/billing")
    assert not [p for p, f in calls if p.startswith("/v1/subscriptions/") or p == "/v1/checkout/sessions"]


def test_ids_are_remembered_per_mode(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    t = sb._kv_key("price_pro")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_x")
    assert sb._kv_key("price_pro") != t and "live" in sb._kv_key("price_pro")


def test_the_webhook_is_updated_in_place_when_it_is_ours(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("SANDBOX", raising=False)
    store.set_kv("stripe_webhook_secret", "whsec_ours")
    posts, deletes = [], []
    monkeypatch.setattr(sb, "_http_get", lambda path: {"data": [{"id": "we_1", "url": "https://x.test/webhooks/stripe"}]})
    monkeypatch.setattr(sb, "_http", lambda path, fields: posts.append((path, fields)) or {"id": "we_1"})
    monkeypatch.setattr(sb, "_http_delete", lambda path: deletes.append(path) or {})
    out = sb.setup_webhook_endpoint("https://x.test")
    assert out and deletes == [] and posts[0][0] == "/v1/webhook_endpoints/we_1"
    assert "invoice.paid" in posts[0][1].values()
    assert sb.webhook_events_current()
