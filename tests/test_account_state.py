"""The account's state, decided once (owner's Command Center spec,
2026-09-22).

Four states, one rule: a failed read is "error", never "new". Five
essentials with lock-and-reveal, three competing at once, every lock
explained. Pure functions first, then the route.
"""
import uuid

import pytest

import account_state as acs
import app as appmod
import db as store


# ---- the pure rules ---------------------------------------------------

def test_a_fresh_account_shows_identity_song_and_a_locked_link():
    """First login: exactly three cards, and the smart link is visible
    but locked, with the lock explained - so the reader sees where setup
    is going without five tasks at once."""
    out = acs.build({})
    shown = [s["key"] for s in out["shown"]]
    assert shown == ["identity", "song", "link"], shown
    by = {s["key"]: s for s in out["steps"]}
    assert by["identity"]["status"] == "not_started"
    assert by["song"]["status"] == "not_started"
    assert by["link"]["status"] == "locked"
    assert "Add a song first" in by["link"]["lock_text"]
    # asset and capture wait behind song and link
    assert by["asset"]["revealed"] is False
    assert by["capture"]["revealed"] is False
    assert out["done"] == 0 and out["total"] == 5
    assert out["progress"] == "0 of 5 essentials complete."
    assert out["next"]["key"] == "identity"
    assert out["complete"] is False


def test_a_song_unlocks_the_link_and_reveals_the_rack():
    out = acs.build({"identity": True, "song": True})
    by = {s["key"]: s for s in out["steps"]}
    assert by["link"]["status"] == "not_started", "the lock opened"
    assert by["asset"]["status"] == "not_started" and by["asset"]["revealed"]
    assert by["capture"]["revealed"] is False, "capture waits for the link"
    assert out["done"] == 2 and out["progress"] == "2 of 5 essentials complete."
    assert out["next"]["key"] == "asset"


def test_the_link_reveals_capture_and_all_five_is_complete():
    out = acs.build({"identity": True, "song": True, "asset": True, "link": True})
    by = {s["key"]: s for s in out["steps"]}
    assert by["capture"]["revealed"] and by["capture"]["status"] == "not_started"
    assert out["next"]["key"] == "capture"
    done = acs.build({k: True for k in acs.KEYS})
    assert done["complete"] is True and done["next"] is None
    assert done["progress"] == "5 of 5 essentials complete."


def test_a_step_this_plan_cannot_open_is_dropped_not_counted():
    out = acs.build({}, reachable={"identity", "song", "link"})
    assert out["total"] == 3
    assert [s["key"] for s in out["steps"]] == ["identity", "song", "link"]


def test_never_more_than_three_compete():
    for flags in ({}, {"identity": True}, {"song": True},
                  {"identity": True, "song": True},
                  {"identity": True, "song": True, "link": True}):
        out = acs.build(flags)
        open_cards = [s for s in out["shown"] if not s["done"]]
        assert len(open_cards) <= acs.SHOW_AT_ONCE, (flags, [s["key"] for s in open_cards])


def test_state_of_is_new_only_with_nothing_done_and_nothing_saved():
    assert acs.state_of(acs.build({}), has_records=False) == "new"
    assert acs.state_of(acs.build({}), has_records=True) == "setup"
    assert acs.state_of(acs.build({"identity": True}), False) == "setup"
    assert acs.state_of(acs.build({k: True for k in acs.KEYS}), False) == "operational"
    # nothing on offer for this plan: nothing to set up
    assert acs.state_of(acs.build({}, reachable=set()), False) == "operational"


def test_a_failed_read_is_error_never_new():
    """The rule this module exists for."""
    class Broken:
        def __getattr__(self, name):
            def boom(*a, **k):
                raise RuntimeError("db is down")
            return boom
    out = acs.decide("uid", Broken(), Broken(), Broken())
    assert out["state"] == "error"
    assert out["essentials"] is None
    assert "db is down" in out["error"]


# ---- the facts, against a real store ----------------------------------

PW = "state-1"


def _account(name="Fresh"):
    email = "acs-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "pro")
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def test_the_signup_name_does_not_count_as_identity():
    """Audit, 2026-09-22: a brand-new account read "1 / 5 done" because
    has_profile counted the name typed at signup. Identity is artist or
    label details SAVED, and a fresh account has saved none."""
    import links_store as mls
    import release_ready_store
    _c, uid = _account(name="Typed At Signup")
    flags = acs.read(uid, store, mls, release_ready_store)
    assert flags == {"identity": False, "song": False, "asset": False,
                     "link": False, "capture": False}, flags


def test_capture_needs_both_halves():
    import links_store as mls
    import release_ready_store
    _c, uid = _account()
    cid = mls.create_campaign(uid, "cap-%s" % uuid.uuid4().hex[:6],
                              {"title": "Cap", "settings": {"email_capture": True}})
    flags = acs.read(uid, store, mls, release_ready_store)
    assert flags["link"] is True
    assert flags["capture"] is False, "capture without consent text is not capture"
    mls.update_campaign(cid, uid, {"settings": {"email_capture": True,
                                               "consent_text": "You agree to hear from us."}})
    assert acs.read(uid, store, mls, release_ready_store)["capture"] is True


def test_a_rack_preset_is_a_setting_not_an_asset():
    import links_store as mls
    import release_ready_store
    _c, uid = _account()
    store.save_rack_preset(uid, {"out": 0})
    assert acs.read(uid, store, mls, release_ready_store)["asset"] is False


# ---- the route --------------------------------------------------------

def test_a_broken_read_renders_the_error_page_never_a_fresh_account(monkeypatch):
    """The page-level half of the rule. Before this, _firstrun_panel
    wrapped every query in `except Exception: return None`, so one bad
    read deleted the setup panel and the account looked finished."""
    c, _uid = _account()
    def boom(_uid):
        raise RuntimeError("db is down")
    monkeypatch.setattr(store, "get_epk", boom)
    r = c.get("/command-center")
    body = r.get_data(as_text=True)
    assert r.status_code == 503
    assert "We could not load your Command Center" in body
    assert "Your account and setup progress are safe" in body
    assert "Try again" in body and 'href="/all-tools"' in body
    assert "Start here" not in body, "an error must not look like setup"
    assert "/5<" not in body and "0<span" not in body, "no zero values"


def test_a_fresh_account_is_not_lied_to():
    """The four things the audit caught the operational page saying to a
    brand-new account (2026-09-22): a date filter over no data, "every
    live campaign is capturing fans" with no campaigns, "What Changed
    Since Your Last Visit" on a first visit, and "1 / 5 done" for a name
    typed at signup."""
    c, _uid = _account(name="Typed At Signup")
    body = c.get("/command-center").get_data(as_text=True)
    assert 'id="date-range"' not in body
    assert "every live campaign is capturing fans" not in body
    assert "What Changed Since Your Last Visit" not in body
    assert "0<span" in body and "1<span" not in body.split("done")[0]
    # the three cards, the lock explained, the rest waiting
    assert "Tell us who you are" in body and "Add your first song" in body
    assert "Create your first smart link" in body
    assert "Add a song first so Street Banker knows what the link supports." in body
    assert "Turn on fan capture" not in body


def test_all_tools_is_the_directory_moved_out():
    c, _uid = _account()
    r = c.get("/all-tools")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert body.count('class="tools-card"') >= 30, "the whole directory"
    assert 'id="tools-q"' in body, "searchable"
