"""The Studio has to be a room you can leave - and a door you can see.

Two owner reports, one week apart. First: "studio opens strange and always
has huh song in it" - /studio redirected into the most recently touched
project and the console's only exit linked back to /studio, a loop. Then,
after the exit was repointed: "studio still loads messed up, and its named
huh" - because the redirect itself was the problem. Landing inside one
project with no list in sight reads as broken, whatever the project is
called. So /studio is a page again: it names the projects, offers the newest
as "Continue working", and the console is one click away.

Archiving is the other half: the owner could not put "huh" away. The store
had archive_project for a year with nothing calling it.
"""
import uuid

import pytest

import app as appmod
import studio_store as sstore

PASSWORD = "studio-nav-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


def _account(application, label):
    email = "snav-%s-%s@example.net" % (label, uuid.uuid4().hex[:8])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        import db as store
        user = store.get_user_by_email(email)
    return client, user


@pytest.fixture
def owner(application):
    return _account(application, "owner")


def _project(user, title):
    return sstore.create_project(None, user["id"], title=title,
                                 artist_name="Prayers")


# --- the front door ----------------------------------------------------------

def test_studio_is_a_page_that_names_the_projects(owner, application):
    """No redirect. The page lists what you have and offers the newest as
    the thing to continue."""
    client, user = owner
    with application.app_context():
        older = _project(user, "older song")
        newest = _project(user, "newest song")
    r = client.get("/studio")
    assert r.status_code == 200, "the front door is a page, not a redirect"
    body = r.get_data(as_text=True)
    assert "older song" in body and "newest song" in body
    assert "Continue working" in body
    assert body.index("newest song") < body.index("older song")
    assert "/studio/session/%s" % newest in body
    assert "/studio/session/%s" % older in body
    assert "Mix and Master unlock when a source is uploaded" in body


def test_the_console_exit_lands_on_the_studio_page_not_back_in_the_session(owner, application):
    """The escape hatch used to be a loop: the eyebrow pointed at /studio and
    /studio redirected into the newest session."""
    client, user = owner
    with application.app_context():
        pid = _project(user, "huh")
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert 'href="/studio"' in body, "the way out must reach the Studio page"
    out = client.get("/studio")
    assert out.status_code == 200
    assert "Control Room" in out.get_data(as_text=True)


def test_the_switcher_appears_once_there_is_a_choice(owner, application):
    client, user = owner
    with application.app_context():
        first = _project(user, "huh")
    only = client.get("/studio/session/%s" % first).get_data(as_text=True)
    assert 'id="sr-switch"' not in only, "one session is not a choice"

    with application.app_context():
        _project(user, "Gothic Summer")
    both = client.get("/studio/session/%s" % first).get_data(as_text=True)
    assert 'id="sr-switch"' in both
    assert "Gothic Summer" in both
    assert "/studio/projects" in both


def test_switching_opens_the_other_session(owner, application):
    client, user = owner
    with application.app_context():
        a = _project(user, "huh")
        b = _project(user, "Gothic Summer")
    r = client.get("/studio/open?project_id=%s" % b)
    assert r.status_code in (302, 303)
    assert b in r.headers["Location"] and a not in r.headers["Location"]


def test_you_cannot_open_somebody_elses_session(owner, application):
    """An id that is not yours is a 404, not a redirect into their console."""
    client, _user = owner
    _other_client, other = _account(application, "other")
    with application.app_context():
        theirs = _project(other, "Not yours")
    assert client.get("/studio/open?project_id=%s" % theirs).status_code == 404
    assert client.get("/studio/open?project_id=nonsense").status_code == 404


def test_an_account_with_no_sessions_sees_the_start_state(application):
    client, _user = _account(application, "empty")
    r = client.get("/studio")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Start a session" in body and "No projects yet" in body
    assert "Continue working" not in body


# --- archiving ---------------------------------------------------------------

def test_the_owner_can_archive_a_project_and_it_is_gone_everywhere(owner, application):
    client, user = owner
    with application.app_context():
        pid = _project(user, "huh")
        keep = _project(user, "Gothic Summer")

    session = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert "/studio/session/%s/archive" % pid in session, "the Team panel offers it"
    listing = client.get("/studio/projects").get_data(as_text=True)
    assert "/studio/session/%s/archive" % pid in listing, "each row offers it"

    r = client.post("/studio/session/%s/archive" % pid)
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/studio/projects?archived=1")

    after = client.get("/studio/projects?archived=1").get_data(as_text=True)
    assert "Project archived" in after
    assert "/studio/session/%s" % pid not in after
    assert "/studio/session/%s" % keep in after

    home = client.get("/studio").get_data(as_text=True)
    assert "/studio/session/%s" % pid not in home
    assert "/studio/session/%s" % keep in home
    assert client.get("/studio/open?project_id=%s" % pid).status_code == 404
    assert client.get("/studio/session/%s" % pid).status_code == 404
    assert client.post("/studio/session/%s/archive" % pid).status_code == 404


def test_archiving_an_unknown_project_is_a_404(owner):
    client, _user = owner
    assert client.post("/studio/session/nonsense/archive").status_code == 404


def test_a_shared_member_cannot_archive(owner, application):
    """The member can open the console through an accepted team seat; the
    archive verb is the owner's alone, and says so with a 403 rather than
    pretending the project is not there."""
    owner_client, owner_user = owner
    engineer_client, engineer = _account(application, "engineer")
    with application.app_context():
        import db as store
        pid = _project(owner_user, "Signal Fire")
        invite = store.add_team_invite(owner_user["id"], engineer["email"],
                                       "manager")
        store.accept_team_invite(invite["invite_token"], engineer["id"])
        seat = [t for t in store.list_team(owner_user["id"])
                if t["email"] == engineer["email"]][0]
        sstore.add_member(None, owner_user["id"], pid, "MixedByCee",
                          "mix_engineer", team_member_id=seat["id"])
    console = engineer_client.get("/studio/session/%s" % pid)
    assert console.status_code == 200
    assert "/studio/session/%s/archive" % pid not in console.get_data(as_text=True)
    assert engineer_client.post("/studio/session/%s/archive" % pid).status_code == 403
    assert owner_client.get("/studio/session/%s" % pid).status_code == 200
    home = engineer_client.get("/studio")
    assert home.status_code == 200, "a shared-only account lands on the page too"
    assert "Shared with you" in home.get_data(as_text=True)
    assert "/studio/session/%s" % pid in home.get_data(as_text=True)
