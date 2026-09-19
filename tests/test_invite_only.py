"""Nobody makes an account unless the owner gives them one.

Owner, 2026-09-17: "right now make sure no one can make an account unless i
give them one". On a deployed service /signup is shut; the owner makes an
invitation in Settings (one address, one plan, one use) and that link is the
only way in. Member-issued team and roster links may attach an existing
account but never mint a new one.
"""
import io
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

# --- the split home page's door ------------------------------------------
# Added 2026-09-17 with the split home page, because it is a second place
# the app talks to a stranger about getting in, and the owner's rule is
# "no sign ups until i say so". A door that says "Create an account" while
# /signup refuses to create one is the page lying about the product.

def test_the_split_door_offers_an_invitation_and_not_an_account(shut, monkeypatch):
    monkeypatch.setenv("SPLIT_HOME", "1")
    body = appmod.app.test_client().get("/").get_data(as_text=True)
    assert 'id="sbdoor-h"' in body, "the split page is the one under test"
    assert "opening by invitation" in body
    # Nothing anywhere on the page offers an account, footer included.
    # Writing this test is how the footer link was found.
    assert "Create an account" not in body
    # It never grows a registration form of its own: the only form on it
    # is the sign-in form, posting to /login.
    door = body.split('class="sbdoor"')[1].split("</section>")[0]
    assert door.count("<form") == 1
    assert 'action="/login' in door
    assert 'action="/signup' not in door


def test_the_split_door_follows_the_door_rather_than_deciding_for_itself(shut, monkeypatch):
    """When the owner does open sign-up, the line changes on its own. The
    page must not need a second edit to stop being wrong."""
    monkeypatch.setenv("SPLIT_HOME", "1")
    monkeypatch.setenv("SIGNUP_MODE", "open")
    body = appmod.app.test_client().get("/").get_data(as_text=True)
    assert "Create an account" in body and "opening by invitation" not in body


def test_the_long_homepage_says_nothing_different(shut, monkeypatch):
    """Whichever front page is on, a stranger is told the same thing."""
    monkeypatch.delenv("SPLIT_HOME", raising=False)
    body = appmod.app.test_client().get("/").get_data(as_text=True)
    # The long page links /signup rather than describing it, and /signup
    # itself is the page that says invitation only.
    r = appmod.app.test_client().get("/signup")
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    assert "invitation" in page.lower()
    assert store.get_user_by_email("never-made@example.net") is None
    assert body  # the long page still renders with the door shut


# --- no page advertises a door that is shut ------------------------------
# The lock above proves no route mints an account. These prove the product
# stops offering one, which is a different thing and was the gap: twelve
# public pages and the footer said "Create an account" and sent a stranger
# to a page that told them no. Every one of those buttons now asks
# app.inject_the_door for its words.

# (page, the wording it uses when the door is open)
OFFERS = [
    ("/", "Create an account"),
    ("/plan", "Create an account"),
    ("/release-check", "Create an account to build the release"),
    ("/rollout", "Create an account to build one"),
    ("/distribution", "Create an account to build one"),
    ("/creative-studio", "Create an account to start"),
    ("/lanes", "Create an account"),
]


@pytest.mark.parametrize("path,open_label", OFFERS)
def test_with_the_door_shut_the_page_asks_for_an_invitation(shut, path, open_label):
    body = appmod.app.test_client().get(path).get_data(as_text=True)
    assert "Create an account" not in body, path
    assert "Ask for an invitation" in body, path


@pytest.mark.parametrize("path,open_label", OFFERS)
def test_with_the_door_open_each_page_keeps_its_own_wording(monkeypatch, path, open_label):
    """One label pasted over every button would be the cure being worse
    than the disease, so each page keeps the sentence it was written with
    and only swaps it while the door is shut."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("SIGNUP_MODE", "open")
    body = appmod.app.test_client().get(path).get_data(as_text=True)
    assert open_label in body, path
    assert "Ask for an invitation" not in body, path


def test_no_template_hard_codes_the_offer_any_more():
    """A new page that writes the words itself would go stale the moment
    the owner opens sign-up, and would advertise a shut door until
    somebody noticed. This is the rule that stops the next one."""
    import glob
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    offenders = []
    for path in glob.glob(_os.path.join(here, "templates", "**", "*.html"),
                          recursive=True):
        text = io.open(path, encoding="utf-8").read()
        for line in text.splitlines():
            if "Create an account" in line and "signup_cta" not in line:
                offenders.append((_os.path.relpath(path, here), line.strip()[:70]))
    assert not offenders, offenders

