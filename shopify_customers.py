"""Shopify customers into the Fan CRM - the ones who said yes to email.

The store is the commerce engine and already holds the people who bought
something. This reads them through the Admin API and files, into the Fan
CRM, only the customers whose email-marketing consent Shopify records as
subscribed: a purchase is not permission to mail. Everyone else is
counted and skipped, and the page says how many.

    SHOPIFY_DOMAIN        your-store.myshopify.com (shared with the Buy Buttons)
    SHOPIFY_ADMIN_TOKEN   an Admin API access token with read_customers

It runs when the artist presses the button. Nothing here writes to
Shopify.
"""
import json
import os
import urllib.request

API_VERSION = "2025-07"
PAGE = 250
MAX_PAGES = 20          # 5,000 customers a run; the next run continues from the cursor

QUERY = """query($after: String) {
  customers(first: %d, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id firstName lastName numberOfOrders createdAt tags
      amountSpent { amount currencyCode }
      defaultEmailAddress { emailAddress marketingState marketingUpdatedAt }
    } }
  }
}""" % PAGE


class ShopifyError(Exception):
    pass


def domain():
    return (os.environ.get("SHOPIFY_DOMAIN") or "").strip()


def token():
    return (os.environ.get("SHOPIFY_ADMIN_TOKEN") or "").strip()


def configured():
    return bool(domain() and token())


def token_looks_right():
    """Admin API access tokens begin with shpat_. The API key and the API
    secret from the same screen do not, and both earn a 401 that says
    nothing about which was pasted - so the page says it first."""
    return token().startswith("shpat_")


def status():
    if configured() and not token_looks_right():
        return {"on": True, "headline": "Shopify is connected, but the token does not look right",
                "detail": "SHOPIFY_ADMIN_TOKEN should be the Admin API access token, which begins "
                          "with shpat_. The API key and the API secret key from the same screen "
                          "do not work here."}
    if configured():
        return {"on": True, "headline": "Shopify is connected",
                "detail": "Imports the customers whose email-marketing consent Shopify records as "
                          "subscribed. A purchase alone is not permission to mail; those are skipped "
                          "and counted."}
    return {"on": False, "headline": "Shopify is not connected",
            "detail": "SHOPIFY_ADMIN_TOKEN (an Admin API token with read_customers) beside "
                      "SHOPIFY_DOMAIN turns this on."}


def _post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ShopifyError("Shopify %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:200]))
    except Exception as e:
        raise ShopifyError("Shopify: %s" % e)


def _customer(node):
    # defaultEmailAddress is the current shape; the older email +
    # emailMarketingConsent pair is read when a store still answers with it.
    addr = node.get("defaultEmailAddress") or {}
    consent = node.get("emailMarketingConsent") or {}
    email = addr.get("emailAddress") or node.get("email") or ""
    state = addr.get("marketingState") or consent.get("marketingState") or ""
    updated = addr.get("marketingUpdatedAt") or consent.get("consentUpdatedAt") or ""
    spent = node.get("amountSpent") or {}
    try:
        orders = int(node.get("numberOfOrders") or 0)
    except (TypeError, ValueError):
        orders = 0
    name = " ".join(x for x in (node.get("firstName"), node.get("lastName")) if x).strip()
    return {"email": email.strip().lower(), "name": name, "orders": orders,
            "spent": spent.get("amount") or "0", "currency": spent.get("currencyCode") or "",
            "tags": list(node.get("tags") or []), "created": (node.get("createdAt") or "")[:10],
            "subscribed": state.upper() == "SUBSCRIBED",
            "consent_updated": updated[:10]}


def fetch_customers(post=None, after=None):
    """Every customer, normalised; (customers, next_cursor). The cursor is
    None when the store is read to the end, else where the cap stopped."""
    if not configured():
        raise ShopifyError("Shopify is not configured")
    url = "https://%s/admin/api/%s/graphql.json" % (domain(), API_VERSION)
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token(),
               "User-Agent": "StreetBanker/1.0"}
    send = post or _post
    out, cursor, pages = [], after, 0
    while pages < MAX_PAGES:
        answer = send(url, headers, {"query": QUERY, "variables": {"after": cursor}}) or {}
        if answer.get("errors"):
            raise ShopifyError("Shopify: %s" % (answer["errors"][0].get("message") or "query refused"))
        block = ((answer.get("data") or {}).get("customers") or {})
        for edge in block.get("edges") or []:
            out.append(_customer(edge.get("node") or {}))
        pages += 1
        info = block.get("pageInfo") or {}
        cursor = info.get("endCursor")
        if not info.get("hasNextPage"):
            return out, None
    return out, cursor


def import_fans(user_id, customers):
    """File the subscribed ones. Returns what happened, in counts."""
    import links_store as mls
    summary = {"fetched": len(customers), "imported": 0, "new": 0, "updated": 0,
               "skipped_unsubscribed": 0, "skipped_no_email": 0}
    for c in customers:
        if not c["email"] or "@" not in c["email"]:
            summary["skipped_no_email"] += 1
            continue
        if not c["subscribed"]:
            summary["skipped_unsubscribed"] += 1
            continue
        existed = mls.fan_by_email(user_id, c["email"]) is not None
        fan_id = mls.upsert_fan(user_id, c["email"], None, c["name"])
        tags = ["shopify"] + (["customer"] if c["orders"] > 0 else [])
        mls.add_fan_tags(fan_id, tags)
        if not mls.find_consent(fan_id, "shopify_email_marketing"):
            mls.add_consent(fan_id, None, "shopify_email_marketing",
                            "Subscribed to email marketing on Shopify"
                            + (" (consent updated %s)" % c["consent_updated"] if c["consent_updated"] else ""))
        summary["imported"] += 1
        summary["updated" if existed else "new"] += 1
    return summary
