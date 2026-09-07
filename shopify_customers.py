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
import time
import urllib.parse
import urllib.request

import db as store

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


# Shopify's Dev Dashboard (2025) shows no token in any UI: the app holds a
# Client ID and a Client Secret and exchanges them for a 24-hour Admin
# token (the client credentials grant). SHOPIFY_ADMIN_TOKEN, the legacy
# admin-created token, still wins when it is set.
GRANT_KEY = "shopify:admin-token"
GRANT_ERROR_KEY = "shopify:admin-token-error"
GRANT_MARGIN = 5 * 60          # mint a fresh one this long before expiry


def legacy_token():
    return (os.environ.get("SHOPIFY_ADMIN_TOKEN") or "").strip()


def client_id():
    return (os.environ.get("SHOPIFY_CLIENT_ID") or "").strip()


def client_secret():
    return (os.environ.get("SHOPIFY_CLIENT_SECRET") or "").strip()


def uses_grant():
    return bool(client_id() and client_secret()) and not legacy_token()


def _post_form(url, fields):
    """Form-encoded POST for the token grant - tests monkeypatch this.
    Returns (status, parsed body); the body is {} when it is not JSON."""
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode("utf-8"),
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "User-Agent": "StreetBanker/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"network": str(e)}


def granted_token(post_form=None, now=None):
    """The 24-hour Admin token from the client credentials grant, kept in
    app_kv so a deploy or a second worker does not mint another. '' when
    the grant is refused; the reason is kept for status()."""
    if not (domain() and client_id() and client_secret()):
        return ""
    now = now if now is not None else time.time()
    try:
        kept = json.loads(store.get_kv(GRANT_KEY) or "{}")
    except ValueError:
        kept = {}
    if kept.get("token") and kept.get("client_id") == client_id() and now < float(kept.get("expires_at") or 0) - GRANT_MARGIN:
        return kept["token"]
    status_code, answer = (post_form or _post_form)(
        "https://%s/admin/oauth/access_token" % domain(),
        {"grant_type": "client_credentials", "client_id": client_id(), "client_secret": client_secret()})
    token_value = (answer or {}).get("access_token") if isinstance(answer, dict) else None
    if status_code != 200 or not token_value:
        why = ""
        if isinstance(answer, dict):
            why = answer.get("error_description") or answer.get("error") or answer.get("network") or ""
        store.set_kv(GRANT_ERROR_KEY, json.dumps({"status": status_code, "why": why[:200], "at": now}))
        return ""
    store.set_kv(GRANT_KEY, json.dumps({"token": token_value, "client_id": client_id(),
                                        "expires_at": now + float(answer.get("expires_in") or 86399),
                                        "scope": answer.get("scope") or ""}))
    store.set_kv(GRANT_ERROR_KEY, "")
    return token_value


def grant_error():
    try:
        return json.loads(store.get_kv(GRANT_ERROR_KEY) or "null") or None
    except ValueError:
        return None


def mint_storefront_token(mutation, title, post=None):
    """Ask the Admin API, with the granted token, to create a Storefront
    token for the Buy Buttons. (token, reason, http status); the token is
    '' when Shopify refuses - usually the unauthenticated_* scopes."""
    admin = token()
    if not (domain() and admin):
        return "", "no Admin token", 0
    url = "https://%s/admin/api/%s/graphql.json" % (domain(), API_VERSION)
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": admin,
               "User-Agent": "StreetBanker/1.0"}
    try:
        answer = (post or _post)(url, headers, {"query": mutation, "variables": {"input": {"title": title}}})
    except ShopifyError as e:
        return "", str(e), 0
    if isinstance(answer, tuple):            # a buy-side fake answers (status, body)
        status, answer = answer
    else:
        status = 200
    payload = ((answer or {}).get("data") or {}).get("storefrontAccessTokenCreate") or {} if isinstance(answer, dict) else {}
    made = (payload.get("storefrontAccessToken") or {}).get("accessToken") or ""
    if status == 200 and made:
        return made, "", 200
    why = ""
    if isinstance(answer, dict):
        errs = payload.get("userErrors") or answer.get("errors") or []
        if errs:
            why = (errs[0] or {}).get("message") or ""
        why = why or answer.get("network") or ""
    return "", why, status


def token():
    return legacy_token() or (granted_token() if uses_grant() else "")


def configured():
    return bool(domain() and (legacy_token() or (client_id() and client_secret())))


def token_looks_right():
    """A legacy Admin API access token begins with shpat_; the API key and
    the API secret from that old screen do not, and both earn a 401 that
    says nothing about which was pasted - so the page says it first. A
    granted token is right by construction."""
    if uses_grant():
        return True
    return legacy_token().startswith("shpat_")


def status():
    if configured() and not token_looks_right():
        return {"on": True, "headline": "Shopify is connected, but the token does not look right",
                "detail": "SHOPIFY_ADMIN_TOKEN should be the Admin API access token, which begins "
                          "with shpat_. The API key and the API secret key from the same screen "
                          "do not work here."}
    if configured() and uses_grant():
        err = grant_error() if not granted_token() else None
        if err:
            return {"on": True, "headline": "Shopify refused the app's credentials",
                    "detail": "The client credentials grant answered %s%s. It works only when the app "
                              "and the store sit in the same Shopify organization in the Dev Dashboard, "
                              "the app is installed on the store, and its released version carries "
                              "read_customers." % (err.get("status") or "nothing", (": " + err["why"]) if err.get("why") else "")}
        return {"on": True, "headline": "Shopify is connected",
                "detail": "Through the app's Client ID and secret; a 24-hour token is minted as needed. "
                          "Imports the customers whose email-marketing consent Shopify records as "
                          "subscribed. A purchase alone is not permission to mail; those are skipped "
                          "and counted."}
    if configured():
        return {"on": True, "headline": "Shopify is connected",
                "detail": "Imports the customers whose email-marketing consent Shopify records as "
                          "subscribed. A purchase alone is not permission to mail; those are skipped "
                          "and counted."}
    return {"on": False, "headline": "Shopify is not connected",
            "detail": "SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET from the app's settings in the "
                      "Dev Dashboard (or a legacy SHOPIFY_ADMIN_TOKEN) beside SHOPIFY_DOMAIN turn this on."}


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
