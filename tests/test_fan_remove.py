"""The fans page said "manage or delete records in the Fan CRM", and the Fan CRM could not.

Found by the route walk of 2026-09-12: ml_fans was one of the user-owned
tables nothing ever deleted from. A fan who asks to be forgotten is
forgotten - the row, their consent records and the events they raised -
and only by the account that holds them.
"""
import uuid

import pytest

import db as store
import links_store as mls
from app import create_app

PW = "fans-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "fanowner-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
        cid = mls.create_campaign(client._uid, "fan-%s" % uuid.uuid4().hex[:6],
                                  {"title": "Fan Drop"})
        fan = mls.upsert_fan(client._uid, "someone@example.net", cid, "Some One")
        fid = fan["id"] if isinstance(fan, dict) else fan
        mls.add_consent(fid, cid, "email", "yes please")
        mls.track(cid, "capture", fan_id=fid)
        client._fan, client._cid = fid, cid
    return client


def _counts(client):
    with client._app.app_context(), store.get_db() as db:
        return (db.execute("SELECT COUNT(*) FROM ml_fans WHERE id = ?", (client._fan,)).fetchone()[0],
                db.execute("SELECT COUNT(*) FROM ml_consents WHERE fan_id = ?", (client._fan,)).fetchone()[0],
                db.execute("SELECT COUNT(*) FROM ml_events WHERE fan_id = ?", (client._fan,)).fetchone()[0])


def test_the_crm_offers_remove_per_fan(artist):
    body = artist.get("/links/fans").get_data(as_text=True)
    assert "/links/fans/%s/delete" % artist._fan in body
    assert 'aria-label="Remove someone@example.net"' in body


def test_remove_takes_the_fan_their_consents_and_their_events(artist):
    assert _counts(artist) == (1, 1, 1)
    r = artist.post("/links/fans/%s/delete" % artist._fan)
    assert r.status_code == 302 and "/links/fans" in r.headers["Location"]
    assert _counts(artist) == (0, 0, 0)


def test_another_account_cannot_remove_them(artist):
    other = create_app().test_client()
    other.post("/signup", data={"name": "S", "password": PW,
                                "email": "other-%s@example.net" % uuid.uuid4().hex[:8]})
    other.post("/links/fans/%s/delete" % artist._fan)
    assert _counts(artist) == (1, 1, 1)


def test_anonymous_is_sent_to_login(artist):
    anon = create_app().test_client()
    r = anon.post("/links/fans/%s/delete" % artist._fan)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert _counts(artist) == (1, 1, 1)
