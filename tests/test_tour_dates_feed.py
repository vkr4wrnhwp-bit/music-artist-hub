"""Tour dates, first-hand from TOUR.

Bandsintown declined the platform an app_id (2026-09-07), so the dates
the artist already holds in TOUR feed the EPK and Signal's live-dates
tab. The rules under test: a hold is never a date, a past date is never
upcoming, the Tickets link appears only where a link exists, the page
names its source, and one owner's tour never lands on another's page.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import signal_ingest as ingest
import signal_providers as providers
import signal_store as sstore
import tour_dates
from tests.test_tour_date_page import _show, _tour, _user

TIX = "https://tix.example/basement-east"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _status(client, tid, sid, status):
    r = client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": status})
    assert r.status_code == 302


def _ticket(client, tid, sid, url):
    r = client.post("/tours/%s/shows/%s/marketing" % (tid, sid), data={"ticket_url": url})
    assert r.status_code == 302


def _past_tour(client):
    r = client.post("/tours/new", data={
        "name": "Last Year", "artist_name": "Test Artist", "start_date": "2024-03-01",
        "end_date": "2024-03-10", "home_tz": "America/New_York", "currency": "USD"})
    assert r.status_code == 302
    return r.headers["Location"].rstrip("/").split("/")[-1]


def _three(flask_app):
    """An owner, one tour, three shows: a hold, a confirmed date with a
    ticket link, an advanced date without one."""
    client, owner = _user(flask_app)
    tid = _tour(client)
    hold = _show(client, tid, "2030-05-02", "Hold House")
    conf = _show(client, tid, "2030-05-04", "The Basement East")
    adv = _show(client, tid, "2030-05-06", "Terminal West")
    _status(client, tid, conf, "confirmed")
    _ticket(client, tid, conf, TIX)
    _status(client, tid, adv, "advanced")
    return client, owner, tid, (hold, conf, adv)


def _slug(client, owner):
    client.get("/epk")  # visiting the editor mints the slug
    return store.get_epk(owner["id"])["slug"]


# --- the feed ---------------------------------------------------------------

def test_upcoming_is_confirmed_and_advanced_only_in_date_order(flask_app):
    client, owner, tid, (hold, conf, adv) = _three(flask_app)
    rows = tour_dates.upcoming(owner["id"])
    assert [(r["venue"], r["status"]) for r in rows] == [
        ("The Basement East", "confirmed"), ("Terminal West", "advanced")]
    assert rows[0] == dict(rows[0], date="2030-05-04", city="Nashville, TN",
                           ticket_url=TIX, tour_name="Test Run")
    assert rows[1]["ticket_url"] == ""
    assert "Hold House" not in [r["venue"] for r in rows]
    # the day after the last date, nothing is upcoming
    assert tour_dates.upcoming(owner["id"], today=date(2030, 5, 7)) == []
    # on the day itself the date still stands
    assert [r["venue"] for r in tour_dates.upcoming(owner["id"], today="2030-05-06")] == ["Terminal West"]
    assert tour_dates.upcoming(None) == [] and tour_dates.upcoming("nobody-%s" % uuid.uuid4().hex) == []


def test_a_played_date_is_never_upcoming(flask_app):
    client, owner, tid, _ids = _three(flask_app)
    past = _past_tour(client)
    sid = _show(client, past, "2024-03-05", "The Earl")
    _status(client, past, sid, "played")
    assert "The Earl" not in [r["venue"] for r in tour_dates.upcoming(owner["id"])]
    played = tour_dates.played(owner["id"])
    assert [(r["venue"], r["status"], r["tour_name"]) for r in played] == [("The Earl", "played", "Last Year")]
    # a confirmed date in the past is not upcoming either - a page must
    # never show a date that has gone
    old = _show(client, past, "2024-03-07", "The Masquerade")
    _status(client, past, old, "confirmed")
    assert "The Masquerade" not in [r["venue"] for r in tour_dates.upcoming(owner["id"])]


# --- the EPK ----------------------------------------------------------------

def _assert_two_dates(body):
    assert "The Basement East" in body and "Terminal West" in body
    assert body.index("The Basement East") < body.index("Terminal West"), "date order"
    assert "May 4, 2030" in body and "May 6, 2030" in body
    assert "Hold House" not in body
    assert body.count(TIX) == 1 and body.count("Tickets ↗") == 1, "one link, on the date that has one"
    assert "Dates from the artist's tour in Street Banker" in body
    assert "Live dates via Bandsintown" not in body and "tracking on Bandsintown" not in body


def test_the_epk_editor_shows_the_two_confirmed_dates(flask_app):
    client, owner, tid, _ids = _three(flask_app)
    body = client.get("/epk").get_data(as_text=True)
    _assert_two_dates(body)
    assert "Tour dates: from your tour in Street Banker (2 confirmed)" in body
    assert "confirm a date in TOUR" not in body
    assert "not enabled on this server" not in body and "Awaiting app_id" not in body


def test_the_public_epk_shows_the_same_two_dates_to_anyone(flask_app):
    client, owner, tid, _ids = _three(flask_app)
    slug = _slug(client, owner)
    body = flask_app.test_client().get("/epk/" + slug).get_data(as_text=True)
    assert "Tour Dates" in body
    _assert_two_dates(body)
    assert 'target="_blank" rel="noopener"' in body[body.index(TIX) - 200: body.index(TIX) + 200]


def test_with_no_confirmed_date_the_public_kit_has_no_dates_block(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, "2030-05-02", "Hold House")  # a hold is not a date
    body = client.get("/epk").get_data(as_text=True)
    assert "Tour dates: confirm a date in TOUR and it appears here" in body
    assert "No confirmed dates yet" in body and "Hold House" not in body
    slug = _slug(client, owner)
    pub = flask_app.test_client().get("/epk/" + slug).get_data(as_text=True)
    assert "Hold House" not in pub
    assert "Dates from the artist's tour in Street Banker" not in pub
    assert "Tour Dates" not in pub, "no rows, no block"


def test_another_owner_s_tour_never_lands_on_this_kit(flask_app):
    client, owner, tid, _ids = _three(flask_app)
    other, other_owner = _user(flask_app, "Other Act")
    otid = _tour(other)
    sid = _show(other, otid, "2030-05-05", "Leak Venue")
    _status(other, otid, sid, "confirmed")
    assert "Leak Venue" in [r["venue"] for r in tour_dates.upcoming(other_owner["id"])]
    assert "Leak Venue" not in [r["venue"] for r in tour_dates.upcoming(owner["id"])]
    body = client.get("/epk").get_data(as_text=True)
    pub = flask_app.test_client().get("/epk/" + _slug(client, owner)).get_data(as_text=True)
    assert "Leak Venue" not in body and "Leak Venue" not in pub
    _assert_two_dates(pub)


def test_the_connections_board_states_the_source(flask_app):
    """/connections is plan-gated (402 for a fresh signup); the showcase
    account reads it. It holds no confirmed date, so the line says where
    one would come from - and never tells the owner to configure
    Bandsintown."""
    from tests.test_app import _demo
    body = _demo(flask_app).get("/connections").get_data(as_text=True)
    assert "Tour dates: confirm a date in TOUR and it appears here" in body
    assert "declined" in body and "Awaiting app_id" not in body


# --- Signal -----------------------------------------------------------------

def _seat(owner):
    org = sstore.default_org()
    sstore.upsert_member(org["id"], owner["email"], owner["name"], "owner", user_id=owner["id"])


def test_the_signal_live_dates_tab_reads_the_owner_s_tour(flask_app):
    sstore.init_signal()
    client, owner, tid, _ids = _three(flask_app)
    _seat(owner)
    # the Signal artist is the tour's artist, spelled with different case
    mine = sstore.upsert_artist("musicbrainz", "mb-%s" % uuid.uuid4().hex, {"name": "TEST artist"})
    someone = sstore.upsert_artist("musicbrainz", "mb-%s" % uuid.uuid4().hex,
                                   {"name": "Somebody Else %s" % uuid.uuid4().hex[:6]})
    providers.reset_registry(providers.ProviderRegistry(
        adapters=[providers.BandsintownAdapter(), providers.TourDatesAdapter()]))
    try:
        body = client.get("/signal/artist/%s?tab=events" % mine).get_data(as_text=True)
        assert "Live dates" in body
        assert "The Basement East" in body and "Terminal West" in body
        assert body.index("The Basement East") < body.index("Terminal West")
        assert "Hold House" not in body
        assert body.count(TIX) == 1
        assert "Source: your tour in Street Banker" in body
        assert "Bandsintown" not in body
        # another act's page never borrows these dates
        body = client.get("/signal/artist/%s?tab=events" % someone).get_data(as_text=True)
        assert "The Basement East" not in body and "Terminal West" not in body
        assert "Source: your tour in Street Banker" in body and "not evidence" in body
        # the other tabs still render; what they may show is pinned below
        assert client.get("/signal/artist/%s?tab=cities" % mine).status_code == 200
        # outside a request there is no viewer, so nothing is configured
        assert providers.registry().is_demo() is True
    finally:
        providers.reset_registry(None)


def test_the_tour_adapter_is_configured_only_for_an_owner_with_dates(flask_app):
    client, owner, tid, _ids = _three(flask_app)
    a = providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: "test artist")
    assert a.configured() is True and a.health_check()["ok"] is True
    assert [e["venue"] for e in a.get_events("any")] == ["The Basement East", "Terminal West"]
    assert a.get_events("any")[0] == dict(a.get_events("any")[0], date="2030-05-04",
                                          city="Nashville, TN", tickets=TIX)
    # no name resolved: no question, no guess
    assert providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: "").get_events("x") == []
    # another act by name: nothing
    assert providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: "Other Act").get_events("x") == []
    # the owner's own account name answers for a tour with no artist name
    with store.get_db() as conn:
        conn.execute("UPDATE tours SET artist_name='' WHERE id=?", (tid,))
    own = providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: owner["name"].upper())
    assert len(own.get_events("x")) == 2
    assert providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: "Other Act").get_events("x") == []
    # nobody signed in, or an owner with only holds: not configured, and
    # the registry keeps the demo (nothing real stood up)
    assert providers.TourDatesAdapter().configured() is False
    holds, holds_owner = _user(flask_app)
    htid = _tour(holds)
    _show(holds, htid, "2030-05-02", "Hold House")
    assert providers.TourDatesAdapter(user_id=holds_owner["id"]).configured() is False
    reg = providers.ProviderRegistry(adapters=[providers.TourDatesAdapter(user_id=holds_owner["id"])])
    assert reg.is_demo() is True
    reg = providers.ProviderRegistry(adapters=[providers.TourDatesAdapter(user_id=owner["id"])])
    assert reg.for_capability(providers.CAP_EVENTS).key == "tour_dates"
    # a real adapter, configured: the mock stands down for EVERY capability
    # (the registry's all-or-nothing rule), and what nobody real covers is
    # not measured - never the mock's invented numbers
    assert reg.is_demo() is False
    for cap in providers.ALL_CAPABILITIES:
        if cap != providers.CAP_EVENTS:
            assert reg.for_capability(cap) is None, cap
    assert not hasattr(providers.TourDatesAdapter, "first_party"), "no exemption from the rule"
    assert providers._REAL_ADAPTERS[0] is providers.BandsintownAdapter, "the dormant specialist keeps its place"
    assert providers.TourDatesAdapter in providers._REAL_ADAPTERS


def test_the_mock_stands_down_for_the_owner_but_its_universe_stays_labelled(flask_app):
    """Two truths at once. For the owner with a confirmed date the mock
    has stood down: the registry is not in demo, and every capability the
    tour cannot answer is not measured. But the artists already on screen
    were ingested by the mock, and they stay fictional whoever is looking -
    so every Signal page still carries the demo banner for them. Stripping
    that label would be the fabrication the rule exists to prevent. A
    viewer with no dates still gets the mock, labelled as before."""
    sstore.init_signal()
    client, owner, tid, _ids = _three(flask_app)
    _seat(owner)
    mine = sstore.upsert_artist("musicbrainz", "mb-%s" % uuid.uuid4().hex, {"name": "Test Artist"})
    if not sstore.seeded_by("mock"):
        ingest.refresh_universe(max_artists=6, reg=providers.ProviderRegistry(adapters=[]), force=True)
    assert sstore.seeded_by("mock") and not sstore.seeded_by("no-such-provider")
    providers.reset_registry(providers.ProviderRegistry(
        adapters=[providers.BandsintownAdapter(), providers.TourDatesAdapter()]))
    try:
        with client:
            client.get("/signal")
            reg = providers.registry()
            assert reg.is_demo() is False, "the owner's own tour is a configured real source"
            assert reg.for_capability(providers.CAP_EVENTS).key == "tour_dates"
            for cap in (providers.CAP_ARTIST, providers.CAP_METRICS, providers.CAP_CITIES):
                assert reg.for_capability(cap) is None, "%s: not measured, not the mock" % cap
        mock_artist = [a for a in sstore.list_artists() if a["id"] != mine][0]
        for path in ("/signal", "/signal/breaking", "/signal/cities", "/signal/undervalued",
                     "/signal/artist/%s" % mock_artist["id"],
                     "/signal/artist/%s?tab=cities" % mock_artist["id"],
                     "/signal/artist/%s?tab=events" % mine):
            body = client.get(path).get_data(as_text=True)
            assert body.count("Demo data") >= 1 and "fictional" in body, path
        body = client.get("/signal/artist/%s?tab=events" % mine).get_data(as_text=True)
        assert "The Basement East" in body and "Source: your tour in Street Banker" in body
        # a seat with no confirmed date: the mock answers, and says so
        other, other_owner = _user(flask_app)
        _seat(other_owner)
        with other:
            other.get("/signal")
            assert providers.registry().is_demo() is True
        body = other.get("/signal").get_data(as_text=True)
        assert "Demo data" in body and "No music-data provider is connected" in body
    finally:
        providers.reset_registry(None)

    class _Real(providers.MusicIntelligenceProvider):
        key, label, capabilities = "real", "Real", (providers.CAP_ARTIST,)

        def configured(self):
            return True
    reg = providers.ProviderRegistry(adapters=[providers.TourDatesAdapter(user_id=owner["id"]), _Real()])
    assert reg.is_demo() is False
    assert reg.for_capability(providers.CAP_EVENTS).key == "tour_dates"
    assert reg.for_capability(providers.CAP_ARTIST).key == "real"
    assert reg.for_capability(providers.CAP_METRICS) is None, "not measured, not invented"


# --- the clock ---------------------------------------------------------------

def _tour_in(client, tz, name):
    r = client.post("/tours/new", data={
        "name": name, "artist_name": "Test Artist", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": tz, "currency": "USD"})
    assert r.status_code == 302
    return r.headers["Location"].rstrip("/").split("/")[-1]


def test_today_is_the_tour_s_own_day_not_the_server_s(flask_app, monkeypatch):
    """Render runs UTC. At 02:00 UTC on May 7 it is 7pm on May 6 in Los
    Angeles - doors - so a confirmed May 6 show in an LA tour is still
    upcoming, while the same date in a UTC tour has passed. TOUR keeps
    this clock everywhere (tour_engine.today_in); the feed must too."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    import tour_engine as eng
    client, owner = _user(flask_app)
    la = _tour_in(client, "America/Los_Angeles", "West Coast")
    utc = _tour_in(client, "UTC", "Greenwich")
    la_show = _show(client, la, "2030-05-06", "The Troubadour")
    utc_show = _show(client, utc, "2030-05-06", "The Dome")
    _status(client, la, la_show, "confirmed")
    _status(client, utc, utc_show, "confirmed")
    gone = _show(client, la, "2030-05-05", "The Echo")
    _status(client, la, gone, "played")
    instant = datetime(2030, 5, 7, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(eng, "now_in", lambda tz: instant.astimezone(
        ZoneInfo(tz) if eng.valid_tz(tz) else timezone.utc))
    assert eng.today_in("America/Los_Angeles") == "2030-05-06" and eng.today_in("UTC") == "2030-05-07"
    assert [r["venue"] for r in tour_dates.upcoming(owner["id"])] == ["The Troubadour"]
    assert [r["venue"] for r in tour_dates.played(owner["id"])] == ["The Echo"]
    # the kit and the count follow the same clock
    body = client.get("/epk").get_data(as_text=True)
    assert "The Troubadour" in body and "The Dome" not in body
    assert "Tour dates: from your tour in Street Banker (1 confirmed)" in body
    # an explicit today still applies to every tour (tests rely on it)
    assert tour_dates.upcoming(owner["id"], today="2030-05-07") == []
    assert len(tour_dates.upcoming(owner["id"], today="2030-05-06")) == 2


def test_a_datetime_today_keeps_the_show_on_that_day(flask_app):
    """datetime is a date subclass whose isoformat carries a clock. A
    cutoff of '2030-05-06T02:00:00' would sort after '2030-05-06' and drop
    the show on that very day (and call it played a day early). The day
    is the day, whatever type carries it."""
    from datetime import datetime, timezone
    client, owner = _user(flask_app)
    tid = _tour(client)
    tonight = _show(client, tid, "2030-05-06", "The Troubadour")
    _status(client, tid, tonight, "confirmed")
    gone = _show(client, tid, "2030-05-05", "The Echo")
    _status(client, tid, gone, "played")
    same_day_played = _show(client, tid, "2030-05-06", "The Smell")
    _status(client, tid, same_day_played, "played")
    for today in (datetime(2030, 5, 6, 2, 0), datetime(2030, 5, 6, 23, 59, tzinfo=timezone.utc),
                  date(2030, 5, 6), "2030-05-06", "2030-05-06T02:00:00"):
        assert [r["venue"] for r in tour_dates.upcoming(owner["id"], today=today)] == ["The Troubadour"], today
        assert [r["venue"] for r in tour_dates.played(owner["id"], today=today)] == ["The Echo"], today
    assert tour_dates.upcoming(owner["id"], today=datetime(2030, 5, 7, 0, 0)) == []
    assert [r["venue"] for r in tour_dates.played(owner["id"], today=datetime(2030, 5, 7, 0, 0))] == ["The Smell", "The Echo"]


def test_the_count_is_the_count_of_dates_the_kit_shows(flask_app):
    """Fifteen confirmed dates: the kit lists fifteen and says fifteen -
    the same number /connections computes from upcoming(). No silent
    display cap under-reporting the count."""
    client, owner = _user(flask_app)
    tid = _tour(client)
    for i in range(1, 16):
        sid = _show(client, tid, "2030-05-%02d" % i, "Venue %02d" % i)
        _status(client, tid, sid, "confirmed")
    rows = tour_dates.upcoming(owner["id"])
    assert len(rows) == 15 == len(tour_dates.epk_rows(owner["id"]))
    body = client.get("/epk").get_data(as_text=True)
    assert "Tour dates: from your tour in Street Banker (15 confirmed)" in body
    pub = flask_app.test_client().get("/epk/" + _slug(client, owner)).get_data(as_text=True)
    assert all(("Venue %02d" % i) in pub for i in range(1, 16))
    assert pub.index("Venue 01") < pub.index("Venue 15")


def test_sixty_dates_are_sixty_everywhere_no_silent_cap(flask_app):
    """An act with sixty confirmed dates: the feed, the kit, the public
    kit and Signal all hold sixty and say sixty (/connections is plan-gated
    here; it computes its count from the same upcoming() call). A default
    cap of fifty would have listed fifty, lost the ten latest, and stated
    a count that was wrong - a number under the honesty rule. A caller who
    asks for fewer still gets fewer."""
    client, owner = _user(flask_app)
    tid = _tour(client)
    for i in range(60):
        d = date(2030, 5, 1) + timedelta(days=i)
        sid = _show(client, tid, d.isoformat(), "Venue %02d" % (i + 1))
        _status(client, tid, sid, "confirmed")
    assert len(tour_dates.upcoming(owner["id"])) == 60 == len(tour_dates.epk_rows(owner["id"]))
    assert len(tour_dates.upcoming(owner["id"], limit=5)) == 5
    assert len(tour_dates.event_rows(owner["id"], artist_name="Test Artist")) == 60
    body = client.get("/epk").get_data(as_text=True)
    assert "Tour dates: from your tour in Street Banker (60 confirmed)" in body
    assert "(50 confirmed)" not in body
    pub = flask_app.test_client().get("/epk/" + _slug(client, owner)).get_data(as_text=True)
    assert all(("Venue %02d" % i) in pub for i in range(1, 61))
    assert pub.index("Venue 01") < pub.index("Venue 51") < pub.index("Venue 60")
    a = providers.TourDatesAdapter(user_id=owner["id"], resolve=lambda pid: "test artist")
    assert len(a.get_events("any")) == 60
