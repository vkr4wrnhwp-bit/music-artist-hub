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
                  "invoice.payment_failed")


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


def _stored_webhook_secret():
    """Signing secret saved by the in-app webhook setup. Lazy import keeps
    this module import-safe before the database exists."""
    try:
        import db
        return db.get_kv("stripe_webhook_secret") or ""
    except Exception:
        return ""


def webhook_configured():
    return bool(os.environ.get("STRIPE_WEBHOOK_SECRET") or _stored_webhook_secret())


def webhook_events_current():
    """Was the stored endpoint set up with today's event list? An endpoint
    made before a new event was added never receives it, so the owner's
    billing card offers to update it. An endpoint set up by hand in the
    dashboard (the env secret) is taken to be the owner's own business."""
    if os.environ.get("STRIPE_WEBHOOK_SECRET"):
        return True
    try:
        import db
        return (db.get_kv("stripe_webhook_events") or "") == ",".join(WEBHOOK_EVENTS)
    except Exception:
        return True


def _http(path, fields):
    """Form-encoded POST to the Stripe API — tests monkeypatch this."""
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"],
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# The referral offer (owner, 2026-09-18, "yes"): the new artist gets 50% off
# their first month; the referrer gets 50% off their next month once the new
# artist has paid. It was 100% off, which paid the referrer on a $0 checkout.
REFERRAL_PERCENT = 50
_REF_COUPON_KEY = "stripe_ref_coupon_50"


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
        coupon_id = db.get_kv(_REF_COUPON_KEY)
        if coupon_id:
            return coupon_id
        created = _http("/v1/coupons", {
            "percent_off": str(REFERRAL_PERCENT), "duration": "once",
            "name": "Street Banker referral - 50% off your first month"})
        if created.get("id"):
            db.set_kv(_REF_COUPON_KEY, created["id"])
            return created["id"]
    except Exception:
        pass
    return None


def credit_customer(customer_id, amount_cents, description):
    """Negative balance transaction = credit against future invoices."""
    if not (configured() and customer_id):
        return False
    try:
        out = _http("/v1/customers/%s/balance_transactions" % customer_id,
                    {"amount": str(-abs(int(amount_cents))), "currency": "usd",
                     "description": description[:300]})
        return bool(out.get("id"))
    except Exception:
        return False


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


def ensure_plan_product(plan):
    """The Stripe product for a tier, created once and remembered in app_kv.
    A subscription item's price needs a product id; checkout sessions made
    their products inline, so changing tiers needs one of its own."""
    if plan not in PRICES or not configured():
        return None
    try:
        import db
        key = "stripe_product_" + plan
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


def change_subscription_plan(subscription_id, plan, upgrade):
    """Move an existing subscription to another tier, instead of opening a
    second subscription beside it (found by the 2026-09-18 launch check: a
    plan change used to start a new checkout and the old subscription kept
    billing, unseen by the app).

    An upgrade is invoiced at once for the difference, and with
    pending_if_incomplete Stripe applies it only once that is paid. A
    downgrade takes effect now, with the unused part credited to the next
    invoice. Returns {"ok", "pending", "status"} or None when the
    subscription cannot be changed (gone, cancelled, or Stripe refused)."""
    if plan not in PRICES or not configured() or not subscription_id:
        return None
    sid = urllib.parse.quote(subscription_id, safe="")
    try:
        sub = _http_get("/v1/subscriptions/" + sid)
        if sub.get("status") not in ("active", "trialing", "past_due"):
            return None
        items = (sub.get("items") or {}).get("data") or []
        product = ensure_plan_product(plan)
        if not items or not product:
            return None
        fields = {
            "items[0][id]": items[0]["id"],
            "items[0][price_data][currency]": "usd",
            "items[0][price_data][product]": product,
            "items[0][price_data][unit_amount]": str(PRICES[plan][0]),
            "items[0][price_data][recurring][interval]": "month",
            "proration_behavior": "always_invoice" if upgrade else "create_prorations",
        }
        if upgrade:
            fields["payment_behavior"] = "pending_if_incomplete"
        out = _http("/v1/subscriptions/" + sid, fields)
        if not out.get("id"):
            return None
        pending = bool(out.get("pending_update"))
        if not pending:
            # Only a subset of fields may ride with a pending update, so the
            # tier's name goes on in its own call once the change has landed.
            try:
                _http("/v1/subscriptions/" + sid, {"metadata[plan]": plan})
            except Exception:
                pass
        return {"ok": True, "pending": pending, "status": out.get("status")}
    except Exception:
        return None


def _http_get(path):
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"]})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def active_subscription_for_email(email):
    """Look up an active subscription by customer email — the webhook-less
    fallback so a completed checkout can always be claimed in-app.
    Returns {customer_id, subscription_id, plan} or None."""
    if not configured() or not email:
        return None
    try:
        customers = _http_get("/v1/customers?" + urllib.parse.urlencode(
            {"email": email, "limit": 5})).get("data", [])
        for cust in customers:
            subs = _http_get("/v1/subscriptions?" + urllib.parse.urlencode(
                {"customer": cust["id"], "status": "active", "limit": 5})).get("data", [])
            for sub in subs:
                plan = (sub.get("metadata") or {}).get("plan")
                if plan not in PRICES:
                    # Fall back to matching the product name we created.
                    items = (sub.get("items") or {}).get("data") or []
                    for it in items:
                        nickname = ((it.get("price") or {}).get("nickname") or "")
                        for key, (_, name) in PRICES.items():
                            if name in nickname:
                                plan = key
                    if plan not in PRICES:
                        for key in PRICES:
                            if (sub.get("description") or "").lower().find(key) >= 0:
                                plan = key
                if plan in PRICES:
                    return {"customer_id": cust["id"],
                            "subscription_id": sub["id"], "plan": plan}
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
        existing = _http_get("/v1/webhook_endpoints?limit=100").get("data", [])
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
        db.set_kv("stripe_webhook_secret", created["secret"])
        db.set_kv("stripe_webhook_events", ",".join(WEBHOOK_EVENTS))
        return {"id": created["id"], "url": url, "events": len(WEBHOOK_EVENTS)}
    except Exception:
        return None


def verify_webhook(sig_header, body, tolerance=600):
    """Stripe-Signature check: HMAC-SHA256 of '{t}.{body}' with the secret.
    Accepts the env secret or the one saved by in-app webhook setup."""
    secrets = [s for s in (os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
                           _stored_webhook_secret()) if s]
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
