"""A legacy smart link, once made, could never be taken down.

The table audit of 2026-09-12 listed smart_links among the user-owned
tables with inserts and no delete; /links showed each one with its
click count and nothing else. Take down removes the link and its click
log, for the account that owns it, and the public /l/<slug> no longer
lands anywhere.
"""
import uuid

import pytest

import db as store
from app import create_app

PW = "legacy-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "lgcy-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "L", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
        client._slug = store.create_db_link("lg-%s" % uuid.uuid4().hex[:6], client._uid,
                                            "Old Link", "https://example.net/x", [])
        if isinstance(client._slug, dict):
            client._slug = client._slug["slug"]
        store.log_click(client._slug)
    return client


def test_the_list_offers_take_down(artist):
    body = artist.get("/links").get_data(as_text=True)
    assert "/links/legacy/%s/delete" % artist._slug in body


def test_take_down_removes_the_link_and_its_clicks(artist):
    assert artist.get("/l/%s" % artist._slug).status_code in (200, 302)
    r = artist.post("/links/legacy/%s/delete" % artist._slug)
    assert r.status_code == 302
    with artist._app.app_context():
        assert store.get_db_link(artist._slug) is None
        with store.get_db() as db:
            assert db.execute("SELECT COUNT(*) FROM link_clicks WHERE slug = ?",
                              (artist._slug,)).fetchone()[0] == 0
    # /l/<unknown> falls back to /links by design (test_app pins it), so
    # "taken down" reads as: no landing page, no redirect to the target.
    gone = artist._app.test_client().get("/l/%s" % artist._slug)
    assert gone.status_code == 302 and gone.headers["Location"].endswith("/links")


def test_another_account_cannot_take_it_down(artist):
    other = create_app().test_client()
    other.post("/signup", data={"name": "S", "password": PW,
                                "email": "lgcy-o-%s@example.net" % uuid.uuid4().hex[:8]})
    other.post("/links/legacy/%s/delete" % artist._slug)
    with artist._app.app_context():
        assert store.get_db_link(artist._slug) is not None
