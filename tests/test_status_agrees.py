"""The checklists describe the account, and they agree with each other.

Codex audit, 2026-09-17: an account with tens of thousands of statement
rows was still told to "add a track", and the onboarding list called a
smart link done while the score beside it read not started. Both came
from one page reading one table where another page read a different one.
A step is still done only when the thing exists; it now looks in every
place the thing can exist.
"""
import re
import uuid

import pytest

import app as appmod
import db as store
import links_store as mls

PW = "status-agrees-pass-1"


@pytest.fixture
def open_signup(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _step_done(body, title):
    """Whether the start-here list has ticked a step. Every step is on the
    page whether or not it is done; done ones are struck through."""
    m = re.search(r'line-through[^>]*>' + re.escape(title) + r'<', body)
    return bool(m)


def _account():
    email = "status-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "S", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], "pro")
    return c, store.get_user(user["id"])


def test_statements_name_the_songs_so_nothing_asks_for_a_track(open_signup):
    c, user = _account()
    assert not _step_done(c.get("/command-center").get_data(as_text=True), "Add a track")
    store.save_statement(user["id"], "spotify-q1.csv", [
        {"title": "Cell 5", "source": "Spotify", "amount": 41.2, "period": "2026-01"},
        {"title": "Long Way Down", "source": "Spotify", "amount": 12.8, "period": "2026-01"},
    ])
    assert sorted(store.statement_titles(user["id"])) == ["Cell 5", "Long Way Down"]
    assert _step_done(c.get("/command-center").get_data(as_text=True), "Add a track")


def test_a_smart_link_counts_whichever_door_made_it(open_signup):
    c, user = _account()
    assert not _step_done(c.get("/command-center").get_data(as_text=True), "Make a smart link")
    mls.create_campaign(user["id"], "new-single-" + uuid.uuid4().hex[:6], {"title": "New single", "kind": "release"})
    assert _step_done(c.get("/command-center").get_data(as_text=True), "Make a smart link")


def test_the_two_checklists_never_disagree(open_signup, monkeypatch):
    """Tutor mode and the start-here list read the same account, so a step
    that is done in one is done in the other."""
    c, user = _account()
    store.save_statement(user["id"], "s.csv", [{"title": "A Song", "source": "Apple", "amount": 3.0, "period": "2026-02"}])
    mls.create_campaign(user["id"], "a-song-" + uuid.uuid4().hex[:6], {"title": "A Song", "kind": "release"})
    c.post("/tutor/toggle", data={"on": "1"})
    page = c.get("/command-center").get_data(as_text=True)
    assert _step_done(page, "Add a track") and _step_done(page, "Make a smart link")


def test_statement_titles_are_this_account_s_own(open_signup):
    _c, mine = _account()
    _o, theirs = _account()
    store.save_statement(mine["id"], "mine.csv", [{"title": "Mine", "source": "Spotify", "amount": 1.0, "period": "2026-01"}])
    assert store.statement_titles(mine["id"]) == ["Mine"]
    assert store.statement_titles(theirs["id"]) == []
