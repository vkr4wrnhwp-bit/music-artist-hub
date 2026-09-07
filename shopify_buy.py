"""Shopify Buy Buttons — the store's checkout, inside the app.

The store at artiswarrecords.com is the ecosystem's real commerce
engine, and the app has only ever linked out to it. A link is a
handoff: the fan leaves, the cart is somewhere else, and whatever
brought them here does not follow them. Buy Buttons put the same
checkout on the page they are already on. No payment code is added on
this side and no card data touches this server - the embed is Shopify's
own SDK talking to Shopify.

Env-gated like every other provider here:

    SHOPIFY_DOMAIN           your-store.myshopify.com
    SHOPIFY_STOREFRONT_TOKEN Storefront API access token (public scope)
    SHOPIFY_COLLECTION_ID    numeric id of the collection to show

Without all three, `configured()` is False and the page keeps the
outbound link. It does not render an empty widget, a spinner, or a
"coming soon" - an unconfigured integration should look like the honest
link it still is, not like a broken store.

The token is a *Storefront* token, which is designed to ship to
browsers: it can read published products and create checkouts, and
nothing else. The admin API key must never appear here.
"""

import hashlib
import json
import os
import urllib.request

import db as store

API_VERSION = "2025-07"
CHECK_TTL = 10 * 60
# Validated against Shopify's Storefront schema (2026-09-06).
CHECK_QUERY = """query($id: ID!) {
  shop { name primaryDomain { host } }
  collection(id: $id) { title handle products(first: 1) { edges { node { title } } } }
}"""


def domain():
    return (os.environ.get("SHOPIFY_DOMAIN") or "").strip()


def token():
    return (os.environ.get("SHOPIFY_STOREFRONT_TOKEN") or "").strip()


def collection_id():
    return (os.environ.get("SHOPIFY_COLLECTION_ID") or "").strip()


def configured():
    return bool(domain() and token() and collection_id())


def context():
    """What the template needs, and a reason when it needs nothing."""
    if configured():
        return {"configured": True, "domain": domain(), "token": token(),
                "collection_id": collection_id(), "reason": ""}
    missing = [name for name, value in (
        ("SHOPIFY_DOMAIN", domain()),
        ("SHOPIFY_STOREFRONT_TOKEN", token()),
        ("SHOPIFY_COLLECTION_ID", collection_id())) if not value]
    return {"configured": False, "domain": "", "token": "",
            "collection_id": "",
            "reason": "Set %s to embed the store." % ", ".join(missing)}


def _post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"network": str(e)}


def check(post=None, fresh=False):
    """Ask Shopify whether the saved Storefront token and collection work,
    with the same call the embed makes. Cached ten minutes, keyed on the
    values, so a fix shows the next time the owner looks. The owner sees
    this; nobody else does. Returns None when nothing is configured."""
    if not configured():
        return None
    key = "shopify:storefront-check:" + hashlib.sha1(
        ("%s|%s|%s" % (domain(), token(), collection_id())).encode("utf-8")).hexdigest()[:12]
    if not fresh:
        cached = store.cache_get(key, CHECK_TTL)
        if cached is not None:
            return cached
    url = "https://%s/api/%s/graphql.json" % (domain(), API_VERSION)
    headers = {"Content-Type": "application/json", "X-Shopify-Storefront-Access-Token": token(),
               "User-Agent": "StreetBanker/1.0"}
    gid = "gid://shopify/Collection/%s" % collection_id()
    status, answer = (post or _post)(url, headers, {"query": CHECK_QUERY, "variables": {"id": gid}})
    out = {"ok": False, "shop": "", "collection": "", "has_products": False, "error": ""}
    if status == 401:
        out["error"] = "Shopify rejected the Storefront token (401). It must be the Storefront API access token, not the Admin one."
    elif status == 0:
        out["error"] = "Shopify could not be reached: %s" % (answer.get("network") or "no answer")
    elif status != 200 or not isinstance(answer, dict):
        out["error"] = "Shopify answered %s." % status
    elif answer.get("errors"):
        out["error"] = "Shopify: %s" % ((answer["errors"][0] or {}).get("message") or "query refused")
    else:
        data = answer.get("data") or {}
        shop, coll = data.get("shop") or {}, data.get("collection")
        out["shop"] = shop.get("name") or ""
        if coll is None:
            out["error"] = ("The token works, but no collection has the id %s on this store, or it is not published to the sales channel."
                            % collection_id())
        else:
            out["collection"] = coll.get("title") or coll.get("handle") or ""
            out["has_products"] = bool((coll.get("products") or {}).get("edges"))
            out["ok"] = True
            if not out["has_products"]:
                out["error"] = "The collection is empty, so the page would show nothing."
    store.cache_set(key, out)
    return out
