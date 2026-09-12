"""A false alarm sent to a distributor costs more than the feature is worth.

Every string in this file is a real "Digital Service Provider" value from
a real Symphonic export - King 810, June 2026. That report carried 39 of
them covering 24 actual stores, and the gap logic treated each string as
its own store. On one track, Hungry Gods, that produced six flags for
stores it was already earning on: Amazon Music Unlimited and Amazon Ad
Supported while it earned on Amazon and Amazon Prime, Qobuz (JPY) while
it earned on Qobuz (USA), and three YouTube lines while it earned on
three other YouTube lines.

An artist writes to their distributor about that, the distributor
replies in one line, and the credibility needed for the gap that IS real
is gone.

The opposite error is worse and is tested too: merging two stores that
are genuinely different would HIDE a gap, so anything unrecognised keeps
its own name.
"""
import statements_engine as se
import store_identity as si


def test_the_tiers_of_one_store_are_one_store():
    for line in ("Amazon", "Amazon Prime", "Amazon Music Unlimited",
                 "Amazon Ad Supported"):
        assert si.store_of(line) == "Amazon", line
    for line in ("YouTube Streaming", "YouTube Shorts", "YouTube Content ID",
                 "YouTube Audio Tier", "YouTube Publishing: Content ID",
                 "YouTube Publishing: Shorts"):
        assert si.store_of(line) == "YouTube", line
    assert si.store_of("Qobuz (USA)") == si.store_of("Qobuz (JPY)")
    assert si.store_of("Pandora (Radio)") == si.store_of("Pandora (On Demand)")
    assert si.store_of("iTunes") == si.store_of("iTunes Match")


def test_genuinely_different_stores_stay_apart():
    """Over-merging hides a real gap, which is the more dangerous error."""
    distinct = {si.store_of(n) for n in
                ("Spotify", "Apple Music", "Deezer", "TIDAL", "Anghami",
                 "Audiomack", "NetEase", "JioSaavn", "LINE Music")}
    assert len(distinct) == 9


def test_an_unrecognised_name_keeps_its_own_identity():
    assert si.store_of("Some New DSP 2027") == "Some New DSP 2027"


def test_a_society_is_never_a_delivery_gap():
    """Nothing is delivered TO SoundExchange - it collects on broadcast.
    The same goes for content-ID licensing and B2B background music."""
    for name in ("SoundExchange: Sirius XM Radio, Inc",
                 "Audible Magic: Music Choice",
                 "Facebook / Instagram", "Twitch: DJ Program",
                 "SoundTrack Your Brand"):
        assert not si.is_deliverable(si.store_of(name)), name
    for name in ("Spotify", "Deezer", "Anghami", "TIDAL"):
        assert si.is_deliverable(si.store_of(name)), name


def test_a_track_is_not_flagged_for_a_store_it_already_earns_on():
    """The exact Hungry Gods shape, reduced to its bones."""
    rows = []

    def row(title, source, amount):
        rows.append({"title": title, "source": source, "amount": amount,
                     "period": "2026-06", "territory": "", "isrc": ""})

    # The track earns on two Amazon tiers and one YouTube line.
    row("Hungry Gods", "Amazon Prime", 40.0)
    row("Hungry Gods", "YouTube Streaming", 60.0)
    # The catalogue as a whole also earns on other Amazon and YouTube
    # lines, and on a store the track really is absent from.
    row("Other", "Amazon Music Unlimited", 20.0)
    row("Other", "YouTube Shorts", 10.0)
    row("Other", "Deezer", 30.0)
    row("Other", "SoundExchange: Sirius XM Radio, Inc", 5.0)

    gaps = se.analyze(rows)["coverage_gaps"]
    hungry = [g for g in gaps if g["title"] == "Hungry Gods"]
    assert hungry, "it IS missing from Deezer, so a gap should exist"
    missing = hungry[0]["missing_sources"]
    assert missing == ["Deezer"], (
        "only the store it is genuinely absent from: %r" % missing)
    assert "Amazon" not in missing and "YouTube" not in missing
    assert "SoundExchange" not in missing, "a society is not a delivery gap"
