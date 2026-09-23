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
    assert "command-plate.webp" in body, "the photographed three-screen plate"
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
    assert "analytics-plate.webp?v=" in body and "command-plate" not in body
    assert "Pinned Artist" in body and "Change artist" in body
    assert "Not measured" in body, "the analyser's own words for what nobody measured"
    assert "Start with a trusted source" not in body and "an-z-fold" not in body
    assert "Explore more tools" in body


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
    assert "Connect your first data source" not in page and "command-plate" not in page


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
