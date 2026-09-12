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


def availability(isrc):
    """Which platforms carry this recording.

    Returns {"ok": bool, "links": {platform: url}, "why": str}. `ok` False
    means nothing was established - which is different from an empty
    `links`, and the caller must not flatten the two.
    """
    url, why = _spotify_url_for_isrc(isrc)
    if not url:
        return {"ok": False, "links": {}, "why": why}
    found = music_apis.odesli_lookup(url)
    if not found:
        # Spotify has it, so at minimum that is known.
        return {"ok": True, "links": {"spotify": url},
                "why": "only Spotify could be checked; the link service did not answer",
                "partial": True}
    return {"ok": True, "links": found.get("links") or {}, "why": "",
            "title": found.get("title") or "", "artist": found.get("artist") or "",
            "page": found.get("page") or ""}


def check_gap(isrc, missing_sources):
    """Sort a gap's missing stores into the two conversations, plus the
    ones nobody can answer.

    `carried` is the important list: the store has the recording and the
    statement shows nothing from it. `absent` is a delivery question.
    `unchecked` is neither, and stays visible so a letter cannot quietly
    imply it was checked.
    """
    result = availability(isrc)
    out = {"ok": result["ok"], "why": result.get("why") or "",
           "partial": bool(result.get("partial")),
           "carried": [], "absent": [], "unchecked": [],
           "title": result.get("title") or "", "page": result.get("page") or ""}
    if not result["ok"]:
        out["unchecked"] = sorted(missing_sources)
        return out

    links = result["links"]
    for source in sorted(missing_sources):
        platform = platform_for(source)
        if platform is None:
            out["unchecked"].append(source)
        elif platform in links:
            out["carried"].append({"source": source, "url": links[platform]})
        elif out["partial"]:
            # Only Spotify was established, so silence about the rest is
            # ignorance rather than absence.
            out["unchecked"].append(source)
        else:
            out["absent"].append(source)
    return out
