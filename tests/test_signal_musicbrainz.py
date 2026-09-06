"""Signal's MusicBrainz adapter, against canned MusicBrainz answers.

Two things matter. The adapter returns the same shapes the mock does, so
the rest of Signal cannot tell which answered; and it never invents what
MusicBrainz does not know - listeners, cities, a distributor - so when it
is the only real provider, those read as not measured rather than as the
demo's numbers (the registry rule tested at the end).
"""
import json
import uuid
from urllib.parse import parse_qs, urlparse

import pytest

import signal_providers as providers

MBID = "5b11f4ce-a62d-471e-81fc-a69a8278c7da"


def _fake_fetch(calls):
    """Answers like the MusicBrainz web service, and records what was asked."""
    def fetch(url):
        calls.append(url)
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.endswith("/artist/") and q.get("query"):
            return {"artists": [{"id": MBID, "name": "Nirvana", "country": "US",
                                 "area": {"name": "United States"},
                                 "begin-area": {"name": "Aberdeen"},
                                 "tags": [{"count": 2, "name": "rock"}, {"count": 9, "name": "grunge"}]}]}
        if u.path.endswith("/artist/" + MBID):
            return {"id": MBID, "name": "Nirvana", "country": "US", "disambiguation": "90s US grunge band",
                    "area": {"name": "United States"}, "begin-area": {"name": "Aberdeen"},
                    "tags": [{"count": 9, "name": "grunge"}],
                    "relations": [{"type": "official homepage", "url": {"resource": "https://www.nirvana.com/"}},
                                  {"type": "youtube", "url": {"resource": "https://www.youtube.com/nirvana"}}]}
        if u.path.endswith("/release-group/"):
            return {"release-groups": [
                {"id": "rg-1", "title": "Nevermind", "primary-type": "Album", "first-release-date": "1991-09-24"},
                {"id": "rg-2", "title": "In Utero", "primary-type": "Album", "first-release-date": "1993-09-21"}]}
        if u.path.endswith("/release/"):
            rg = q.get("release-group")
            return {"releases": [{"id": "rel-" + rg, "barcode": "720642442524" if rg == "rg-1" else "",
                                  "label-info": [{"label": {"name": "DGC"}, "catalog-number": "DGCD-24425"}],
                                  "media": [{"track-count": 12}]}]}
        raise AssertionError("unexpected request: " + url)
    return fetch


def _adapter(calls):
    return providers.MusicBrainzAdapter(fetch=_fake_fetch(calls), sleep=lambda s: None)


def test_it_is_inert_until_the_contact_is_set(monkeypatch):
    monkeypatch.delenv("MUSICBRAINZ_ENABLED", raising=False)
    monkeypatch.delenv("MUSICBRAINZ_CONTACT", raising=False)
    a = providers.MusicBrainzAdapter()
    assert a.configured() is False
    monkeypatch.setenv("MUSICBRAINZ_ENABLED", "1")
    assert a.configured() is False, "the flag alone is not enough; their policy wants a contact"
    monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
    assert a.configured() is True
    assert a.health_check()["ok"] is True


def test_search_returns_the_mocks_shape_with_real_fields():
    calls = []
    hits = _adapter(calls).search_artists("nirvana", limit=5)
    assert len(hits) == 1
    a = hits[0]
    assert a["provider_artist_id"] == MBID and a["name"] == "Nirvana"
    assert a["genre"] == "Grunge", "the most-voted tag, not the first"
    assert a["country"] == "US" and a["city"] == "Aberdeen"
    assert "query=nirvana" in calls[0] and "limit=5" in calls[0]
    for key in ("career_stage", "monthly_listeners", "image_url", "website", "socials", "state"):
        assert key in a, key


def test_a_blank_search_is_empty_not_a_random_sample():
    calls = []
    assert _adapter(calls).search_artists("", limit=25) == []
    assert calls == [], "nothing was asked - there is no honest 'some artists'"


def test_the_artist_carries_no_invented_numbers():
    a = _adapter([]).get_artist(MBID)
    assert a["monthly_listeners"] is None and a["career_stage"] == ""
    assert a["website"] == "https://www.nirvana.com/"
    assert a["socials"]["youtube"] == "https://www.youtube.com/nirvana"
    assert a["socials"]["instagram"] == ""


def test_releases_carry_label_and_barcode_and_no_distributor():
    calls = []
    rels = _adapter(calls).get_artist_releases(MBID)
    assert [r["title"] for r in rels] == ["In Utero", "Nevermind"], "newest first"
    nevermind = rels[1]
    assert nevermind["label_text"] == "DGC" and nevermind["upc"] == "720642442524"
    assert nevermind["track_count"] == 12 and nevermind["release_type"] == "Album"
    assert nevermind["distributor_name"] == "" and nevermind["distributor_class"] == "Unknown"
    assert rels[0]["upc"] == ""
    # One group listing plus one release per group, and no more.
    assert len(calls) == 3


def test_label_evidence_names_its_source():
    ev = _adapter([]).get_label_evidence("rg-1")
    assert ev == [{"label_name": "DGC", "catalog_number": "DGCD-24425",
                   "source_type": "release_metadata", "source_label": "MusicBrainz release",
                   "source_url": "https://musicbrainz.org/release/rel-rg-1", "confidence": 0.8}]


def test_requests_are_spaced_to_their_limit():
    waits = []
    a = providers.MusicBrainzAdapter(fetch=_fake_fetch([]), sleep=waits.append)
    a.get_artist_releases(MBID)
    assert len(waits) >= 2 and all(0 < w <= a.min_interval for w in waits)


def test_a_network_failure_is_a_provider_error_not_a_crash(monkeypatch):
    monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
    a = providers.MusicBrainzAdapter(sleep=lambda s: None)
    a.base_url = "http://127.0.0.1:9/ws/2"
    with pytest.raises(providers.ProviderError):
        a.get_artist(MBID)


# --- the registry rule -------------------------------------------------------

def test_a_real_identity_never_gets_the_mocks_numbers(monkeypatch):
    monkeypatch.setenv("MUSICBRAINZ_ENABLED", "1")
    monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
    reg = providers.ProviderRegistry(adapters=[providers.MusicBrainzAdapter(fetch=_fake_fetch([]), sleep=lambda s: None)])
    assert reg.is_demo() is False
    assert reg.for_capability(providers.CAP_ARTIST).key == "musicbrainz"
    assert reg.for_capability(providers.CAP_RELEASES).key == "musicbrainz"
    for cap in (providers.CAP_METRICS, providers.CAP_CITIES, providers.CAP_PLAYLISTS,
                providers.CAP_SOCIAL, providers.CAP_RIGHTS):
        assert reg.for_capability(cap) is None, cap


def test_ingest_writes_identity_and_releases_and_no_metrics(monkeypatch):
    import db as store
    import signal_ingest as ingest
    import signal_store as sstore
    store.init_db()
    sstore.init_signal()
    monkeypatch.setenv("MUSICBRAINZ_ENABLED", "1")
    monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
    reg = providers.ProviderRegistry(adapters=[providers.MusicBrainzAdapter(fetch=_fake_fetch([]), sleep=lambda s: None)])
    artist_id = ingest.ingest_artist(MBID, reg=reg, force=True)
    assert artist_id
    art = sstore.get_artist(artist_id)
    assert art["canonical_name"] == "Nirvana"
    assert sstore.metric_series(artist_id, "spotify_monthly_listeners") == []
    titles = {r["title"] for r in sstore.list_releases(artist_id)}
    assert {"Nevermind", "In Utero"} <= titles
