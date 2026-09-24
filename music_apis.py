"""Free public music APIs: iTunes Search (real tracks, artwork, 30-second
previews — no key) and Odesli/Songlink (universal all-platform links —
no key, 10 req/min). Responses are cached in SQLite to respect rate
limits and keep pages fast. `_fetch_json` is the seam tests monkeypatch
so no test ever touches the network.
"""

import json
import time
import urllib.parse
import urllib.request

import db as store

_TIMEOUT = 12
_UA = "StreetBanker/1.0 (team.summitarts@gmail.com)"

ITUNES_TTL = 24 * 3600        # searches refresh daily
ODESLI_TTL = 7 * 24 * 3600    # platform link sets are stable


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_image_bytes(url, timeout=60):
    """Raw image download (used by the artwork generator save). Seam for tests."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def itunes_search(term, limit=18):
    """Real songs from the iTunes catalog: title, artist, art, preview."""
    term = (term or "").strip()
    if not term:
        return []
    key = "itunes:%d:%s" % (limit, term.lower())
    data = store.cache_get(key, ITUNES_TTL)
    if data is None:
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": term, "entity": "song", "limit": limit})
        try:
            data = _fetch_json(url)
        except Exception:
            return []
        store.cache_set(key, data)
    out = []
    for t in data.get("results", []):
        art = (t.get("artworkUrl100") or "").replace("100x100", "300x300")
        if not (t.get("trackName") and art):
            continue
        out.append({
            "title": t.get("trackName"),
            "artist": t.get("artistName") or "",
            "album": t.get("collectionName") or "",
            "art": art,
            "preview": t.get("previewUrl") or "",
            "url": t.get("trackViewUrl") or "",
        })
    return out


def odesli_lookup(source_url):
    """One track URL in -> every platform's link out. None on failure."""
    source_url = (source_url or "").strip()
    if not source_url.startswith("http"):
        return None
    key = "odesli:" + source_url
    data = store.cache_get(key, ODESLI_TTL)
    if data is None:
        url = "https://api.song.link/v1-alpha.1/links?" + urllib.parse.urlencode(
            {"url": source_url})
        try:
            data = _fetch_json(url)
        except Exception:
            return None
        store.cache_set(key, data)
    try:
        uid = data.get("entityUniqueId")
        ent = (data.get("entitiesByUniqueId") or {}).get(uid, {})
        links = {p: v.get("url") for p, v in (data.get("linksByPlatform") or {}).items()
                 if v.get("url")}
        if not links:
            return None
        return {
            "title": ent.get("title") or "",
            "artist": ent.get("artistName") or "",
            "art": ent.get("thumbnailUrl") or "",
            "page": data.get("pageUrl") or "",
            "links": links,
        }
    except Exception:
        return None


DEEZER_TTL = 30 * 24 * 3600   # ISRC/UPC assignments never change


APPLE_TTL = DEEZER_TTL


def apple_has_isrc(isrc):
    """Does Apple's catalogue carry this exact recording?

    (True|False|None, detail), the same contract as deezer_has_isrc, for
    the same reason: None is "not answered" and must never be read as
    absence. Apple's lookup endpoint is public and keyless and takes an
    ISRC directly; a hit is a song object with the store page's URL, a
    miss is resultCount 0 - a real no. The iTunes Store and Apple Music
    share this catalogue, so one answer serves both statement lines.
    """
    isrc = (isrc or "").strip().upper().replace("-", "")
    if not isrc:
        return None, "no ISRC on the statement row"
    key = "apple-isrc:" + isrc
    data = store.cache_get(key, APPLE_TTL)
    if data is None:
        try:
            data = _fetch_json("https://itunes.apple.com/lookup?"
                               + urllib.parse.urlencode({"isrc": isrc, "entity": "song"}))
        except Exception as exc:                               # noqa: BLE001
            return None, "Apple did not answer (%s)" % (str(exc)[:60] or "no detail")
        store.cache_set(key, data)
    if not isinstance(data, dict) or "resultCount" not in data:
        return None, "Apple sent something unreadable"
    songs = [r for r in (data.get("results") or [])
             if isinstance(r, dict) and r.get("kind") == "song" and r.get("trackViewUrl")]
    if songs:
        return True, songs[0]["trackViewUrl"]
    if int(data.get("resultCount") or 0) == 0:
        return False, "not in Apple's catalogue"
    return None, "Apple answered with no song for that code"


def deezer_has_isrc(isrc):
    """Does Deezer's catalogue carry this exact recording?

    (True|False|None, detail). None means the question was not answered -
    a network failure or an unreadable reply - and must never be reported
    as absence: a bad afternoon at Deezer would otherwise generate a
    letter claiming a track was never delivered.

    Their free endpoint is unambiguous, which is what makes it usable
    here: a real track object, or {"error": {"code": 800, "message": "no
    data"}}. No key, no quota to burn.
    """
    isrc = (isrc or "").strip().upper().replace("-", "")
    if not isrc:
        return None, "no ISRC on the statement row"
    key = "deezer-isrc:" + isrc
    data = store.cache_get(key, DEEZER_TTL)
    if data is None:
        try:
            data = _fetch_json("https://api.deezer.com/track/isrc:" + isrc)
        except Exception as exc:                               # noqa: BLE001
            return None, "Deezer did not answer (%s)" % (str(exc)[:60] or "no detail")
        # Only an answer is kept for 30 days: a track, or their 800 "no
        # data". A quota or other error object comes back with HTTP 200 too,
        # and caching it turned a minute's blip into a month of "Deezer
        # refused" without Deezer being asked again (audit, 2026-09-23).
        if _deezer_answer(data, no_data_is_answer=True):
            store.cache_set(key, data)
    if not isinstance(data, dict):
        return None, "Deezer sent something unreadable"
    error = data.get("error") or {}
    if error:
        # 800 / "no data" is a real answer: they do not have it. Anything
        # else is their problem, not evidence about the recording.
        if isinstance(error, dict) and str(error.get("code")) == "800":
            return False, "not in Deezer's catalogue"
        said = error.get("message") if isinstance(error, dict) else error
        return None, "Deezer refused (%s)" % str(said or error)[:60]
    link = (data.get("link") or "").strip()
    if not link:
        return None, "Deezer answered without a track link"
    return True, link


def _deezer_answer(reply, no_data_is_answer=False):
    """True when a Deezer reply is an answer worth keeping for a month.

    Deezer answers errors with HTTP 200 and an {"error": {...}} object
    (quota, 4; no data, 800). Only their 800 "no data" is an answer, and
    only where absence is the question; every other error, and anything
    that is not a JSON object, is their problem and is asked again next
    time rather than cached as a miss."""
    if not isinstance(reply, dict):
        return False
    error = reply.get("error")
    if error:
        return bool(no_data_is_answer and isinstance(error, dict)
                    and str(error.get("code")) == "800")
    return True


def _norm_name(text):
    """A title or an artist name, compared as a person would read it:
    accents, case, punctuation and a "(feat. ...)" tail do not make two
    names different."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    t = t.lower()
    t = re.sub(r"[\(\[]\s*(feat|ft|featuring|with)\b[^\)\]]*[\)\]]", " ", t)
    t = re.sub(r"\s(feat|ft|featuring)\.?\s.*$", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


DEEZER_CANDIDATES = 10     # keyword hits read before one is accepted


def deezer_track_metadata(title, artist):
    """Industry identifiers for a track from Deezer's free API: ISRC, and
    the album's UPC, label, release date. Returns a dict or None.

    A keyword search is not an identity. The first hit for "Hello Probe
    Artist" was Adele's "Hello", and its ISRC, UPC and label were stored
    as the artist's own (audit, 2026-09-23). A hit is accepted only when
    its title AND its artist name match the ones asked for; with no artist
    to match, nothing is accepted. Even then it is a match by name, not a
    confirmation, and the result says so: `source`, `matched_by`,
    `read_on` (the day Deezer answered) and `lookup_codes` (the codes as
    Deezer gave them, so a page can tell a looked-up code from a typed
    one later).
    """
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title or not artist:
        return None
    # "deezer3": answers cached under "deezer2" were first hits taken
    # without matching the artist, and are not reused.
    key = "deezer3:%s|%s" % (title.lower(), artist.lower())
    data = store.cache_get(key, DEEZER_TTL)
    if data is None:
        # Plain keyword query — Deezer's quoted advanced syntax 404s when urlencoded.
        url = "https://api.deezer.com/search?" + urllib.parse.urlencode(
            {"q": ("%s %s" % (title, artist)).strip(), "limit": DEEZER_CANDIDATES})
        want_title, want_artist = _norm_name(title), _norm_name(artist)
        try:
            found = _fetch_json(url)
            if not _deezer_answer(found) or not isinstance(found.get("data"), list):
                return None                       # an error object: asked again next time
            hit = next((h for h in found["data"] if isinstance(h, dict)
                        and _norm_name((h.get("artist") or {}).get("name")) == want_artist
                        and want_title in (_norm_name(h.get("title_short")),
                                           _norm_name(h.get("title")))), None)
            if hit is None:
                data = {}                          # Deezer answered: no such track by this artist
            else:
                track = _fetch_json("https://api.deezer.com/track/%s" % hit["id"])
                if not _deezer_answer(track) or not track.get("id"):
                    return None
                album_id = (track.get("album") or {}).get("id")
                album = _fetch_json("https://api.deezer.com/album/%s" % album_id) if album_id else {}
                if album_id and (not _deezer_answer(album) or not album.get("id")):
                    return None
                from datetime import datetime, timezone
                data = {"track": track, "album": album,
                        "read_on": datetime.now(timezone.utc).date().isoformat()}
        except Exception:
            return None
        store.cache_set(key, data)
    track = data.get("track") or {}
    if not track:
        return None
    album = data.get("album") or {}
    genres = [g.get("name") for g in ((album.get("genres") or {}).get("data") or [])
              if g.get("name")]
    codes = {"isrc": track.get("isrc") or "", "upc": album.get("upc") or "",
             "label": album.get("label") or ""}
    return dict(codes, **{
        "release_date": album.get("release_date") or track.get("release_date") or "",
        "album": album.get("title") or (track.get("album") or {}).get("title") or "",
        "genre": genres[0] if genres else "",
        "duration": track.get("duration") or 0,
        "track_count": album.get("nb_tracks") or 0,
        "source": "Deezer",
        "matched_by": "title and artist",
        "read_on": data.get("read_on") or "",
        "lookup_codes": {k: v for k, v in codes.items() if v},
    })


def deezer_artist_known_absent(name):
    """True when Deezer answered a search for this name with no artist at
    all - the only case where "no Deezer match" is a fact. False when it
    was never asked, did not answer, or sent an error."""
    name = (name or "").strip()
    if not name:
        return False
    return store.cache_get("deezerartist:%s" % name.lower(), DEEZER_TTL) == {}


def deezer_artist_fans(name):
    """Deezer fan count for an artist by name — a second platform signal
    for Artist Pulse. Returns {name, fans, url} or None."""
    name = (name or "").strip()
    if not name:
        return None
    key = "deezerartist:%s" % name.lower()
    data = store.cache_get(key, DEEZER_TTL)
    if data is None:
        url = "https://api.deezer.com/search/artist?" + urllib.parse.urlencode(
            {"q": name, "limit": 1})
        try:
            reply = _fetch_json(url)
        except Exception:
            return None
        # An error object (quota and the like, sent with HTTP 200) is not
        # "no match": it is not cached, and Deezer is asked again next time.
        if not _deezer_answer(reply) or not isinstance(reply.get("data"), list):
            return None
        hits = reply["data"]
        data = hits[0] if hits else {}
        store.cache_set(key, data)
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return {"name": data.get("name") or name,
            "fans": data.get("nb_fan") or 0,
            "url": data.get("link") or ""}


PRESS_TTL = 24 * 3600  # news results refresh daily


def press_mentions(term, limit=10):
    """Real press coverage from Google News RSS (no key). Returns
    [{title, source, url, date}] for the artist to pick from."""
    term = (term or "").strip()
    if not term:
        return []
    key = "press:" + term.lower()
    cached = store.cache_get(key, PRESS_TTL)
    if cached is not None:
        return cached[:limit]
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": term, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(_fetch_text(url))
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            source = (item.findtext("source") or "").strip()
            link = (item.findtext("link") or "").strip()
            date = (item.findtext("pubDate") or "").strip()
            if not title:
                continue
            # Google News titles end with " - Publication"; keep the headline.
            if source and title.endswith(" - " + source):
                title = title[: -len(" - " + source)]
            out.append({"title": title, "source": source or "News",
                        "url": link, "date": date[:16]})
    except Exception:
        return []
    store.cache_set(key, out)
    return out[:limit]


MUSICBRAINZ_TTL = 30 * 24 * 3600
_MB = "https://musicbrainz.org/ws/2"
_WRITER_ROLES = {"composer", "lyricist", "writer"}


def musicbrainz_credits(isrc):
    """Songwriters and publishers for a recording, looked up by ISRC in the
    open MusicBrainz database (no key, 1 request/second). Returns
    {"writers": [...], "publishers": [...]} or None."""
    isrc = (isrc or "").strip().upper()
    if not isrc:
        return None
    key = "mb:" + isrc
    data = store.cache_get(key, MUSICBRAINZ_TTL)
    if data is None:
        try:
            recs = _fetch_json("%s/isrc/%s?fmt=json" % (_MB, isrc)).get("recordings", [])
            works, relations = [], []
            if recs:
                time.sleep(1.05)  # MusicBrainz rate limit
                rec = _fetch_json("%s/recording/%s?fmt=json&inc=work-rels" % (_MB, recs[0]["id"]))
                works = [rel["work"]["id"] for rel in rec.get("relations", [])
                         if rel.get("work")]
            if works:
                time.sleep(1.05)
                w = _fetch_json("%s/work/%s?fmt=json&inc=artist-rels+label-rels" % (_MB, works[0]))
                relations = w.get("relations", [])
            data = {"relations": relations}
        except Exception:
            return None
        store.cache_set(key, data)
    writers, publishers = [], []
    for rel in data.get("relations", []):
        name = ((rel.get("artist") or rel.get("label")) or {}).get("name")
        if not name:
            continue
        bucket = writers if rel.get("type") in _WRITER_ROLES else (
            publishers if rel.get("type") == "publisher" else None)
        if bucket is not None and name not in bucket:
            bucket.append(name)
    if not writers and not publishers:
        return None
    return {"writers": writers, "publishers": publishers}


# Display order + branding for the universal landing page.
PLATFORM_DISPLAY = [
    ("spotify", "Spotify", "spotify"),
    ("appleMusic", "Apple Music", "apple"),
    ("itunes", "iTunes", "apple"),
    ("youtube", "YouTube", "youtube"),
    ("youtubeMusic", "YouTube Music", "youtube"),
    ("tidal", "TIDAL", "other"),
    ("deezer", "Deezer", "other"),
    ("amazonMusic", "Amazon Music", "other"),
    ("soundcloud", "SoundCloud", "other"),
    ("pandora", "Pandora", "other"),
    ("audiomack", "Audiomack", "other"),
]


def ordered_platform_links(links):
    """[(label, logo_key, url)] in display order, then any extras."""
    out, seen = [], set()
    for key, label, logo in PLATFORM_DISPLAY:
        if links.get(key):
            out.append((label, logo, links[key]))
            seen.add(key)
    for key, url in links.items():
        if key not in seen:
            out.append((key.replace("Music", " Music").title(), "other", url))
    return out
