"""The Releases Room: the room's opening screen (owner's mockup, 2026-09-22).

Three of this room's cards were one page with a different query string, so
they are this screen now. The honesty rules these lock:

  a figure nothing measured reads "Not measured", never 0
  nothing scheduled ANYWHERE is a different statement from nothing due, and
    the two read differently
  the stage is the TIGHTEST window still ahead of the release date
  a task's due day appears only where the plan window it belongs to has one
  the three merged pages are not tiles; the three separate pages are
  nothing on the page says a release was delivered
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import app as appmod
import db as store
import links_store as mls
import releases_room as rl
import rollout_store as ros

PW = "releases-room-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account(name="Release Artist"):
    email = "rlroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _campaign(uid, days_out=None, title="Test single"):
    body = {"title": title, "artist_name": "Release Artist"}
    if days_out is not None:
        body["release_date"] = (date.today() + timedelta(days=days_out)).isoformat()
    return mls.create_campaign(uid, "rl-%s" % uuid.uuid4().hex[:8], body)


# --- the stage, which was inverted once and must not invert again ----------

def test_the_stage_is_the_tightest_window_still_ahead_of_the_date():
    """Ten days out is the 14-day plan, not the 60-day one it started in.
    This is the bug this function was written with: reading the stages in
    order and keeping the first match put a release a week away back at the
    beginning of its own arc."""
    assert rl.stage_now(90) == "60"
    assert rl.stage_now(60) == "60"
    assert rl.stage_now(45) == "60", (
        "45 days out the 30-day window has not opened yet, so the 60-day "
        "plan is still the tightest one ahead")
    assert rl.stage_now(30) == "30"
    assert rl.stage_now(10) == "14"
    assert rl.stage_now(7) == "week"
    assert rl.stage_now(3) == "week", "three days out is still release week"
    assert rl.stage_now(0) == "after", "release day itself begins post-release"
    assert rl.stage_now(-5) == "after"


def test_no_release_date_means_no_stage_at_all():
    """Not a guess at one. Without a date the arc has nowhere to put a mark,
    so every step reads as ahead and none of them claims to be now."""
    assert rl.stage_now(None) is None
    states = {s["state"] for s in rl.arc(None)}
    assert states == {"ahead"}, states


def test_the_arc_marks_one_stage_now_and_everything_before_it_done():
    got = [(s["key"], s["state"]) for s in rl.arc(10)]
    assert got == [("60", "done"), ("30", "done"), ("14", "now"),
                   ("week", "ahead"), ("after", "ahead")], got


# --- the due day, which is blank rather than invented ----------------------

def test_a_due_day_is_the_check_s_window_counted_back_from_release_day():
    """One step, and anyone can check it: metadata is wanted 30 days out, the
    release is 1 November, so it is due 2 October."""
    assert rl.due_on("metadata", "2026-11-01") == "2026-10-02"
    assert rl.due_on("smart_link", "2026-11-01") == "2026-10-18"  # 14 days out
    assert rl.due_on("smart_link", "") == "", "no release date, no day"
    assert rl.due_on("smart_link", None) == ""
    assert rl.due_on("smart_link", "not a date") == ""
    assert rl.due_on("nothing_we_know", "2026-11-01") == "", (
        "a check with no window gets no day: a date nobody can trace is worse "
        "than a blank, because somebody will work to it")


def test_an_overdue_day_is_still_shown():
    """A release ten days away still shows metadata as having been due 30 days
    out. Hiding a date because it has passed would be the kinder lie."""
    assert rl.due_on("metadata", "2026-01-20") == "2025-12-21"


# --- the three figures ----------------------------------------------------

def test_a_figure_nothing_measured_reads_not_measured_and_never_zero():
    head = rl.headline([], None, None)
    assert [f["value"] for f in head] == ["Not measured"] * 3
    assert "0" not in [f["value"] for f in head]


def test_nothing_scheduled_anywhere_reads_differently_from_nothing_due():
    """The distinction _release_drops exists for. No rollout at all cannot be
    counted, so it says so; a rollout whose posts carry no dates HAS been
    counted, and 0 is the honest answer."""
    none_at_all = rl.headline([], None, None)[2]
    counted_zero = rl.headline([], None, 0)[2]
    assert none_at_all["value"] == "Not measured"
    assert none_at_all["sub"] == "Nothing scheduled yet"
    assert counted_zero["value"] == "0"
    assert counted_zero["sub"] == "Across all campaigns"


def test_the_checks_figure_is_passed_over_total_not_a_score():
    checks = [("A", True, "", "/a", "release"), ("B", False, "why", "/b", "metadata")]
    assert rl.headline(checks, 5, 2)[0]["value"] == "1 / 2"


# --- the tiles -----------------------------------------------------------

def test_the_merged_pages_are_not_tiles_and_the_separate_ones_are():
    """Autopilot, the calendar and the ready view ARE this screen, so a tile
    to any of them would be the double-door the rooms audit ruled out. The
    three genuinely separate pages stay."""
    cards = {"autopilot": ("/releases/autopilot", "M1", "Releases", "desk"),
             "release-calendar": ("/releases/autopilot?view=calendar", "M1", "Calendar", "c"),
             "release-check": ("/releases/autopilot?view=ready", "M1", "Release check", "r"),
             "rollout": ("/rollout", "M1", "Rollout Studio", "one plan"),
             "sync-packs": ("/sync/packs", "M1", "Sync Packs", "packs"),
             "distribution": ("/distribution", "M1", "Distribution", "stores")}
    got = [t["key"] for t in rl.build(None, [], [], None, None, None, [], [],
                                      [], cards)["tiles"]]
    assert got == ["rollout", "sync-packs", "distribution"], got


def test_a_seat_that_cannot_open_a_page_is_not_shown_its_tile():
    cards = {"rollout": ("/rollout", "M1", "Rollout Studio", "one plan"),
             "distribution": ("/distribution", "M1", "Distribution", "stores")}
    out = rl.build(None, [], [], None, None, None, [], [], [], cards,
                   can_open=lambda href: href != "/distribution")
    assert [t["key"] for t in out["tiles"]] == ["rollout"]


# --- the page itself -----------------------------------------------------

def test_an_empty_account_is_told_in_words_and_shown_no_zero_figures():
    c, _uid = _account()
    page = c.get("/room/releases").get_data(as_text=True)
    assert ">Releases</h1>" in page
    # Owner, 2026-09-22: a plate whose every window reads "Not measured"
    # is worse than no plate, so an account that has measured nothing
    # now meets the STANDBY - words about what will fill each window.
    # The zero rule is unchanged and still checked below.
    # The caption standby became the DISPLAY the same afternoon (owner:
    # "slot machine-y" - the big window sequences the room's features,
    # the small ones are a reel, a hint and a ticker, never a caption).
    # The zero rule is unchanged and still checked.
    import re as _re
    _f = _re.findall(r"rk-cine-frame[^>]*>\s*(?:<img[^>]*>\s*)?<b[^>]*>([^<]*)", page)
    assert _f == ['Rollout Studio', 'Release Checks', 'Sync Packs', 'Distribution'], _f
    assert page.count("rk-reel-win") == 1 and page.count("rk-tip-win") == 1 and page.count("rk-tick-win") == 1
    assert "Create a release" in page, "the hero pill is the way in"
    assert "rk-pl-n" not in page, "no reading is drawn while nothing is measured"
    assert "Nothing is being checked yet." in page
    assert "No release chosen." in page
    assert "Nothing is scheduled." in page


def test_a_release_ten_days_out_puts_the_arc_on_the_14_day_plan():
    c, uid = _account()
    _campaign(uid, days_out=10, title="Ten days out")
    page = c.get("/room/releases").get_data(as_text=True)
    assert "Ten days out" in page
    # The rail is the shared one now (room-kit.css), so the state class is
    # the kit's rk-step--now rather than this room's own.
    assert 'rk-step rk-step--now' in page
    now = page.split('rk-step rk-step--now')[1].split('</li>')[0]
    assert "14-day plan" in now, now[:400]
    assert "Finalise and confirm" in now


def test_a_release_with_no_date_says_so_rather_than_guessing_one():
    c, uid = _account()
    _campaign(uid, days_out=None, title="No date yet")
    page = c.get("/room/releases").get_data(as_text=True)
    assert "No release date set" in page, "the days figure names what is missing"
    assert "No release date" in page, "and so does the release panel"
    assert 'rk-step rk-step--now' not in page, (
        "no date, no now: the arc cannot place a release it has no day for")


def test_the_room_never_says_a_release_was_delivered():
    """Delivery is the distributor's to confirm and this application cannot
    see it. The page says that in as many words."""
    c, uid = _account()
    _campaign(uid, days_out=20)
    page = c.get("/room/releases").get_data(as_text=True)
    assert "that is the distributor&#39;s" in page or "distributor" in page
    for claim in ("Delivered", "delivered to", "is live in stores",
                  "Available everywhere"):
        assert claim not in page, claim


def test_a_dated_rollout_post_appears_on_the_page_and_an_undated_one_does_not():
    c, uid = _account()
    cid = ros.create_campaign(uid, {"title": "Rollout one"})
    when = (date.today() + timedelta(days=4)).isoformat()
    ros.add_post(cid, {"platform": "TikTok", "phase": "pre",
                       "caption": "Teaser clip", "scheduled_date": when})
    ros.add_post(cid, {"platform": "Instagram", "phase": "pre",
                       "caption": "No day on this one", "scheduled_date": ""})
    page = c.get("/room/releases").get_data(as_text=True)
    # The rail carries his short label ("Sep 26"), not the stored ISO day.
    assert "Teaser clip" in page and rl.short_day(when) in page
    assert "No day on this one" not in page, (
        "there is no day to show it on, so the calendar does not show it")
    assert "Not measured" in page  # the other two figures, still unmeasured
