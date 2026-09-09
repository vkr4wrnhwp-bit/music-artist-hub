"""Discogs, asked about the pressing behind a song.

Discogs is a discography, not an audience source. It answers what a
record IS - the label, the catalogue number, the country, the year, the
format, and the people printed on the sleeve - and publishes no listener
figure at all. So the owner looks a song up, picks the pressing that is
actually theirs, and attaches it; the attach fills only passport fields
that are still EMPTY, the same rule the MLC fill action follows, and
records which fields Discogs supplied.

Credits are the deliberate exception. They are shown for the owner to
read and are never written into splits or the passport's songwriter
fields: a credit on a third-party database is somebody else's record of
a release, not a rights claim this app may make on an artist's behalf.

The canned answers below are Discogs' own shapes, trimmed - verified
against the live API and their documentation on 2026-09-09.
"""
import json
import uuid
from datetime import timedelta

import pytest

import db as store
import signal_providers as providers
from app import create_app

PASSWORD = "discogs-pass-123"

# --- Discogs' own shapes, trimmed ------------------------------------------

SEARCH = {
    "pagination": {"page": 1, "pages": 1, "per_page": 10, "items": 2},
    "results": [
        {"country": "UK", "year": "1987", "type": "release",
         "label": ["RCA", "BMG Records (UK) Ltd."], "id": 249504,
         "master_id": 96559, "catno": "PB 41447",
         "title": "Rick Astley - Never Gonna Give You Up",
         "barcode": ["5012394144777"],
         "uri": "/release/249504-Rick-Astley-Never-Gonna-Give-You-Up",
         "formats": [{"name": "Vinyl", "qty": "1",
                      "descriptions": ["7\"", "45 RPM", "Single", "Stereo"]}]},
        {"country": "Europe", "year": "2015", "type": "release",
         "label": ["Geffen Records"], "id": 7445961, "master_id": 96559,
         "catno": "0602547378781",
         "title": "Rick Astley - Never Gonna Give You Up",
         "barcode": ["602547378781"],
         "uri": "/release/7445961",
         "formats": [{"name": "Vinyl", "qty": "2", "text": "180 Gram",
                      "descriptions": ["LP", "Compilation", "Reissue"]}]},
    ],
}

RELEASE = {
    "id": 249504, "master_id": 96559, "year": 1987, "country": "UK",
    "released": "1987-07-00", "title": "Never Gonna Give You Up",
    "uri": "https://www.discogs.com/release/249504",
    "artists": [{"name": "Rick Astley", "anv": "", "join": "", "role": "", "id": 72872}],
    "labels": [{"name": "RCA", "catno": "PB 41447", "entity_type": "1",
                "entity_type_name": "Label", "id": 895}],
    "formats": [{"name": "Vinyl", "qty": "1",
                 "descriptions": ["7\"", "45 RPM", "Single", "Stereo"]}],
    "identifiers": [
        {"type": "Barcode", "value": "5012394144777"},
        {"type": "Label Code", "value": "LC 0316"},
        {"type": "ISRC", "value": "GB-ARL-87-00123"},
        {"type": "Matrix / Runout", "value": "PB 41447 A", "description": "A side label"},
    ],
    "extraartists": [
        {"name": "Stock, Aitken & Waterman", "anv": "", "role": "Producer, Written-By"},
        {"name": "Mark McGuire", "anv": "", "role": "Engineer"},
    ],
    "tracklist": [
        {"position": "A", "type_": "track", "title": "Never Gonna Give You Up",
         "duration": "3:32",
         "extraartists": [{"name": "Pete Hammond", "role": "Mixed By"}]},
        {"position": "B", "type_": "track", "title": "Never Gonna Give You Up (Instrumental)"},
    ],
}

OK_HEADERS = {"X-Discogs-Ratelimit": "60", "X-Discogs-Ratelimit-Used": "1",
              "X-Discogs-Ratelimit-Remaining": "59", "Content-Type": "application/json"}


class Fake(object):
    """A canned wire. Records every call so a test can read the headers
    that went out, and answers the shapes above by path."""

    def __init__(self, status=200, body=None, headers=None):
        self.status, self.body, self.headers = status, body, headers
        self.calls = []

    def __call__(self, method, url, headers):
        self.calls.append({"method": method, "url": url, "headers": dict(headers)})
        if self.status != 200:
            return self.status, (self.headers or {}), self.body
        if "/database/search" in url:
            return 200, OK_HEADERS, SEARCH
        if "/releases/" in url:
            return 200, OK_HEADERS, RELEASE
        if "/versions" in url:
            return 200, OK_HEADERS, {"pagination": {"page": 1, "pages": 1},
                                     "versions": []}
        return 404, OK_HEADERS, {"message": "not found"}


def _adapter(monkeypatch, fake=None):
    """A Discogs adapter with a canned wire, wired in as the one the app
    uses. `sleep` is stubbed so the rate-limit pacing does not make the
    suite wait for it."""
    fake = fake if fake is not None else Fake()
    adapter = providers.DiscogsAdapter(transport=fake, sleep=lambda s: None)
    monkeypatch.setattr(providers, "discogs_adapter", lambda: adapter)
    return adapter, fake


def _connect(monkeypatch, fake=None):
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "a-personal-access-token")
    monkeypatch.delenv("SANDBOX", raising=False)
    # The six-hour cache is a real store and the test database outlives one
    # test, so a test that counts calls turns it off and the one test that
    # is ABOUT the cache turns it back on with a question of its own.
    monkeypatch.setenv("DISCOGS_CACHE_S", "0")
    return _adapter(monkeypatch, fake)


def _artist(app_obj):
    email = "discogs-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _track(client, user, title="Never Gonna Give You Up", **passport):
    client.post("/tracks/add", data={"title": title})
    track = [t for t in store.list_os_tracks(user["id"]) if t["title"] == title][0]
    if passport:
        p = track["passport"]
        p.update(passport)
        store.update_os_track_passport(user["id"], track["id"], p)
    return track


# --- the adapter ------------------------------------------------------------

def test_search_parses_the_candidates_discogs_answers(monkeypatch):
    adapter, fake = _connect(monkeypatch)
    rows = adapter.search_release("Rick Astley", "Never Gonna Give You Up")
    assert [r["release_id"] for r in rows] == ["249504", "7445961"]
    first = rows[0]
    assert first["year"] == "1987" and first["country"] == "UK"
    assert first["label"] == "RCA", "the imprint, not the pressing plant"
    assert first["catno"] == "PB 41447"
    assert first["formats"] == 'Vinyl, 7", 45 RPM, Single, Stereo'
    assert first["master_id"] == "96559"
    assert first["url"] == "https://www.discogs.com/release/249504"
    # A multi-disc pressing says how many, and their free-text note rides along.
    assert rows[1]["formats"] == "2 x Vinyl, LP, Compilation, Reissue, 180 Gram"

    url = fake.calls[0]["url"]
    assert url.startswith("https://api.discogs.com/database/search?")
    assert "type=release" in url and "artist=Rick+Astley" in url
    assert "release_title=Never+Gonna+Give+You+Up" in url

    # A catalogue number or a barcode identifies a pressing on its own.
    adapter.search_release("Rick Astley", "Never Gonna Give You Up",
                           catno="PB 41447", barcode="5012394144777")
    url = fake.calls[-1]["url"]
    assert "catno=PB+41447" in url and "barcode=5012394144777" in url
    # Nothing to go on is nothing back, not the front page of the database.
    assert adapter.search_release("", "") == [] and len(fake.calls) == 2


def test_a_release_carries_the_pressing_detail_and_its_zero_dates_are_not_invented(monkeypatch):
    adapter, _fake = _connect(monkeypatch)
    rel = adapter.get_release(249504)
    assert rel["label"] == "RCA" and rel["catno"] == "PB 41447"
    assert rel["country"] == "UK" and rel["formats"] == 'Vinyl, 7", 45 RPM, Single, Stereo'
    assert rel["barcode"] == "5012394144777"
    assert rel["isrc"] == "GBARL8700123", "punctuation stripped, as an ISRC is stored"
    # Discogs prints an unknown day as 00. July 1987 is July 1987; there is
    # no day here, and one must not be invented to fill a date field.
    assert rel["released"] == "1987-07"
    assert providers._discogs_date("1987-00-00") == "1987"
    assert providers._discogs_date("") == ""


def test_credits_are_normalised_name_and_role_and_a_compound_role_stays_whole(monkeypatch):
    adapter, _fake = _connect(monkeypatch)
    credits = adapter.credits_for(249504)
    assert {"name": "Mark McGuire", "role": "Engineer"} in credits
    assert {"name": "Pete Hammond", "role": "Mixed By"} in credits, "track credits count too"
    # "Producer, Written-By" is how the sleeve reads. Splitting it would be
    # this app deciding which half of somebody's credit is a writing claim.
    assert {"name": "Stock, Aitken & Waterman", "role": "Producer, Written-By"} in credits
    assert all(set(c) == {"name", "role"} for c in credits)


def test_the_user_agent_is_always_sent_and_is_descriptive(monkeypatch):
    """Discogs refuses a request with no User-Agent at the edge, and their
    docs name generic library and browser agents as the ones they block."""
    adapter, fake = _connect(monkeypatch)
    adapter.search_release("Rick Astley", "Never Gonna Give You Up")
    adapter.get_release(249504)
    adapter.pressings_for(96559)
    assert len(fake.calls) == 3
    for call in fake.calls:
        ua = call["headers"].get("User-Agent") or ""
        assert ua, "Discogs answers 403 to a request with no User-Agent"
        assert "StreetBanker" in ua and "://" in ua, "it must identify this app"
        low = ua.lower()
        assert not any(bad in low for bad in ("curl/", "mozilla/", "python-requests",
                                              "urllib", "libwww")), (
            "their docs list generic agents as the ones they silently block")
        # The token travels as a header, not in the query string.
        assert call["headers"]["Authorization"] == "Discogs token=a-personal-access-token"
        assert "token=a-personal" not in call["url"]


def test_the_rate_limit_headers_are_read_and_a_spent_window_waits_once(monkeypatch):
    """Their limit is 60 a minute authenticated, over a rolling 60-second
    window, reported on every response. The adapter paces itself by it and
    never spins: there is no retry loop to run away."""
    slept = []
    fake = Fake()
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "t")
    adapter = providers.DiscogsAdapter(transport=fake, sleep=slept.append)
    monkeypatch.setenv("DISCOGS_CACHE_S", "0")
    adapter.get_release(249504)
    assert adapter.rate_limit() == {"limit": 60, "remaining": 59}

    monkeypatch.setitem(OK_HEADERS, "X-Discogs-Ratelimit-Remaining", "0")
    adapter.get_release(249504)
    assert adapter.rate_limit()["remaining"] == 0
    slept[:] = []
    adapter.get_release(249504)
    assert slept and max(slept) >= adapter.window_s, "the window is waited out, once"


def test_a_401_and_a_429_carry_discogs_own_message(monkeypatch):
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "wrong")
    monkeypatch.setenv("DISCOGS_CACHE_S", "0")
    bad = Fake(status=401,
               body={"message": "Invalid consumer token. Please register an app "
                                "before making requests."})
    adapter = providers.DiscogsAdapter(transport=bad, sleep=lambda s: None)
    with pytest.raises(providers.ProviderError) as e:
        adapter.search_release("Rick Astley", "Never Gonna Give You Up")
    assert "Invalid consumer token" in str(e.value) and "401" in str(e.value)

    spent = Fake(status=429, body={"message": "You are making requests too quickly."},
                 headers={"X-Discogs-Ratelimit-Remaining": "0"})
    adapter = providers.DiscogsAdapter(transport=spent, sleep=lambda s: None)
    with pytest.raises(providers.ProviderError) as e:
        adapter.get_release(249504)
    assert "429" in str(e.value) and "too quickly" in str(e.value)
    assert len(spent.calls) == 1, "a refusal is raised, never retried in a loop"

    # A refusal with no body at all - which is what a spent window answered
    # on 2026-09-09 - states their published limit rather than quoting
    # words Discogs did not say.
    silent = Fake(status=429, body=None)
    adapter = providers.DiscogsAdapter(transport=silent, sleep=lambda s: None)
    with pytest.raises(providers.ProviderError) as e:
        adapter.get_release(249504)
    assert "60 requests a minute" in str(e.value)


def test_the_cache_holds_for_six_hours_and_a_non_200_is_never_cached(monkeypatch):
    adapter, fake = _connect(monkeypatch)
    monkeypatch.delenv("DISCOGS_CACHE_S", raising=False)
    assert adapter.cache_ttl() == 6 * 3600
    # A question nothing else in the suite asks, so the shared store starts
    # empty for it however the file is ordered.
    who = "Cache Probe %s" % uuid.uuid4().hex[:8]
    params = {"type": "release", "per_page": adapter.per_page, "page": 1,
              "artist": who, "release_title": "Night Drive"}

    now = providers._utcnow()
    monkeypatch.setattr(providers, "_utcnow", lambda: now)
    adapter.search_release(who, "Night Drive")
    adapter.search_release(who, "Night Drive")
    assert len(fake.calls) == 1, "the same question inside six hours is not asked twice"
    # The store keeps whole seconds, as the Soundcharts cache does.
    assert adapter.cached_at("/database/search", params) == now.replace(microsecond=0)

    monkeypatch.setattr(providers, "_utcnow",
                        lambda: now + timedelta(seconds=6 * 3600 + 1))
    assert adapter.cached_at("/database/search", params) is None, "the hold has expired"
    adapter.search_release(who, "Night Drive")
    assert len(fake.calls) == 2, "past six hours it is asked again"

    # An error frozen for six hours would be worse than no cache at all.
    bad = Fake(status=401, body={"message": "Invalid consumer token."})
    adapter = providers.DiscogsAdapter(transport=bad, sleep=lambda s: None)
    for _ in range(2):
        with pytest.raises(providers.ProviderError):
            adapter.get_release(249504)
    assert len(bad.calls) == 2, "a refusal is asked again, never served from the cache"

    monkeypatch.setenv("DISCOGS_CACHE_S", "0")
    assert providers.DiscogsAdapter.cache_ttl() == 0


def test_it_is_a_release_source_and_never_claims_to_measure_an_audience():
    caps = providers.DiscogsAdapter.capabilities
    assert providers.CAP_RELEASES in caps and providers.CAP_LABEL in caps
    # Discogs publishes community have/want counts and marketplace prices.
    # Those measure a second-hand market, not an audience.
    assert providers.CAP_METRICS not in caps
    assert providers.CAP_CITIES not in caps and providers.CAP_PLAYLISTS not in caps
    assert providers.DiscogsAdapter in providers._REAL_ADAPTERS


# --- the page ---------------------------------------------------------------

def test_without_the_token_there_is_no_action_and_the_page_names_the_variable(monkeypatch):
    for k in ("DISCOGS_ENABLED", "DISCOGS_TOKEN", "SANDBOX"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "discogs_adapter", lambda: providers.DiscogsAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    client, user = _artist(create_app())
    track = _track(client, user)
    page = client.get("/tracks").get_data(as_text=True)
    assert "Look up on Discogs" not in page
    assert "DISCOGS_TOKEN" in page and "DISCOGS_ENABLED" in page
    assert "No Discogs pressing attached" in page

    r = client.post("/tracks/%s/discogs" % track["id"], data={"action": "search"})
    assert r.status_code == 302 and "discogs=off" in r.headers["Location"]
    assert store.get_discogs_link(user["id"], track["id"]) is None


def test_a_sandbox_deployment_makes_no_call_even_with_a_token(monkeypatch):
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "a-real-looking-token")
    monkeypatch.setenv("SANDBOX", "1")
    adapter = providers.DiscogsAdapter(
        transport=lambda *a: pytest.fail("a sandbox must not reach Discogs"))
    monkeypatch.setattr(providers, "discogs_adapter", lambda: adapter)
    assert adapter.configured() is False
    assert adapter.health_check()["detail"] == "off in this sandbox deployment"

    client, user = _artist(create_app())
    track = _track(client, user)
    page = client.get("/tracks?discogs=%s" % track["id"]).get_data(as_text=True)
    assert "Look up on Discogs" not in page
    assert "off on this sandbox deployment" in page
    client.post("/tracks/%s/discogs" % track["id"], data={"action": "search"})
    assert store.get_discogs_link(user["id"], track["id"]) is None


def test_the_lookup_lists_candidates_and_runs_only_when_it_is_asked_for(monkeypatch):
    _adapter_obj, fake = _connect(monkeypatch)
    client, user = _artist(create_app())
    track = _track(client, user)

    page = client.get("/tracks").get_data(as_text=True)
    assert "Look up on Discogs" in page
    assert fake.calls == [], "opening the page calls nothing"

    r = client.post("/tracks/%s/discogs" % track["id"], data={"action": "search"})
    assert r.status_code == 302 and r.headers["Location"].endswith(
        "/tracks?discogs=%s#passports" % track["id"])
    page = client.get(r.headers["Location"]).get_data(as_text=True)
    # Year, country, label, catalogue number and format, per candidate.
    assert "1987" in page and "UK" in page and "RCA" in page and "PB 41447" in page
    assert 'Vinyl, 7&#34;, 45 RPM, Single, Stereo' in page or "45 RPM" in page
    assert "0602547378781" in page, "the reissue is offered too"
    assert "https://www.discogs.com/release/249504" in page
    assert store.get_discogs_link(user["id"], track["id"]) is None, "a search writes nothing"


def test_attach_stores_the_link_and_fills_only_empty_passport_fields(monkeypatch):
    _adapter_obj, _fake = _connect(monkeypatch)
    client, user = _artist(create_app())
    # A label the artist typed is a decision. Discogs is evidence, and
    # evidence never overwrites a decision.
    track = _track(client, user, label="My Own Imprint", isrc="USAIW2600123")

    client.post("/tracks/%s/discogs" % track["id"],
                data={"action": "attach", "release_id": "249504"})

    passport = store.get_os_track(user["id"], track["id"])["passport"]
    assert passport["label"] == "My Own Imprint", "what the artist typed stands"
    assert passport["isrc"] == "USAIW2600123", "so does the ISRC they typed"
    assert passport["release_title"] == "Never Gonna Give You Up"
    assert passport["release_date"] == "1987-07"
    assert passport["upc"] == "5012394144777"

    link = store.get_discogs_link(user["id"], track["id"])
    assert link["release_id"] == "249504" and link["master_id"] == "96559"
    assert link["catno"] == "PB 41447" and link["country"] == "UK"
    assert link["url"] == "https://www.discogs.com/release/249504"
    # The link records exactly which fields Discogs supplied, so a filled
    # value can always be told from a typed one afterwards.
    assert set(link["filled"]) == {"release_title", "release_date", "upc"}
    assert "label" not in link["filled"] and "isrc" not in link["filled"]

    page = client.get("/tracks").get_data(as_text=True)
    assert "Filled from Discogs" in page and "Release on Discogs" in page
    assert "PB 41447" in page


def test_credits_are_shown_and_never_written_into_splits_or_songwriters(monkeypatch):
    _adapter_obj, _fake = _connect(monkeypatch)
    client, user = _artist(create_app())
    track = _track(client, user)
    client.post("/tracks/%s/discogs" % track["id"],
                data={"action": "attach", "release_id": "249504"})

    passport = store.get_os_track(user["id"], track["id"])["passport"]
    for field in ("songwriters", "publishers", "producers", "split_sheet_status",
                  "pub_admin", "pro", "master_owner"):
        assert not (passport.get(field) or "").strip(), (
            "%s is a rights claim; a third-party database does not get to "
            "make it on somebody's behalf" % field)

    link = store.get_discogs_link(user["id"], track["id"])
    assert {"name": "Stock, Aitken & Waterman", "role": "Producer, Written-By"} in link["credits"]

    page = client.get("/tracks").get_data(as_text=True)
    assert "Credits printed on this pressing" in page
    assert "Mark McGuire" in page and "Engineer" in page
    assert "Producer, Written-By" in page
    assert "never written into your splits or songwriter fields" in page


def test_a_refusal_shows_discogs_own_words_on_the_page_and_writes_nothing(monkeypatch):
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "revoked")
    monkeypatch.delenv("SANDBOX", raising=False)
    monkeypatch.setenv("DISCOGS_CACHE_S", "0")
    for status, message in (
            (401, "Invalid consumer token. Please register an app before making requests."),
            (429, "You are making requests too quickly.")):
        fake = Fake(status=status, body={"message": message})
        adapter = providers.DiscogsAdapter(transport=fake, sleep=lambda s: None)
        monkeypatch.setattr(providers, "discogs_adapter", lambda a=adapter: a)
        client, user = _artist(create_app())
        track = _track(client, user)

        r = client.post("/tracks/%s/discogs" % track["id"], data={"action": "search"})
        page = client.get(r.headers["Location"]).get_data(as_text=True)
        assert message.split(".")[0] in page, "Discogs' own message, not a bare status"
        assert "Nothing was saved" in page
        assert store.get_discogs_link(user["id"], track["id"]) is None

        # An attach that hits the same refusal writes nothing either.
        client.post("/tracks/%s/discogs" % track["id"],
                    data={"action": "attach", "release_id": "249504"})
        assert store.get_discogs_link(user["id"], track["id"]) is None
        assert not store.get_os_track(user["id"], track["id"])["passport"].get("release_title")


def test_another_accounts_track_cannot_be_attached_to_and_deletion_cleans_up(monkeypatch):
    _adapter_obj, _fake = _connect(monkeypatch)
    app_obj = create_app()
    a, ua = _artist(app_obj)
    ta = _track(a, ua)
    a.post("/tracks/%s/discogs" % ta["id"], data={"action": "attach", "release_id": "249504"})
    assert store.get_discogs_link(ua["id"], ta["id"]) is not None

    b, _ub = _artist(app_obj)
    assert b.post("/tracks/%s/discogs" % ta["id"],
                  data={"action": "attach", "release_id": "249504"}).status_code == 404

    a.post("/tracks/%s/delete" % ta["id"])
    assert store.get_discogs_link(ua["id"], ta["id"]) is None
