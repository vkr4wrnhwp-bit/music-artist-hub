"""The Studio has to be a room you can leave.

The owner: "studio opens strange and always has huh song in it". Both halves
were one bug. /studio redirects into the most recently touched project - which
is right most of the time - but the console's only way out linked back to
/studio, which redirected straight into the same session. So you landed on one
song and the exit returned you to it.
"""
import uuid

import pytest

import app as appmod
import studio_store as sstore

PASSWORD = "studio-nav-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def owner(application):
    email = "snav-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Nav Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        import db as store
        user = store.get_user_by_email(email)
    return client, user


def _project(user, title):
    return sstore.create_project(None, user["id"], title=title,
                                 artist_name="Prayers")


def test_the_console_links_to_the_list_not_back_to_itself(owner, application):
    """The escape hatch was a loop: the eyebrow pointed at /studio, and
    /studio redirects into the newest session."""
    client, user = owner
    with application.app_context():
        pid = _project(user, "huh")
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert "/studio/projects" in body, "the way out must reach the list"


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
    other_email = "sother-%s@example.net" % uuid.uuid4().hex[:8]
    other = application.test_client()
    other.post("/signup", data={"name": "Other", "email": other_email,
                                "password": PASSWORD})
    other.post("/login", data={"email": other_email, "password": PASSWORD})
    with application.app_context():
        import db as store
        theirs = _project(store.get_user_by_email(other_email), "Not yours")
    assert client.get("/studio/open?project_id=%s" % theirs).status_code == 404
    assert client.get("/studio/open?project_id=nonsense").status_code == 404


def test_studio_still_opens_the_newest_session(owner, application):
    """The redirect stays: the owner previously reported the console being
    buried, and landing on work in progress is right most of the time. What
    changed is that it is no longer a trap."""
    client, user = owner
    with application.app_context():
        _project(user, "older")
        newest = _project(user, "newest")
    r = client.get("/studio")
    assert r.status_code in (302, 303)
    assert newest in r.headers["Location"]


def test_an_account_with_no_sessions_sees_the_front_door(owner, application):
    """The branch that renders this used to sit behind `if projects:` AFTER
    the redirects had already returned for that case - dead the day it was
    written, so the "continue" card never rendered for anybody."""
    email = "sempty-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Empty", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.get("/studio")
    assert r.status_code == 200, "no sessions means the home page, not a redirect"
