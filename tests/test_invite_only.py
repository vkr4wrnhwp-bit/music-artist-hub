"""Nobody makes an account unless the owner gives them one.

Owner, 2026-09-17: "right now make sure no one can make an account unless i
give them one". On a deployed service /signup is shut; the owner makes an
invitation in Settings (one address, one plan, one use) and that link is the
only way in. Member-issued team and roster links may attach an existing
account but never mint a new one.
"""
import re
import uuid

import pytest

import app as appmod
import db as store

PW = "invite-only-pass-1"


def _addr(tag):
    return "%s-%s@example.net" % (tag, uuid.uuid4().hex[:8])


@pytest.fixture
def shut(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("SIGNUP_MODE", raising=False)


def _owner_client(monkeypatch):
    email = _addr("owner")
    monkeypatch.setenv("SIGNUP_MODE", "open")
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    monkeypatch.setenv("OWNER_EMAILS", email)
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    c.post("/login", data={"email": email, "password": PW})
    return c


def test_off_render_the_door_is_open_as_the_suite_expects():
    email = _addr("local")
    r = appmod.app.test_client().post("/signup", data={"name": "Local", "email": email, "password": PW})
    assert r.status_code == 302 and store.get_user_by_email(email) is not None


def test_a_deployed_service_refuses_a_stranger(shut):
    c = appmod.app.test_client()
    # The page is still there, form and all: the owner shows it to people.
    page = c.get("/signup")
    assert page.status_code == 200 and b'name="password"' in page.data and b"Create your account" in page.data
    assert b"opening by invitation" in page.data
    # Submitting it creates nothing, and says why rather than pretending.
    email = _addr("stranger")
    r = c.post("/signup", data={"name": "Stranger", "email": email, "password": PW})
    assert r.status_code == 403 and b"invitation only" in r.data and b'name="password"' in r.data
    assert store.get_user_by_email(email) is None


def test_signup_mode_open_is_the_only_way_to_reopen_it(shut, monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    email = _addr("reopened")
    r = appmod.app.test_client().post("/signup", data={"name": "Re", "email": email, "password": PW})
    assert r.status_code == 302 and store.get_user_by_email(email) is not None


def test_the_owners_invitation_is_the_way_in_once_for_that_address_on_that_plan(shut, monkeypatch):
    owner = _owner_client(monkeypatch)
    monkeypatch.setenv("RENDER", "true")
    email = _addr("partner")
    assert owner.post("/admin/invite", data={"email": email, "plan": "pro"}).status_code == 302
    settings = owner.get("/settings").get_data(as_text=True)
    link = re.search(r'value="([^"]*/signup\?invite=[^"]+)"', settings).group(1)
    token = link.split("invite=")[1]
    guest = appmod.app.test_client()
    page = guest.get("/signup?invite=" + token).get_data(as_text=True)
    assert email in page and "readonly" in page
    # the form cannot swap the address for another one
    r = guest.post("/signup", data={"invite": token, "name": "Partner", "email": _addr("swap"), "password": PW})
    assert r.status_code == 302
    made = store.get_user_by_email(email)
    assert made is not None and made["plan"] == "pro"
    # one use
    again = appmod.app.test_client().post("/signup", data={"invite": token, "name": "Again", "email": email, "password": PW})
    assert again.status_code == 403


def test_nobody_but_the_owner_can_invite(shut, monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    email = _addr("artist")
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Artist", "email": email, "password": PW})
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    monkeypatch.setenv("OWNER_EMAILS", "somebody-else@example.net")
    assert c.post("/admin/invite", data={"email": _addr("x"), "plan": "artist"}).status_code == 404
    assert "Invite someone" not in c.get("/settings").get_data(as_text=True)
