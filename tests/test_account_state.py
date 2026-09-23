"""The account's state, decided once (owner's Command Center spec,
2026-09-22).

Four states, one rule: a failed read is "error", never "new". Five
essentials with lock-and-reveal, three competing at once, every lock
explained. Pure functions first, then the route.
"""
import io
import re
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
    # real records mean a WORKING account: operational, with the
    # essentials still shown until done - never an onboarding page over
    # someone's money
    assert acs.state_of(acs.build({}), has_records=True) == "operational"
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
    assert "0 of 5 essentials complete." in body
    assert "1 of 5" not in body, "a name typed at signup is not a milestone"
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


# ---- Pass 2: the zero page ----------------------------------------------

def _zero_page(c):
    r = c.get("/command-center")
    return r.status_code, r.get_data(as_text=True)


def test_a_new_account_gets_the_zero_page():
    """The page from the owner's mockup, in the spec's order, with nothing
    the spec forbids: no royalties, recovery, release metrics, empty
    tables, charts or since-your-last-visit."""
    c, _uid = _account(name="Typed At Signup")
    code, body = _zero_page(c)
    assert code == 200
    assert 'class="cz"' in body, "the zero page, not the operational one"
    # the header, exact words
    assert "Start with the essentials. Street Banker will guide the next move." in body
    assert "Continue setup" in body
    # the three static screens, exact words, and nothing rotating
    assert "Build your foundation one step at a time." in body
    assert "Complete your artist or label profile." in body
    assert "0 of 5 essentials complete." in body
    assert "rk-cine" not in body and "animation" not in body.split('class="cz-rack"')[1].split("</section>")[0]
    # order: rack, first steps, fits together, quiet + explore, help
    i = body.index
    assert i("Where you are") < i("Your first steps") < i("How Street Banker fits together") \
        < i("Nothing needs attention yet") < i("You can explore at your own pace") \
        < i("Need help choosing your first step?")
    # the four neutral stages, unmarked
    for stage in ("Plan &amp; Own", "Create", "Launch &amp; Grow", "Live &amp; Learn"):
        assert stage in body
    assert "%" not in body.split("How Street Banker fits together")[1].split("Nothing needs attention")[0]
    # the forbidden list
    for bad in ("Total Royalties Collected", "Earnings Trend", "Money Left on the Table",
                "Open Actions", "Upcoming Releases", "What Changed Since Your Last Visit",
                "The Operating System", 'id="date-range"', "Today's Priorities"):
        assert bad not in body, bad
    # the directory is behind one door
    assert 'href="/all-tools"' in body


def test_the_zero_page_offers_three_cards_with_the_lock_explained():
    c, _uid = _account()
    _code, body = _zero_page(c)
    cards = re.split(r'<li class="cz-card[" ]', body)[1:]
    assert len(cards) == 3, len(cards)
    assert "Tell us who you are" in cards[0] and "cz-btn--primary" in cards[0]
    assert "Add your first song" in cards[1] and "cz-btn--outline" in cards[1]
    assert "Create your first smart link" in cards[2] and "cz-btn--locked" in cards[2]
    assert "Add a song first so Street Banker knows what the link supports." in cards[2]
    assert "Open the Rack" not in body and "Turn on fan capture" not in body


def test_continue_setup_opens_the_first_incomplete_milestone():
    """Not a generic settings page (spec)."""
    import links_store as mls
    c, uid = _account()
    def cta(body):
        # the door, before the ?returnTo=…&from=… it carries since Pass 4
        m = re.search(r'<a class="cz-cta" href="([^"?]+)', body)
        return m.group(1) if m else None
    _code, body = _zero_page(c)
    assert cta(body) == "/epk", "fresh: the profile"
    store.save_epk(uid, {"artist_name": "Rello"})
    _code, body = _zero_page(c)
    assert cta(body) == "/tracks", "then: the song"
    assert "1 of 5 essentials complete." in body
    assert "Add your first song." in body, "START HERE names the next step"


def test_real_records_mean_the_operational_page_even_mid_setup():
    """An account with a statement is working. Its money is never hidden
    behind an onboarding page; the essentials ride along until done."""
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])
    code, body = _zero_page(c)
    assert code == 200
    assert 'class="cz"' not in body
    assert "Total Royalties Collected" in body
    assert "Start here" in body, "the essentials panel rides along"


def test_all_tools_is_in_the_sidebar():
    c, _uid = _account()
    _code, body = _zero_page(c)
    assert 'href="/all-tools"' in body.split('id="sb-main"')[0], "in the sidebar, not only on the page"


def test_the_crt_green_is_a_token():
    """One of the twelve red design-system tests: #5DFF8F was a raw
    literal in the plates. It is --sb-crt now, and the plates read it."""
    import re as _re
    tokens = io.open("tools/tailwind-input.css", encoding="utf-8").read()
    assert "--sb-crt: #5DFF8F" in tokens and "--sb-crt-dim: #34C96A" in tokens
    for sheet in ("static/css/room-kit.css", "static/css/business-room.css",
                  "static/css/studio-room.css", "static/css/command-zero.css"):
        css = io.open(sheet, encoding="utf-8").read().lower()
        assert not _re.search(r"#5dff8f|#34c96a", css), "%s still carries the literal" % sheet


# ---- Pass 4: the way back, and what you are told --------------------------

def test_done_line_is_decided_by_saved_state_not_the_param():
    """?from=song names the door. Whether anything is SAID is decided by
    whether the song exists."""
    nothing = acs.build({})
    assert acs.done_line(nothing, "song") == ""
    assert acs.done_line(nothing, "nope") == ""
    assert acs.done_line(nothing, "") == ""
    after_song = acs.build({"identity": True, "song": True})
    line = acs.done_line(after_song, "song")
    assert line == ("Your first song was added. Setup is now 2 of 5 complete. "
                    "Next, add the working audio in the Rack."), line
    done = acs.build({k: True for k in acs.KEYS})
    assert acs.done_line(done, "capture").endswith("Every essential is in place.")


def test_every_setup_door_carries_a_way_back():
    c, _uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    for key, href in (("identity", "/epk"), ("song", "/tracks")):
        assert '%s?returnTo=/command-center&amp;from=%s' % (href, key) in body, key
    # the locked card has no door, so no returnTo
    assert "/links/new?returnTo" not in body


def test_the_shell_honours_a_same_site_return_and_ignores_the_rest():
    c, _uid = _account()
    # /epk renders in place; /tracks redirects a pro plan to the catalog
    # (and now carries the query with it - asserted separately below)
    body = c.get("/epk?returnTo=/command-center&from=identity").get_data(as_text=True)
    assert 'id="sb-room-back"' in body
    assert 'href="/command-center"' in body.split('id="sb-room-back"')[0][-120:] \
        or 'href="/command-center" id="sb-room-back"' in body
    assert "Back to Command Center" in body
    # a hostile returnTo is dropped, not followed
    for bad in ("//evil.example", "https://evil.example/x", "/\\\\evil"):
        body = c.get("/epk?returnTo=" + bad).get_data(as_text=True)
        assert "evil" not in body.split('id="sb-main"')[1].split("</main>")[0][:4000], bad


def test_coming_back_through_a_door_reports_what_is_now_real():
    c, uid = _account()
    # back from the profile door with NOTHING saved: no claim
    body = c.get("/command-center?from=identity").get_data(as_text=True)
    assert "Your profile was saved" not in body
    # save it, come back through the same door: the sentence, the count,
    # the next step
    store.save_epk(uid, {"artist_name": "Rello"})
    body = c.get("/command-center?from=identity").get_data(as_text=True)
    assert "Your profile was saved. Setup is now 1 of 5 complete. Next, add your first song." in body
    assert 'role="status"' in body
    # and not on a plain visit
    body = c.get("/command-center").get_data(as_text=True)
    assert "Your profile was saved" not in body


def test_the_song_door_survives_the_catalog_redirect():
    """/tracks sends a pro plan to /catalog?view=passports. The way back
    the Command Center gave that door has to ride through."""
    c, _uid = _account()
    r = c.get("/tracks?returnTo=/command-center&from=song", follow_redirects=False)
    assert r.status_code == 302
    assert "returnTo=/command-center" in r.headers["Location"] and "from=song" in r.headers["Location"]
    body = c.get(r.headers["Location"]).get_data(as_text=True)
    assert "Back to Command Center" in body


def test_the_rack_is_the_owners_plate_with_measured_screens():
    """The photograph is the hardware (owner-generated, 2026-09-22) and
    only the readouts are drawn on it. Each screen's box is a fraction
    MEASURED off the file - a round number would be an unmeasured
    placeholder, the Studio LCD lesson - and the drawn CSS rack that
    stood in until the plate arrived is gone for good."""
    import os
    assert os.path.exists("static/img/command-plate.webp")
    c, _uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    assert 'class="cz-plate" src="/static/img/command-plate.webp' in body
    boxes = re.findall(r'class="cz-screen" style="--x:([\d.]+)%;--y:([\d.]+)%;--w:([\d.]+)%;--h:([\d.]+)%"', body)
    assert len(boxes) == 3, boxes
    for x, y, w, h in boxes:
        for v in (x, y, w, h):
            assert "." in v and not v.endswith(".0"), "a round fraction is an unmeasured one: %s" % v
    # all three share one glass row
    assert len({(y, h) for _x, y, _w, h in boxes}) == 1
    css = io.open("static/css/command-zero.css", encoding="utf-8").read()
    for drawn in ("cz-rack-plate", "cz-screw", "cz-ear", "cz-rack-silk"):
        assert drawn not in css, "the drawn rack is still in the sheet: %s" % drawn
