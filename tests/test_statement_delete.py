"""An upload you cannot remove is a figure you cannot correct.

There was no way to delete a statement, and it surfaced for a concrete
reason: the ISRC column arrived after some statements were already
uploaded, so those rows carry no ISRC and the store check has nothing to
look up. The fix is to upload the file again - which, with no delete,
would double every figure on the money pages.

It also matters on its own. A wrong file, a duplicate, a test upload:
each one silently changes reported earnings, the recovery estimate and
the valuation, and none of it could be undone.
"""
import io
import uuid

import pytest

import db as store
from app import create_app

CSV = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,Royalty\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Spotify,100.00\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Deezer,5.00\n")


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "stmt-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "King 810", "email": email,
                                 "password": "stmtpw123456"})
    # /statements answers 402 without a plan, which is why an earlier
    # version of this test saw no uploads at all.
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _upload(client, name="jun.csv", csv=CSV):
    return client.post("/statements",
                       data={"statement": (io.BytesIO(csv.encode()), name)},
                       content_type="multipart/form-data")


def test_removing_an_upload_takes_its_rows_with_it(artist):
    _upload(artist)
    with artist._app.app_context():
        uploads = store.get_statements(artist._uid)
        assert len(uploads) == 1
        assert len(store.get_statement_rows(artist._uid)) == 2

    artist.post("/statements/%s/delete" % uploads[0]["id"])
    with artist._app.app_context():
        assert store.get_statements(artist._uid) == []
        assert store.get_statement_rows(artist._uid) == [], (
            "orphan rows would keep counting toward every money figure")


def test_the_page_offers_the_control_and_confirms_afterwards(artist):
    _upload(artist)
    body = artist.get("/statements").get_data(as_text=True)
    assert "Remove</button>" in body
    assert "jun.csv" in body

    with artist._app.app_context():
        upload_id = store.get_statements(artist._uid)[0]["id"]
    artist.post("/statements/%s/delete" % upload_id)
    after = artist.get("/statements?removed=1").get_data(as_text=True)
    assert "Upload removed" in after


def test_only_the_owner_can_remove_an_upload(artist):
    _upload(artist)
    with artist._app.app_context():
        upload_id = store.get_statements(artist._uid)[0]["id"]

    stranger = create_app().test_client()
    stranger.post("/signup", data={
        "name": "S", "password": "stmtpw123456",
        "email": "other-%s@example.net" % uuid.uuid4().hex[:8]})
    stranger.post("/plan/switch", data={"plan": "pro"})
    stranger.post("/statements/%s/delete" % upload_id)

    with artist._app.app_context():
        assert store.get_statements(artist._uid), "a guessed id removes nothing"


def test_the_isrc_survives_the_upload(artist):
    """The reason delete was needed: without an ISRC on the row, the store
    check has nothing to ask about."""
    _upload(artist)
    with artist._app.app_context():
        rows = store.get_statement_rows(artist._uid)
    assert all(r["isrc"] == "GBWUL2686921" for r in rows)


def test_removing_one_of_two_leaves_the_other(artist):
    _upload(artist, "jun.csv")
    _upload(artist, "may.csv", CSV.replace("JUN-26", "MAY-26"))
    with artist._app.app_context():
        uploads = store.get_statements(artist._uid)
        assert len(uploads) == 2
    artist.post("/statements/%s/delete" % uploads[0]["id"])
    with artist._app.app_context():
        left = store.get_statements(artist._uid)
        assert len(left) == 1
        assert len(store.get_statement_rows(artist._uid)) == 2
