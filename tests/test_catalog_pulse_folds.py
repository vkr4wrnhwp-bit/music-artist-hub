"""Two more pages folded into the one that already had their data.

/identifiers rendered the catalog's own records a second time, read for
their codes. /stats rendered Artist Pulse's own numbers a second time -
the same followers, popularity, Deezer fans and snapshot history - plus
one section of owned link engagement. Each is now a section of the page
it duplicated, the old URL forwards, and the nav has one entry fewer.
"""
import io
import os
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "fold-tests-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    """A fresh pro account (the catalog is a pro page) with two catalog
    records: one carrying real codes, one carrying none."""
    import db as store

    email = "fold-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Fold Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        coded = store.add_catalog_track(uid, {"title": "Coded Song",
                                              "artist": "Fold Tester"})
        store.set_catalog_track_meta(uid, coded, {"isrc": "USSB12600077",
                                                  "upc": "198000000077",
                                                  "label": "Fold Records"})
        store.add_catalog_track(uid, {"title": "Bare Song", "artist": "Fold Tester"})
    return {"client": client, "uid": uid}


# --- the old doors -------------------------------------------------------------

def test_identifiers_forwards_to_the_catalog_section(artist):
    r = artist["client"].get("/identifiers")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/catalog#identifiers")


def test_stats_forwards_to_the_pulse_section(artist):
    r = artist["client"].get("/stats")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/pulse#engagement")


def test_nothing_points_at_the_folded_pages_any_more():
    import glob
    import inspect

    import artist_os
    import hubs
    import insights_engine

    keys = {k for _hk, _n, _t, items in hubs.HUBS for k, *_ in items}
    assert "identifiers" not in keys and "stats" not in keys
    assert "identifiers" not in hubs.LIVE_KEYS and "stats" not in hubs.LIVE_KEYS
    stale = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        s = io.open(p, encoding="utf-8").read()
        if 'href="/identifiers"' in s or 'href="/stats"' in s:
            stale.append(os.path.basename(p))
    assert stale == [], stale
    for name in ("identifiers.html", "stats.html"):
        assert not os.path.exists(os.path.join(HERE, "templates", name)), name
    # The two links that lived in code rather than templates.
    assert '"/stats"' not in inspect.getsource(insights_engine)
    assert all(link != "/identifiers" for *_, link in artist_os.PASSPORT_FIELDS)
    assert any(link == "/catalog#identifiers" for *_, link in artist_os.PASSPORT_FIELDS)


# --- identifiers, on the catalog ---------------------------------------------------

def test_the_codes_sit_beside_their_records(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'id="identifiers"' in body and "Your Identifiers" in body
    assert "USSB12600077" in body and "198000000077" in body
    assert "Fold Records" in body


def test_coverage_is_a_meter_counted_from_the_records(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISRC (recordings): 1/2"' in body
    assert 'aria-label="UPC (releases): 1/2"' in body


def test_the_iswc_meter_counts_the_work_codes_the_registry_returned(artist):
    """The meter said "Not pulled" and the comment above it said nothing
    in the app ever pulls an ISWC. Both stopped being true when a track's
    passport could be checked against The MLC: a matched work carries a
    work code, and it belongs on the catalog row."""
    import db as store

    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISWC (works): 0/2"' in body, "counted, not disclaimed"
    assert "Not pulled" not in body

    cat = [t for t in store.get_catalog_tracks(artist["uid"])
           if t["title"] == "Coded Song"][0]
    store.add_track_mlc_check(
        artist["uid"], cat["passport_track_id"], "ISRC USSB12600077", "match", "",
        [{"song_code": "BA1234", "iswc": "T-900.000.001-2", "share_total": 100.0,
          "writers": [], "publishers": []}])
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISWC (works): 1/2"' in body
    assert "T-900.000.001-2" in body


def test_the_work_code_shows_on_the_song_it_belongs_to(artist):
    import db as store

    cat = [t for t in store.get_catalog_tracks(artist["uid"])
           if t["title"] == "Coded Song"][0]
    store.add_track_mlc_check(
        artist["uid"], cat["passport_track_id"], "ISRC USSB12600077", "match", "",
        [{"song_code": "BA1234", "iswc": "T-900.000.001-2", "share_total": 100.0,
          "writers": [], "publishers": []}])
    body = artist["client"].get("/catalog").get_data(as_text=True)
    passports = body.split('id="passports"')[1].split("</section>")[0]
    assert "ISWC T-900.000.001-2" in passports
    # The bare song has no work code and claims none.
    ids = body.split('id="identifiers"')[1].split("</section>")[0]
    assert ids.count("T-900.000.001-2") == 1


def test_a_check_with_no_work_code_is_not_counted(artist):
    """The MLC answers about plenty of works with no ISWC on file. A
    match is not a work code."""
    import db as store

    cat = [t for t in store.get_catalog_tracks(artist["uid"])
           if t["title"] == "Coded Song"][0]
    store.add_track_mlc_check(
        artist["uid"], cat["passport_track_id"], "ISRC USSB12600077", "match", "",
        [{"song_code": "BA9999", "iswc": "", "share_total": 50.0,
          "writers": [], "publishers": []}])
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISWC (works): 0/2"' in body


def test_nothing_still_claims_the_iswc_is_unreachable():
    """The comment in app.py said outright that nothing this app reads
    pulls an ISWC. It was load-bearing for the meter above it."""
    src = io.open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
    assert "Nothing this app reads ever pulls an ISWC" not in src


def test_a_missing_isrc_is_a_word_and_an_action(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'sb-lamp--crit">MISSING' in body
    assert 'value="Resolve 1 missing ISRC(s) in catalog"' in body


def test_the_registration_rings_read_the_real_percentage(artist):
    """Found while folding: the Registered / Unregistered rings were drawn
    at 82% and 17% for every account - constants, beside the real count.
    One track of two carries an ISRC, so the rings are 50 and 50."""
    body = artist["client"].get("/catalog").get_data(as_text=True)
    rings = body.split('id="identifiers"')[1]
    assert rings.count(">50%</div>") == 2
    assert "82%" not in body and "17%" not in body


def test_an_empty_catalog_does_not_pretend_to_measure(application):
    import db as store

    email = "fold-empty-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Empty", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    body = client.get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISRC (recordings): No tracks"' in body
    assert "MISSING" not in body.split('id="identifiers"')[1].split("</section>")[0]


# --- engagement, on the pulse ---------------------------------------------------------

def test_link_engagement_shows_without_spotify(artist, monkeypatch):
    """First-party counts from the artist's own smart links do not depend
    on a Spotify credential, so they show in the Not Connected state too."""
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    body = artist["client"].get("/pulse").get_data(as_text=True)
    assert "Not Connected" in body
    assert 'id="engagement"' in body and "Your Link Engagement" in body
    for cap in ("page views", "platform clicks", "pre-saves"):
        assert cap + "</span>" in body, cap


def test_link_engagement_counts_the_artists_own_links(artist):
    import links_store as mls

    with artist["client"].application.app_context():
        cid = mls.create_campaign(artist["uid"], "fold-%s" % uuid.uuid4().hex[:6],
                                  {"title": "Counted Drop"})
        mls.track(cid, "pageview")
        mls.track(cid, "pageview")
        mls.track(cid, "click", service_key="spotify")
    body = artist["client"].get("/pulse").get_data(as_text=True)
    section = body.split('id="engagement"')[1].split("</section>")[0]
    assert '<span class="sb-lcd-v">2</span>' in section
    assert '<span class="sb-lcd-v">1</span>' in section


# --- the pulse, through the provider registry ------------------------------------
#
# Artist Pulse read Spotify's own Web API and nothing else, so the first
# number a label asks for - monthly listeners - was not on the page:
# Spotify's public API does not carry it. Whatever the registry has for
# CAP_METRICS now answers, its figures are stored provider-stamped beside
# the Spotify ones, and the caption says how old they are.

import signal_providers as providers


class FakeMetrics(providers.MusicIntelligenceProvider):
    """A configured CAP_ARTIST + CAP_METRICS provider, shaped like
    Soundcharts and reaching no network."""

    key = "fakecharts"
    label = "FakeCharts"
    capabilities = (providers.CAP_ARTIST, providers.CAP_METRICS)

    def __init__(self, hours=3, found=True):
        self.searches = self.metric_calls = 0
        self.hours, self.found = hours, found

    def configured(self):
        return True

    def search_artists(self, query, limit=20):
        self.searches += 1
        return ([{"provider_artist_id": "fc-1", "name": query}]
                if self.found else [])

    def get_artist_metrics(self, provider_artist_id, start, end):
        self.metric_calls += 1
        return [{"date": "2026-09-01", "metric": "spotify_monthly_listeners", "value": 39000},
                {"date": "2026-09-08", "metric": "spotify_monthly_listeners", "value": 42100},
                {"date": "2026-09-08", "metric": "spotify_followers", "value": 8800}]

    def metrics_cached_at(self, provider_artist_id, start, end):
        from datetime import datetime, timedelta, timezone
        return datetime.now(timezone.utc) - timedelta(hours=self.hours)


@pytest.fixture
def metrics_provider():
    fake = FakeMetrics()
    providers.reset_registry(providers.ProviderRegistry(adapters=[fake]))
    yield fake
    providers.reset_registry(None)


def _pick_artist(uid, name="Fold Tester"):
    import db as store
    store.save_pulse_profile(uid, "spotify-artist-1", name)


def test_monthly_listeners_come_from_the_registry_and_carry_their_age(artist, metrics_provider):
    _pick_artist(artist["uid"])
    body = artist["client"].get("/pulse").get_data(as_text=True)
    section = body.split('id="measured"')[1].split("</section>")[0]
    assert "measured by FakeCharts" in body
    assert '<span class="sb-lcd-v">42,100</span>' in section
    assert "monthly listeners" in section
    assert '<span class="sb-lcd-v">8,800</span>' in section
    assert "Measured by FakeCharts, 3 hours ago." in section
    assert "Not measured" not in section


def test_the_provider_id_is_resolved_once_and_kept(artist, metrics_provider):
    import db as store

    _pick_artist(artist["uid"])
    artist["client"].get("/pulse")
    assert metrics_provider.searches == 1
    profile = store.get_pulse_profile(artist["uid"])
    assert profile["provider"] == "fakecharts"
    assert profile["provider_artist_id"] == "fc-1"
    artist["client"].get("/pulse")
    assert metrics_provider.searches == 1, "the second load asked the store, not the vendor"
    assert metrics_provider.metric_calls == 2, "the figures are still re-read; the id is not"


def test_a_new_artist_drops_the_old_providers_id(artist, metrics_provider):
    import db as store

    _pick_artist(artist["uid"])
    artist["client"].get("/pulse")
    assert store.get_pulse_profile(artist["uid"])["provider_artist_id"] == "fc-1"
    store.save_pulse_profile(artist["uid"], "spotify-artist-2", "Someone Else")
    profile = store.get_pulse_profile(artist["uid"])
    assert profile["provider_artist_id"] == "" and profile["provider"] == ""


def test_the_snapshots_are_provider_stamped_and_sit_beside_spotifys(artist, metrics_provider):
    import db as store

    _pick_artist(artist["uid"])
    store.record_pulse_snapshot(artist["uid"], 100, 20, 5, day="2026-09-08")
    artist["client"].get("/pulse")
    spotify_rows = store.list_pulse_snapshots(artist["uid"])
    fake_rows = store.list_pulse_snapshots(artist["uid"], provider="fakecharts")
    assert [r["day"] for r in spotify_rows] == ["2026-09-08"]
    assert spotify_rows[0]["followers"] == 100, "the same day from another provider did not overwrite it"
    assert [r["day"] for r in fake_rows] == ["2026-09-01", "2026-09-08"]
    assert fake_rows[-1]["monthly_listeners"] == 42100 and fake_rows[-1]["followers"] == 8800
    assert all(r["provider"] == "fakecharts" for r in fake_rows)


def test_a_day_the_provider_did_not_report_listeners_stays_null(artist, metrics_provider):
    """A nought there would read as an audience of nobody."""
    import db as store

    _pick_artist(artist["uid"])
    store.record_pulse_snapshot(artist["uid"], 10, 0, 0, provider="fakecharts",
                                day="2026-08-01")
    rows = store.list_pulse_snapshots(artist["uid"], provider="fakecharts")
    assert rows[0]["monthly_listeners"] is None


def test_with_no_real_metrics_provider_the_spotify_page_is_what_it_was(artist):
    _pick_artist(artist["uid"])
    providers.reset_registry(providers.ProviderRegistry(adapters=[]))
    try:
        body = artist["client"].get("/pulse").get_data(as_text=True)
    finally:
        providers.reset_registry(None)
    assert 'id="measured"' not in body, "the mock must not stand in for a real audience"
    assert 'id="engagement"' in body


def test_a_provider_that_cannot_find_the_artist_says_nothing(artist):
    fake = FakeMetrics(found=False)
    providers.reset_registry(providers.ProviderRegistry(adapters=[fake]))
    try:
        _pick_artist(artist["uid"], "Nobody At All")
        body = artist["client"].get("/pulse").get_data(as_text=True)
    finally:
        providers.reset_registry(None)
    assert 'id="measured"' not in body
    assert fake.metric_calls == 0


def test_each_cadence_line_describes_its_own_source():
    """The page said the Spotify block was "refreshed every 6 hours" and,
    twelve lines up, that peers were "snapshotted whenever this page
    loads". Both read the same API on the same load; only one could be
    true. The six hours belong to the cached metrics provider."""
    src = io.open(os.path.join(HERE, "templates", "pulse.html"),
                  encoding="utf-8").read()
    assert "refreshed every 6 hours" not in src
    assert "read fresh on every load of this page" in src
    assert "snapshotted whenever this page loads" in src
    assert "{{ metrics.note }}" in src
