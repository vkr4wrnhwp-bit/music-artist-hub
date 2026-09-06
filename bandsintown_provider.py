"""Bandsintown public Events API — real upcoming tour dates.

Env-gated like the Spotify provider: everything no-ops until
BANDSINTOWN_APP_ID is set, so the app never fakes a connection.
Events are looked up by the artist's exact Bandsintown name and
cached in SQLite so pages stay fast and we stay polite to the API.
`_fetch_json` is the seam tests monkeypatch.
"""

import json
import os
import urllib.parse
import urllib.request

import db as store

_TIMEOUT = 12
_UA = "StreetBanker/1.0 (team.summitarts@gmail.com)"

EVENTS_TTL = 6 * 3600  # tour dates change slowly; refresh a few times a day

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def configured():
    return bool(os.environ.get("BANDSINTOWN_APP_ID"))


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fmt_date(iso):
    # "2026-08-01T20:00:00" -> "Aug 1, 2026"
    try:
        d, _, _ = iso.partition("T")
        y, m, day = d.split("-")
        return "%s %d, %s" % (_MONTHS[int(m) - 1], int(day), y)
    except (ValueError, IndexError):
        return iso


ARTIST_TTL = 6 * 3600


def _events_data(artist_name):
    """The raw upcoming-events list for a name, cached; None on any miss."""
    artist_name = (artist_name or "").strip()
    if not artist_name or not configured():
        return None
    key = "bandsintown:%s" % artist_name.lower()
    data = store.cache_get(key, EVENTS_TTL)
    if data is None:
        url = ("https://rest.bandsintown.com/artists/%s/events?" %
               urllib.parse.quote(artist_name, safe="")) + urllib.parse.urlencode(
            {"app_id": os.environ["BANDSINTOWN_APP_ID"], "date": "upcoming"})
        try:
            data = _fetch_json(url)
        except Exception:
            return None
        # The API answers errors as JSON objects; only cache real lists.
        if not isinstance(data, list):
            return None
        store.cache_set(key, data)
    return data


def artist_info(artist_name):
    """The artist's own Bandsintown record - how many people track them
    there and how many dates are up - or None on any miss. Their errors
    come back as objects without a name, so a name is the test."""
    artist_name = (artist_name or "").strip()
    if not artist_name or not configured():
        return None
    key = "bandsintown:artist:%s" % artist_name.lower()
    data = store.cache_get(key, ARTIST_TTL)
    if data is None:
        url = ("https://rest.bandsintown.com/artists/%s?" %
               urllib.parse.quote(artist_name, safe="")) + urllib.parse.urlencode(
            {"app_id": os.environ["BANDSINTOWN_APP_ID"]})
        try:
            data = _fetch_json(url)
        except Exception:
            return None
        if not isinstance(data, dict) or not data.get("name"):
            return None
        store.cache_set(key, data)
    try:
        trackers = int(data.get("tracker_count") or 0)
        upcoming = int(data.get("upcoming_event_count") or 0)
    except (TypeError, ValueError):
        trackers, upcoming = 0, 0
    return {"name": data.get("name") or artist_name, "url": data.get("url") or "",
            "image_url": data.get("image_url") or "", "mbid": data.get("mbid") or "",
            "trackers": trackers, "upcoming": upcoming}


def event_rows(artist_name, limit=50):
    """Upcoming shows in Signal's shape: ISO date, city / region / country,
    venue, page and ticket links. [] on any miss."""
    data = _events_data(artist_name)
    out = []
    for ev in (data or [])[:limit]:
        venue = ev.get("venue") or {}
        tickets = next((o.get("url") for o in (ev.get("offers") or [])
                        if o.get("type") == "Tickets" and o.get("url")), "")
        out.append({"date": (ev.get("datetime") or "")[:10], "city": venue.get("city") or "",
                    "region": venue.get("region") or "", "country": venue.get("country") or "",
                    "venue": venue.get("name") or "TBA", "url": ev.get("url") or "",
                    "tickets": tickets, "lineup": list(ev.get("lineup") or [])})
    return out


def upcoming_events(artist_name, limit=12):
    """Upcoming shows for an artist, normalized for display. [] on any miss."""
    data = _events_data(artist_name)
    if data is None:
        return []
    out = []
    for ev in data[:limit]:
        venue = ev.get("venue") or {}
        loc = ", ".join(p for p in (venue.get("city"),
                                    venue.get("region") or venue.get("country"))
                        if p)
        tickets = next((o.get("url") for o in (ev.get("offers") or [])
                        if o.get("type") == "Tickets" and o.get("url")), "")
        out.append({
            "date": _fmt_date(ev.get("datetime") or ""),
            "iso": ev.get("datetime") or "",
            "venue": venue.get("name") or "TBA",
            "location": loc,
            "url": ev.get("url") or "",
            "tickets": tickets,
        })
    return out
