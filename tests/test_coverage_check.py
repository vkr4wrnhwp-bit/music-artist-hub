"""A gap in a statement is not yet a claim about a store.

The coverage finding says a track earned on some stores and not others.
That supports two different letters, and sending the wrong one costs an
artist credibility they will need later:

  the store does not carry it  -> ask the distributor to deliver it
  the store carries it and you -> ask the distributor to account for it
  were paid nothing

So the stores get asked. The rule this file holds is that "we could not
check" never degrades into "it is not there" - not when the ISRC is
missing, not when Spotify is unconfigured, not when the link service
times out, and not for a source that is not a catalogue at all.
"""
import pytest

import coverage_check as cc


class _Stub:
    """Stands in for the two vendors, so the logic is testable without a
    network and without credentials."""

    def __init__(self, url="https://open.spotify.com/track/abc", links=None,
                 odesli=True):
        self.url, self.links, self.odesli = url, links or {}, odesli

    def spotify(self, isrc):
        return (self.url, None) if self.url else (None, "not in Spotify's catalogue")

    def lookup(self, url):
        if not self.odesli:
            return None
        return {"title": "Hungry Gods", "artist": "King 810",
                "page": "https://song.link/x", "links": self.links}


@pytest.fixture
def stubbed(monkeypatch):
    def _apply(stub):
        monkeypatch.setattr(cc, "_spotify_url_for_isrc", stub.spotify)
        monkeypatch.setattr(cc.music_apis, "odesli_lookup", stub.lookup)
        return stub
    return _apply


def test_a_store_that_carries_it_is_the_finding_worth_a_letter(stubbed):
    """Present on the store, absent from the money."""
    stubbed(_Stub(links={"spotify": "https://open.spotify.com/track/abc",
                         "appleMusic": "https://music.apple.com/x",
                         "deezer": "https://deezer.com/x"}))
    out = cc.check_gap("GBRKQ2454700", ["Apple Music", "Deezer"])
    assert out["ok"]
    carried = {c["source"] for c in out["carried"]}
    assert carried == {"Apple Music", "Deezer"}
    assert out["absent"] == [] and out["unchecked"] == []


def test_a_store_that_does_not_carry_it_is_a_delivery_question(stubbed):
    stubbed(_Stub(links={"spotify": "https://open.spotify.com/track/abc"}))
    out = cc.check_gap("GBRKQ2454700", ["Apple Music", "Deezer"])
    assert out["carried"] == []
    assert out["absent"] == ["Apple Music", "Deezer"]


def test_a_source_that_is_not_a_catalogue_is_never_called_absent(stubbed):
    """SoundExchange is a society, Audible Magic licenses background
    music, Qobuz (JPY) is a currency split of a store nobody can query.
    Saying "not on the store" about any of them would be an invention."""
    stubbed(_Stub(links={"spotify": "https://open.spotify.com/track/abc"}))
    out = cc.check_gap("GBRKQ2454700", [
        "SoundExchange: Sirius XM Radio, Inc", "Audible Magic: Music Choice",
        "Facebook / Instagram", "Qobuz (JPY)"])
    assert out["absent"] == []
    assert len(out["unchecked"]) == 4


def test_no_isrc_means_unchecked_not_absent(monkeypatch):
    monkeypatch.setattr(cc.spotify_provider, "pulse_configured", lambda: True)
    out = cc.check_gap("", ["Apple Music", "Deezer"])
    assert out["ok"] is False
    assert out["absent"] == [] and out["carried"] == []
    assert out["unchecked"] == ["Apple Music", "Deezer"]
    assert "no ISRC" in out["why"]


def test_spotify_unconfigured_means_unchecked_not_absent(monkeypatch):
    monkeypatch.setattr(cc.spotify_provider, "pulse_configured", lambda: False)
    out = cc.check_gap("GBRKQ2454700", ["Apple Music"])
    assert out["ok"] is False
    assert out["absent"] == []
    assert "not connected" in out["why"]


def test_the_link_service_failing_does_not_empty_the_catalogue(stubbed):
    """Odesli down means we know about Spotify and nothing else. Every
    other store has to read unchecked, or an outage would generate a
    letter claiming a track is on no platform at all."""
    stubbed(_Stub(odesli=False))
    out = cc.check_gap("GBRKQ2454700", ["Apple Music", "Deezer", "TIDAL"])
    assert out["ok"] is True and out["partial"] is True
    assert out["absent"] == []
    assert out["unchecked"] == ["Apple Music", "Deezer", "TIDAL"]


def test_the_same_store_under_four_names_asks_one_question():
    """A single report carries YouTube Streaming, YouTube Content ID,
    YouTube Shorts and YouTube Audio Tier. All four are the same
    catalogue question."""
    for name in ("YouTube Streaming", "YouTube Content ID", "YouTube Shorts",
                 "YouTube Audio Tier", "YouTube Publishing: Shorts"):
        assert cc.platform_for(name) == "youtube", name


def test_sources_that_cannot_be_checked_are_reported_as_such():
    for name in ("SoundExchange: Sirius XM Radio, Inc",
                 "Audible Magic: Medianet - Securus", "Qobuz (USA)",
                 "Facebook / Instagram", "Twitch: DJ Program"):
        assert cc.platform_for(name) is None, name
