"""Bandsintown: the artist record on the EPK, and live dates in Signal.

Shapes follow Bandsintown's OpenAPI 3.0.0 - ArtistData (tracker_count,
upcoming_event_count), EventData (datetime, venue, offers, lineup). The
provider stays inert without BANDSINTOWN_APP_ID, an error object is a
miss rather than a record, and Signal's tab says whose listing it is -
or "not measured" when no live-events provider is connected at all.
"""
import uuid

import pytest

import bandsintown_provider as bit
import db as store
import signal_providers as providers
import signal_store as sstore

ARTIST = {"id": "1", "name": "Art Is War", "url": "https://www.bandsintown.com/a/1",
          "image_url": "https://photos.bandsintown.com/1.jpg", "thumb_url": "", "facebook_page_url": "",
          "mbid": "5b11f4ce-a62d-471e-81fc-a69a8278c7da", "tracker_count": 12345, "upcoming_event_count": 2}
EVENTS = [{"id": "e1", "datetime": "2026-11-01T20:00:00", "url": "https://www.bandsintown.com/e/1",
           "venue": {"name": "The Fillmore", "city": "Charlotte", "region": "NC", "country": "United States",
                     "latitude": "35.2", "longitude": "-80.8"},
           "offers": [{"type": "Tickets", "url": "https://tix.example/1", "status": "available"}],
           "lineup": ["Art Is War", "Guest"]},
          {"id": "e2", "datetime": "2026-11-03T20:00:00", "url": "https://www.bandsintown.com/e/2",
           "venue": {"name": "Cat's Cradle", "city": "Carrboro", "region": "NC", "country": "United States"},
           "offers": [], "lineup": ["Art Is War"]}]


def _fake_fetch(calls):
    def fetch(url):
        calls.append(url)
        if "/events?" in url:
            return EVENTS
        if "Nobody" in url:
            return {"error": "Not Found"}
        return ARTIST
    return fetch


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("BANDSINTOWN_APP_ID", "test-app")
    calls = []
    monkeypatch.setattr(bit, "_fetch_json", _fake_fetch(calls))
    store.init_db()
    return calls


def test_the_artist_record_is_real_cached_and_honest_about_misses(on, monkeypatch):
    name = "Art Is War %s" % uuid.uuid4().hex[:6]
    info = bit.artist_info(name)
    assert info["trackers"] == 12345 and info["upcoming"] == 2 and info["url"].startswith("https://")
    assert info["mbid"] == ARTIST["mbid"]
    assert any("app_id=test-app" in c and "/artists/Art%20Is%20War" in c for c in on)
    n = len(on)
    bit.artist_info(name)
    assert len(on) == n, "the second read is the cache"
    assert bit.artist_info("Nobody %s" % uuid.uuid4().hex[:6]) is None, "their error object is a miss"
    assert bit.artist_info("") is None
    monkeypatch.delenv("BANDSINTOWN_APP_ID")
    assert bit.artist_info(name) is None and bit.event_rows(name) == []


def test_event_rows_carry_the_country_and_the_iso_date(on):
    rows = bit.event_rows("Art Is War %s" % uuid.uuid4().hex[:6])
    assert [r["date"] for r in rows] == ["2026-11-01", "2026-11-03"]
    assert rows[0]["country"] == "United States" and rows[0]["region"] == "NC" and rows[0]["city"] == "Charlotte"
    assert rows[0]["tickets"] == "https://tix.example/1" and rows[1]["tickets"] == ""
    assert rows[0]["lineup"] == ["Art Is War", "Guest"] and rows[1]["venue"] == "Cat's Cradle"


def test_the_signal_adapter_follows_the_app_id_and_resolves_the_name(on, monkeypatch):
    # A name of its own: the events cache is keyed by name and shared with
    # every other test that asked about "Art Is War" earlier in the run.
    name = "Art Is War %s" % uuid.uuid4().hex[:6]
    a = providers.BandsintownAdapter(resolve=lambda pid: name if pid == "mbid-1" else "")
    assert a.configured() is True and a.health_check()["ok"] is True
    ev = a.get_events("mbid-1")
    assert [e["venue"] for e in ev] == ["The Fillmore", "Cat's Cradle"]
    assert a.get_events("unknown") == [], "no name, no question, no guess"
    monkeypatch.delenv("BANDSINTOWN_APP_ID")
    assert a.configured() is False and "BANDSINTOWN_APP_ID" in a.health_check()["detail"]
    with pytest.raises(providers.ProviderError):
        a.events_for_name(name)


def test_the_registry_serves_events_from_it_and_nothing_else(on):
    reg = providers.ProviderRegistry(adapters=[providers.BandsintownAdapter(resolve=lambda p: "x")])
    assert reg.is_demo() is False
    assert reg.for_capability(providers.CAP_EVENTS).key == "bandsintown"
    for cap in (providers.CAP_ARTIST, providers.CAP_METRICS, providers.CAP_CITIES):
        assert reg.for_capability(cap) is None, cap
    assert providers._REAL_ADAPTERS[0] is providers.BandsintownAdapter, "the specialist is asked first"


def test_the_name_lookup_walks_the_provider_ids(on):
    sstore.init_signal()
    pid = "mb-%s" % uuid.uuid4().hex
    name = "Art Is War %s" % uuid.uuid4().hex[:6]
    artist_id = sstore.upsert_artist("musicbrainz", pid, {"name": name})
    assert sstore.artist_name_for_provider_id(pid) == name
    assert sstore.provider_ids(artist_id)[0] == {"provider": "musicbrainz", "provider_id": pid}
    a = providers.BandsintownAdapter()
    assert [e["date"] for e in a.get_events(pid)] == ["2026-11-01", "2026-11-03"]


def test_the_live_dates_tab_names_its_source_or_says_not_measured(on, monkeypatch):
    import app as appmod
    import signal_hub
    sstore.init_signal()
    flask_app = appmod.create_app()
    email = "bit-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Scout", "email": email, "password": "signal-pass-123"})
    client.post("/login", data={"email": email, "password": "signal-pass-123"})
    user = store.get_user_by_email(email)
    org = sstore.default_org()
    sstore.upsert_member(org["id"], email, "Scout", "owner", user_id=user["id"])
    pid = "mb-%s" % uuid.uuid4().hex
    artist_id = sstore.upsert_artist("musicbrainz", pid, {"name": "Art Is War %s" % uuid.uuid4().hex[:6]})

    providers.reset_registry(providers.ProviderRegistry(adapters=[providers.BandsintownAdapter()]))
    try:
        body = client.get("/signal/artist/%s?tab=events" % artist_id).get_data(as_text=True)
        assert "Live dates" in body and "The Fillmore" in body and "Charlotte, NC, United States" in body
        assert "as Bandsintown lists them today" in body and "https://tix.example/1" in body

        providers.reset_registry(providers.ProviderRegistry(adapters=[providers.MusicBrainzAdapter()]))
        monkeypatch.setenv("MUSICBRAINZ_ENABLED", "1")
        monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
        body = client.get("/signal/artist/%s?tab=events" % artist_id).get_data(as_text=True)
        assert "Not measured" in body and "The Fillmore" not in body
    finally:
        providers.reset_registry(None)


def test_the_epk_shows_the_record_beside_the_dates(on):
    from app import create_app
    from tests.test_app import _demo
    app_obj = create_app()
    client = _demo(app_obj)
    assert client.post("/epk/save", json={"bandsintown_artist": "Art Is War"}).get_json()["ok"]
    body = client.get("/epk").get_data(as_text=True)
    assert "12,345 tracking on Bandsintown" in body and "2 upcoming" in body
    assert "The Fillmore" in body
