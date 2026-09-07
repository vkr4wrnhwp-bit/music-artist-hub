"""Shopify's Dev Dashboard shows no token in any UI (2025). The app holds
a Client ID and a Client Secret, exchanges them for a 24-hour Admin token
(client credentials grant), and mints its own permanent Storefront token
once through the Admin API. The legacy env tokens still win when set,
and every refusal is named on the page rather than swallowed.
"""
import json

import db as store
import shopify_buy as sb
import shopify_customers as sc


def _creds(monkeypatch, admin_token=None):
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "client-abc")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "secret-xyz")
    if admin_token is None:
        monkeypatch.delenv("SHOPIFY_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", admin_token)
    monkeypatch.delenv("SHOPIFY_STOREFRONT_TOKEN", raising=False)
    store.set_kv(sc.GRANT_KEY, "")
    store.set_kv(sc.GRANT_ERROR_KEY, "")
    store.set_kv(sb.STOREFRONT_KEY, "")
    store.set_kv(sb.STOREFRONT_ERROR_KEY, "")


def test_the_admin_token_is_minted_from_the_apps_credentials_and_kept_a_day(monkeypatch):
    _creds(monkeypatch)
    calls = []

    def grant(url, fields):
        calls.append((url, fields))
        return 200, {"access_token": "granted-1", "scope": "read_customers", "expires_in": 86399}
    monkeypatch.setattr(sc, "_post_form", grant)
    assert sc.configured() and sc.uses_grant() and sc.token_looks_right()
    assert sc.token() == "granted-1"
    assert calls[0][0] == "https://art-is-war.myshopify.com/admin/oauth/access_token"
    assert calls[0][1] == {"grant_type": "client_credentials", "client_id": "client-abc", "client_secret": "secret-xyz"}
    assert sc.token() == "granted-1" and len(calls) == 1, "kept, not minted again per call"
    kept = json.loads(store.get_kv(sc.GRANT_KEY))
    assert kept["scope"] == "read_customers" and kept["client_id"] == "client-abc"
    # Near expiry it mints again; a new client id never reuses the old token.
    assert sc.granted_token(now=kept["expires_at"] - 60) == "granted-1" and len(calls) == 2
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "client-new")
    sc.token()
    assert len(calls) == 3 and calls[2][1]["client_id"] == "client-new"
    assert sc.status()["headline"] == "Shopify is connected" and "24-hour token" in sc.status()["detail"]


def test_a_refused_grant_is_named_and_the_legacy_token_still_wins(monkeypatch):
    _creds(monkeypatch)
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: (400, {"error": "invalid_grant", "error_description": "Shop is not in your organization"}))
    assert sc.token() == "" and sc.configured()
    s = sc.status()
    assert s["headline"] == "Shopify refused the app's credentials"
    assert "400: Shop is not in your organization" in s["detail"] and "same Shopify organization" in s["detail"]
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: (0, {"network": "timed out"}))
    store.set_kv(sc.GRANT_ERROR_KEY, "")
    assert sc.token() == "" and "timed out" in sc.status()["detail"]
    # The app's credentials win over a legacy token left beside them: a stale one must not silence the grant.
    calls = []
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: calls.append(1) or (200, {"access_token": "granted-2", "expires_in": 86399}))
    store.set_kv(sc.GRANT_KEY, "")
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "0123456789abcdef0123456789abcdef")
    assert sc.uses_grant() and sc.token() == "granted-2" and calls and sc.token_looks_right()
    # Without credentials the legacy token is used as before.
    monkeypatch.delenv("SHOPIFY_CLIENT_ID", raising=False)
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "shpat_legacy")
    assert sc.token() == "shpat_legacy" and not sc.uses_grant()
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "0123456789abcdef0123456789abcdef")
    assert not sc.token_looks_right() and "does not look right" in sc.status()["headline"]


def test_the_storefront_token_is_minted_once_through_the_admin_api(monkeypatch):
    _creds(monkeypatch)
    monkeypatch.setenv("SHOPIFY_COLLECTION_ID", "298812866663")
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: (200, {"access_token": "granted-1", "expires_in": 86399}))
    mints = []

    def mint(url, headers, body):
        mints.append((url, headers, body))
        return 200, {"data": {"storefrontAccessTokenCreate": {"storefrontAccessToken": {"accessToken": "sf-1", "title": "Street Banker Buy Buttons"}, "userErrors": []}}}
    monkeypatch.setattr(sb, "_post", mint)
    assert sb.token() == "sf-1" and sb.configured()
    assert mints[0][0] == "https://art-is-war.myshopify.com/admin/api/%s/graphql.json" % sb.API_VERSION
    assert mints[0][1]["X-Shopify-Access-Token"] == "granted-1" and "storefrontAccessTokenCreate" in mints[0][2]["query"]
    assert sb.token() == "sf-1" and len(mints) == 1, "kept in app_kv; a shop may hold only a hundred"
    assert sb.context()["configured"] and sb.context()["token"] == "sf-1"
    # The env token wins when set.
    monkeypatch.setenv("SHOPIFY_STOREFRONT_TOKEN", "sf-env")
    assert sb.token() == "sf-env"


def test_a_storefront_mint_that_shopify_refuses_names_the_scopes(monkeypatch):
    _creds(monkeypatch)
    monkeypatch.setenv("SHOPIFY_COLLECTION_ID", "298812866663")
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: (200, {"access_token": "granted-1", "expires_in": 86399}))
    monkeypatch.setattr(sb, "_post", lambda url, headers, body: (200, {"data": {"storefrontAccessTokenCreate": {"storefrontAccessToken": None, "userErrors": [{"field": ["input"], "message": "Access denied for storefrontAccessTokenCreate"}]}}}))
    assert sb.token() == "" and not sb.configured()
    ctx = sb.context()
    assert not ctx["configured"] and "unauthenticated_read_product_listings" in ctx["reason"]
    assert "Access denied for storefrontAccessTokenCreate" in ctx["reason"]
    # No admin token at all: nothing is minted and nothing is claimed.
    monkeypatch.setattr(sc, "_post_form", lambda url, fields: (401, {}))
    store.set_kv(sc.GRANT_KEY, "")
    assert sb.token() == ""


def test_without_credentials_nothing_changes(monkeypatch):
    for key in ("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_STOREFRONT_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    store.set_kv(sb.STOREFRONT_KEY, "")
    assert not sc.configured() and sc.token() == "" and not sc.uses_grant()
    assert "SHOPIFY_CLIENT_ID" in sc.status()["detail"]
    assert sb.token() == "" and not sb.configured()
