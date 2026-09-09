"""Signal's Soundcharts adapter, against answers shaped like their sandbox.

The canned bodies below are trimmed copies of what the public sandbox
(`soundcharts`/`soundcharts`, artist Billie Eilish) actually returned on
2026-09-06, so a shape drift on their side shows up here as a failing
test rather than as a blank page. The last test talks to the sandbox for
real and runs only when SOUNDCHARTS_SANDBOX_LIVE=1.

The honesty points held: a blank search is empty, an estimated stream
count is None, the 28-day change is None when no point sits 28 days
back, a distributor nobody recognises is "Needs Research", and an
endpoint a plan does not include is an error, never a guess.
"""
import base64
import json
import os
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

import signal_providers as providers

BILLIE = "11e81bcc-9c1c-ce38-b96b-a0369fe50396"
ALBUM = "b202abee-d19e-424e-9285-b420f4b98706"

ARTIST = {"uuid": BILLIE, "slug": "billie-eilish", "name": "Billie Eilish",
          "appUrl": "https://app.soundcharts.com/app/artist/billie-eilish/overview",
          "imageUrl": "https://assets.soundcharts.com/artist/c/1/c/%s.jpg" % BILLIE,
          "webUrl": "http://www.billieeilish.com/", "countryCode": "US",
          "genres": [{"root": "pop", "sub": ["pop"]}, {"root": "r&b", "sub": ["r&b/soul"]}],
          "isni": "000000046748058X", "ipi": "00792187700", "careerStage": "superstar",
          "growthLevel": "decline", "cityName": "Los Angeles"}

STATS = {"social": [{"platform": "spotify", "value": 130422316, "date": "2026-09-06T00:00:00+00:00",
                     "evolution": 197140, "percentEvolution": 0.15},
                    {"platform": "instagram", "value": 124103562, "date": "2026-09-06T00:00:00+00:00",
                     "evolution": -1000, "percentEvolution": -0.01}],
         "streaming": [{"platform": "pandora", "value": 2432093, "date": "2026-09-06T00:00:00+00:00"},
                       {"platform": "spotify", "value": 78313841, "date": "2026-09-06T00:00:00+00:00",
                        "evolution": -216007, "percentEvolution": -0.28}]}


def _plots(day, rows):
    return [{"date": day + "T00:00:00+00:00", "value": v, "countryName": cn, "countryCode": cc,
             "region": r, "cityName": c} for (c, r, cc, cn, v) in rows]


def _fake_fetch(calls, deny=()):
    def fetch(url):
        calls.append(url)
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        for d in deny:
            if d in p:
                raise providers.ProviderError("Soundcharts 403: Endpoint not included in your plan")
        if p.startswith("/api/v2/artist/search/"):
            return {"items": [ARTIST, dict(ARTIST, uuid="955fd961-faf4-4daf-a91e-7e9d6ac678b5",
                                           name="Billie Eilish", careerStage="long_tail", genres=[], cityName="")],
                    "page": {"offset": 0, "limit": int(q.get("limit", 20)), "next": None, "total": 2}}
        if p == "/api/v2.9/artist/" + BILLIE:
            return {"type": "artist", "object": ARTIST}
        if p == "/api/v2/artist/%s/current/stats" % BILLIE:
            return STATS
        if p == "/api/v2/artist/%s/streaming/spotify/listening" % BILLIE:
            return {"items": [{"date": "2020-10-10T00:00:00+00:00", "value": 40948759},
                              {"date": "2020-10-03T00:00:00+00:00", "value": 41548457}],
                    "page": {"offset": 0, "limit": 100, "next": None, "total": 2}}
        if p == "/api/v2/artist/%s/audience/spotify" % BILLIE:
            # Two pages, the way a 120-day window of daily points arrives.
            if q.get("offset") == "2":
                return {"items": [{"date": "2020-10-03T00:00:00+00:00", "followerCount": 33141024}],
                        "page": {"offset": 2, "limit": 2, "next": None, "total": 3}}
            return {"items": [{"date": "2020-10-01T00:00:00+00:00", "followerCount": 33066531, "likeCount": None},
                              {"date": "2020-10-02T00:00:00+00:00", "followerCount": 33103434}],
                    "page": {"offset": 0, "limit": 2, "total": 3,
                             "next": "/api/v2/artist/%s/audience/spotify?startDate=%s&endDate=%s&offset=2&limit=2"
                                     % (BILLIE, q.get("startDate"), q.get("endDate"))}}
        if p == "/api/v2/artist/%s/streaming/spotify" % BILLIE:
            return {"items": [
                {"date": "2020-10-10T00:00:00+00:00", "value": 40948759, "cityPlots": _plots("2020-10-10", [
                    ("Chicago", "Illinois", "US", "United States", 542605),
                    ("Amsterdam", "North Holland", "NL", "Netherlands", 248242),
                    ("Copenhagen", "", "DK", "Denmark", 164712)])},
                {"date": "2020-09-12T00:00:00+00:00", "value": 41000000, "cityPlots": _plots("2020-09-12", [
                    ("Chicago", "Illinois", "US", "United States", 500000),
                    ("Amsterdam", "North Holland", "NL", "Netherlands", 250000)])},
                {"date": "2020-10-03T00:00:00+00:00", "value": 41548457, "cityPlots": []}],
                "page": {"offset": 0, "limit": 100, "next": None, "total": 3}}
        if p == "/api/v2.34/artist/%s/albums" % BILLIE:
            return {"items": [
                {"name": "Happier Than Ever", "creditName": "Billie Eilish",
                 "releaseDate": "2021-07-30T00:00:00+00:00", "uuid": "63e0332f-5b4a-4828-83e3-d1178e51fd07", "type": "album"},
                {"name": "WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?", "creditName": "Billie Eilish",
                 "releaseDate": "2019-03-29T00:00:00+00:00", "uuid": ALBUM, "type": "album"},
                {"name": "&burn - Single", "creditName": "Billie Eilish & Vince Staples",
                 "releaseDate": "2017-12-15T00:00:00+00:00", "uuid": "17d44056-aea3-45d9-817b-a8c487d3e58a", "type": ""}],
                "page": {"offset": 0, "limit": 8, "next": None, "total": 3}}
        if p == "/api/v2.51/album/by-uuid/" + ALBUM:
            return {"type": "album", "object": {
                "name": "WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?", "creditName": "Billie Eilish",
                "upc": "00602577427657", "releaseDate": "2019-03-29T00:00:00+00:00", "totalTracks": 14,
                "copyright": "(P) 2019 Darkroom/Interscope Records", "distributor": "Universal",
                "uuid": ALBUM, "labels": [{"name": "Interscope", "type": "Universal"},
                                          {"name": "Darkroom", "type": "Universal"}], "type": "album"}}
        if p == "/api/v2.51/album/by-uuid/63e0332f-5b4a-4828-83e3-d1178e51fd07":
            return {"type": "album", "object": {
                "name": "Happier Than Ever", "upc": "00602438254736", "totalTracks": 16,
                "copyright": "(P) 2021 Darkroom/Interscope Records", "distributor": "Some Digital Co.",
                "labels": [{"name": "Darkroom", "type": ""}], "type": "album"}}
        if p.startswith("/api/v2.51/album/by-uuid/"):
            raise providers.ProviderError("Soundcharts 404: Album not found")
        if p == "/api/v2.20/artist/%s/playlist/current/spotify" % BILLIE:
            return {"items": [{"playlist": {"name": "Running & Gym & Cardio", "platform": "spotify",
                                            "latestSubscriberCount": 120000, "type": "Curators & Listeners"},
                               "position": 9786, "peakPosition": 974, "entryDate": "2021-09-10T05:02:01+00:00",
                               "song": {"name": "bad guy"}},
                              {"playlist": {"name": "Today's Top Hits", "platform": "spotify",
                                            "latestSubscriberCount": 34000000, "type": "Editorial"},
                               "position": 3, "peakPosition": 1, "entryDate": "2024-05-17T00:00:00+00:00",
                               "song": {"name": "LUNCH"}}]}
        if p == "/api/v2/artist/%s/events" % BILLIE:
            return {"items": [
                {"name": "Billie Eilish", "type": "concert", "date": "2016-07-15T19:00:00+00:00",
                 "venue": {"name": "House of Blues New Orleans", "cityName": "New Orleans",
                           "countryCode": "US", "region": "Louisiana"}, "festival": None},
                {"name": "Billie Eilish", "type": "concert", "date": "2099-03-01T20:00:00+00:00",
                 "venue": {"name": "The Forum", "cityName": "Inglewood", "countryCode": "US",
                           "region": "California"}, "festival": None}],
                "page": {"offset": 0, "limit": 100, "next": None, "total": 2}}
        raise AssertionError("unexpected request: " + url)
    return fetch


@pytest.fixture(autouse=True)
def kv(monkeypatch):
    """Each test gets its own cache. The adapter keeps every 200 for six
    hours in the app's key/value store, and the tests share one SQLite
    file - without this, one test's answers would be served to the next
    test's failing fetch."""
    import db
    store = {}
    monkeypatch.setattr(db, "get_kv", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(db, "set_kv", lambda key, value: store.__setitem__(key, value))
    return store


LEGACY_KEYS = ("SOUNDCHARTS_APP_ID", "SOUNDCHARTS_API_KEY")
OAUTH_KEYS = ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET", "SOUNDCHARTS_TEAM_ID")


@pytest.fixture
def sc(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    for k in OAUTH_KEYS:
        monkeypatch.delenv(k, raising=False)
    calls = []
    a = providers.SoundchartsAdapter(fetch=_fake_fetch(calls))
    a.calls = calls
    return a


def test_unconfigured_it_refuses_rather_than_guessing(monkeypatch):
    for k in ("SOUNDCHARTS_ENABLED",) + LEGACY_KEYS + OAUTH_KEYS:
        monkeypatch.delenv(k, raising=False)
    a = providers.SoundchartsAdapter(fetch=lambda url: pytest.fail("must not call out"))
    assert a.configured() is False
    with pytest.raises(providers.ProviderError):
        a.get_artist(BILLIE)


def test_search_returns_the_shared_shape(sc):
    hits = sc.search_artists("billie eilish", limit=5)
    assert len(hits) == 2 and hits[0]["provider_artist_id"] == BILLIE
    a = hits[0]
    assert a["name"] == "Billie Eilish" and a["genre"] == "Pop" and a["country"] == "US"
    assert a["city"] == "Los Angeles" and a["career_stage"] == "Established"
    assert a["monthly_listeners"] is None, "the search carries no number; none is invented"
    assert hits[1]["career_stage"] == "Emerging" and hits[1]["genre"] == ""
    assert "/api/v2/artist/search/billie%20eilish?" in sc.calls[0] and "limit=5" in sc.calls[0]
    for key in ("image_url", "website", "socials", "state", "region"):
        assert key in a, key


def test_a_blank_search_is_empty_and_free(sc):
    assert sc.search_artists("", limit=25) == []
    assert sc.calls == []


def test_the_artist_carries_the_measured_listener_count(sc):
    a = sc.get_artist(BILLIE)
    assert a["monthly_listeners"] == 78313841, "Spotify's figure from current stats, not Pandora's"
    assert a["website"] == "http://www.billieeilish.com/" and a["isni"] == "000000046748058X"
    assert a["socials"] == {"instagram": "", "tiktok": "", "youtube": ""}


def test_metrics_are_two_series_and_pages_are_followed(sc):
    pts = sc.get_artist_metrics(BILLIE, date(2020, 10, 1), date(2020, 10, 10))
    listeners = [p for p in pts if p["metric"] == "spotify_monthly_listeners"]
    followers = [p for p in pts if p["metric"] == "spotify_followers"]
    assert [p["date"] for p in listeners] == ["2020-10-03", "2020-10-10"]
    assert listeners[1]["value"] == 40948759
    assert [p["date"] for p in followers] == ["2020-10-01", "2020-10-02", "2020-10-03"]
    assert any("offset=2" in c for c in sc.calls), "the second page was fetched"
    assert any("startDate=2020-10-01&endDate=2020-10-10" in c for c in sc.calls)


def test_a_metric_endpoint_outside_the_plan_costs_that_series_only(monkeypatch, kv):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    a = providers.SoundchartsAdapter(fetch=_fake_fetch([], deny=("/streaming/spotify/listening",)))
    pts = a.get_artist_metrics(BILLIE, date(2020, 10, 1), date(2020, 10, 10))
    assert pts and all(p["metric"] == "spotify_followers" for p in pts)
    kv.clear()               # or the followers series above answers for the next adapter
    both = providers.SoundchartsAdapter(fetch=_fake_fetch([], deny=("/streaming/spotify", "/audience/spotify")))
    with pytest.raises(providers.ProviderError):
        both.get_artist_metrics(BILLIE, date(2020, 10, 1), date(2020, 10, 10))


def test_a_later_page_failing_keeps_the_first_page(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    inner = _fake_fetch([])

    def fetch(url):
        if "offset=2" in url:
            raise providers.ProviderError("Soundcharts 403: their own next-link, refused")
        return inner(url)
    a = providers.SoundchartsAdapter(fetch=fetch)
    pts = a.get_artist_metrics(BILLIE, date(2020, 10, 1), date(2020, 10, 10))
    assert [p["date"] for p in pts if p["metric"] == "spotify_followers"] == ["2020-10-01", "2020-10-02"]


def test_cities_come_from_the_newest_breakdown_with_an_honest_change(sc):
    cities = sc.get_artist_cities(BILLIE, date(2020, 9, 1), date(2020, 10, 10))
    assert [c["city"] for c in cities] == ["Chicago", "Amsterdam", "Copenhagen"], "largest first"
    chicago, amsterdam, copenhagen = cities
    assert chicago["listeners"] == 542605 and chicago["country"] == "US" and chicago["region"] == "Illinois"
    assert chicago["change_28d_pct"] == 8.5, "against the 12 Sep breakdown, 28 days back"
    assert amsterdam["change_28d_pct"] == -0.7
    assert copenhagen["change_28d_pct"] is None, "no earlier point for it - not measured"
    assert chicago["as_of"] == "2020-10-10"


def test_releases_pull_label_upc_and_distributor_from_the_album(sc):
    rels = sc.get_artist_releases(BILLIE)
    assert [r["title"][:7] for r in rels] == ["Happier", "WHEN WE", "&burn -"], "newest first"
    happier, wwafa, burn = rels
    assert wwafa["upc"] == "00602577427657" and wwafa["label_text"] == "Interscope, Darkroom"
    assert wwafa["distributor_name"] == "Universal" and wwafa["distributor_class"] == "Major Label"
    assert wwafa["track_count"] == 14 and wwafa["release_type"] == "Album"
    assert happier["distributor_class"] == "Needs Research", "an unrecognised distributor is research, not a guess"
    assert burn["upc"] == "" and burn["distributor_class"] == "Unknown", "album not in the plan: blank, no crash"
    assert burn["release_type"] == "Unknown"
    assert len([c for c in sc.calls if "/album/by-uuid/" in c]) == 3, "one metadata call per album"


def test_distributor_ladder_matches_the_products_classes():
    import signal_store as sstore
    for name, cls in (("Universal", "Major Label"), ("Sony Music", "Major Label"),
                      ("DistroKid", "DIY / Self-Service"), ("The Orchard", "Major-Affiliated Distribution"),
                      ("Believe", "Enterprise Distribution"), ("ADA", "Major-Affiliated Distribution"),
                      ("Canada Records", "Needs Research"), ("", "Unknown")):
        assert providers._sc_distributor_class(name) == cls, name
        assert cls in sstore.DISTRIBUTOR_CLASSES


def test_label_and_distributor_evidence_name_their_source(sc):
    labels = sc.get_label_evidence(ALBUM)
    assert [l["label_name"] for l in labels] == ["Interscope", "Darkroom"]
    assert labels[0]["classification"] == "Major Label" and labels[0]["source_label"] == "Soundcharts album metadata"
    dist = sc.get_distributor_evidence(ALBUM)
    assert len(dist) == 1 and dist[0]["distributor_name"] == "Universal"
    assert dist[0]["confidence"] == 0.6 and "beta" in dist[0]["source_label"]
    with pytest.raises(providers.ProviderError):
        sc.get_distributor_evidence("nope")          # an album outside the plan is an error, not a blank claim


def test_playlists_social_and_events_keep_to_what_is_measured(sc):
    pls = sc.get_playlist_activity(BILLIE, date(2020, 1, 1), date(2020, 2, 1))
    assert pls[1]["playlist_name"] == "Today's Top Hits" and pls[1]["editorial"] is True
    assert pls[0]["editorial"] is False and pls[0]["followers"] == 120000
    assert all(p["estimated_streams"] is None for p in pls), "they do not measure it; nor do we"
    social = {s["platform"]: s for s in sc.get_social_activity(BILLIE, date(2020, 1, 1), date(2020, 2, 1))}
    assert social["instagram"]["followers"] == 124103562
    assert social["instagram"]["change_28d_pct"] is None and social["instagram"]["change_7d_pct"] == -0.01
    events = sc.get_events(BILLIE)
    assert [e["city"] for e in events] == ["Inglewood"], "2016 is not upcoming"
    assert events[0]["venue"] == "The Forum" and events[0]["date"] == "2099-03-01"


def test_the_registry_prefers_it_and_still_says_none_for_rights(sc):
    reg = providers.ProviderRegistry(adapters=[sc])
    assert reg.is_demo() is False
    for cap in (providers.CAP_ARTIST, providers.CAP_METRICS, providers.CAP_CITIES,
                providers.CAP_RELEASES, providers.CAP_LABEL, providers.CAP_DISTRIBUTOR):
        assert reg.for_capability(cap).key == "soundcharts", cap
    assert reg.for_capability(providers.CAP_RIGHTS) is None


def test_ingest_writes_metrics_cities_releases_and_evidence(sc):
    import db as store
    import signal_ingest as ingest
    import signal_store as sstore
    store.init_db()
    sstore.init_signal()
    reg = providers.ProviderRegistry(adapters=[sc])
    artist_id = ingest.ingest_artist(BILLIE, reg=reg, force=True)
    assert artist_id
    art = sstore.get_artist(artist_id)
    assert art["canonical_name"] == "Billie Eilish"
    assert sstore.metric_series(artist_id, "spotify_monthly_listeners")[-1][1] == 40948759
    assert sstore.metric_series(artist_id, "spotify_followers")
    titles = {r["title"] for r in sstore.list_releases(artist_id)}
    assert "Happier Than Ever" in titles


# --- the six-hour cache ---------------------------------------------------------
#
# Every Soundcharts call is billed. The same question inside six hours is
# answered from the app's key/value store; an error is never kept, so a
# transient 500 cannot stick for six hours.

@pytest.fixture
def cached(monkeypatch, kv):
    """A configured adapter with a movable clock over the per-test store."""
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    monkeypatch.delenv("SOUNDCHARTS_CACHE_S", raising=False)
    now = [datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(providers, "_utcnow", lambda: now[0])
    calls = []
    a = providers.SoundchartsAdapter(fetch=_fake_fetch(calls))
    a.calls, a.kv, a.now = calls, kv, now
    return a


def test_the_same_question_twice_inside_six_hours_is_one_fetch(cached):
    first = cached.get_artist(BILLIE)
    n = len(cached.calls)
    assert n >= 1
    assert cached.get_artist(BILLIE) == first
    assert len(cached.calls) == n, "the second read came from the store"
    assert all(k.startswith("soundcharts:") for k in cached.kv)
    entry = json.loads(next(iter(cached.kv.values())))
    assert set(entry) == {"at", "status", "body"} and entry["status"] == 200


def test_after_six_hours_and_a_second_it_fetches_again(cached):
    cached.get_artist(BILLIE)
    n = len(cached.calls)
    cached.now[0] += timedelta(hours=6, seconds=1)
    cached.get_artist(BILLIE)
    assert len(cached.calls) == 2 * n


def test_a_failed_call_is_not_cached(cached):
    boom = [True]
    real = cached._fetch

    def flaky(url):
        if boom[0]:
            raise providers.ProviderError("Soundcharts 500: Internal Server Error")
        return real(url)
    cached._fetch = flaky
    with pytest.raises(providers.ProviderError):
        cached._get("/api/v2.9/artist/%s" % BILLIE)
    assert cached.kv == {}, "a 500 must not stick for six hours"
    boom[0] = False
    assert cached._get("/api/v2.9/artist/%s" % BILLIE)["object"]["uuid"] == BILLIE
    assert len(cached.kv) == 1


def test_the_order_of_the_parameters_does_not_change_the_key():
    k = providers.SoundchartsAdapter.cache_key
    assert k("/x", {"offset": 0, "limit": 5}) == k("/x", {"limit": 5, "offset": 0})
    assert k("/x", {"offset": 0, "limit": 5}) != k("/x", {"offset": 0, "limit": 6})
    assert k("/x", {}) != k("/y", {})


def test_the_ttl_is_six_hours_unless_the_environment_says_otherwise(monkeypatch):
    monkeypatch.delenv("SOUNDCHARTS_CACHE_S", raising=False)
    assert providers.SoundchartsAdapter.cache_ttl() == 6 * 3600
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "60")
    assert providers.SoundchartsAdapter.cache_ttl() == 60
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    assert providers.SoundchartsAdapter.cache_ttl() == 0


def test_a_zero_ttl_disables_the_cache(cached, monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    cached.get_artist(BILLIE)
    n = len(cached.calls)
    cached.get_artist(BILLIE)
    assert len(cached.calls) == 2 * n and cached.kv == {}


# --- signing in ------------------------------------------------------------------
# Soundcharts' current grant is OAuth client credentials: a client id and
# secret are exchanged for a one-hour bearer token. These drive the whole
# path over a fake wire - the token endpoint and the API - so the header
# on every call, the mint count and the 401 retry are all asserted, and
# nothing reaches the network.

def _wire(minted, api, token_answer=None, deny_401=0):
    """`minted` collects (url, headers, body) of every token request; `api`
    collects (url, headers) of every API call. The first `deny_401` API
    calls answer 401 the way an expired token does."""
    state = {"n": 0, "denied": 0}

    def token_http(url, headers, body):
        minted.append((url, headers, body))
        if token_answer is not None:
            return token_answer()
        state["n"] += 1
        return {"access_token": "tok-%d" % state["n"], "token_type": "bearer",
                "expires_in": 3600, "refresh_token": None}

    def http(url, headers):
        api.append((url, headers))
        if state["denied"] < deny_401:
            state["denied"] += 1
            raise providers._HttpError(401, "Expired JWT Token")
        return {"type": "artist", "object": ARTIST}
    return http, token_http


@pytest.fixture
def oauth(monkeypatch, kv):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_CLIENT_ID", "cid")
    monkeypatch.setenv("SOUNDCHARTS_CLIENT_SECRET", "sec")
    monkeypatch.delenv("SOUNDCHARTS_TEAM_ID", raising=False)
    for k in LEGACY_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")      # every call reaches the wire
    now = [datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(providers, "_utcnow", lambda: now[0])

    def make(**wire_kw):
        minted, api = [], []
        http, token_http = _wire(minted, api, **wire_kw)
        a = providers.SoundchartsAdapter(http=http, token_http=token_http)
        a.minted, a.api, a.now, a.kv = minted, api, now, kv
        return a
    return make


def _bearer(call):
    return call[1].get("Authorization")


def test_oauth_mode_mints_once_and_reuses_the_token(oauth):
    a = oauth()
    assert a.configured() and a.auth_mode() == "oauth"
    assert a.get_artist(BILLIE)["name"] == "Billie Eilish"
    assert a.get_artist(BILLIE)["name"] == "Billie Eilish"
    assert len(a.minted) == 1, "one sign-in serves every call inside the hour"
    assert len(a.api) == 4, "an artist is two calls (identity + current stats), so four on the wire"
    url, headers, body = a.minted[0]
    assert url == providers.SOUNDCHARTS_TOKEN_URL == "https://account.soundcharts.com/oauth/token"
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"cid:sec").decode("ascii")
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert body == "grant_type=client_credentials"
    assert [_bearer(c) for c in a.api] == ["Bearer tok-1"] * 4
    assert all("x-app-id" not in c[1] and "x-api-key" not in c[1] for c in a.api)
    entry = json.loads(a.kv["soundcharts:oauth-token"])
    assert entry["token"] == "tok-1" and entry["expires_at"] == "2026-09-09T13:00:00+00:00"


def test_the_team_id_rides_along_when_set(oauth, monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_TEAM_ID", "team-7")
    a = oauth()
    a.get_artist(BILLIE)
    assert a.minted[0][2] == "grant_type=client_credentials&team_id=team-7"


def test_the_token_is_re_minted_after_expiry_with_a_minute_to_spare(oauth):
    a = oauth()
    a.get_artist(BILLIE)
    a.now[0] += timedelta(seconds=3600 - 61)
    a.get_artist(BILLIE)
    assert len(a.minted) == 1, "fifty-nine minutes in, the token still has more than a minute"
    a.now[0] += timedelta(seconds=2)
    a.get_artist(BILLIE)
    assert len(a.minted) == 2, "inside the last minute it is minted again"
    assert _bearer(a.api[-1]) == "Bearer tok-2"


def test_a_stored_token_is_shared_by_a_second_process(oauth):
    first = oauth()
    first.get_artist(BILLIE)
    second = oauth()
    second.get_artist(BILLIE)
    assert second.minted == [] and _bearer(second.api[0]) == "Bearer tok-1"


def test_a_401_forgets_the_token_and_mints_exactly_once_more(oauth):
    a = oauth(deny_401=1)
    assert a.get_artist(BILLIE)["name"] == "Billie Eilish"
    assert len(a.minted) == 2
    assert [_bearer(c) for c in a.api] == ["Bearer tok-1", "Bearer tok-2", "Bearer tok-2"],         "the 401, the retry, then the stats call on the fresh token"
    a.kv.clear()
    stubborn = oauth(deny_401=2)
    with pytest.raises(providers.ProviderError, match=r"^Soundcharts 401: Expired JWT Token$"):
        stubborn.get_artist(BILLIE)
    assert len(stubborn.minted) == 2 and len(stubborn.api) == 2, "a second 401 is the answer"


def test_a_sign_in_failure_names_the_status_and_calls_no_api(oauth):
    def refused():
        raise providers._HttpError(401, "Invalid client credentials")
    a = oauth(token_answer=refused)
    with pytest.raises(providers.ProviderError, match=r"^Soundcharts sign-in failed: 401 Invalid client credentials$"):
        a.get_artist(BILLIE)
    assert a.api == [] and "soundcharts:oauth-token" not in a.kv

    def empty():
        return {"token_type": "bearer"}
    b = oauth(token_answer=empty)
    with pytest.raises(providers.ProviderError, match=r"sign-in failed: no access_token"):
        b.get_artist(BILLIE)


def test_legacy_mode_still_sends_the_app_id_headers_and_never_signs_in(oauth, monkeypatch):
    for k in ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET"):
        monkeypatch.delenv(k)
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    a = oauth()
    assert a.auth_mode() == "legacy"
    assert a.get_artist(BILLIE)["name"] == "Billie Eilish"
    assert a.minted == [] and a.kv == {}
    assert a.api[0][1]["x-app-id"] == "id" and a.api[0][1]["x-api-key"] == "key"
    assert "Authorization" not in a.api[0][1]


@pytest.mark.parametrize("flag, env, configured, mode", [
    ("1", {"SOUNDCHARTS_CLIENT_ID": "c", "SOUNDCHARTS_CLIENT_SECRET": "s"}, True, "oauth"),
    ("1", {"SOUNDCHARTS_APP_ID": "a", "SOUNDCHARTS_API_KEY": "k"}, True, "legacy"),
    ("1", {"SOUNDCHARTS_CLIENT_ID": "c", "SOUNDCHARTS_CLIENT_SECRET": "s",
           "SOUNDCHARTS_APP_ID": "a", "SOUNDCHARTS_API_KEY": "k"}, True, "oauth"),
    ("1", {"SOUNDCHARTS_CLIENT_ID": "c"}, False, ""),
    ("1", {"SOUNDCHARTS_CLIENT_SECRET": "s", "SOUNDCHARTS_API_KEY": "k"}, False, ""),
    ("1", {}, False, ""),
    ("", {"SOUNDCHARTS_CLIENT_ID": "c", "SOUNDCHARTS_CLIENT_SECRET": "s"}, False, "oauth"),
    ("", {"SOUNDCHARTS_APP_ID": "a", "SOUNDCHARTS_API_KEY": "k"}, False, "legacy"),
])
def test_configured_needs_the_flag_and_either_pair(monkeypatch, flag, env, configured, mode):
    for k in LEGACY_KEYS + OAUTH_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", flag)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    a = providers.SoundchartsAdapter()
    assert a.configured() is configured and a.auth_mode() == mode
    h = a.health_check()
    assert h["configured"] is configured
    assert h["auth"] == providers.SOUNDCHARTS_AUTH_LABELS.get(mode, "")
    if flag and not mode:
        assert "SOUNDCHARTS_CLIENT_ID" in h["detail"] and "SOUNDCHARTS_APP_ID" in h["detail"]


# --- the sandbox itself --------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("SOUNDCHARTS_SANDBOX_LIVE"),
                    reason="talks to Soundcharts' public sandbox; set SOUNDCHARTS_SANDBOX_LIVE=1")
def test_the_public_sandbox_answers_in_these_shapes(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "soundcharts")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "soundcharts")
    for k in OAUTH_KEYS:
        monkeypatch.delenv(k, raising=False)      # the sandbox is legacy-only
    a = providers.SoundchartsAdapter()
    art = a.get_artist(BILLIE)
    assert art["name"] == "Billie Eilish" and art["city"] == "Los Angeles" and art["monthly_listeners"] > 1000000
    hits = a.search_artists("billie eilish", limit=3)
    assert hits and hits[0]["provider_artist_id"] == BILLIE
    pts = a.get_artist_metrics(BILLIE, date(2020, 10, 1), date(2020, 10, 10))
    assert {p["metric"] for p in pts} == {"spotify_monthly_listeners", "spotify_followers"}
    cities = a.get_artist_cities(BILLIE, date(2020, 10, 1), date(2020, 10, 10))
    assert cities and cities[0]["listeners"] > 0 and all(c["change_28d_pct"] is None for c in cities)
    rels = a.get_artist_releases(BILLIE)
    assert rels and all(r["provider"] == "soundcharts" for r in rels)
    labels = a.get_label_evidence(ALBUM)
    assert {l["label_name"] for l in labels} == {"Interscope", "Darkroom"}
    assert a.get_distributor_evidence(ALBUM)[0]["distributor_name"] == "Universal"
    assert a.get_playlist_activity(BILLIE, date(2020, 1, 1), date(2020, 2, 1))
    assert a.get_social_activity(BILLIE, date(2020, 1, 1), date(2020, 2, 1))
    assert isinstance(a.get_events(BILLIE), list)


def test_a_ready_made_access_token_is_sent_as_the_bearer(monkeypatch):
    """The owner's Soundcharts page (2026-09-09) shows an app id and a
    token, not an api key: the token goes on the wire as the bearer, no
    minting, no legacy headers."""
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.delenv("SOUNDCHARTS_CLIENT_ID", raising=False)
    monkeypatch.delenv("SOUNDCHARTS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SOUNDCHARTS_API_KEY", raising=False)
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "app-1")
    monkeypatch.setenv("SOUNDCHARTS_ACCESS_TOKEN", "issued-token")
    seen = []

    def http(url, headers):
        seen.append(dict(headers))
        return {"items": []}
    a = providers.SoundchartsAdapter(http=http, token_http=lambda *a: (_ for _ in ()).throw(AssertionError("no minting")))
    assert a.auth_mode() == "token" and a.configured()
    assert a.search_artists("billie") == []
    assert seen and seen[0].get("Authorization") == "Bearer issued-token"
    assert "x-api-key" not in seen[0]
    assert a.health_check()["auth"] == "access token issued by Soundcharts"


def test_a_token_their_account_wants_as_an_api_key_is_retried_as_the_pair(monkeypatch):
    """Live, 2026-09-09: the value Soundcharts issued beside the app id was
    refused as a bearer with 401 Invalid credentials. Their dashboard names
    it inconsistently, so rather than make somebody guess which slot a secret
    belongs in, a 401 in token mode tries the x-app-id + x-api-key pair once
    and keeps whichever the account accepts."""
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    for k in ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET", "SOUNDCHARTS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "app-1")
    monkeypatch.setenv("SOUNDCHARTS_ACCESS_TOKEN", "the-value")
    seen = []

    def http(url, headers):
        seen.append(dict(headers))
        if "Authorization" in headers:                 # their account refuses a bearer
            raise providers._HttpError(401, "Invalid credentials")
        assert headers["x-app-id"] == "app-1" and headers["x-api-key"] == "the-value"
        return {"items": []}
    a = providers.SoundchartsAdapter(http=http)
    assert a.auth_mode() == "token"
    assert a.search_artists("billie") == []
    assert len(seen) == 2 and "Authorization" in seen[0] and "x-api-key" in seen[1]
    a.search_artists("another")                        # remembered: no wasted 401
    assert "x-api-key" in seen[-1] and all("Authorization" not in h for h in seen[2:])


def test_a_pair_that_is_also_refused_reports_their_words_and_does_not_latch(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    for k in ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET", "SOUNDCHARTS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "app-1")
    monkeypatch.setenv("SOUNDCHARTS_ACCESS_TOKEN", "the-value")

    def http(url, headers):
        raise providers._HttpError(401, "Invalid credentials")
    a = providers.SoundchartsAdapter(http=http)
    with pytest.raises(providers.ProviderError) as e:
        a.search_artists("billie")
    assert "401" in str(e.value) and "Invalid credentials" in str(e.value)
    assert a._pair_instead is False, "a shape that also failed is not remembered"
