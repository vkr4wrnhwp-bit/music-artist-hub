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

def test_an_empty_account_is_told_in_words_and_shown_no_zero_figures():
    c, _uid = _account()
    page = c.get("/room/analytics").get_data(as_text=True)
    assert "Analytics Room" in page
    assert "What is measured, by whom, and how it moved." in page
    assert page.count("rk-fig-n--none") == 3, (
        "three figures, none of them measurable on an account with nothing")
    assert "Not pinned yet" in page
    assert "Needs two readings on different days" in page


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
