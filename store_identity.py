"""Which STORE a statement line refers to.

A distributor report names revenue lines, not stores. One real Symphonic
export carried 39 distinct "Digital Service Provider" strings covering
roughly 25 actual places a recording can be delivered:

    Amazon, Amazon Prime, Amazon Music Unlimited, Amazon Ad Supported
    YouTube Streaming, YouTube Shorts, YouTube Content ID,
        YouTube Audio Tier, YouTube Publishing: Content ID,
        YouTube Publishing: Shorts
    iTunes, iTunes Match
    Qobuz (USA), Qobuz (JPY)
    Pandora (Radio), Pandora (On Demand)

Treating each string as its own store is how a coverage gap fires on a
track that IS delivered. Hungry Gods earns on Amazon, Amazon Prime,
Qobuz (USA), YouTube Streaming, YouTube Content ID and YouTube Audio
Tier - and was flagged as missing from Amazon Music Unlimited, Amazon Ad
Supported, Qobuz (JPY), YouTube Shorts and both YouTube Publishing
lines. Six false alarms out of twenty-seven, on one track.

Those are tiers and revenue types of a store the recording is already
on. A distributor answering that letter says so in one line, and the
artist has spent credibility they will need for the gap that is real.

So the delivery question is asked per STORE. The underlying report lines
are kept for display, because an artist reading a finding should still
see the words their own statement used.

The rule is deliberately conservative: anything not recognised keeps its
own full name and is treated as its own store. Over-merging invents a
delivery that never happened, which is the more dangerous error - it
HIDES a real gap.
"""

import re

# Prefix -> store. Order matters only in that the longest sensible prefix
# should be listed; matching takes the first hit.
_PREFIXES = (
    ("amazon", "Amazon"),
    ("apple music", "Apple Music"),
    ("itunes", "iTunes"),
    ("youtube", "YouTube"),
    ("spotify", "Spotify"),
    ("deezer", "Deezer"),
    ("tidal", "TIDAL"),
    ("pandora", "Pandora"),
    ("qobuz", "Qobuz"),
    ("anghami", "Anghami"),
    ("audiomack", "Audiomack"),
    ("jiosaavn", "JioSaavn"),
    ("netease", "NetEase"),
    ("line music", "LINE Music"),
    ("trebel", "Trebel Music"),
    ("iheart", "iHeartRadio"),
    ("tiktok", "TikTok"),
    ("snap", "Snap"),
    ("soundcloud", "SoundCloud"),
    ("napster", "Napster"),
    ("facebook", "Facebook / Instagram"),
    ("instagram", "Facebook / Instagram"),
    ("audible magic", "Audible Magic"),
    ("soundexchange", "SoundExchange"),
    ("soundtrack your brand", "SoundTrack Your Brand"),
    ("twitch", "Twitch"),
    ("fluxus", "Yandex Music"),
    ("yandex", "Yandex Music"),
)

# Stores a recording is DELIVERED to, versus arrangements that pay on
# use. Nobody delivers a track "to SoundExchange" - it is a society that
# collects on broadcast - so its absence from a statement is never a
# delivery gap and must never be reported as one.
_NOT_A_STORE = {
    "SoundExchange",      # a collection society
    "Audible Magic",      # content identification licensing
    "Facebook / Instagram",  # a licensing deal, not a catalogue
    "Twitch",             # likewise
    "SoundTrack Your Brand",  # B2B background music licensing
}


def store_of(source):
    """The store a report line belongs to. Unrecognised names keep their
    own, because merging two real stores would hide a genuine gap."""
    name = (source or "").strip()
    if not name:
        return "Unknown source"
    flat = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    flat = re.sub(r"\s+", " ", flat).strip()
    for prefix, store in _PREFIXES:
        if flat.startswith(prefix):
            return store
    return name


def is_deliverable(store):
    """True when "is the recording on it?" is a question with an answer.

    A society or a licensing arrangement is not a shop a distributor
    delivers to, so its absence is not evidence of anything.
    """
    return store not in _NOT_A_STORE


def group(sources):
    """{store: [the report lines that belong to it]}."""
    out = {}
    for source in sources:
        out.setdefault(store_of(source), []).append(source)
    for lines in out.values():
        lines.sort()
    return out
