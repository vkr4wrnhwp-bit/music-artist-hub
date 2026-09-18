"""The connected store's customers are the owner's, and only the owner's.

SHOPIFY_* is server configuration, so the connection is one store: the
owner's. Until 2026-09-17 the "Import subscribed customers" button was
offered to every signed-in account and the POST checked nothing, so a
partner's artist could have filed the owner's customer list as their own
fans. Nobody had pressed it. A per-account connection is a different
feature; these tests are about the door.
"""
import uuid

import pytest

import app as appmod
import db as store

PW = "fan-import-pass-1"


@pytest.fixture
def connected(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("SHOPIFY_DOMAIN", "example.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ADMIN_TOKEN", "shpat_notarealtoken")


def _client(monkeypatch, owner=False):
    email = "%s-%s@example.net" % ("owner" if owner else "artist", uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "F", "email": email, "password": PW})
    if owner:
        monkeypatch.setenv("OWNER_EMAILS", email)
    c.post("/login", data={"email": email, "password": PW})
    return c, email


def test_another_account_is_never_offered_the_owners_store(connected, monkeypatch):
    artist, _ = _client(monkeypatch)
    for path in ("/fans", "/links/fans"):
        body = artist.get(path).get_data(as_text=True)
        assert "Import subscribed" not in body, path
        assert "/links/fans/import/shopify" not in body, path


def test_another_account_cannot_call_the_import_or_the_reconnect(connected, monkeypatch):
    artist, email = _client(monkeypatch)
    before = store.latest_fan_import(store.get_user_by_email(email)["id"], "shopify")
    assert artist.post("/links/fans/import/shopify").status_code == 404
    assert artist.post("/links/fans/shopify/reconnect").status_code == 404
    assert store.latest_fan_import(store.get_user_by_email(email)["id"], "shopify") == before


def test_the_owner_still_has_it(connected, monkeypatch):
    owner, _ = _client(monkeypatch, owner=True)
    body = owner.get("/links/fans").get_data(as_text=True)
    assert "/links/fans/import/shopify" in body
    # Reaching the route is what matters; the call itself goes to Shopify.
    assert owner.post("/links/fans/shopify/reconnect").status_code == 302
