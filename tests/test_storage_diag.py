"""Object storage says why it is unreachable, to the person who owns it.

The round-trip check existed but lived inside /presave/diag, which only a
label-plan account could open, so the owner of the bucket could not see it.
It answers the owner, reports the SHAPE of each credential, and never
prints a value. Since 2026-09-23 (audit, providers-15) it answers ONLY the
owner: any signed-in account could make the server write into the owner's
bucket and read back the raw S3 error body.
"""
import uuid

import pytest

import app as appmod
import db as store

PASSWORD = "diag-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, monkeypatch=None):
    """A signed-in account; the owner when `monkeypatch` is given."""
    email = "diag-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Diag", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    if monkeypatch is not None:
        monkeypatch.setenv("OWNER_EMAILS", email)
    return client, store.get_user_by_email(email)


def test_a_customer_gets_nothing(flask_app):
    client, _user_row = _user(flask_app)
    r = client.get("/storage/diag")
    assert r.status_code == 404 and b"R2_" not in r.data


def test_a_visitor_gets_nothing(flask_app):
    """The app-wide login wall answers first with a redirect; the route's own
    401 is the backstop if that wall ever stops covering this path."""
    r = flask_app.test_client().get("/storage/diag")
    assert r.status_code in (302, 401)
    assert b"R2_" not in r.data


def test_unset_storage_says_so_and_says_where_uploads_go(flask_app, monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    client, _user_row = _user(flask_app, monkeypatch)
    body = client.get("/storage/diag").get_json()
    assert body["configured"] is False
    assert "disk" in body["note"]
    assert "Render" in body["next"]


def test_a_malformed_pair_is_named_without_printing_it(flask_app, monkeypatch):
    """The shape the owner's account actually had: a 32-character secret
    where R2 wants 64 hex, and a bucket holding an id rather than a name."""
    monkeypatch.setenv("R2_ACCOUNT_ID", "b" * 32)
    monkeypatch.setenv("R2_BUCKET", "a" * 32)              # an id, not a name
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "c" * 32)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "d" * 32)   # should be 64
    client, _user_row = _user(flask_app, monkeypatch)
    body = client.get("/storage/diag").get_json()
    assert body["configured"] is True and not body.get("ok")
    hints = " ".join(body["next"])
    assert "64 hex" in hints and "32" in hints
    assert "bucket" in hints.lower() and "name" in hints.lower()
    # No secret, and no whole credential, is echoed anywhere in the answer.
    printed = str(body)
    assert "d" * 32 not in printed and "c" * 32 not in printed
    assert "a" * 32 not in printed and "b" * 32 not in printed
