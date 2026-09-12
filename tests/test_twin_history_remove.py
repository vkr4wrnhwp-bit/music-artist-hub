"""Saved Generations on the Artist Twin was a list that only grew.

The table audit of 2026-09-12 listed twin_generations among the
user-owned tables with inserts and no delete anywhere. Each saved
generation can be removed by the account that made it, and by no one
else.
"""
import uuid

import pytest

import db as store
from app import create_app

PW = "twin-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "twin-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Twin", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
        store.save_twin_generation(client._uid, "bio", "A short bio.", "account name only")
        client._gid = store.list_twin_generations(client._uid)[0]["id"]
    return client


def test_the_page_offers_remove_per_generation(artist):
    body = artist.get("/artist-twin").get_data(as_text=True)
    assert "/artist-twin/history/%s/delete" % artist._gid in body


def test_remove_takes_that_generation(artist):
    r = artist.post("/artist-twin/history/%s/delete" % artist._gid)
    assert r.status_code == 302
    with artist._app.app_context():
        assert store.list_twin_generations(artist._uid) == []


def test_another_account_cannot_remove_it(artist):
    other = create_app().test_client()
    other.post("/signup", data={"name": "S", "password": PW,
                                "email": "twin-o-%s@example.net" % uuid.uuid4().hex[:8]})
    other.post("/artist-twin/history/%s/delete" % artist._gid)
    with artist._app.app_context():
        assert [g["id"] for g in store.list_twin_generations(artist._uid)] == [artist._gid]
