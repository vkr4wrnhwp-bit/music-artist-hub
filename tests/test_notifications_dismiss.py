"""A notification you cannot remove is a list that only grows.

Reported live, 2026-09-12: "in notifications you cant delete them".
The page listed every event ever recorded against the account, marked
them read on view, and offered no way to take one off. Dismiss removes
one; Clear all removes the lot. Both are scoped to the account inside
the DELETE, so a guessed id belonging to somebody else removes nothing.
"""
import uuid

import pytest

import db as store
from app import create_app


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "notif-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "A", "email": email,
                                 "password": "notifpw123456"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _notify(client, title):
    with client._app.app_context():
        store.notify(client._uid, "fan", title, "body", "/fans")
        return store.list_notifications(client._uid)[0]["id"]


def test_dismiss_removes_that_one_and_leaves_the_rest(artist):
    keep = _notify(artist, "Keep me")
    gone = _notify(artist, "Dismiss me")
    artist.post("/notifications/%d/dismiss" % gone)
    with artist._app.app_context():
        left = [n["id"] for n in store.list_notifications(artist._uid)]
    assert left == [keep]


def test_the_page_offers_dismiss_per_row_and_clear_all(artist):
    _notify(artist, "One event")
    body = artist.get("/notifications").get_data(as_text=True)
    assert "Dismiss: One event" in body
    assert "Clear all" in body and "/notifications/clear" in body


def test_clear_all_empties_the_list(artist):
    _notify(artist, "a"); _notify(artist, "b")
    artist.post("/notifications/clear")
    with artist._app.app_context():
        assert store.list_notifications(artist._uid) == []
    assert "Quiet for now" in artist.get("/notifications").get_data(as_text=True)


def test_somebody_elses_id_removes_nothing(artist):
    mine = _notify(artist, "Mine")
    stranger = create_app().test_client()
    stranger.post("/signup", data={"name": "S", "password": "notifpw123456",
                                   "email": "other-%s@example.net" % uuid.uuid4().hex[:8]})
    stranger.post("/notifications/%d/dismiss" % mine)
    with artist._app.app_context():
        assert [n["id"] for n in store.list_notifications(artist._uid)] == [mine]


def test_anonymous_cannot_clear_anything(artist):
    mine = _notify(artist, "Mine")
    anon = create_app().test_client()
    r = anon.post("/notifications/clear")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with artist._app.app_context():
        assert [n["id"] for n in store.list_notifications(artist._uid)] == [mine]
