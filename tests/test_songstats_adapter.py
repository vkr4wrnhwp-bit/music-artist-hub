"""Songstats, written against their published OpenAPI 3.1 specification.

Read from developers.stats.company rather than recalled: base URL
https://api.songstats.com/enterprise/v1, an `apikey` request header, and
/artists/historic_stats returning per-source daily history — exactly the
dated series this registry's CAP_METRICS contract asks for.

The fixtures below are their own documented example response, so these
tests fail if the mapping drifts from the shape they publish.
"""
import datetime
import os

import pytest

import signal_providers as sp

# Their documented example, trimmed to two days.
HISTORIC = {
    "result": "success", "message": "Data Retrieved.",
    "stats": [
        {"source": "spotify", "data": {"history": [
            {"date": "2021-06-23", "popularity_current": 75,
             "followers_total": 1737771, "monthly_listeners_current": 9284594,
             "streams_total": 1058987},
            {"date": "2021-06-24", "popularity_current": 75,
             "followers_total": 1737887, "monthly_listeners_current": 9284594},
        ]}},
        {"source": "apple_music", "data": {"history": [
            {"date": "2021-06-23", "playlists_current": 12},
        ]}},
    ],
}


def _adapter(payload):
    return sp.SongstatsAdapter(fetch=lambda url: payload)


def test_the_history_becomes_the_rows_this_registry_expects():
    rows = _adapter(HISTORIC).get_artist_metrics(
        "abc", datetime.date(2021, 6, 23), datetime.date(2021, 6, 24))
    got = {(r["metric"], r["date"]): r["value"] for r in rows}
    assert got[("spotify_monthly_listeners", "2021-06-23")] == 9284594
    assert got[("spotify_followers", "2021-06-24")] == 1737887
    assert got[("spotify_popularity", "2021-06-23")] == 75


def test_only_the_spotify_block_is_read():
    """Other sources carry different keys; guessing at them would invent
    numbers rather than report them."""
    rows = _adapter(HISTORIC).get_artist_metrics(
        "abc", datetime.date(2021, 6, 23), datetime.date(2021, 6, 24))
    assert all(r["metric"].startswith("spotify_") for r in rows)


def test_a_missing_figure_is_dropped_rather_than_stored_as_zero():
    """The second day has no monthly_listeners_current. A nought there
    would read as an audience of nobody."""
    payload = {"stats": [{"source": "spotify", "data": {"history": [
        {"date": "2021-06-23", "followers_total": 10},
        {"date": "2021-06-24", "followers_total": 11,
         "monthly_listeners_current": None},
    ]}}]}
    rows = _adapter(payload).get_artist_metrics(
        "abc", datetime.date(2021, 6, 23), datetime.date(2021, 6, 24))
    assert not [r for r in rows if r["metric"] == "spotify_monthly_listeners"]
    assert len([r for r in rows if r["metric"] == "spotify_followers"]) == 2


def test_an_empty_or_malformed_answer_is_not_a_crash():
    for payload in ({}, {"stats": []}, {"stats": [{"source": "spotify"}]},
                    {"stats": [{"source": "spotify",
                                "data": {"history": [{"date": "", "followers_total": 5}]}}]}):
        assert _adapter(payload).get_artist_metrics(
            "abc", datetime.date(2021, 6, 23), datetime.date(2021, 6, 24)) == []


def test_search_maps_to_provider_artist_ids():
    payload = {"artists": [
        {"songstats_artist_id": "sa-1", "name": "KING 810", "avatar": "x.jpg"},
        {"name": "No id here"},
    ]}
    found = _adapter(payload).search_artists("king 810")
    assert [a["provider_artist_id"] for a in found] == ["sa-1"], (
        "a result with no id is not an artist we can ask about again")
    assert found[0]["name"] == "KING 810"


def test_an_empty_query_never_reaches_them():
    """Their universe is large and every request counts against a
    per-resource monthly ceiling."""
    def explode(url):
        raise AssertionError("an empty query must not be sent")
    assert sp.SongstatsAdapter(fetch=explode).search_artists("  ") == []


# --- how it reports itself ---------------------------------------------------

def test_it_stays_inert_until_its_key_exists(monkeypatch):
    monkeypatch.delenv("SONGSTATS_ENABLED", raising=False)
    adapter = sp.SongstatsAdapter()
    assert not adapter.configured()
    assert "SONGSTATS_ENABLED" in adapter.health_check()["detail"]


def test_the_flag_alone_is_not_enough(monkeypatch):
    monkeypatch.setenv("SONGSTATS_ENABLED", "1")
    monkeypatch.delenv("SONGSTATS_API_KEY", raising=False)
    adapter = sp.SongstatsAdapter()
    assert not adapter.configured()
    assert "SONGSTATS_API_KEY" in adapter.health_check()["detail"]


def test_it_declares_only_what_it_can_answer():
    adapter = sp.SongstatsAdapter()
    assert adapter.supports(sp.CAP_METRICS) and adapter.supports(sp.CAP_ARTIST)
    for cap in (sp.CAP_CITIES, sp.CAP_PLAYLISTS, sp.CAP_RIGHTS, sp.CAP_EVENTS):
        assert not adapter.supports(cap), (
            "declaring a capability it cannot serve would take it from a "
            "provider that can")


def test_soundcharts_still_wins_the_capabilities_they_share():
    """Preference order decides. Soundcharts covers nine capabilities to
    Songstats' two, so a silent swap on CAP_METRICS would strand cities
    and playlists with nothing announcing it."""
    keys = [a.key for a in sp.ProviderRegistry().adapters]
    assert keys.index("soundcharts") < keys.index("songstats")
