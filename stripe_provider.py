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

_TIMEOUT = 20

# Tier -> (monthly cents, display name). Keep in sync with plans.PLANS.
PRICES = {
    "artist": (900, "Street Banker Artist"),
    "pro": (2900, "Street Banker Pro"),
    "label": (9900, "Street Banker Label"),
}


def configured():
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def webhook_configured():
    return bool(os.environ.get("STRIPE_WEBHOOK_SECRET"))


def _http(path, fields):
    """Form-encoded POST to the Stripe API — tests monkeypatch this."""
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"],
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_checkout_session(user_id, email, plan, base_url):
    """Hosted subscription checkout for one tier. Returns the session or None."""
    if plan not in PRICES or not configured():
        return None
    cents, name = PRICES[plan]
    fields = {
        "mode": "subscription",
        "client_reference_id": user_id,
        "customer_email": email,
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
    try:
        return _http("/v1/checkout/sessions", fields)
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
        "success_url": base_url + "/club/" + slug + "?joined=1",
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


def create_portal_session(customer_id, return_url):
    """Stripe-hosted billing portal (cancel, card update, invoices)."""
    try:
        return _http("/v1/billing_portal/sessions",
                     {"customer": customer_id, "return_url": return_url})
    except Exception:
        return None


def verify_webhook(sig_header, body, tolerance=600):
    """Stripe-Signature check: HMAC-SHA256 of '{t}.{body}' with the secret."""
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not (secret and sig_header):
        return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    t = parts.get("t", "")
    if not t.isdigit() or abs(time.time() - int(t)) > tolerance:
        return False
    payload = body.decode("utf-8") if isinstance(body, bytes) else body
    expected = hmac.new(secret.encode(), ("%s.%s" % (t, payload)).encode(),
                        hashlib.sha256).hexdigest()
    sigs = [p.split("=", 1)[1] for p in sig_header.split(",")
            if p.startswith("v1=")]
    return any(hmac.compare_digest(expected, s) for s in sigs)
