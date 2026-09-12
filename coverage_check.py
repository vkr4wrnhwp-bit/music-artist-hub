"""Is the recording actually on the store, or only missing from the money?

A coverage gap says a track earned on some stores and not others. That is
a fact about a STATEMENT, and on its own it supports two completely
different conversations:

  the store does not carry it   -> a delivery problem. Ask the distributor
                                   to deliver it. Nobody owes anything.
  the store carries it and paid  -> a reporting or accounting problem. The
  you nothing                      money exists somewhere. This is the one
                                   worth a letter.

Guessing between them is how an artist sends a distributor a demand for
money over a track that was never delivered, which costs them credibility
they will need later. So this module asks the stores.

The route is ISRC -> Spotify -> Odesli. Spotify's catalogue search takes
an ISRC exactly, which is the only safe way to identify a recording: a
title match breaks on remixes, live versions, features and anything with
a comma in it, and a wrong match here becomes a wrong claim in a letter.
Odesli then answers which platforms carry that same recording.

What it will not do is pretend to an answer. A source with no platform
mapping, a track with no ISRC, or a vendor that refuses returns
"unchecked" with the reason, never "absent".
"""

import re

import music_apis
import spotify_provider
import store_identity

# Statement source names as distributors write them, mapped to the
# platform keys Odesli answers with. Matching is done on a normalised
# prefix because the same store arrives as "YouTube Streaming",
# "YouTube Content ID", "YouTube Shorts" and "YouTube Audio Tier" in one
# report, and all four are the same catalogue question.
_PLATFORM_BY_PREFIX = (
    ("spotify", "spotify"),
    ("apple", "appleMusic"),
    ("itunes", "itunes"),
    ("youtube", "youtube"),
    ("deezer", "deezer"),
    ("amazon", "amazonMusic"),
    ("tidal", "tidal"),
    ("pandora", "pandora"),
    ("soundcloud", "soundcloud"),
    ("napster", "napster"),
    ("yandex", "yandex"),
    ("audiomack", "audiomack"),
    ("anghami", "anghami"),
    ("audius", "audius"),
    ("tiktok", "tiktok"),
)


def platform_for(source):
    """The Odesli platform a statement source refers to, or None.

    None is a real answer and is reported as such: SoundExchange, a
    society, an Audible Magic licensee and a hotel background-music
    service are not catalogues anybody can search, and saying "not on
    the store" about one of those would be an invention.
    """
    # Normalise through store_identity first, so this module and the gap
    # logic cannot disagree about which store a report line names. A
    # second prefix list is a second opinion waiting to drift.
    if not store_identity.is_deliverable(store_identity.store_of(source)):
        return None
    name = re.sub(r"[^a-z0-9 ]", " ", (source or "").lower()).strip()
    for prefix, platform in _PLATFORM_BY_PREFIX:
        if name.startswith(prefix):
            return platform
    return None


def _spotify_url_for_isrc(isrc):
    """Find the recording by its own identifier. (url, None) or (None, why)."""
    isrc = (isrc or "").strip().upper().replace("-", "")
    if not isrc:
        return None, "no ISRC on the statement row"
    if not spotify_provider.pulse_configured():
        return None, "Spotify is not connected on this deployment"
    try:
        token = spotify_provider.app_token()
        if not token:
            return None, "Spotify did not issue a token"
        import urllib.parse
        data = spotify_provider._api(
            "/search?" + urllib.parse.urlencode(
                {"q": "isrc:" + isrc, "type": "track", "limit": 1}), token)
    except Exception as exc:                                   # noqa: BLE001
        return None, "Spotify did not answer (%s)" % (str(exc)[:80] or "no detail")
    items = ((data or {}).get("tracks") or {}).get("items") or []
    if not items:
        # Not an error: Spotify genuinely does not have this recording.
        return None, "not in Spotify's catalogue under that ISRC"
    url = ((items[0].get("external_urls") or {}).get("spotify") or "").strip()
    return (url or None), (None if url else "Spotify returned no link")


# The stores this can ask, and nothing else. Odesli would have answered
# for thirty platforms from one call; its public API now returns
# 401 PUBLIC_API_ACCESS_DEPRECATED, permanently. So each store is asked
# directly, and only these two can be:
#
#   Deezer   free, exact by ISRC, verified against a real recording
#   Spotify  exact by ISRC, needs the app's own credentials
#
# Everything else reports as unchecked. That is a thin answer and an
# honest one - and Deezer happens to be where the first real finding on
# this catalogue was, so it is not a token.
CHECKABLE = ("deezer", "spotify")

# Songstats answers for far more stores than the two above, so when it is
# configured it widens what can be asked. Its response shape is not yet
# confirmed (see SongstatsAdapter.track_platforms), and an unreadable
# answer yields no platforms - which the sorting below treats as
# unchecked, never as absent. So a wrong guess costs coverage and cannot
# produce a false claim.
SONGSTATS_ALIASES = {
    "spotify": "spotify", "apple_music": "appleMusic", "apple": "appleMusic",
    "itunes": "itunes", "deezer": "deezer", "tidal": "tidal",
    "amazon": "amazonMusic", "amazon_music": "amazonMusic",
    "youtube": "youtube", "youtube_music": "youtube", "pandora": "pandora",
    "soundcloud": "soundcloud", "audiomack": "audiomack",
    "anghami": "anghami", "napster": "napster", "tiktok": "tiktok",
    "boomplay": "boomplay", "jiosaavn": "jiosaavn", "netease": "netease",
    "yandex": "yandex", "line_music": "lineMusic", "qobuz": "qobuz",
}


def _songstats_links(isrc):
    """({platform: url}, note) from Songstats, or empty when it cannot say."""
    try:
        import signal_providers as sp
        found, note = sp.SongstatsAdapter().track_platforms(isrc)
    except Exception as exc:                                   # noqa: BLE001
        return {}, "Songstats: %s" % (str(exc)[:80] or "no detail")
    out = {}
    for name, url in (found or {}).items():
        platform = SONGSTATS_ALIASES.get(name)
        if platform:
            out[platform] = url
    if found and not out:
        return {}, "Songstats named only stores this does not map: %s" % (
            ", ".join(sorted(found)[:8]))
    return out, note


def availability(isrc):
    """Which stores carry this recording, asked one at a time.

    {"ok": bool, "links": {platform: url}, "absent": [platform],
     "why": str}. `ok` False means nothing at all was established, which
    is different from an empty `links`, and the caller must not flatten
    the two: a store that answered "no" and a store that could not be
    reached lead to different letters.
    """
    isrc = (isrc or "").strip().upper().replace("-", "")
    if not isrc:
        return {"ok": False, "links": {}, "absent": [],
                "why": "no ISRC on the statement row"}

    links, absent, unknown = {}, [], []

    # Songstats first when available: one call, many stores.
    songstats, note = _songstats_links(isrc)
    links.update(songstats)
    if note:
        unknown.append(note)

    present, detail = music_apis.deezer_has_isrc(isrc)
    if present is True:
        links["deezer"] = detail
    elif present is False:
        absent.append("deezer")
    else:
        unknown.append("Deezer (%s)" % detail)

    url, why = _spotify_url_for_isrc(isrc)
    if url:
        links["spotify"] = url
    elif "not in Spotify's catalogue" in (why or ""):
        absent.append("spotify")
    else:
        unknown.append("Spotify (%s)" % why)

    if not links and not absent:
        return {"ok": False, "links": {}, "absent": [],
                "why": "; ".join(unknown) or "no store could be asked"}
    return {"ok": True, "links": links, "absent": absent,
            "why": "; ".join(unknown)}


def check_gap(isrc, missing_sources):
    """Sort a gap's silent stores into the three answers.

    `carried` is the one worth a letter: the store lists the recording and
    the statement shows nothing from it. `absent` is a delivery question
    and mentions no money. `unchecked` is neither, and stays visible so a
    letter cannot imply a check that never ran - which covers most stores,
    because only Deezer and Spotify can be asked at all.
    """
    result = availability(isrc)
    out = {"ok": result["ok"], "why": result.get("why") or "",
           "carried": [], "absent": [], "unchecked": [],
           "title": "", "page": ""}
    if not result["ok"]:
        out["unchecked"] = sorted(missing_sources)
        return out

    links = result["links"]
    answered_no = set(result.get("absent") or ())
    # A store Songstats reported on is answerable for this recording even
    # though it is not directly queryable.
    checkable = set(CHECKABLE) | set(links)
    for source in sorted(missing_sources):
        platform = platform_for(source)
        if platform is None or platform not in checkable:
            # Not a catalogue, or a catalogue nothing here can query.
            out["unchecked"].append(source)
        elif platform in links:
            out["carried"].append({"source": source, "url": links[platform]})
        elif platform in answered_no:
            out["absent"].append(source)
        else:
            out["unchecked"].append(source)
    return out
