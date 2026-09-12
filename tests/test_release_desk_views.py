"""The Calendar tab jumped to the foot of the page, and a release could not leave the desk.

Reported live, 2026-09-12: "calendar in the top of release autopilot
just jumps to the bottom of the screen and theres no way to archive or
delete a release".

The tab was an anchor to a section at the end of the same page. A tab
is a view: ?view=calendar now renders the scheduler first and alone.
Archive already existed on the smart-link page; the desk offers it too
and comes back to the desk afterwards. There is no delete on purpose -
fans signed up through the link, and their records outlive the campaign.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import links_store as mls

PASSWORD = "desk-pass-12345"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    email = "rdv-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Desk", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        soon = (date.today() + timedelta(days=10)).isoformat()
        cid = mls.create_campaign(uid, "rdv-%s" % uuid.uuid4().hex[:6],
                                  {"title": "Leaving Drop", "release_date": soon})
    return {"client": client, "uid": uid, "campaign": cid}


def test_the_calendar_tab_is_a_view_not_an_anchor(artist):
    body = artist["client"].get("/releases/autopilot").get_data(as_text=True)
    assert 'href="/releases/autopilot?view=calendar"' in body
    assert 'href="/releases/autopilot#calendar"' not in body


def test_the_calendar_view_opens_on_the_scheduler(artist):
    body = artist["client"].get("/releases/autopilot?view=calendar").get_data(as_text=True)
    assert 'id="calendar"' in body
    assert 'id="rd-campaign"' not in body, "the picker strip belongs to the other view"
    assert 'id="clean"' not in body, "the desk's own sections belong to the other view"


def test_the_desk_offers_archive_and_comes_back(artist):
    body = artist["client"].get("/releases/autopilot").get_data(as_text=True)
    assert "Archive this release" in body
    r = artist["client"].post("/links/%s/archive" % artist["campaign"],
                              data={"next": "/releases/autopilot"})
    assert r.headers["Location"].endswith("/releases/autopilot")
    after = artist["client"].get("/releases/autopilot").get_data(as_text=True)
    assert "Leaving Drop" not in after


def test_next_never_leaves_the_site(artist):
    r = artist["client"].post("/links/%s/archive" % artist["campaign"],
                              data={"next": "https://evil.example/phish"})
    assert r.headers["Location"].endswith("/links")
