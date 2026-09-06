"""Shopify customers into the Fan CRM - only the ones who said yes.

A purchase is not permission to mail. The import files only customers
whose email-marketing consent Shopify records as subscribed, counts the
rest, records the consent once, tags the fan so the source is visible,
and keeps every run - counts or the vendor's error - so the page can
say what it did. Without the Admin token it says so and does nothing.
"""
import uuid

import pytest

import db as store
import links_store as mls
import shopify_customers as sc
from app import create_app

PASSWORD = "fans-pass-123"


def _node(email, first, last, orders, state, updated="2026-01-05T00:00:00Z", legacy=False):
    node = {"id": "gid://shopify/Customer/%s" % uuid.uuid4().hex[:8],
            "firstName": first, "lastName": last, "numberOfOrders": str(orders),
            "createdAt": "2025-11-02T10:00:00Z", "tags": ["vip"] if orders > 2 else [],
            "amountSpent": {"amount": "%d.00" % (orders * 20), "currencyCode": "USD"}}
    if legacy:      # the deprecated pair a store may still answer with
        node.update(email=email, emailMarketingConsent={"marketingState": state, "consentUpdatedAt": updated})
    else:
        node["defaultEmailAddress"] = {"emailAddress": email, "marketingState": state, "marketingUpdatedAt": updated}
    return node


PAGE1 = [_node("ava@example.net", "Ava", "Kane", 3, "SUBSCRIBED"),
         _node("bo@example.net", "Bo", "", 1, "NOT_SUBSCRIBED"),
         _node("", "Nobody", "", 0, "SUBSCRIBED"),
         _node("cy@example.net", "Cy", "Ro", 0, "SUBSCRIBED", updated="")]
PAGE2 = [_node("di@example.net", "Di", "Lo", 5, "UNSUBSCRIBED"),
         _node("ev@example.net", "Ev", "Ng", 2, "SUBSCRIBED", legacy=True)]


class Fake(object):
    def __init__(self, error=None):
        self.calls, self.error = [], error

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), body))
        if self.error:
            return {"errors": [{"message": self.error}]}
        after = (body.get("variables") or {}).get("after")
        if after is None:
            return {"data": {"customers": {"pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                                           "edges": [{"node": n} for n in PAGE1]}}}
        return {"data": {"customers": {"pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                                       "edges": [{"node": n} for n in PAGE2]}}}


def _connect(monkeypatch, fake):
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "shpat-test")
    monkeypatch.setattr(sc, "_post", fake)


def _artist(app_obj):
    email = "sf-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def test_it_is_inert_without_the_admin_token(monkeypatch):
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    monkeypatch.delenv("SHOPIFY_ADMIN_TOKEN", raising=False)
    assert sc.configured() is False and sc.status()["on"] is False
    with pytest.raises(sc.ShopifyError):
        sc.fetch_customers(post=lambda *a: pytest.fail("must not call out"))


def test_fetch_pages_the_store_with_the_documented_call(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    customers, cursor = sc.fetch_customers()
    assert len(customers) == 6 and cursor is None, "read to the end"
    url, headers, body = fake.calls[0]
    assert url == "https://art-is-war.myshopify.com/admin/api/%s/graphql.json" % sc.API_VERSION
    assert headers["X-Shopify-Access-Token"] == "shpat-test"
    assert "customers(first: 250, after: $after)" in body["query"] and "defaultEmailAddress" in body["query"]
    assert fake.calls[1][2]["variables"] == {"after": "c1"}
    ava = customers[0]
    assert ava == {"email": "ava@example.net", "name": "Ava Kane", "orders": 3, "spent": "60.00",
                   "currency": "USD", "tags": ["vip"], "created": "2025-11-02", "subscribed": True,
                   "consent_updated": "2026-01-05"}
    assert customers[1]["subscribed"] is False and customers[3]["consent_updated"] == ""


def test_the_cap_stops_and_hands_back_a_cursor(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    monkeypatch.setattr(sc, "MAX_PAGES", 1)
    customers, cursor = sc.fetch_customers()
    assert len(customers) == 4 and cursor == "c1"


def test_only_subscribed_customers_become_fans_and_consent_is_recorded_once(monkeypatch):
    _connect(monkeypatch, Fake())
    store.init_db()
    uid = "u-%s" % uuid.uuid4().hex
    customers, _ = sc.fetch_customers()
    summary = sc.import_fans(uid, customers)
    assert summary == {"fetched": 6, "imported": 3, "new": 3, "updated": 0,
                       "skipped_unsubscribed": 2, "skipped_no_email": 1}
    fans = {f["email"]: f for f in mls.list_fans(uid)}
    assert set(fans) == {"ava@example.net", "cy@example.net", "ev@example.net"}
    assert fans["ava@example.net"]["name"] == "Ava Kane"
    import json
    assert json.loads(fans["ava@example.net"]["tags"]) == ["shopify", "customer"]
    assert json.loads(fans["cy@example.net"]["tags"]) == ["shopify"], "no orders, no 'customer' tag"
    consents = mls.list_consents(fans["ava@example.net"]["id"])
    assert len(consents) == 1 and consents[0]["consent_type"] == "shopify_email_marketing"
    assert "consent updated 2026-01-05" in consents[0]["consent_text"]
    # A second run is an update, and the consent row is not doubled.
    again = sc.import_fans(uid, customers)
    assert again["new"] == 0 and again["updated"] == 3
    assert len(mls.list_consents(fans["ava@example.net"]["id"])) == 1


def test_the_page_offers_the_import_only_when_connected_and_keeps_every_run(monkeypatch):
    monkeypatch.delenv("SHOPIFY_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("SHOPIFY_DOMAIN", "art-is-war.myshopify.com")
    app_obj = create_app()
    client, user = _artist(app_obj)
    page = client.get("/links/fans").get_data(as_text=True)
    assert 'id="import"' in page and "Shopify is not connected" not in page and "SHOPIFY_ADMIN_TOKEN" in page
    assert "Import subscribed customers" not in page
    r = client.post("/links/fans/import/shopify")
    assert "imp=off" in r.headers["Location"]
    assert store.latest_fan_import(user["id"], "shopify") is None
    assert "not connected on this service" in client.get("/links/fans?imp=off").get_data(as_text=True)

    fake = Fake()
    _connect(monkeypatch, fake)
    page = client.get("/links/fans").get_data(as_text=True)
    assert "Import subscribed customers" in page and "A purchase alone is not permission" in page
    r = client.post("/links/fans/import/shopify")
    assert r.status_code == 302 and r.headers["Location"].endswith("/links/fans#import")
    last = store.latest_fan_import(user["id"], "shopify")
    assert last["summary"]["imported"] == 3 and last["error"] == "" and last["cursor"] == ""
    page = client.get("/links/fans").get_data(as_text=True)
    assert "imported 3 of 6 read" in page and "2 skipped, not subscribed" in page and "1 with no email" in page
    assert "ava@example.net" in page

    fake.error = "Access denied for customers field"
    client.post("/links/fans/import/shopify")
    page = client.get("/links/fans").get_data(as_text=True)
    assert "Last run failed: Shopify: Access denied for customers field" in page
    assert len(mls.list_fans(user["id"])) == 3, "a failed run changes nothing"


def test_a_capped_run_continues_from_its_cursor(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    monkeypatch.setattr(sc, "MAX_PAGES", 1)
    app_obj = create_app()
    client, user = _artist(app_obj)
    client.post("/links/fans/import/shopify")
    first = store.latest_fan_import(user["id"], "shopify")
    assert first["cursor"] == "c1" and first["summary"]["imported"] == 2
    assert "The store has more" in client.get("/links/fans").get_data(as_text=True)
    client.post("/links/fans/import/shopify")
    assert fake.calls[-1][2]["variables"] == {"after": "c1"}, "the next run starts where the last stopped"
    second = store.latest_fan_import(user["id"], "shopify")
    assert second["cursor"] == "" and second["summary"]["imported"] == 1
    assert len(mls.list_fans(user["id"])) == 3


def test_the_fan_dashboard_offers_the_import_on_its_empty_state(monkeypatch):
    _connect(monkeypatch, Fake())
    app_obj = create_app()
    client, user = _artist(app_obj)
    page = client.get("/fans").get_data(as_text=True)
    assert "No fans captured yet" in page and "Import subscribed Shopify customers" in page
    monkeypatch.delenv("SHOPIFY_ADMIN_TOKEN", raising=False)
    page = client.get("/fans").get_data(as_text=True)
    assert "Import subscribed Shopify customers" not in page
