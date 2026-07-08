"""Free public music APIs: iTunes Search (real tracks, artwork, 30-second
previews — no key) and Odesli/Songlink (universal all-platform links —
no key, 10 req/min). Responses are cached in SQLite to respect rate
limits and keep pages fast. `_fetch_json` is the seam tests monkeypatch
so no test ever touches the network.
"""

import json
import urllib.parse
import urllib.request

import db as store

_TIMEOUT = 6
_UA = "StreetBanker/1.0 (team.summitarts@gmail.com)"

ITUNES_TTL = 24 * 3600        # searches refresh daily
ODESLI_TTL = 7 * 24 * 3600    # platform link sets are stable


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
