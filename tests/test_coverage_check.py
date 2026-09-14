"""A gap in a statement is not yet a claim about a store.

The coverage finding says a track earned on some stores and not others.
That supports two different letters, and sending the wrong one costs an
artist credibility they will need later:

  the store carries it and paid  -> ask the distributor to account for it
  you nothing
  the store does not carry it    -> ask them to deliver it

So the stores get asked. Only two can be: Deezer, free and exact by
ISRC, and Spotify, exact by ISRC with the app's own credentials. Odesli
would have answered for thirty platforms from one call - its public API
now returns 401 PUBLIC_API_ACCESS_DEPRECATED, permanently - so
everything else reports as unchecked.

The rule this file holds is that "could not check" never degrades into
"it is not there": not when the ISRC is missing, not when a store times
out, not when a store is not a catalogue at all, and not when it is a
catalogue nothing here can query.
"""
import pytest

import coverage_check as cc

ISRC = "GBWUL2686921"


@pytest.fixture
def stores(monkeypatch):
    """Stand in for both vendors, so the sorting logic is testable with no
    network and no credentials."""
    def _apply(deezer=(True, "https://www.deezer.com/track/1"),
               spotify=("https://open.spotify.com/track/1", None),
               apple=(None, "Apple did not answer (stubbed)")):
        monkeypatch.setattr(cc.music_apis, "deezer_has_isrc",
                            lambda isrc: deezer)
        monkeypatch.setattr(cc.music_apis, "apple_has_isrc",
                            lambda isrc: apple)
        monkeypatch.setattr(cc, "_spotify_url_for_isrc", lambda isrc: spotify)
    return _apply


def test_a_store_that_carries_it_is_the_finding_worth_a_letter(stores):
    stores()
    out = cc.check_gap(ISRC, ["Deezer", "Spotify"])
    assert out["ok"]
    assert {c["source"] for c in out["carried"]} == {"Deezer", "Spotify"}
    assert out["absent"] == [] and out["unchecked"] == []


def test_a_store_that_answers_no_is_a_delivery_question(stores):
    stores(deezer=(False, "not in Deezer's catalogue"),
           spotify=(None, "not in Spotify's catalogue under that ISRC"))
    out = cc.check_gap(ISRC, ["Deezer", "Spotify"])
    assert out["carried"] == []
    assert out["absent"] == ["Deezer", "Spotify"]


def test_a_store_that_could_not_be_reached_is_not_called_absent(stores):
    """A bad afternoon at Deezer must not produce a letter claiming the
    recording was never delivered."""
    stores(deezer=(None, "Deezer did not answer (timed out)"))
    out = cc.check_gap(ISRC, ["Deezer"])
    assert out["absent"] == []
    assert out["unchecked"] == ["Deezer"]
    assert "did not answer" in out["why"]


def test_a_store_nothing_here_can_query_reports_as_unchecked(stores):
    """Anghami, Audiomack, Pandora, TikTok and the rest are real stores
    with no route to ask them. That is unchecked, never absent."""
    stores()
    out = cc.check_gap(ISRC, ["Anghami", "Audiomack", "Pandora", "TikTok",
                              "iHeartRadio", "NetEase"])
    assert out["absent"] == []
    assert out["carried"] == []
    assert len(out["unchecked"]) == 6


def test_a_source_that_is_not_a_catalogue_is_never_called_absent(stores):
    """SoundExchange is a society, Audible Magic licenses background
    music, Facebook is a licensing deal. None is a shop with a search box."""
    stores()
    out = cc.check_gap(ISRC, ["SoundExchange: Sirius XM Radio, Inc",
                              "Audible Magic: Music Choice",
                              "Facebook / Instagram", "Twitch: DJ Program"])
    assert out["absent"] == []
    assert len(out["unchecked"]) == 4


def test_no_isrc_means_unchecked_not_absent(monkeypatch):
    monkeypatch.setattr(cc.spotify_provider, "pulse_configured", lambda: True)
    out = cc.check_gap("", ["Deezer", "Spotify"])
    assert out["ok"] is False
    assert out["absent"] == [] and out["carried"] == []
    assert out["unchecked"] == ["Deezer", "Spotify"]
    assert "no ISRC" in out["why"]


def test_neither_store_answering_establishes_nothing(stores):
    stores(deezer=(None, "Deezer did not answer"),
           spotify=(None, "Spotify is not connected on this deployment"))
    out = cc.check_gap(ISRC, ["Deezer", "Spotify", "Anghami"])
    assert out["ok"] is False
    assert out["absent"] == [] and out["carried"] == []
    assert sorted(out["unchecked"]) == ["Anghami", "Deezer", "Spotify"]


def test_one_store_answering_is_enough_to_report_that_one(stores):
    """Deezer needs no key, so it answers on a deployment with no Spotify
    credentials - and that is where the first real finding on this
    catalogue came from."""
    stores(spotify=(None, "Spotify is not connected on this deployment"))
    out = cc.check_gap(ISRC, ["Deezer", "Spotify"])
    assert out["ok"] is True
    assert [c["source"] for c in out["carried"]] == ["Deezer"]
    assert out["unchecked"] == ["Spotify"]
    assert "not connected" in out["why"]


def test_the_same_store_under_four_names_asks_one_question():
    for name in ("YouTube Streaming", "YouTube Shorts", "YouTube Content ID",
                 "YouTube Audio Tier", "YouTube Publishing: Shorts"):
        assert cc.platform_for(name) == "youtube", name


def test_sources_that_cannot_be_checked_are_reported_as_such():
    for name in ("SoundExchange: Sirius XM Radio, Inc",
                 "Audible Magic: Medianet - Securus", "Facebook / Instagram",
                 "Twitch: DJ Program", "SoundTrack Your Brand"):
        assert cc.platform_for(name) is None, name


def test_songstats_widens_what_can_be_asked(monkeypatch):
    """It answers for stores nothing else here can reach, so those stop
    reading as unchecked."""
    monkeypatch.setattr(cc, "_songstats_links",
                        lambda isrc, **kw: ({"anghami": "https://anghami/x",
                                       "pandora": "https://pandora/x"}, ""))
    monkeypatch.setattr(cc.music_apis, "deezer_has_isrc",
                        lambda isrc: (True, "https://deezer/x"))
    monkeypatch.setattr(cc.music_apis, "apple_has_isrc",
                        lambda isrc: (None, "stubbed"))
    monkeypatch.setattr(cc, "_spotify_url_for_isrc",
                        lambda isrc: (None, "Spotify is not connected"))
    out = cc.check_gap(ISRC, ["Anghami", "Pandora", "Deezer", "NetEase"])
    carried = {c["source"] for c in out["carried"]}
    assert carried == {"Anghami", "Pandora", "Deezer"}
    assert out["unchecked"] == ["NetEase"], "still unreachable, still honest"


def test_an_unreadable_songstats_reply_costs_coverage_not_correctness(monkeypatch):
    """Its response shape could not be confirmed before the lookup was
    written. A shape the parser cannot read must yield NO platforms - which
    sorts as unchecked - rather than an absence nobody established."""
    monkeypatch.setattr(cc, "_songstats_links",
                        lambda isrc, **kw: ({}, "unrecognised shape; top-level keys: a, b"))
    monkeypatch.setattr(cc.music_apis, "deezer_has_isrc",
                        lambda isrc: (True, "https://deezer/x"))
    monkeypatch.setattr(cc.music_apis, "apple_has_isrc",
                        lambda isrc: (None, "stubbed"))
    monkeypatch.setattr(cc, "_spotify_url_for_isrc",
                        lambda isrc: (None, "Spotify is not connected"))
    out = cc.check_gap(ISRC, ["Anghami", "Deezer"])
    assert [c["source"] for c in out["carried"]] == ["Deezer"]
    assert out["absent"] == [], "an unreadable reply is not an absence"
    assert out["unchecked"] == ["Anghami"]
    assert "unrecognised shape" in out["why"], "and it says what it saw"


def test_songstats_naming_a_store_we_do_not_map_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(cc, "_songstats_links", cc._songstats_links)
    import signal_providers as sp
    monkeypatch.setattr(sp.SongstatsAdapter, "track_platforms",
                        lambda self, isrc, **kw: ({"some_new_dsp": "https://x"}, ""))
    links, note = cc._songstats_links(ISRC)
    assert links == {}
    assert "does not map" in note and "some_new_dsp" in note



def test_spotify_resolves_the_isrc_to_the_id_songstats_is_asked_with(monkeypatch):
    """The exact chain: the code names the track, Spotify names the id,
    Songstats is asked by that id - no search by code involved."""
    asked = {}
    monkeypatch.setattr(cc, "_spotify_url_for_isrc",
                        lambda isrc: ("https://open.spotify.com/track/5153euQCxTD7EzkAoXhfb7?si=abc", None))
    monkeypatch.setattr(cc.music_apis, "deezer_has_isrc", lambda isrc: (None, "skipped"))

    def fake(isrc, spotify_track_id=""):
        asked["id"] = spotify_track_id
        return {"anghami": "https://anghami/x"}, ""
    monkeypatch.setattr(cc, "_songstats_links", fake)
    out = cc.availability(ISRC)
    assert asked["id"] == "5153euQCxTD7EzkAoXhfb7"
    assert out["links"]["anghami"] == "https://anghami/x" and out["links"]["spotify"]
    assert cc.spotify_track_id_for(ISRC) == "5153euQCxTD7EzkAoXhfb7"
