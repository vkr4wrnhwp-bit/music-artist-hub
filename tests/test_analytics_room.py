"""The Analytics Room: the room's opening screen (owner's mockup, 2026-09-22).

This is the room that refuses to guess, so its tests are mostly about what
it will NOT say:

  a figure nobody measured reads "Not measured", in words, with the reason
  a null reading is never read as 0 - a zero is a measurement somebody took
  every reading carries the provider that took it and the day it was read
  a line needs two readings on DIFFERENT days before it is drawn
  nothing on the screen is read live from a provider
  income is not here at all (owner: "let analytics stay about measurements")
"""
import re
import uuid
from datetime import date, timedelta

import pytest

import analytics_room as ar
import app as appmod
import db as store

PW = "analytics-room-1"
TODAY = date(2026, 9, 22)


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account(name="Analytics Artist"):
    email = "anroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _snap(day, followers=None, popularity=None):
    return {"day": day, "followers": followers, "popularity": popularity}


def _pin(uid):
    """One connected source: the populated analyser, not the page from zero."""
    store.save_pulse_profile(uid, "spotify-artist-1", "Pinned Artist")


# --- a null is never a zero ------------------------------------------------

def test_a_null_reading_is_skipped_not_read_as_zero():
    """The snapshot columns were made nullable precisely because a provider
    that has stopped counting sends 0 for a field it no longer measures.
    Reading that back as a following of nobody is the bug the whole column
    change existed to prevent."""
    snaps = [_snap("2026-09-01", followers=1200),
             _snap("2026-09-02", followers=None)]
    value, day = ar.latest(snaps, "followers")
    assert value == 1200 and day == "2026-09-01", (
        "the newest row has no reading, so the newest READING is the older one")


def test_no_reading_at_all_is_none_rather_than_zero():
    assert ar.latest([_snap("2026-09-01")], "followers") == (None, "")
    assert ar.latest([], "followers") == (None, "")


# --- the three figures -----------------------------------------------------

def test_an_unmeasured_figure_is_words_and_carries_its_reason():
    figs = {f["key"]: f for f in ar.figures(None, None, None)}
    for key in ("visits", "followers", "listeners"):
        assert figs[key]["value"] == "Not measured", key
        assert figs[key]["measured"] is False
        assert figs[key]["why"], "an absence must name what would fill it"
    assert "Spotify" in figs["followers"]["why"]


def test_a_measured_figure_prints_the_number_and_drops_the_reason():
    figs = {f["key"]: f for f in ar.figures(1234, None, None)}
    assert figs["visits"]["value"] == "1,234"
    assert figs["visits"]["measured"] is True
    assert figs["visits"]["why"] == ""


def test_zero_is_a_measurement_and_is_printed_as_one():
    """0 visits is not the same as no tracking. Somebody counted."""
    figs = {f["key"]: f for f in ar.figures(0, None, None)}
    assert figs["visits"]["value"] == "0"
    assert figs["visits"]["measured"] is True


# --- readings carry their provenance ---------------------------------------

def test_every_reading_names_its_provider_and_the_day_it_was_read():
    r = ar.reading("Followers", 900, "Spotify for Artists", "2026-09-22", TODAY)
    assert r["provider"] == "Spotify for Artists"
    assert r["read"] == "2026-09-22"
    assert r["state"] == "fresh" and r["lamp"] == "fresh"


def test_an_old_reading_says_how_old_rather_than_passing_as_current():
    r = ar.reading("Followers", 900, "Spotify", "2026-09-10", TODAY)
    assert r["state"] == "stale"
    assert r["lamp"] == "12 days old"


def test_an_unmeasured_reading_shows_the_reason_where_the_date_would_be():
    r = ar.reading("Monthly listeners", None, "Soundcharts", "", TODAY,
                   why="Needs a metrics provider key")
    assert r["shown"] == ""
    assert r["state"] == "none" and r["lamp"] == "not measured"
    assert r["read"] == "Needs a metrics provider key"


# --- the path --------------------------------------------------------------

def test_the_path_counts_distinct_days_not_rows():
    """Two readings taken on one afternoon are one day of history and
    cannot draw a line between them."""
    same_day = [_snap("2026-09-01", 10), _snap("2026-09-01", 12)]
    assert ar.days_measured(same_day) == 1
    step = {s["key"]: s for s in ar.path(True, same_day, 0, 0)}["trending"]
    assert step["reached"] is False
    assert step["line"] == "Needs a second day"


def test_the_path_says_what_each_step_counted():
    snaps = [_snap("2026-09-01", 10), _snap("2026-09-02", 12)]
    steps = {s["key"]: s for s in ar.path(True, snaps, 2, 3)}
    assert steps["pinned"]["line"] == "Artist pinned"
    assert steps["measuring"]["line"] == "2 readings stored"
    assert steps["trending"]["line"] == "2 days of history"
    assert steps["compared"]["line"] == "2 peers"
    assert steps["read"]["line"] == "3 observations"
    assert all(s["reached"] for s in steps.values())


def test_an_account_with_nothing_has_every_step_unreached_and_says_so():
    steps = ar.path(False, [], 0, 0)
    assert not any(s["reached"] for s in steps)
    assert [s["line"] for s in steps] == [
        "Not pinned yet", "Nothing stored yet", "Needs a second day",
        "No peers yet", "Nothing to read yet"]


# --- the chart -------------------------------------------------------------

def test_a_line_needs_two_days_before_it_is_drawn():
    one = ar.chart([_snap("2026-09-01", 10)], "followers", "Followers", "Spotify")
    assert one["can_draw"] is False
    assert "two readings on different days" in one["why"]

    two = ar.chart([_snap("2026-09-01", 10), _snap("2026-09-02", 14)],
                   "followers", "Followers", "Spotify")
    assert two["can_draw"] is True and two["why"] == ""
    assert two["low"] == 10 and two["high"] == 14


def test_the_chart_skips_null_readings_rather_than_plotting_them_at_zero():
    got = ar.chart([_snap("2026-09-01", 10), _snap("2026-09-02", None),
                    _snap("2026-09-03", 14)], "followers", "Followers", "Spotify")
    assert [p["value"] for p in got["points"]] == [10, 14]
    assert got["low"] == 10, "a null must not drag the axis to zero"


# --- the tiles -------------------------------------------------------------

def test_the_room_closes_with_the_three_tiles_the_mockup_draws():
    cards = {"scores": ("/qualification", "M1", "Scores", "growth and trust"),
             "artist-twin": ("/artist-twin", "M1", "Artist Twin", "writing agent"),
             "reports": ("/reports", "M1", "Reports", "exports")}
    out = ar.build(None, [], [], None, None, [], cards, today=TODAY)
    assert [t["key"] for t in out["tiles"]] == ["scores", "artist-twin", "reports"]


def test_a_seat_that_cannot_open_a_page_is_not_shown_its_tile():
    cards = {"scores": ("/qualification", "M1", "Scores", "x"),
             "reports": ("/reports", "M1", "Reports", "y")}
    out = ar.build(None, [], [], None, None, [], cards, today=TODAY,
                   can_open=lambda href: href != "/reports")
    assert [t["key"] for t in out["tiles"]] == ["scores"]


# --- the page itself -------------------------------------------------------

def test_an_empty_account_meets_the_page_from_zero_not_an_empty_analyser():
    """The page from zero (owner's Analytics spec + mockup, 2026-09-23). The
    analyser waits for a source; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it. No chart frame, no date filter, no comparison, no
    nought, no "Not measured" - and none of the analyser's parts."""
    import re as _re
    c, _uid = _account()
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "room-plate.webp" in body, "the rooms' photographed three-window plate"
    assert "analytics-plate.webp" not in body, "the analyser waits for a source"
    assert "rk-cine" not in body and "rk-reel-win" not in body, "nothing rotates"
    assert "an-plot" not in body and "rk-pl-n" not in body, "no chart frame, no reading"
    assert 'class="an-read-v' not in body, "no reading row, measured or not"
    assert "Nobody pinned" not in body and "Not pinned yet" not in body
    # the three screens, the spec's words exactly, none of them a door
    for k, v in ar.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3 and 'class="cz-screen-v" href' not in body
    # the header: the spec's subtitle and its one door, carrying the way back
    assert "Turn connected data into clear next moves." in body
    assert 'class="rk-cta" href="%s"' % ar.CONNECT_DOOR in body and "Connect your first source" in body
    assert "Pin your artist" not in body
    # the card and the four lenses, each a door to the room that owns the next step
    assert "Start with a trusted source" in body and "Connect your first data source" in body
    assert 'class="an-z-btn" href="%s"' % ar.CONNECT_DOOR in body and ">View connections<" in body
    assert "You will see what each source can provide before connecting it." in body
    assert "What Analytics will organize" in body
    for _k, name, line, href, _rooms in ar.LENSES:
        assert name in body and line in body, name
        assert 'class="an-z-lens" href="%s?returnTo=/room/analytics"' % href in body, href
    # the five steps as education, Connect lit
    for _k, name, line in ar.WORKFLOW:
        assert name in body and line in body, name
    rail = body.split("How Analytics works")[1].split("Your insights will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body
    # the two empties in words, their links, help, the drawer open
    assert "Your insights will appear here" in body and "Nothing is measured yet" in body
    assert "It will not turn missing data into zero." in body
    assert 'href="#an-z-lang-h">How data coverage works' in body
    assert 'href="%s">Supported sources' % ar.CONNECT_DOOR in body
    assert "Not sure what to connect first?" in body and 'href="/contact">Ask Street Banker' in body
    assert '<details class="an-z-fold" open>' in body and "More Analytics tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    assert _re.findall(r'data-room-card="([a-z-]+)"', body) == list(ar.ZERO_TILES)
    # no date filter, no comparison, no export, no nought
    zone = body.split("Start with a trusted source", 1)[1].split("More Analytics tools", 1)[0]
    for control in ('name="range"', 'name="period"', "Compare", "Export", "Last 30 days", "<select"):
        assert control not in zone, control
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert not _re.search(r"(?<![\d.])0%", text) and not _re.search(r"\b0 (visits|followers|listeners)", text)
    assert "Explore more tools" not in body and "The measurement path" not in body


def test_connections_carries_the_way_back_and_the_saved_source_says_the_line():
    """The door opens Connections with returnTo=/room/analytics?from=connect;
    the shell's back-link brings the person back, and the room says the
    sentence only once a source is really on file."""
    import urllib.parse as _u
    assert ar.CONNECT_DOOR.startswith("/connections?returnTo=")
    back = _u.unquote(ar.CONNECT_DOOR.split("returnTo=", 1)[1])
    assert back == "/room/analytics?from=connect"
    c, uid = _account()
    page = c.get("/connections?returnTo=" + _u.quote(back, safe="")).get_data(as_text=True)
    assert 'href="%s"' % back in page, "the shell's back-link carries the query"
    assert ar.DONE_LINE not in c.get(back).get_data(as_text=True), "the param alone says nothing"
    _pin(uid)
    assert ar.DONE_LINE in c.get(back).get_data(as_text=True)
    assert ar.DONE_LINE not in c.get("/room/analytics").get_data(as_text=True)


def test_the_done_line_is_said_by_the_record_not_the_param():
    assert ar.done_line("connect", False) == ""
    assert ar.done_line(None, True) == ""
    assert ar.done_line("pin", True) == ""
    assert ar.done_line("connect", True) == ar.DONE_LINE


def test_new_account_is_empty_on_every_count_the_room_reads():
    assert ar.new_account(None, [], None, []) is True
    assert ar.new_account({"artist_name": "X"}, [], None, []) is False
    assert ar.new_account(None, [_snap("2026-03-01", 10)], None, []) is False
    assert ar.new_account(None, [], 0, []) is False, "a counted zero is a measurement"
    assert ar.new_account(None, [], None, [{"artist_id": "p"}]) is False


def test_one_pinned_artist_brings_the_analyser_back_untouched():
    c, uid = _account()
    _pin(uid)
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    # Since 2026-09-23 the working room draws the rooms' shared plate too;
    # what separates it from the page from zero is the readings on it.
    assert "room-plate.webp?v=" in body and "analytics-plate.webp" not in body
    assert "Pinned Artist" in body and "Change artist" in body
    assert "Not measured" in body, "the analyser's own words for what nobody measured"
    assert "Start with a trusted source" not in body and "an-z-fold" not in body
    for _k, words in ar.ZERO_RACK:
        assert words not in body, "the page from zero's screens: %s" % words
    assert "Explore more tools" in body


# --- the working page on the rooms' shared plate (owner, 2026-09-23) -------

def _working(followers_by_day=()):
    """A pinned account with Spotify readings on the given days."""
    c, uid = _account()
    _pin(uid)
    for day, followers in followers_by_day:
        store.record_pulse_snapshot(uid, followers, 40, None, day=day)
    page = c.get("/room/analytics").get_data(as_text=True)
    return page, page.split('class="rk an"', 1)[1]


def _screens(body):
    """(label, value classes, value, line under it) for each screen."""
    rack = body.split('<section class="cz-rack"', 1)[1].split("</section>", 1)[0]
    return re.findall(
        r'<li class="cz-screen"[^>]*>\s*<span class="cz-screen-k">([^<]*)</span>\s*'
        r'<span class="(cz-screen-v[^"]*)">([^<]*)</span>\s*'
        r'(?:<span class="cz-screen-s">([^<]*)</span>)?', rack)


def test_the_screens_are_the_three_figures_named_and_an_absence_is_words():
    """The shared plate prints no names, so every screen says what it is;
    the line under it is what the old window printed there - where the
    reading came from, or what would fill it."""
    visits, followers, listeners = ar.rack_screens(ar.figures(None, 0, None))
    assert [s["k"] for s in (visits, followers, listeners)] == [
        "Link visits", "Followers", "Monthly listeners"]
    assert visits["v"] == "Not measured" and visits["none"] and not visits["fig"]
    assert visits["sub"] == "No smart links tracked yet"
    assert listeners["v"] == "Not measured" and listeners["sub"] == "Needs a metrics provider"
    assert followers["v"] == "0" and followers["fig"] and not followers["none"], (
        "a counted zero is a measurement, and is set as one")
    assert followers["sub"] == "From the connected provider"
    assert not any(s.get("href") for s in (visits, followers, listeners)), "a reading is not a door"


def test_the_working_page_draws_the_rooms_plate_with_three_named_screens():
    page, body = _working([("2026-09-10", 1200), ("2026-09-11", 1340)])
    assert "command-zero.css?v=4" in page and "analytics-room.css?v=4" in page
    assert 'class="cz-plate" src="/static/img/room-plate.webp?v=' in body
    assert "analytics-plate.webp" not in body, "the old four-window analyser is gone"
    assert body.count('<li class="cz-screen"') == 3
    got = _screens(body)
    assert [g[0] for g in got] == ["Link visits", "Followers", "Monthly listeners"]
    by = {g[0]: g for g in got}
    assert by["Followers"][2] == "1,340" and "cz-screen-v--fig" in by["Followers"][1]
    assert by["Followers"][3] == "From the connected provider"
    for label, why in (("Link visits", "No smart links tracked yet"),
                       ("Monthly listeners", "Needs a metrics provider")):
        assert by[label][2] == "Not measured" and "cz-screen-v--none" in by[label][1], label
        assert by[label][3] == why, label
    # none of the old plate's parts, and no nought anywhere on the glass
    for part in ("rk-pl-win", "rk-pl-sr", "rk-reel", "an-pl-trend"):
        assert part not in body, part
    assert not any(g[2] == "0" for g in got)
    assert 'href="/signal' not in body, "Signal is internal: no door to it from a room"


def test_the_trend_is_its_own_panel_directly_under_the_plate():
    """Nothing lost: the line the old analyser drew in its long upper
    screen is the panel under the plate, with its measured range and its
    first and last day printed as the axis."""
    _page, body = _working([("2026-09-10", 1200), ("2026-09-11", 1340)])
    rack, trend = body.index('<section class="cz-rack"'), body.index('<section class="rk-panel an-trend"')
    assert rack < trend < body.index('id="an-path-h"')
    between = body[body.index("</section>", rack):trend]
    assert 'class="rk-foot an-pl-foot"' in between and "<section" not in between.split("</section>", 1)[1], (
        "only the plate's own foot line sits between the plate and the trend")
    panel = body[trend:body.index("</section>", trend)]
    assert "Followers over time" in panel and "Read by Spotify" in panel
    assert '<polyline class="an-plot-line"' in panel
    for label in ("1,340", "1,200", "2026-09-10", "2026-09-11"):
        assert label in panel, label
    assert "an-plot" not in body[rack:body.index("</section>", rack)], "no chart on the glass"


def test_one_reading_is_no_line_and_the_trend_panel_says_why():
    _page, body = _working([("2026-09-10", 1200)])
    trend = body.index('<section class="rk-panel an-trend"')
    assert body.index('<section class="cz-rack"') < trend
    panel = body[trend:body.index("</section>", trend)]
    assert "Needs two readings on different days before it can draw." in panel
    assert "Read by" not in panel, "no line, so nothing claims to have been read into one"
    assert "an-plot" not in body, "one point is not a line"
    assert {g[0]: g[2] for g in _screens(body)}["Followers"] == "1,200"


def test_the_trend_prints_its_measured_range_and_its_first_and_last_day():
    got = ar.chart([_snap("2026-09-01", 1200), _snap("2026-09-02", None),
                    _snap("2026-09-03", 1340)], "followers", "Followers", "Spotify")
    assert got["axis"] == {"high": "1,340", "low": "1,200",
                           "first": "2026-09-01", "last": "2026-09-03"}
    assert ar.chart([_snap("2026-09-01", 10)], "followers", "F", "S")["axis"] is None
    assert ar.chart([_snap("2026-09-01", 10), _snap("2026-09-01", 12)],
                    "followers", "F", "S")["axis"] is None, "one afternoon is one day"


def test_a_seat_that_may_not_write_gets_no_door_and_a_lens_it_cannot_open_is_words():
    z = ar.zero_page(can_add="seat", can_open=lambda href: href != "/room/business")
    assert z["project"]["can"] == "seat"
    by = {l["key"]: l for l in z["lenses"]}
    assert by["revenue"]["href"] == "" and by["audience"]["href"] == "/room/fans"
    assert ar.zero_page()["project"]["can"] is True


def test_a_failed_read_is_the_error_page_never_a_new_account(monkeypatch):
    """Owner's spec: a loading failure must never be mistaken for an empty
    account. Before this the peers and the link counts each had their own
    fallback to nothing, which read as a fresh account."""
    def boom(*_a, **_k):
        raise RuntimeError("analytics: store down")
    monkeypatch.setattr(store, "list_pulse_peers", boom)
    c, _uid = _account()
    r = c.get("/room/analytics")
    assert r.status_code == 503
    page = r.get_data(as_text=True)
    assert "We could not load Analytics" in page
    assert 'href="/room/analytics"' in page and 'href="/connections"' in page and "Review connections" in page
    assert "Connect your first data source" not in page and "room-plate" not in page


def test_the_reason_a_line_cannot_be_drawn_is_shown_once_there_are_readings():
    """The chart's own explanation, in the state it belongs to: something
    measured, but not yet on two different days."""
    got = ar.chart(
        [{"day": "2026-03-01", "followers": 1200}], "followers", "Followers", "Spotify")
    assert got["can_draw"] is False
    assert "two readings on different days" in got["why"].lower()


def test_the_room_never_shows_income(monkeypatch):
    """Owner, 2026-09-22: "let analytics stay about measurements." Royalties
    live in the Business room; a panel here would put the same figures in a
    second room."""
    c, _uid = _account()
    page = c.get("/room/analytics").get_data(as_text=True)
    body = page.split('class="rk an"', 1)[1].split("</div>\n{% endblock %}")[0]
    for claim in ("Income at a glance", "Total earnings", "Royalties at a glance"):
        assert claim not in body, claim


def test_the_room_reads_nothing_live_from_a_provider(monkeypatch):
    """A room door is opened constantly, and the Pulse page already spends
    and caches the provider calls. If this screen ever starts calling out,
    this test says so."""
    import spotify_provider as spotify
    called = []
    monkeypatch.setattr(spotify, "artist_pulse",
                        lambda *a, **k: called.append(a) or None)
    c, _uid = _account()
    assert c.get("/room/analytics").status_code == 200
    assert called == [], "the room screen called a provider"


def test_uncollected_insight_opens_the_publishing_room():
    """Owner, 2026-09-22. "See what's missing" pointed at /publishing,
    which redirects to /royalties#streams - the very page the "Income
    breakdown" insight beside it already opens. Two promises, one page.
    It opens the Publishing ROOM now, whose plate reads MONEY GOING
    UNCOLLECTED."""
    import io as _io
    src = _io.open("insights_engine.py", encoding="utf-8").read()
    i = src.index("See what's missing")
    near = src[max(0, i - 400):i]
    assert '"/room/publishing"' in near, near[-160:]
    assert '"/publishing"' not in near, "still the redirect, not the room"


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {k: ("/" + k, "M1", k.title(), "desc", "hidden" if k == "artist-twin" else "live")
             for k in ar.ZERO_TILES}
    tiles = {t["key"]: t for t in ar.build(None, [], [], None, None, [], cards, zero=True)["zero_tiles"]}
    assert tiles["artist-twin"]["state"] == "hidden" and tiles["pulse"]["state"] != "hidden"


def test_the_owners_hidden_mark_stays_on_a_populated_room_tile():
    """The populated room's tiles carry the owner's mark too: the same
    pill the drawer from zero shows, by the same state."""
    cards = {k: ("/" + k, "M1", k.title(), "desc", "hidden" if k == "reports" else "live")
             for k in ("scores", "artist-twin", "reports")}
    tiles = {t["key"]: t for t in ar.build(None, [], [], None, None, [], cards, today=TODAY, zero=False)["tiles"]}
    assert tiles["reports"]["state"] == "hidden" and tiles["scores"]["state"] != "hidden"


# --- the demo account is the showcase, never the page from zero -----------

DEMO_LOGINS = ("demo@streetbanker.io", "demo-pro@streetbanker.io",
               "demo-artist@streetbanker.io")


@pytest.mark.parametrize("email", DEMO_LOGINS)
def test_every_demo_login_sees_the_showcase_never_the_page_from_zero(email):
    """Owner's ruling: the demo account is the showcase, never the page
    from zero (audit analytics-2, 2026-09-23). No demo login had a pinned
    artist, a reading or a peer, so every one of them got "Start with a
    trusted source" under a "Sample data" lamp with no sample anywhere on
    the page. The example is labelled, names its sample source on every
    reading, and offers the demo no write door."""
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": email, "password": "sweep"})
    r = demo.get("/room/analytics")
    assert r.status_code == 200, email
    body = r.get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Start with a trusted source" not in body and "an-z-" not in body, "the page from zero"
    assert ar.CONNECT_DOOR not in body
    assert "Sample data" in body and "generated for the example" in body
    got = {g[0]: g for g in _screens(body)}
    for label in ("Link visits", "Followers", "Monthly listeners"):
        assert "cz-screen-v--fig" in got[label][1], "%s carries a sample reading" % label
    assert got["Monthly listeners"][3] == "From %s" % ar.SHOWCASE_SOURCE
    assert "Read by %s" % ar.SHOWCASE_SOURCE in body and '<polyline class="an-plot-line"' in body
    # a shared demo is never offered a write door
    assert "Change artist" not in body and "Pin your artist" not in body


def test_the_showcase_is_labelled_dated_and_never_a_nought():
    sc = ar.showcase(today=TODAY, artist_name="Synthwave Surfer")
    out = ar.build(sc["profile"], sc["snaps"], sc["peers"], sc["visits"], None, [],
                   {}, today=TODAY, sample=True, zero=False, metrics=sc["metrics"])
    assert out["sample"] is True and out["idle"] is False and out["artist"] == "Synthwave Surfer"
    rows = {r["label"]: r for r in out["readings"]}
    for label in ("Followers", "Monthly listeners"):
        assert rows[label]["provider"] == ar.SHOWCASE_SOURCE and rows[label]["read"] == TODAY.isoformat(), label
        assert rows[label]["state"] == "fresh", label
    assert all(f["measured"] and f["value"] != "0" for f in out["figures"])
    assert out["chart"]["can_draw"] and out["chart"]["provider"] == ar.SHOWCASE_SOURCE
    assert ar.days_measured(sc["metrics"]["snapshots"]) == len(sc["metrics"]["snapshots"]) > 1
    assert all(s["reached"] for s in out["path"][:4])


def test_a_real_account_never_sees_the_sample_lamp():
    c, _uid = _account()
    assert "Sample data" not in c.get("/room/analytics").get_data(as_text=True), "the page from zero"
    c, uid = _account()
    _pin(uid)
    assert "Sample data" not in c.get("/room/analytics").get_data(as_text=True), "the working room"
