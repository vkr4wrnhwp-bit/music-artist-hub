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

def _body(page):
    return page.split('class="rk rl"', 1)[1] if 'class="rk rl"' in page else page.split("<main", 1)[-1]


def test_an_empty_account_meets_the_page_from_zero_not_an_empty_plate():
    """The page from zero (owner's Releases spec + mockup, 2026-09-23). The
    plate waits for a release; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it. No arc, no twelve empty checks, no empty calendar, no
    countdown, no distribution status - and none of the plate's parts."""
    import re as _re
    c, _uid = _account()
    body = _body(c.get("/room/releases").get_data(as_text=True))
    assert "room-plate.webp" in body, "the rooms' photographed three-window plate"
    assert "releases-plate.webp" not in body, "the plate waits for a release"
    assert "rk-cine" not in body and "rk-reel-win" not in body and "rk-tick-win" not in body, "nothing rotates"
    assert "rk-pl-n" not in body and "cz-screen-v--fig" not in body and "cz-screen-v--none" not in body, "no reading"
    assert "rl-plan" not in body and 'id="rl-plan-h"' not in body, "no plan panel: nothing is planned yet"
    for gone in ("Nothing is being checked yet.", "No release chosen.", "Nothing is scheduled.",
                 "60-day", "14-day", "Days out", "rl-donut", "Release / Campaign"):
        assert gone not in body, gone
    # the three screens, the spec's words exactly, none of them a door
    for k, v in rl.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3 and 'class="cz-screen-v" href' not in body
    # the header: the spec's subtitle, the account kept, the one door - the builder ON A RELEASE
    assert rl.ZERO_SUBTITLE in body
    assert "Release Artist" in body, "the account field still says whose releases these are"
    door = rl.DOOR.replace("&", "&amp;")
    assert 'class="rk-cta" href="%s"' % door in body and "Create your first release" in body
    assert rl.DOOR.startswith("/links/new?type=release&"), "the campaign builder opened on a release: the release record itself"
    # the card, the first-save list in place, the four areas as doors
    assert "Start with one release" in body and "Create your first release plan" in body
    assert 'class="rl-z-btn" href="%s"' % door in body and "Create a release</a>" in body
    assert "What do I need before I start?" in body
    for item in rl.FIRST_SAVE:
        assert item in body, item
    assert "What Releases will organize" in body
    for _k, name, line, _card in rl.LENSES:
        assert name.replace("&", "&amp;") in body and line in body, name
    for href in ("/releases/autopilot?returnTo=/room/releases",
                 "/releases/autopilot?view=ready&amp;returnTo=/room/releases",
                 "/releases/autopilot?view=calendar&amp;returnTo=/room/releases",
                 "/distribution?returnTo=/room/releases"):
        assert 'class="rl-z-lens" href="%s"' % href in body, href
    # the five steps as education, numbered, Create lit
    for _k, name, line in rl.WORKFLOW:
        assert name in body and line.replace("&", "&amp;") in body, name
    rail = body.split("How Releases works")[1].split("Your release plan will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body and "rk-step--now" not in body
    assert '<span class="rk-ring" aria-hidden="true">1</span>' in rail and ">5</span>" in rail
    # the two empties in words, help, the drawer open under the four areas
    assert "Your release plan will appear here" in body and "Nothing is scheduled yet" in body
    assert "never shown as confirmed delivery." in body
    assert 'href="#rl-z-flow-h">How release checks work' in body and 'href="#rl-z-need">Release requirements' in body
    assert "Not sure whether your music is ready?" in body and 'href="/contact">Ask Street Banker' in body
    assert '<details class="rl-z-fold" open>' in body and "More Release tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    drawer = body.split('<details class="rl-z-fold"')[1]
    titles = _re.findall(r'<h3 class="rl-z-band">([^<]+)</h3>', drawer)
    assert titles == ["Release record", "Readiness checks", "Rollout &amp; calendar", "Distribution &amp; sync packs"], titles
    assert _re.findall(r'data-room-card="([a-z-]+)"', drawer) == [
        "autopilot", "release-check", "release-calendar", "rollout", "distribution", "sync-packs"]
    # no nought, no countdown, no delivery claim
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert not _re.search(r"\b0 (checks|tasks|days|releases)", text) and not _re.search(r"(?<![\d.])0%", text)
    for claim in ("Delivered", "delivered to", "is live in stores", "Available everywhere"):
        assert claim not in body, claim
    assert "Explore more tools" not in body and "The release arc" not in body


def test_the_saved_release_says_the_line_never_the_param_alone():
    c, uid = _account()
    page = c.get("/room/releases?from=releases-zero-state").get_data(as_text=True)
    assert rl.DONE_LINE not in page, "the param alone says nothing"
    _campaign(uid, days_out=30, title="First single")
    assert rl.DONE_LINE in c.get("/room/releases?from=releases-zero-state").get_data(as_text=True)
    assert rl.DONE_LINE not in c.get("/room/releases").get_data(as_text=True)
    assert rl.done_line("releases-zero-state", 0) == "" and rl.done_line(None, 2) == ""
    assert rl.done_line("releases-zero-state", 1) == rl.DONE_LINE


def test_new_account_is_no_release_and_no_rollout_at_all():
    assert rl.new_account([], None) is True
    assert rl.new_account([{"id": "c"}], None) is False
    assert rl.new_account([], 0) is False, "a rollout with nothing dated is still a rollout"
    assert rl.new_account([], 3) is False


def test_one_release_brings_the_working_room_back():
    c, uid = _account()
    _campaign(uid, days_out=30, title="First single")
    body = _body(c.get("/room/releases").get_data(as_text=True))
    assert "First single" in body and "Explore more tools" in body and "rk-step rk-step--now" in body
    assert "Start with one release" not in body and "rl-z-fold" not in body
    for k, v in rl.ZERO_RACK:
        assert v not in body, "the page from zero's words are gone: %s" % k


# --- the plate: the rooms' three windows (owner, 2026-09-23) ---------------

def _screens(body):
    """[(label, value, value classes, line under it)] off the rack."""
    import re
    rack = body.split('<section class="cz-rack"', 1)[1].split("</section>", 1)[0]
    out = []
    for li in re.findall(r'<li class="cz-screen"[^>]*>(.*?)</li>', rack, re.S):
        k = re.search(r'class="cz-screen-k">([^<]*)<', li).group(1)
        vm = re.search(r'class="(cz-screen-v[^"]*)"[^>]*>([^<]*)<', li)
        sm = re.search(r'class="cz-screen-s">([^<]*)<', li)
        out.append((k, vm.group(2), vm.group(1), sm.group(1) if sm else ""))
    return out


def test_the_working_room_draws_the_rooms_three_window_plate():
    """Every room's rack is the shorter three-window plate (owner,
    2026-09-23). The release clock is gone from the working page; its three
    figures sit on the three screens, each screen naming itself because the
    plate prints no names; the plan window is its own panel under it."""
    import re
    c, uid = _account()
    _campaign(uid, days_out=24, title="Plate single")
    page = c.get("/room/releases").get_data(as_text=True)
    body = _body(page)
    assert 'class="cz-plate" src="/static/img/room-plate.webp?v=' in body
    assert "releases-plate.webp" not in page, "the release clock is gone from the working page"
    assert "rk-pl-win" not in body and "rk-pl-img" not in body and "rk-reel" not in body
    # the plate's rules are linked on the working page, not only from zero
    assert "/static/css/command-zero.css?v=3" in page
    assert "/static/css/releases-room.css?v=6" in page
    got = _screens(body)
    assert [g[0] for g in got] == ["Checks passed", "Days to release", "Open tasks"], got
    checks, days, tasks = got
    assert re.fullmatch(r"\d+ / \d+", checks[1]) and "cz-screen-v--fig" in checks[2], checks
    assert checks[3] == "Read from your own records", checks
    when = (date.today() + timedelta(days=24)).isoformat()
    # the room counts from the UTC day, so the expected figure does too
    left = (date.fromisoformat(when) - datetime.now(timezone.utc).date()).days
    assert days[1] == str(left) and "cz-screen-v--fig" in days[2], days
    assert days[3] == rl.DATE_IS_A_PLAN == "A plan — not proof of delivery", days
    assert re.fullmatch(r"\d+", tasks[1]) and "cz-screen-v--fig" in tasks[2], tasks
    passed, total = (int(n) for n in checks[1].split(" / "))
    assert int(tasks[1]) == total - passed, "open is the total less the passed"
    # three screens, none of them a door
    assert body.count('<li class="cz-screen"') == 3
    assert not re.search(r'<a class="cz-screen-v', body)


def test_the_plan_panel_sits_under_the_plate_with_the_old_ribbon_in_it():
    """Nothing is lost: THE PLAN, the old clock's ribbon window, is its own
    panel directly under the plate (after the plate's own line), ahead of
    the arc and the tasks, and it carries the dated posts soonest first."""
    import re
    c, uid = _account()
    _campaign(uid, days_out=24, title="Plate single")
    cid = ros.create_campaign(uid, {"title": "Rollout one"})
    later = (date.today() + timedelta(days=9)).isoformat()
    sooner = (date.today() + timedelta(days=3)).isoformat()
    ros.add_post(cid, {"platform": "Instagram", "phase": "pre", "caption": "Cover reveal",
                       "scheduled_date": later})
    ros.add_post(cid, {"platform": "TikTok", "phase": "pre", "caption": "Teaser clip",
                       "scheduled_date": sooner})
    body = _body(c.get("/room/releases").get_data(as_text=True))
    rack = body.index('<section class="cz-rack"')
    foot = body.index('class="rk-foot rl-pl-foot"')
    plan = body.index('<section class="rk-panel rl-plan"')
    assert (rack < foot < plan < body.index('aria-label="The release arc"')
            < body.index('id="rl-tasks-h"')), "plate, its line, the plan - then the arc and the tasks"
    panel = body[plan:].split("</section>", 1)[0]
    assert 'id="rl-plan-h">The plan</h2>' in panel
    items = re.findall(r'<b class="rl-plan-w">([^<]*)</b>\s*<span class="rl-plan-t">([^<]*)</span>'
                       r'\s*<span class="rl-plan-s">([^<]*)</span>', panel)
    assert items == [(rl.short_day(sooner), "Teaser clip", "TikTok"),
                     (rl.short_day(later), "Cover reveal", "Instagram")], items
    assert "a scheduled day is a plan" in panel
    # the drops figure still rides on the plate's line, just above the plan it counts
    assert "Scheduled drops: <b>2</b>" in body[foot:plan]


def test_a_release_with_no_rollout_says_the_plan_is_empty_in_words():
    c, uid = _account()
    _campaign(uid, days_out=24, title="Plate single")
    body = _body(c.get("/room/releases").get_data(as_text=True))
    panel = body.split('<section class="rk-panel rl-plan"', 1)[1].split("</section>", 1)[0]
    assert "Nothing scheduled yet &mdash; a rollout puts its dated posts here." in panel
    assert "rl-plan-list" not in panel
    assert "Scheduled drops: <b>Not measured</b> (nothing scheduled yet)." in body


def test_the_screens_say_an_absence_in_words_never_a_nought():
    """No release chosen: Checks and Tasks are words, not 0 / 0 or 0 open.
    A release with no date: Days is words, not a countdown of 0."""
    none = rl.rack_screens([], None, "")
    assert [s["k"] for s in none] == ["Checks passed", "Days to release", "Open tasks"]
    for s in none:
        assert s["v"] == "Not measured" and s["none"] and not s["fig"], s
        assert "0" not in s["v"] and "0" not in s["sub"], s
    assert [s["sub"] for s in none] == ["No release chosen", "No release date set", "No release chosen"]
    checks = [("A", True, "", "/a", "release"), ("B", False, "why", "/b", "metadata")]
    undated = rl.rack_screens(checks, None, "")
    assert undated[1]["v"] == "Not measured" and undated[1]["sub"] == "No release date set"
    assert undated[0]["v"] == "1 / 2" and undated[2]["v"] == "1" and undated[2]["fig"]
    # a date nobody can read is no date either
    assert rl.rack_screens(checks, 5, "not a date")[1]["none"]


def test_a_release_date_is_a_plan_never_proof_of_delivery():
    checks = [("A", True, "", "/a", "release")] * 3
    ahead = rl.rack_screens(checks, 12, "2026-11-01")[1]
    assert (ahead["k"], ahead["v"]) == ("Days to release", "12")
    assert ahead["sub"] == "A plan — not proof of delivery"
    today = rl.rack_screens(checks, 0, "2026-11-01")[1]
    assert (today["k"], today["v"]) == ("Days to release", "Today"), (
        "release day is a word, not a countdown of 0")
    past = rl.rack_screens(checks, -5, "2026-11-01")[1]
    assert (past["k"], past["v"]) == ("Days past release", "5"), (
        "past the date it counts the other way under its own name, never -5")
    for s in (ahead, today, past):
        assert s["fig"] and "delivered" not in s["sub"].lower(), s
        assert "released" not in s["sub"].lower(), s


def test_every_line_on_the_screens_is_one_line_on_the_short_glass():
    """Measured with headless Chrome in Archivo at 12px (2026-09-23): a
    screen line that wraps to two lines is clipped by the glass at a 1280
    window, and the plan's first wording ("Planned Oct 17, 2026 · not proof
    of delivery") was. The widest line kept, "A plan — not proof of
    delivery", is 168px and fits its screen at every rack width the plate is
    drawn at; 30 characters is that line's length. Labels are uppercase and
    letterspaced: "DAYS PAST RELEASE" is 175px against a 183px screen."""
    checks = [("A", True, "", "/a", "release")] * 11 + [("B", False, "", "/b", "metadata")]
    cases = [rl.rack_screens(checks, d, "2026-11-01") for d in (40, 0, -12)]
    cases += [rl.rack_screens([], None, ""), rl.rack_screens(checks[:11], None, "")]
    for screens in cases:
        for s in screens:
            assert len(s["sub"]) <= 30, s["sub"]
            assert len(s["k"]) <= 17, s["k"]


def test_every_check_passed_is_a_measured_nought_with_its_reason():
    checks = [("A", True, "", "/a", "release"), ("B", True, "", "/b", "metadata")]
    tasks = rl.rack_screens(checks, 3, "2026-11-01")[2]
    assert (tasks["v"], tasks["sub"], tasks["fig"]) == ("0", "All 2 checks passed", True)


def test_the_old_plate_is_gone_from_the_code_and_the_sheet():
    """The release clock's windows, boxes and the reel its empty windows ran
    have nothing left to draw; the image file itself stays on disk."""
    import io
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("PLATE", "box", "plate_windows", "standby", "STANDBY_FILL"):
        assert not hasattr(rl, name), name
    out = rl.build({"id": "c", "title": "T"}, [], [], 3, "2026-11-01", None, [], [],
                   [{"id": "c"}], {})
    for key in ("windows", "plan_box", "standby"):
        assert key not in out, key
    assert len(out["screens"]) == 3 and out["ribbon"] == []
    css = io.open(os.path.join(here, "static", "css", "releases-room.css"), encoding="utf-8").read()
    for gone in (".rl-pl ", ".rl-pl-days", ".rl-pl-plan", ".rl-ribbon"):
        assert gone not in css, gone
    assert os.path.exists(os.path.join(here, "static", "img", "releases-plate.webp"))


def test_a_rollout_alone_brings_the_plate_back_too():
    """A rollout with dated posts and no release chosen is activity - the
    first standby hid its posts, and the page from zero must not either."""
    c, uid = _account()
    cid = ros.create_campaign(uid, {"title": "Rollout one"})
    ros.add_post(cid, {"platform": "TikTok", "phase": "pre", "caption": "Teaser clip",
                       "scheduled_date": (date.today() + timedelta(days=4)).isoformat()})
    body = _body(c.get("/room/releases").get_data(as_text=True))
    assert "Teaser clip" in body and "Start with one release" not in body


def test_a_seat_that_may_not_write_gets_no_door_and_an_area_it_cannot_open_is_words():
    cards = {"autopilot": ("/releases/autopilot", "M1", "Releases", "x"),
             "release-check": ("/releases/autopilot?view=ready", "M1", "Release check", "y"),
             "release-calendar": ("/releases/autopilot?view=calendar", "M1", "Release Calendar", "z"),
             "distribution": ("/distribution", "M1", "Distribution", "d"),
             "sync-packs": ("/sync/clearance-packs", "M1", "Sync Packs", "s")}
    z = rl.zero_page(can_add="seat", can_open=lambda href: not href.startswith("/distribution"), cards=cards)
    assert z["project"]["can"] == "seat"
    by = {l["key"]: l for l in z["lenses"]}
    assert by["distribution"]["href"] == "" and by["record"]["href"] == "/releases/autopilot"
    assert [t["key"] for t in z["bands"][-1]["tiles"]] == ["sync-packs"]
    assert rl.zero_page(cards=cards)["project"]["can"] is True


def test_a_failed_read_is_the_error_page_never_a_new_account(monkeypatch):
    """Owner's spec, Pass 1: loading and error detection. Before this the
    rollouts fell back to none-at-all on their own."""
    def boom(*_a, **_k):
        raise RuntimeError("releases: store down")
    monkeypatch.setattr(ros, "list_campaigns", boom)
    c, _uid = _account()
    r = c.get("/room/releases")
    assert r.status_code == 503
    page = r.get_data(as_text=True)
    assert "We could not load Releases" in page
    assert 'href="/room/releases"' in page and 'href="/releases/autopilot"' in page and "Open the release desk" in page
    assert "Start with one release" not in page and "room-plate" not in page


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


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {"autopilot": ("/releases/autopilot", "M1", "Releases", "x", "live"),
             "release-check": ("/releases/autopilot?view=ready", "M1", "Release check", "y", "live"),
             "release-calendar": ("/releases/autopilot?view=calendar", "M1", "Release Calendar", "z", "live"),
             "distribution": ("/distribution", "M1", "Distribution", "d", "live"),
             "sync-packs": ("/sync/clearance-packs", "M1", "Sync Packs", "s", "hidden")}
    z = rl.zero_page(cards=cards)
    tiles = {t["key"]: t for b in z["bands"] for t in b["tiles"]}
    assert tiles["sync-packs"]["state"] == "hidden" and tiles["autopilot"]["state"] != "hidden"


def test_the_owners_hidden_mark_stays_on_a_populated_room_tile():
    """The populated room's tiles carry the owner's mark too: the same
    pill the drawer from zero shows, by the same state."""
    cards = {"autopilot": ("/releases/autopilot", "M1", "Releases", "x", "live"),
             "rollout": ("/rollout", "M1", "Rollout Studio", "r", "hidden"),
             "sync-packs": ("/sync/clearance-packs", "M1", "Sync Packs", "s", "live"),
             "distribution": ("/distribution", "M1", "Distribution", "d", "live")}
    tiles = {t["key"]: t for t in rl.build(None, [], [], None, None, None, [], [], [], cards)["tiles"]}
    assert tiles["rollout"]["state"] == "hidden" and tiles["sync-packs"]["state"] != "hidden"
