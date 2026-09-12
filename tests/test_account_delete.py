"""Settings had no way to leave.

Reported live, 2026-09-12: "in settings theres no delete profile either".

The rules this file holds:

  * the confirmation is the account's own email typed back - a wrong
    address deletes nothing
  * every row that names the account goes, across every table that has
    a user_id column, found from the schema rather than a kept list
  * the login is gone afterwards: the password no longer works
  * an owner account and an account with a live Stripe subscription are
    refused, and told why, rather than half-handled
  * the bucket objects the rows pointed at are asked for deletion after
    the rows commit - and a bucket that will not answer changes nothing
"""
import io
import uuid

import pytest

import blob_store
import db as store
from app import create_app

PW = "delete-me-12345"
CSV = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,Royalty\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Spotify,100.00\n")


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "del-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Leaving", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client.post("/statements",
                data={"statement": (io.BytesIO(CSV.encode()), "jun.csv")},
                content_type="multipart/form-data")
    client._app, client._email = app_obj, email
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
        store.notify(client._uid, "fan", "A fan", "", "/fans")
    return client


def _rows_for(client):
    with client._app.app_context(), store.get_db() as db:
        return {t: db.execute('SELECT COUNT(*) FROM "%s" WHERE "%s" = ?' % (t, k),
                              (client._uid,)).fetchone()[0]
                for t, k in store._tables_keyed_by_user(db)}


def test_the_page_offers_it_and_asks_for_the_email(artist):
    body = artist.get("/settings").get_data(as_text=True)
    assert 'id="delete-account"' in body
    assert 'name="confirm"' in body and "/account/delete" in body


def test_a_wrong_address_deletes_nothing(artist):
    before = _rows_for(artist)
    # the upload itself raised a notification, so >= 1 rather than == 1
    assert before["statements"] == 1 and before["notifications"] >= 1
    r = artist.post("/account/delete", data={"confirm": "someone@else.net"})
    assert "deleted=mismatch" in r.headers["Location"]
    assert _rows_for(artist) == before
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is not None


def test_the_right_address_takes_every_row_and_the_login(artist):
    before = _rows_for(artist)
    assert sum(before.values()) >= 3, "the fixture planted rows in more than one table"
    r = artist.post("/account/delete", data={"confirm": artist._email.upper()})
    assert r.headers["Location"].endswith("/login?deleted=1")
    assert all(n == 0 for n in _rows_for(artist).values()), _rows_for(artist)
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is None
    fresh = artist._app.test_client()
    login = fresh.post("/login", data={"email": artist._email, "password": PW})
    assert "/settings" not in (login.headers.get("Location") or "")
    assert fresh.get("/settings").status_code == 302, "nobody is signed in"
    assert "has been deleted" in fresh.get("/login?deleted=1").get_data(as_text=True)


def test_an_owner_account_is_refused_with_the_reason(artist, monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", artist._email)
    r = artist.post("/account/delete", data={"confirm": artist._email})
    assert "deleted=owner" in r.headers["Location"]
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is not None
    body = artist.get("/settings?deleted=owner").get_data(as_text=True)
    assert "OWNER_EMAILS" in body


def test_a_live_subscription_is_refused_and_pointed_at_billing(artist):
    with artist._app.app_context():
        store.set_stripe_ids(artist._uid, "cus_x", "sub_x")
    r = artist.post("/account/delete", data={"confirm": artist._email})
    assert "deleted=billing" in r.headers["Location"]
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is not None
    assert "/billing" in artist.get("/settings?deleted=billing").get_data(as_text=True)


def test_the_bucket_is_asked_to_drop_what_the_rows_pointed_at(artist, monkeypatch):
    with artist._app.app_context(), store.get_db() as db:
        db.execute("INSERT INTO documents (id, user_id, filename, path, doc_type, created)"
                   " VALUES (?,?,?,?,?,?)",
                   (uuid.uuid4().hex, artist._uid, "m.wav",
                    blob_store.PREFIX + "masters/leaving/m.wav", "audio", "2026-09-12"))
    asked = []
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "delete", lambda key: asked.append(key) or True)
    artist.post("/account/delete", data={"confirm": artist._email})
    assert asked == ["masters/leaving/m.wav"]


def test_a_bucket_that_will_not_answer_does_not_bring_the_account_back(artist, monkeypatch):
    with artist._app.app_context(), store.get_db() as db:
        db.execute("INSERT INTO documents (id, user_id, filename, path, doc_type, created)"
                   " VALUES (?,?,?,?,?,?)",
                   (uuid.uuid4().hex, artist._uid, "m.wav",
                    blob_store.PREFIX + "masters/leaving/m.wav", "audio", "2026-09-12"))
    monkeypatch.setattr(blob_store, "configured", lambda: True)

    def boom(key):
        raise OSError("bucket down")
    monkeypatch.setattr(blob_store, "delete", boom)
    r = artist.post("/account/delete", data={"confirm": artist._email})
    assert r.headers["Location"].endswith("/login?deleted=1")
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is None


def test_anonymous_cannot_delete_anybody(artist):
    anon = create_app().test_client()
    r = anon.post("/account/delete", data={"confirm": artist._email})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with artist._app.app_context():
        assert store.get_user_by_email(artist._email) is not None
