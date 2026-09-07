"""The store's checkout, embedded — or an honest link when it is not.

The app has always linked out to artiswarrecords.com. A link is a
handoff: the fan leaves and the cart is somewhere else. Buy Buttons put
Shopify's own checkout on the page they are already on, with no payment
code on this side.

The three env vars are the store's to give. Until they exist the page
must be the link it always was - not an empty widget, not a spinner,
and not a "coming soon".
"""

import os

import uuid

import shopify_buy
from app import create_app


def _env(monkeypatch, **values):
    for key in ("SHOPIFY_DOMAIN", "SHOPIFY_STOREFRONT_TOKEN",
                "SHOPIFY_COLLECTION_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _demo(app_obj=None):
    client = (app_obj or create_app()).test_client()
    client.post("/login", data={"email": "demo@streetbanker.io",
                                "password": "sweep"})
    return client


def test_unconfigured_is_a_link_not_a_broken_shop(monkeypatch):
    _env(monkeypatch)
    assert shopify_buy.configured() is False
    body = _demo().get("/apparel").get_data(as_text=True)
    assert "The store is not embedded here yet" in body
    assert "artiswarrecords.com" in body          # the store still opens
    assert "shopify-collection" not in body       # no empty mount point
    assert "buy-button-storefront" not in body    # and no SDK to hang on


def test_partial_credentials_do_not_half_open_the_store(monkeypatch):
    _env(monkeypatch, SHOPIFY_DOMAIN="artiswar.myshopify.com")
    assert shopify_buy.configured() is False
    ctx = shopify_buy.context()
    assert "SHOPIFY_STOREFRONT_TOKEN" in ctx["reason"]
    assert "SHOPIFY_COLLECTION_ID" in ctx["reason"]


def test_configured_embeds_the_real_sdk(monkeypatch):
    _env(monkeypatch, SHOPIFY_DOMAIN="artiswar.myshopify.com",
         SHOPIFY_STOREFRONT_TOKEN="storefront_public_token",
         SHOPIFY_COLLECTION_ID="123456789")
    assert shopify_buy.configured() is True
    body = _demo().get("/apparel").get_data(as_text=True)
    assert 'id="shopify-collection"' in body
    assert "sdks.shopifycdn.com/buy-button" in body
    assert '"artiswar.myshopify.com"' in body
    assert '"123456789"' in body
    assert "The store is not embedded here yet" not in body


def test_the_page_never_asks_for_a_card(monkeypatch):
    """Checkout belongs to Shopify. If this page ever grows a card field
    it has stopped being an embed and started being a liability."""
    _env(monkeypatch, SHOPIFY_DOMAIN="artiswar.myshopify.com",
         SHOPIFY_STOREFRONT_TOKEN="storefront_public_token",
         SHOPIFY_COLLECTION_ID="123456789")
    body = _demo().get("/apparel").get_data(as_text=True)
    for banned in ["card number", "cardnumber", "cvc", "cvv", "expiry",
                   'name="card', 'autocomplete="cc-']:
        assert banned not in body.lower(), banned


def test_the_admin_key_is_never_read(monkeypatch):
    """A Storefront token is meant to ship to browsers. An admin key is
    not, so nothing here may reach for one."""
    source = open("shopify_buy.py", encoding="utf-8").read()
    template = open("templates/apparel.html", encoding="utf-8").read()
    for banned in ["SHOPIFY_ADMIN", "ADMIN_API", "X-Shopify-Access-Token"]:
        assert banned not in source, banned
        assert banned not in template, banned


def test_services_points_at_the_page(monkeypatch):
    _env(monkeypatch)
    body = _demo().get("/services").get_data(as_text=True)
    assert 'href="/apparel"' in body


def test_the_public_epk_carries_the_same_embed_only_when_configured(monkeypatch):
    """Where fans actually land. The same partial, gated the same way: no
    credentials, no widget - the Merch section keeps its outbound links."""
    import db as store_mod
    from tests.test_app import _demo
    for key in ("SHOPIFY_DOMAIN", "SHOPIFY_STOREFRONT_TOKEN", "SHOPIFY_COLLECTION_ID"):
        monkeypatch.delenv(key, raising=False)
    app_obj = create_app()
    client = _demo(app_obj)
    assert client.post("/epk/save", json={"store_url": "https://www.artiswarrecords.com"}).get_json()["ok"]
    client.get("/epk")                       # the editor mints the public slug
    demo_user = store_mod.get_user_by_email("demo@streetbanker.io")
    with store_mod.get_db() as conn:
        slug = conn.execute("SELECT slug FROM epk_profiles WHERE slug IS NOT NULL AND user_id = ?",
                            (demo_user["id"],)).fetchone()["slug"]
    anon = app_obj.test_client()
    off = anon.get("/epk/" + slug).get_data(as_text=True)
    assert "Full store" in off and 'id="shopify-collection"' not in off and "buy-button-storefront" not in off
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    monkeypatch.setenv("SHOPIFY_STOREFRONT_TOKEN", "sf-public-token")
    monkeypatch.setenv("SHOPIFY_COLLECTION_ID", "298812866663")
    on = anon.get("/epk/" + slug).get_data(as_text=True)
    assert 'id="shopify-collection"' in on and "buy-button-storefront.min.js" in on
    assert '"sf-public-token"' in on and "298812866663" in on
    assert "shpat_" not in on and "SHOPIFY_ADMIN_TOKEN" not in on, "the admin token never reaches a page"


def _owner(app_obj, monkeypatch):
    """The owner sees the check; nobody else does."""
    import db as store_mod
    email = "owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Owner", "email": email, "password": "owner-pass-123"})
    client.post("/login", data={"email": email, "password": "owner-pass-123"})
    return client


def test_the_storefront_check_names_what_shopify_said(monkeypatch):
    _env(monkeypatch, SHOPIFY_DOMAIN="art-is-war.myshopify.com", SHOPIFY_STOREFRONT_TOKEN="sf-1",
         SHOPIFY_COLLECTION_ID="298812866663")
    import db as store_mod
    store_mod.init_db()
    seen = []

    def post(url, headers, body):
        seen.append((url, headers, body))
        return 200, {"data": {"shop": {"name": "Art Is War", "primaryDomain": {"host": "www.artiswarrecords.com"}},
                              "collection": {"title": "Street Banker", "handle": "street-banker",
                                             "products": {"edges": [{"node": {"title": "Tee"}}]}}}}
    out = shopify_buy.check(post=post, fresh=True)
    assert out["ok"] is True and out["shop"] == "Art Is War" and out["collection"] == "Street Banker"
    assert out["has_products"] is True and out["error"] == ""
    url, headers, body = seen[0]
    assert url == "https://art-is-war.myshopify.com/api/%s/graphql.json" % shopify_buy.API_VERSION
    assert headers["X-Shopify-Storefront-Access-Token"] == "sf-1"
    assert body["variables"] == {"id": "gid://shopify/Collection/298812866663"}
    # Cached on the values: the second read costs nothing, a changed token asks again.
    assert shopify_buy.check(post=lambda *a: (0, {"network": "must not be called"})) == out
    monkeypatch.setenv("SHOPIFY_STOREFRONT_TOKEN", "sf-2")
    bad = shopify_buy.check(post=lambda *a: (401, {}), fresh=True)
    assert bad["ok"] is False and "rejected the Storefront token" in bad["error"] and "not the Admin one" in bad["error"]
    missing = shopify_buy.check(post=lambda *a: (200, {"data": {"shop": {"name": "Art Is War"}, "collection": None}}), fresh=True)
    assert missing["ok"] is False and "no collection has the id 298812866663" in missing["error"]
    empty = shopify_buy.check(post=lambda *a: (200, {"data": {"shop": {"name": "A"}, "collection": {"title": "T", "products": {"edges": []}}}}), fresh=True)
    assert empty["ok"] is True and "empty" in empty["error"]
    _env(monkeypatch)
    assert shopify_buy.check() is None


def test_only_the_owner_sees_the_check_on_the_page(monkeypatch):
    _env(monkeypatch, SHOPIFY_DOMAIN="art-is-war.myshopify.com", SHOPIFY_STOREFRONT_TOKEN="sf-page",
         SHOPIFY_COLLECTION_ID="298812866663")
    monkeypatch.setattr(shopify_buy, "_post", lambda *a: (401, {}))
    app_obj = create_app()
    body = _demo(app_obj).get("/apparel").get_data(as_text=True)
    assert "storefront check failed" not in body and "owner only" not in body
    body = _owner(app_obj, monkeypatch).get("/apparel").get_data(as_text=True)
    assert "storefront check failed" in body and "rejected the Storefront token" in body and "owner only" in body
