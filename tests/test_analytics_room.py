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
    assert "Explore more tools" not in body
    # The rendered heading is "Measurement path"; the old check looked for
    # "The measurement path", which is only a template comment and could
    # never fail (audit analytics-15).
    assert "Measurement path" not in body and 'id="an-path-h"' not in body


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
    # "Review connections" carries the way back (audit analytics-11); the
    # bare /connections this pinned dropped it.
    assert 'href="/room/analytics"' in page and 'href="/connections?returnTo=%2Froom%2Fanalytics"' in page
    assert "Review connections" in page
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
    c, uid = _account()
    _pin(uid)
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 2640.0, "period": "2026-01"}])
    page = c.get("/room/analytics").get_data(as_text=True)
    body = page.split('class="rk an"', 1)[1]
    # the populated room, never the page from zero (audit analytics-15: this
    # used to render a fresh account, which is always the page from zero)
    assert 'id="an-path-h"' in body and "Start with a trusted source" not in body
    for claim in ("Income at a glance", "Total earnings", "Royalties at a glance", "$2,640"):
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


# --- the audit of 2026-09-23 ---------------------------------------------

import html as _html
import io as _io
import json as _json
import urllib.parse as _u

import command_center as cc
import signal_providers as sp


def _links(page):
    """(href, text) for every action button on Connections."""
    return [(_html.unescape(h), t.strip()) for h, t in re.findall(
        r'<a href="([^"]*)" class="sb-btn sb-btn-secondary sb-btn-sm">([^<]*)', page)]


def _back(page):
    """Where the shell's back link goes."""
    return _html.unescape(re.search(r'<a href="([^"]*)" id="sb-room-back"', page).group(1))


def test_the_pin_path_through_connections_comes_back_with_the_done_line(monkeypatch):
    """Audit analytics-1: every action on Connections was a bare path, so
    after pinning on Artist Pulse its back link was plain /room/analytics
    and the done line never showed on the real trip."""
    import spotify_provider as spotify
    monkeypatch.setattr(spotify, "artist_pulse", lambda *a, **k: None)
    c, uid = _account()
    page = c.get(ar.CONNECT_DOOR).get_data(as_text=True)
    links = _links(page)
    assert links and all("returnTo=" in h for h, _t in links), links
    pulse = [h for h, t in links if t.startswith("Link on Artist Pulse")][0]
    assert _u.unquote(pulse.split("returnTo=", 1)[1]) == "/room/analytics?from=connect"
    r = c.post("/pulse/select", data=_json.dumps({"id": "sp-1", "name": "Pinned Artist"}),
               content_type="application/json")
    assert r.get_json()["ok"]
    back = _back(c.get(pulse).get_data(as_text=True))     # the page reloads in place
    assert back == "/room/analytics?from=connect"
    assert ar.DONE_LINE in c.get(back).get_data(as_text=True)
    # a fragment stays after the query
    mlc = [h for h, t in links if "MLC" in t]
    assert not mlc or ("?returnTo=" in mlc[0] and mlc[0].endswith("#mlc"))


def test_the_demo_showcase_names_no_write_door_and_no_zero_lamp():
    """The Sample data lamp is drawn only over the example's readings."""
    c, _uid = _account()
    head = c.get("/room/analytics").get_data(as_text=True).split('class="rk-hero"', 1)[1].split("</section>", 1)[0]
    assert "Sample data" not in head


@pytest.mark.parametrize("target", [
    (store, "get_pulse_profile"), (store, "list_pulse_snapshots"), (store, "list_pulse_peers"),
    (store, "get_statements"), (cc, "list_actions")])
def test_every_failed_read_is_the_error_page(monkeypatch, target):
    """Audit analytics-14(3): each read the page is decided on, not only
    the peers, is the error page when it fails."""
    def boom(*_a, **_k):
        raise RuntimeError("analytics: store down")
    c, _uid = _account()
    monkeypatch.setattr(target[0], target[1], boom)
    r = c.get("/room/analytics")
    assert r.status_code == 503 and "We could not load Analytics" in r.get_data(as_text=True)


def test_a_failed_link_count_is_the_error_page(monkeypatch):
    import links_store
    def boom(*_a, **_k):
        raise RuntimeError("links down")
    c, _uid = _account()
    monkeypatch.setattr(links_store, "account_event_counts", boom)
    assert c.get("/room/analytics").status_code == 503


def test_the_error_page_s_second_door_works_and_keeps_the_way_back(monkeypatch):
    """Audit analytics-11(b): with the profile unreadable, 'Review
    connections' answered 500 and dropped the way back."""
    def boom(*_a, **_k):
        raise RuntimeError("profiles down")
    c, _uid = _account()
    monkeypatch.setattr(store, "get_pulse_profile", boom)
    page = c.get("/room/analytics").get_data(as_text=True)
    assert 'href="/connections?returnTo=%2Froom%2Fanalytics"' in page
    r = c.get("/connections?returnTo=%2Froom%2Fanalytics")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Could not be read just now" in body
    row = body.split("Your Spotify profile", 1)[1].split("</a>", 1)[0]
    assert "Not connected" not in row, "a failed read is never shown as nothing connected"


def test_a_failed_observation_read_is_never_worded_as_empty(monkeypatch):
    """Audit analytics-11(a): the section's failure read 'Nothing to read
    yet'. And an account that is otherwise empty cannot be confirmed
    brand-new while the observations are unreadable."""
    import insights_engine
    def boom(*_a, **_k):
        raise RuntimeError("insights down")
    monkeypatch.setattr(insights_engine, "build_insights", boom)
    c, uid = _account()
    _pin(uid)
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Nothing to read yet" not in body
    assert "Observations could not be read just now" in body
    assert "Could not be read" in body.split('id="an-path-h"', 1)[1].split("</section>", 1)[0]
    c2, _uid2 = _account()
    assert c2.get("/room/analytics").status_code == 503


def _read_seat(access="read", areas=None):
    import team_areas

    def acct(name):
        email = "%s-%s@example.net" % (name, uuid.uuid4().hex[:8])
        cl = appmod.app.test_client()
        cl.post("/signup", data={"name": name, "email": email, "password": PW})
        uid = store.get_user_by_email(email)["id"]
        store.set_user_plan(uid, "pro")
        cl.post("/login", data={"email": email, "password": PW})
        return cl, uid, email
    owner, oid, _ = acct("anowner")
    member, _mid, memail = acct("anseat")
    assert owner.post("/team/invite", data={
        "email": memail, "role": "manager", "access": access, "areas_sent": "1",
        "areas": list(areas if areas is not None else team_areas.keys())}).get_json()["ok"]
    row = [m for m in store.list_team(oid) if m["email"] == memail][0]
    member.post("/team/join/" + row["invite_token"], data={})
    member.post("/portal/%s/open" % oid)
    return member, oid


def test_a_read_seat_gets_no_door_at_the_route_and_a_shut_room_is_words():
    """Audit analytics-14(4): seats were tested only through zero_page()."""
    member, oid = _read_seat("read", ["analytics"])
    body = member.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Start with a trusted source" in body
    assert 'class="rk-cta"' not in body and 'class="an-z-btn"' not in body
    assert ar.ZERO_PROJECT["locked"] in body
    words = re.findall(r'<span class="an-z-lens"[^>]*>', body)
    assert len(words) == 4 and 'class="an-z-lens" href' not in body, "no room but Analytics is open"
    _pin(oid)
    body = member.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Change artist" not in body and 'class="rk-cta"' not in body, "a read seat changes no pin"


def test_a_statement_or_an_observation_is_not_a_new_account():
    """Audit analytics-5, spec 8: brand-new only with no connected source
    and no insights. A statement is a connected source (Connections says
    so) and gives real observations."""
    assert ar.new_account(None, [], None, [], statements=[{"id": "s"}]) is False
    assert ar.new_account(None, [], None, [], observations=[{"kind": "start"}]) is True, "a tip is not a measurement"
    assert ar.new_account(None, [], None, [], observations=[{"kind": "hygiene"}]) is False
    assert ar.new_account(None, [], None, [], actions=[{"id": "a"}]) is False
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 2640.0, "period": "2026-01"}])
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Start with a trusted source" not in body and "Nothing is measured yet" not in body
    assert "Uncollected royalty streams" in body
    assert ar.DONE_LINE in c.get("/room/analytics?from=connect").get_data(as_text=True), (
        "Connections calls an uploaded statement Connected")


def test_an_open_analytics_action_is_not_a_new_account():
    c, uid = _account()
    cc.create_action(uid, "Read the spring numbers", room="analytics")
    body = c.get("/room/analytics").get_data(as_text=True)
    assert "Start with a trusted source" not in body


class _FakeMetrics:
    key, label = "soundcharts", "Soundcharts"

    def supports(self, cap):
        return cap == sp.CAP_METRICS

    def configured(self):
        return True

    def health_check(self):
        return {"key": self.key, "ok": True}

    def __getattr__(self, name):
        def refuse(*_a, **_k):
            raise AssertionError("the room called the provider: %s" % name)
        return refuse


def test_stored_metrics_provider_readings_are_shown_and_credited(monkeypatch):
    """Audit analytics-3: with a metrics provider configured and its
    readings on file, the room said 'Not measured', named the raw key and
    claimed a key was missing. It reads what is stored, without a call."""
    sp.reset_registry(sp.ProviderRegistry(adapters=[_FakeMetrics()]))
    c, uid = _account()
    _pin(uid)
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    assert "Needs a metrics provider" not in body, "a provider is configured"
    assert "Soundcharts has no reading for this artist yet" in body
    day = date.today().isoformat()
    store.record_pulse_snapshot(uid, 5000, None, None, provider="soundcharts", day=day,
                                monthly_listeners=12345)
    body = c.get("/room/analytics").get_data(as_text=True).split('class="rk an"', 1)[1]
    got = {g[0]: g for g in _screens(body)}
    assert got["Monthly listeners"][2] == "12,345" and got["Monthly listeners"][3] == "From Soundcharts"
    assert got["Followers"][2] == "5,000" and got["Followers"][3] == "From Soundcharts"
    rows = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.split('id="an-meas-h"', 1)[1].split("</section>", 1)[0]))
    assert "12,345 Monthly listeners Soundcharts Read: %s" % day in rows, rows
    assert "soundcharts" not in rows and "Needs a metrics provider key" not in rows


def test_connections_lists_the_metrics_provider_and_the_mlc_as_they_are(monkeypatch):
    """Audit analytics-4: no metrics-provider row, and MLC filed under
    'Not connectable yet' while the app runs MLC checks."""
    c, _uid = _account()
    page = c.get("/connections").get_data(as_text=True)
    assert "Metrics provider" in page and "Monthly listeners" in page
    assert "MusicBrainz" not in page, "credits come from The MLC since 2026-09-18"

    class _MLC:
        label = "The MLC"

        def configured(self):
            return True
    monkeypatch.setattr(sp, "mlc_adapter", lambda: _MLC())
    sp.reset_registry(sp.ProviderRegistry(adapters=[_FakeMetrics()]))
    page = c.get("/connections").get_data(as_text=True)
    assert "Soundcharts" in page
    shut = page.split("Not connectable yet", 1)[1]
    assert "MLC" not in shut and "ASCAP" in shut
    row = page.split(">The MLC<", 1)[1].split("</a>", 1)[0]
    assert "Connected" in row and "/recovery" in row


def test_every_source_says_what_it_gives_before_it_is_connected():
    """Audit analytics-7, spec 3: what a source provides, what it does not,
    what access it asks, synced or imported, when the first reading comes,
    and what disconnecting does."""
    c, _uid = _account()
    page = c.get("/connections").get_data(as_text=True)
    for source in ("Your Spotify profile", "Royalty statements", "Metrics provider"):
        block = page.split(source, 1)[1].split("</details>", 1)[0]
        for said in ("Gives", "Does not give", "Access", "How it arrives", "To disconnect"):
            assert said in block, (source, said)


def test_the_zero_header_carries_the_account_chip():
    """Audit analytics-8: the mockup's account chip, as Business keeps it."""
    c, _uid = _account("Chip Artist")
    head = c.get("/room/analytics").get_data(as_text=True).split('class="rk-hero"', 1)[1].split("</section>", 1)[0]
    assert '<span class="rk-chip"' in head and "Chip Artist" in head


def test_ask_street_banker_opens_the_corner_box():
    c, _uid = _account()
    page = c.get("/room/analytics").get_data(as_text=True)
    assert '<a class="an-z-more" id="an-ask" href="/contact">' in page
    script = page.split('getElementById("an-ask")', 1)[1][:600]
    assert 'getElementById("sbq-open")' in script and "preventDefault" in script
