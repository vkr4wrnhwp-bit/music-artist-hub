"""Tour opens onto the Mock Up Tour, not an empty page.

Owner, 2026-09-17: a fresh account found the demonstration routing in the
Tour suite but not on the app's own Tours page. The same builder now runs
here: one full routing, imported through the same parser and the same
store calls as a pasted deal sheet, for an account that has no tours of
its own. No artist is named.
"""
import uuid

import pytest

import app as appmod
import db as store
import tour_store as ts

PW = "mockup-tour-pass-1"


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("MOCK_UP_TOUR", "on")
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


def _client(plan="pro"):
    email = "tourdemo-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "T", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], plan)
    return c, store.get_user(user["id"])


def test_a_new_account_opens_onto_the_mock_up_tour(gated):
    c, user = _client()
    assert ts.list_tours(user["id"]) == []
    body = c.get("/tours").get_data(as_text=True)
    assert "Mock Up Tour" in body
    tours = ts.list_tours(user["id"])
    assert len(tours) == 1 and tours[0]["name"] == "Mock Up Tour"
    shows = ts.list_shows(tours[0]["id"])
    assert len(shows) > 30, "a real routing, not a single date"
    # Invented rooms on real cities (owner, 2026-09-17: "this cant resemble
    # anyone"), in April 2027 so the demo does not become a tour of the past.
    assert any("The Paper Mill" in (s.get("venue") or "") for s in shows)
    assert all((s.get("date") or "").startswith("2027-") for s in shows)
    assert "demonstration" in (tours[0].get("notes") or "").lower()


def test_it_is_built_once_and_never_beside_a_real_tour(gated):
    c, user = _client()
    c.get("/tours")
    c.get("/tours")
    assert len(ts.list_tours(user["id"])) == 1, "a second visit does not build a second copy"
    other, them = _client()
    ts.create_tour(them["id"], {"name": "My own run", "status": "planning"})
    other.get("/tours")
    assert [t["name"] for t in ts.list_tours(them["id"])] == ["My own run"]


def test_an_account_that_cannot_own_a_tour_gets_none(gated):
    c, user = _client(plan="fan")
    c.get("/tours")
    assert ts.list_tours(user["id"]) == []
