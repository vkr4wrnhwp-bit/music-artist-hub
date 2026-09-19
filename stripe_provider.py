"""Stripe billing — real subscriptions behind the tier walls.

Env-gated like every provider: without STRIPE_SECRET_KEY the app keeps
its labeled demo plan-switching and never pretends to charge anyone.
Checkout uses Stripe-hosted pages (no card data ever touches this
server); webhooks are signature-verified. `_http` is the test seam.
"""

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import sandbox

_TIMEOUT = 20

# Tier -> (monthly cents, display name). Keep in sync with plans.PLANS.
PRICES = {
    "artist": (2900, "Street Banker Artist"),
    "pro": (7900, "Street Banker Pro"),
    "label": (19900, "Street Banker Label"),
}


def configured():
    # No card is charged from an experiment, whatever key is set.
    if sandbox.active():
        return False
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


WEBHOOK_EVENTS = ("checkout.session.completed",
                  "checkout.session.async_payment_succeeded",
                  "customer.subscription.deleted",
                  # A plan changed, went past due or unpaid anywhere (the
                  # portal, the dashboard, a retry running out), and the
                  # first paid invoice that settles a referral (2026-09-19).
                  "customer.subscription.updated",
                  "invoice.paid",
                  "invoice.payment_failed",
                  # Money coming back: a referral credit paid on a payment
                  # that was refunded or disputed is the owner's to reverse
                  # (2026-09-19 second review).
                  "charge.refunded",
                  "charge.dispute.created")


def mode():
    """'live' or 'test', from the secret key. Ids Stripe gave in one mode do
    not exist in the other, so everything remembered is kept per mode."""
    key = os.environ.get("STRIPE_SECRET_KEY") or ""
    return "live" if key.startswith(("sk_live", "rk_live")) else "test"


def _kv_key(name):
    return "stripe_%s_%s" % (mode(), name)


def plan_for_amount(cents):
    """Which tier a monthly price in cents is, or None. The three prices are
    distinct, so a subscription changed anywhere still says its tier."""
    for key, (amount, _name) in PRICES.items():
        if int(cents or 0) == amount:
            return key
    return None


def plan_for_subscription(sub):
    """The tier a Stripe subscription object is on, read from its first
    item's price, or None."""
    items = ((sub or {}).get("items") or {}).get("data") or []
    if not items:
        return None
    return plan_for_amount((items[0].get("price") or {}).get("unit_amount"))


# Where the secret lived before it was kept per mode. Its endpoint may be
# the sandbox's, so it still verifies deliveries (nothing breaks on deploy)
# but never counts as this mode's endpoint (2026-09-19 second review: after
# the live key went in, the card said "active" with no live endpoint).
_LEGACY_SECRET_KEY = "stripe_webhook_secret"
_LEGACY_EVENTS_KEY = "stripe_webhook_events"


def _kv(name):
    """Lazy import keeps this module import-safe before the database exists."""
    try:
        import db
        return db.get_kv(name) or ""
    except Exception:
        return ""


def _stored_webhook_secret():
    """Signing secret the in-app setup saved for this mode's endpoint."""
    return _kv(_kv_key("webhook_secret"))


def _legacy_webhook_secret():
    return _kv(_LEGACY_SECRET_KEY)


def webhook_configured():
    """This mode has an endpoint whose signing secret the app holds."""
    return bool(os.environ.get("STRIPE_WEBHOOK_SECRET") or _stored_webhook_secret())


def webhook_accepts():
    """Any secret a delivery can be verified with, the old one included."""
    return bool(webhook_configured() or _legacy_webhook_secret())


def webhook_events_current():
    """Was this mode's endpoint set up by the app with today's event list?
    An endpoint made before an event was added never receives it, and one
    made by hand in the dashboard (the env secret) cannot be checked, so
    the owner's billing card offers the one-click update for both."""
    return _kv(_kv_key("webhook_events")) == ",".join(WEBHOOK_EVENTS)


IDEMPOTENCY_FIELD = "__idempotency_key"


def _http(path, fields):
    """Form-encoded POST to the Stripe API — tests monkeypatch this.

    A caller that must not act twice puts a key under IDEMPOTENCY_FIELD;
    it travels as Stripe's Idempotency-Key header, never as a field."""
    fields = dict(fields)
    idem = fields.pop(IDEMPOTENCY_FIELD, None)
    headers = {"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"],
               "Content-Type": "application/x-www-form-urlencoded"}
    if idem:
        headers["Idempotency-Key"] = idem
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        data=urllib.parse.urlencode(fields).encode(),
        headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# The referral offer (owner, 2026-09-18, "yes"): the new artist gets 50% off
# their first month; the referrer gets 50% off their next month once the new
# artist has paid. It was 100% off, which paid the referrer on a $0 checkout.
REFERRAL_PERCENT = 50
# Stripe allows 40 characters for a coupon's name; the first name tried was
# 49, so the coupon was never created (2026-09-19 review).
REFERRAL_COUPON_NAME = "Referral: 50% off first month"


def _ref_coupon_key():
    return _kv_key("ref_coupon_50")


def referrer_credit_cents(plan):
    """Half of a paid tier's monthly price, or 0 for anything else."""
    amount = PRICES.get(plan or "", (0, ""))[0]
    return amount * REFERRAL_PERCENT // 100


def ensure_referral_coupon():
    """One 50%-off-first-month coupon, created once and remembered in app_kv."""
    if not configured():
        return None
    try:
        import db
        coupon_id = db.get_kv(_ref_coupon_key())
        if coupon_id:
            return coupon_id
        created = _http("/v1/coupons", {
            "percent_off": str(REFERRAL_PERCENT), "duration": "once",
            "name": REFERRAL_COUPON_NAME})
        if created.get("id"):
            db.set_kv(_ref_coupon_key(), created["id"])
            return created["id"]
    except Exception:
        pass
    return None


def apply_credit(customer_id, amount_cents, description, idempotency_key=None, metadata=None):
    """Negative balance transaction = credit against future invoices. With a
    key, Stripe applies it once however many times it is asked.

    Returns "ok", "refused" (Stripe answered no: nothing was applied), or
    "unknown" (no answer, a timeout or a server error: it may have been
    applied). Only "refused" may be tried again later; a retry after an
    "unknown" can credit twice once the key has expired (2026-09-19 second
    review)."""
    if not (configured() and customer_id):
        return "refused"
    fields = {"amount": str(-abs(int(amount_cents))), "currency": "usd",
              "description": description[:300]}
    for k, v in (metadata or {}).items():
        fields["metadata[%s]" % k] = v
    if idempotency_key:
        fields[IDEMPOTENCY_FIELD] = idempotency_key
    try:
        out = _http("/v1/customers/%s/balance_transactions" % customer_id, fields)
    except urllib.error.HTTPError as e:
        return "refused" if e.code in (400, 402, 404) else "unknown"
    except Exception:
        return "unknown"
    return "ok" if out.get("id") else "unknown"


def credit_customer(customer_id, amount_cents, description, idempotency_key=None):
    return apply_credit(customer_id, amount_cents, description, idempotency_key) == "ok"


def find_credit(customer_id, key, value):
    """Is there a balance transaction on this customer tagged key=value?
    True, False, or None when Stripe could not be asked."""
    if not (configured() and customer_id):
        return None
    try:
        rows = _http_get("/v1/customers/%s/balance_transactions?limit=100"
                         % urllib.parse.quote(customer_id, safe="")).get("data", [])
    except Exception:
        return None
    return any((r.get("metadata") or {}).get(key) == value for r in rows)


def create_checkout_session(user_id, email, plan, base_url, coupon=None, customer_id=None):
    """Hosted subscription checkout for one tier. Returns the session or None.

    Card only, so a checkout never completes unpaid and settles days later.
    An account that already has a Stripe customer checks out as that
    customer, so a returning member is not given a second one."""
    if plan not in PRICES or not configured():
        return None
    cents, name = PRICES[plan]
    fields = {
        "mode": "subscription",
        "client_reference_id": user_id,
        "payment_method_types[0]": "card",
        "success_url": base_url + "/billing?upgraded=1",
        "cancel_url": base_url + "/billing",
        "metadata[plan]": plan,
        "subscription_data[metadata][plan]": plan,
        "subscription_data[metadata][user_id]": user_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": name,
    }
    if customer_id:
        fields["customer"] = customer_id
    else:
        fields["customer_email"] = email
    if coupon:
        fields["discounts[0][coupon]"] = coupon
    try:
        return _http("/v1/checkout/sessions", fields)
    except Exception:
        return None


def customer_exists(customer_id):
    """True, False (Stripe has no such customer in this mode, or it was
    deleted), or None when Stripe could not say. Ids made with the sandbox
    key do not exist under the live key, and an account that checked out
    in the sandbox kept them (2026-09-19 second review)."""
    if not configured() or not customer_id:
        return False
    try:
        cust = _http_get("/v1/customers/" + urllib.parse.quote(customer_id, safe=""))
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:
        return None
    return not cust.get("deleted")


def _plan_products():
    return {_kv(_kv_key("product_" + p)) for p in PRICES} - {""}


def is_plan_subscription(sub):
    """Is this one of the app's membership subscriptions? A fan club or any
    other subscription at $29, $79 or $199 is not a tier (2026-09-19 second
    review: Sync took any of them for one)."""
    if ((sub or {}).get("metadata") or {}).get("plan") in PRICES:
        return True
    products = _plan_products()
    for it in ((sub or {}).get("items") or {}).get("data") or []:
        prod = (it.get("price") or {}).get("product")
        if isinstance(prod, dict):
            prod = prod.get("id")
        if prod and prod in products:
            return True
    return False


def subscription_tier(sub):
    """The tier of one of our subscriptions: the billed price first, the
    metadata only when the price says nothing."""
    tier = plan_for_subscription(sub) or ((sub or {}).get("metadata") or {}).get("plan")
    return tier if tier in PRICES else None


# A subscription in any of these can still bill, so a second must not open.
BILLING_STATUSES = ("active", "trialing", "past_due", "unpaid", "incomplete", "paused")


def ensure_plan_product(plan):
    """The Stripe product for a tier, created once and remembered in app_kv.
    A subscription item's price needs a product id; checkout sessions made
    their products inline, so changing tiers needs one of its own."""
    if plan not in PRICES or not configured():
        return None
    try:
        import db
        key = _kv_key("product_" + plan)
        pid = db.get_kv(key)
        if pid:
            return pid
        created = _http("/v1/products", {"name": PRICES[plan][1]})
        if created.get("id"):
            db.set_kv(key, created["id"])
            return created["id"]
    except Exception:
        pass
    return None


def ensure_plan_price(plan):
    """A reusable monthly Price for a tier, created once and remembered. A
    pending update (an upgrade that waits on payment) accepts a price id;
    Stripe does not list inline price_data among what a pending update may
    carry (2026-09-19 review)."""
    if plan not in PRICES or not configured():
        return None
    try:
        import db
        key = _kv_key("price_" + plan)
        pid = db.get_kv(key)
        if pid:
            return pid
        product = ensure_plan_product(plan)
        if not product:
            return None
        created = _http("/v1/prices", {
            "product": product, "currency": "usd",
            "unit_amount": str(PRICES[plan][0]),
            "recurring[interval]": "month"})
        if created.get("id"):
            db.set_kv(key, created["id"])
            return created["id"]
    except Exception:
        pass
    return None


def get_subscription(subscription_id):
    """The subscription as Stripe holds it now, or None."""
    if not configured() or not subscription_id:
        return None
    try:
        return _http_get("/v1/subscriptions/" + urllib.parse.quote(subscription_id, safe=""))
    except Exception:
        return None


def subscription_state(subscription_id):
    """Like get_subscription, but a subscription Stripe does not have comes
    back as {"id": ..., "status": "gone"} and only a failed read is None, so
    a caller can wait and retry instead of acting on a guess."""
    if not configured() or not subscription_id:
        return None
    try:
        return _http_get("/v1/subscriptions/" + urllib.parse.quote(subscription_id, safe=""))
    except urllib.error.HTTPError as e:
        return {"id": subscription_id, "status": "gone"} if e.code == 404 else None
    except Exception:
        return None


def invoice_subscription_id(invoice):
    """The subscription an invoice bills. Newer API versions moved it under
    parent.subscription_details."""
    inv = invoice or {}
    return (inv.get("subscription")
            or (((inv.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
            or "")


def change_subscription_plan(subscription_id, plan):
    """Move an existing subscription to another tier, instead of opening a
    second subscription beside it (found by the 2026-09-18 launch check).

    Returns {"result": ...}:
      changed  moved now (a downgrade, credited to the next bill; or an
               upgrade whose difference was paid)
      pending  an upgrade waiting on its payment; Stripe applies it once the
               invoice is paid, and customer.subscription.updated follows
      same     Stripe already bills this tier
      gone     the subscription no longer exists or has ended: only this may
               lead to a fresh checkout
      error    anything else (Stripe refused, timed out, or the subscription
               has an unpaid bill): nothing new may be started, because the
               old subscription may still be billing (2026-09-19 review)
    """
    if plan not in PRICES or not configured() or not subscription_id:
        return {"result": "error"}
    sid = urllib.parse.quote(subscription_id, safe="")
    try:
        sub = _http_get("/v1/subscriptions/" + sid)
    except urllib.error.HTTPError as e:
        return {"result": "gone" if e.code == 404 else "error"}
    except Exception:
        return {"result": "error"}
    status = sub.get("status") or ""
    if status in ("canceled", "incomplete_expired"):
        return {"result": "gone", "status": status}
    if status not in ("active", "trialing", "past_due"):
        return {"result": "error", "status": status}
    current = plan_for_subscription(sub)
    if current == plan:
        return {"result": "same", "status": status}
    items = (sub.get("items") or {}).get("data") or []
    price = ensure_plan_price(plan)
    if not items or not price:
        return {"result": "error", "status": status}
    upgrade = PRICES[plan][0] > PRICES.get(current or "", (0, ""))[0]
    fields = {
        "items[0][id]": items[0]["id"],
        "items[0][price]": price,
        "proration_behavior": "always_invoice" if upgrade else "create_prorations",
    }
    if upgrade:
        fields["payment_behavior"] = "pending_if_incomplete"
    try:
        out = _http("/v1/subscriptions/" + sid, fields)
    except Exception:
        return {"result": "error", "status": status}
    if not out.get("id"):
        return {"result": "error", "status": status}
    if out.get("pending_update"):
        return {"result": "pending", "status": out.get("status")}
    try:
        _http("/v1/subscriptions/" + sid, {"metadata[plan]": plan})
    except Exception:
        pass
    return {"result": "changed", "status": out.get("status")}


def active_subscription_for_customer(customer_id):
    """A membership subscription on this customer that can still bill, as
    {subscription_id, plan, status}; None when there is none; or
    {"error": True} when Stripe could not be asked. Used before a new
    checkout, so a member who already pays, or owes, is never sold a second
    subscription. Past due and unpaid count: listing only active ones hid
    them (2026-09-19 second review)."""
    if not configured() or not customer_id:
        return None
    try:
        subs = _http_get("/v1/subscriptions?" + urllib.parse.urlencode(
            {"customer": customer_id, "status": "all", "limit": 20})).get("data", [])
    except Exception:
        return {"error": True}
    for sub in subs:
        tier = subscription_tier(sub)
        if sub.get("status") in BILLING_STATUSES and tier and is_plan_subscription(sub):
            return {"subscription_id": sub["id"], "plan": tier, "status": sub.get("status")}
    return None


def close_open_checkout(session_id):
    """Make sure the checkout this account opened earlier cannot become a
    second subscription. Returns (state, session):
      closed    it expired, or is expired now
      complete  it was paid: the caller claims it instead of opening another
      error     Stripe could not say: nothing new may open
    It used to try the expire and read "complete" out of Stripe's error
    text, and any other text let a second checkout open (2026-09-19 second
    review)."""
    if not configured() or not session_id:
        return "error", None
    path = "/v1/checkout/sessions/" + urllib.parse.quote(session_id, safe="")
    for attempt in (1, 2):
        try:
            sess = _http_get(path)
        except urllib.error.HTTPError as e:
            return ("closed" if e.code == 404 else "error"), None
        except Exception:
            return "error", None
        status = sess.get("status")
        if status == "complete":
            return "complete", sess
        if status == "expired":
            return "closed", sess
        if status != "open" or attempt == 2:
            return "error", sess
        try:
            _http(path + "/expire", {})
            return "closed", sess
        except Exception:
            continue            # paid in the meantime? read it again
    return "error", None


def _http_get(path):
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"]})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def active_subscription_for_email(email, user_id=None):
    """Look up a membership subscription by customer email, the webhook-less
    fallback so a completed checkout can always be claimed in-app.
    Returns {customer_id, subscription_id, plan} or None.

    Only the app's own membership subscriptions count (a fan club at the
    same price is not a tier), and one made for another account is not this
    one's (2026-09-19 second review). Past due still holds the plan while
    Stripe retries, so it is found as well."""
    if not configured() or not email:
        return None
    try:
        customers = _http_get("/v1/customers?" + urllib.parse.urlencode(
            {"email": email, "limit": 5})).get("data", [])
        for cust in customers:
            subs = _http_get("/v1/subscriptions?" + urllib.parse.urlencode(
                {"customer": cust["id"], "status": "all", "limit": 20})).get("data", [])
            for sub in subs:
                if sub.get("status") not in ("active", "trialing", "past_due"):
                    continue
                if not is_plan_subscription(sub):
                    continue
                owner = (sub.get("metadata") or {}).get("user_id")
                if user_id and owner and owner != user_id:
                    continue
                tier = subscription_tier(sub)
                if tier:
                    return {"customer_id": cust["id"],
                            "subscription_id": sub["id"], "plan": tier}
        return None
    except Exception:
        return None


def create_club_checkout(artist_id, club_name, price_cents, member_email,
                         slug, base_url):
    """Fan-club membership checkout: recurring monthly, tagged so the
    webhook can route it to the right artist's roster."""
    if not configured():
        return None
    fields = {
        "mode": "subscription",
        "customer_email": member_email,
        "success_url": base_url + "/club/" + slug
                       + "?joined=1&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": base_url + "/club/" + slug,
        "metadata[kind]": "fan_club",
        "metadata[artist_id]": artist_id,
        "metadata[member_email]": member_email,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(int(price_cents)),
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": (club_name or "Fan Club")[:100],
    }
    try:
        return _http("/v1/checkout/sessions", fields)
    except Exception:
        return None


def create_vip_checkout(tour_id, show_id, offer_id, offer_name, unit_cents, quantity,
                        email, name, token, base_url, currency="usd"):
    """A VIP package for one date: one-time payment, tagged so the webhook
    and the success redirect both know which sale it is."""
    if not configured():
        return None
    fields = {
        "mode": "payment",
        # Cards settle at once. A delayed method (bank debit) would complete
        # the session unpaid and settle days later; the app handles that
        # event too, but the fan should not leave the page unsure.
        "payment_method_types[0]": "card",
        "customer_email": email,
        "success_url": base_url + "/vip/" + token + "?paid=1&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": base_url + "/vip/" + token,
        "metadata[kind]": "tour_vip",
        "metadata[tour_id]": tour_id,
        "metadata[show_id]": show_id,
        "metadata[offer_id]": offer_id,
        "metadata[email]": email,
        "metadata[name]": (name or "")[:120],
        "metadata[quantity]": str(int(quantity)),
        "line_items[0][quantity]": str(int(quantity)),
        "line_items[0][price_data][currency]": (currency or "usd").lower(),
        "line_items[0][price_data][unit_amount]": str(int(unit_cents)),
        "line_items[0][price_data][product_data][name]": (offer_name or "VIP package")[:100],
    }
    try:
        return _http("/v1/checkout/sessions", fields)
    except Exception:
        return None


def create_credit_pack_checkout(user_id, email, pack_key, credits, cents, name, base_url):
    """A one-time purchase of credits, tagged so the webhook and the success
    redirect both know whose wallet it fills and can only fill it once."""
    if not configured():
        return None
    fields = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "client_reference_id": user_id,
        "customer_email": email,
        "success_url": base_url + "/billing?credits=1&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": base_url + "/billing#credits",
        "metadata[kind]": "credit_pack",
        "metadata[pack]": pack_key,
        "metadata[credits]": str(int(credits)),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(int(cents)),
        "line_items[0][price_data][product_data][name]": "Street Banker " + name,
    }
    try:
        return _http("/v1/checkout/sessions", fields)
    except Exception:
        return None


def create_release_ready_checkout(user_id, email, job_id, kind, cents, title, base_url,
                                  cancel_path="/creative-studio/release-ready",
                                  expires_at=None, window=None):
    """One full master from Release-Ready, paid once (owner, 2026-09-19:
    $6.99 by default, set in Settings). Tagged so the webhook and the
    success redirect both know which job it pays for. expires_at (a Unix
    time) closes the checkout long before RoEx's link to the audio runs
    out; the same job at the same price in the same window reuses one
    session (the idempotency key), so a double click cannot open two."""
    if not configured():
        return None
    song = (title or "your song").strip()[:70] or "your song"
    name = ("Vocal and beat master: " if kind == "recombine" else "Master: ") + song
    fields = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "client_reference_id": user_id,
        "success_url": base_url + "/creative-studio/release-ready/jobs/" + job_id
                       + "/paid?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": base_url + cancel_path,
        "metadata[kind]": "release_ready",
        "metadata[job_id]": job_id,
        "metadata[product]": "recombine" if kind == "recombine" else "master",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(int(cents)),
        "line_items[0][price_data][product_data][name]": name[:100],
        IDEMPOTENCY_FIELD: "rr-checkout:%s:%d" % (job_id, int(cents))
                           + (":%d" % int(window) if window is not None else ""),
    }
    if expires_at:
        fields["expires_at"] = str(int(expires_at))
    if email:
        fields["customer_email"] = email
    try:
        return _http("/v1/checkout/sessions", fields)
    except Exception:
        return None


def get_checkout_session(session_id):
    """Retrieve a checkout session — lets the success redirect grant fan-club
    access instantly instead of waiting on the webhook."""
    if not configured() or not session_id:
        return None
    try:
        return _http_get("/v1/checkout/sessions/"
                         + urllib.parse.quote(session_id, safe=""))
    except Exception:
        return None


def get_charge(charge_id):
    """A charge as Stripe holds it, or None. A dispute names its charge,
    not the customer."""
    if not configured() or not charge_id:
        return {}
    try:
        return _http_get("/v1/charges/" + urllib.parse.quote(charge_id, safe=""))
    except Exception:
        return None


def create_portal_session(customer_id, return_url):
    """Stripe-hosted billing portal (cancel, card update, invoices)."""
    try:
        return _http("/v1/billing_portal/sessions",
                     {"customer": customer_id, "return_url": return_url})
    except Exception:
        return None


def _http_delete(path):
    req = urllib.request.Request(
        "https://api.stripe.com" + path, method="DELETE",
        headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"]})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def setup_webhook_endpoint(base_url):
    """Owner one-click: create our webhook endpoint on the connected Stripe
    account and keep the signing secret in app_kv on the server — it never
    travels through a dashboard copy-paste. Returns summary dict or None."""
    if not configured():
        return None
    url = base_url + "/webhooks/stripe"
    try:
        import db
        existing = _http_get("/v1/webhook_endpoints?limit=100").get("data", [])
        ours = [ep for ep in existing if ep.get("url") == url]
        if len(ours) == 1 and _stored_webhook_secret():
            # The endpoint this app made in this mode, whose secret it
            # holds: change its event list in place, and switch it back on
            # if Stripe turned it off after failed deliveries. Deleting and
            # re-creating it drops the retries Stripe has queued.
            fields = {"disabled": "false"}
            for i, ev in enumerate(WEBHOOK_EVENTS):
                fields["enabled_events[%d]" % i] = ev
            updated = _http("/v1/webhook_endpoints/" + ours[0]["id"], fields)
            if updated.get("id"):
                db.set_kv(_kv_key("webhook_events"), ",".join(WEBHOOK_EVENTS))
                return {"id": updated["id"], "url": url, "events": len(WEBHOOK_EVENTS)}
        for ep in existing:
            # A secret is only revealed at creation, so stale endpoints for
            # our URL are unverifiable — replace instead of accumulating.
            if ep.get("url") == url:
                _http_delete("/v1/webhook_endpoints/" + ep["id"])
        fields = {"url": url, "description": "Street Banker (auto-configured in-app)"}
        for i, ev in enumerate(WEBHOOK_EVENTS):
            fields["enabled_events[%d]" % i] = ev
        created = _http("/v1/webhook_endpoints", fields)
        if not (created.get("id") and created.get("secret")):
            return None
        import db
        db.set_kv(_kv_key("webhook_secret"), created["secret"])
        db.set_kv(_kv_key("webhook_events"), ",".join(WEBHOOK_EVENTS))
        # The secret from before it was kept per mode belongs to an endpoint
        # this one replaces (or to the sandbox): it stops verifying now.
        db.set_kv(_LEGACY_SECRET_KEY, "")
        db.set_kv(_LEGACY_EVENTS_KEY, "")
        return {"id": created["id"], "url": url, "events": len(WEBHOOK_EVENTS)}
    except Exception:
        return None


def verify_webhook(sig_header, body, tolerance=600):
    """Stripe-Signature check: HMAC-SHA256 of '{t}.{body}' with the secret.
    Accepts the env secret or the one saved by in-app webhook setup."""
    secrets = [s for s in (os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
                           _stored_webhook_secret(), _legacy_webhook_secret()) if s]
    if not (secrets and sig_header):
        return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    t = parts.get("t", "")
    if not t.isdigit() or abs(time.time() - int(t)) > tolerance:
        return False
    payload = body.decode("utf-8") if isinstance(body, bytes) else body
    sigs = [p.split("=", 1)[1] for p in sig_header.split(",")
            if p.startswith("v1=")]
    for secret in secrets:
        expected = hmac.new(secret.encode(), ("%s.%s" % (t, payload)).encode(),
                            hashlib.sha256).hexdigest()
        if any(hmac.compare_digest(expected, s) for s in sigs):
            return True
    return False
