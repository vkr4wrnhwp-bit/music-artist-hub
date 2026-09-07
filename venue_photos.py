"""A photo of the room, from Google Places, beside its date.

The owner, 2026-09-07: "have it import the image of the club on this
page as a thumbnail next to the show." Google Places (New) is the one
source that has a picture of most clubs and lets an app show it, with
the photographer's name attached — their terms require the credit, and
the page prints it.

Env-gated like every other provider: without GOOGLE_MAPS_API_KEY nothing
is looked up and the page says so; in sandbox mode `configured()` is
False even with a key, so an experiment never makes an outbound call.
`_http` is the one seam every call goes through and the one tests
monkeypatch. Every failure here is a None, never an exception on a page:
a venue without a photo keeps its monogram, which is honest.
"""

import json
import os
import re
import urllib.parse
import urllib.request

import sandbox

_TIMEOUT = 10
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
MEDIA_URL = "https://places.googleapis.com/v1/%s/media?maxWidthPx=480&key=%s"
FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.photos"
MAX_BYTES = 8 * 1024 * 1024
# Words that say nothing about which room it is, left out of the match.
_FILLER = {"the", "a", "an", "of", "and", "at", "in", "on", "club", "bar", "venue", "room", "hall"}


def _tokens(text):
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) > 1}


def same_room(name, display):
    """Whether Google's top hit is plausibly the venue that was asked for:
    the two names share at least one real word (a name made only of filler
    words, like The Room, must appear whole). Text Search answers the best
    match for nearly any query, so 'Studio A' in a city with no such club
    can come back as a salon; without this check the salon's photo would
    sit beside the date as the room."""
    a, b = _tokens(name), _tokens(display)
    shared = a & b
    if not a or not shared:
        return False
    if shared - _FILLER:
        return True
    return not (a - _FILLER) and shared == a


def _key():
    return (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()


def configured():
    # A sandbox deployment reports no provider even when a key is present:
    # the whole app already knows how to behave without one.
    if sandbox.active():
        return False
    return bool(_key())


def _http(url, payload=None, headers=None):
    """One outbound call: POST when `payload` is given, else GET, following
    redirects (the photo endpoint answers with one). Returns (body bytes,
    content type). Raises on any failure; the callers turn that into None."""
    merged = {"User-Agent": "StreetBanker/1.0", "Accept": "*/*"}
    merged.update(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        merged["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=merged,
                                 method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
        return body, (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()


def lookup(name, city):
    """The best Places match for a venue name in a city, or None: no key,
    no match, no answer. The result carries the first photo's resource
    name and the credit Google attaches to it."""
    if not configured():
        return None
    query = " ".join(p for p in ((name or "").strip(), (city or "").strip()) if p)
    if not query:
        return None
    try:
        body, _ct = _http(SEARCH_URL, {"textQuery": query, "maxResultCount": 1},
                          {"X-Goog-Api-Key": _key(), "X-Goog-FieldMask": FIELD_MASK})
        doc = json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        return None
    places = doc.get("places") if isinstance(doc, dict) else None
    if not places or not isinstance(places[0], dict):
        return None
    place = places[0]
    display = place.get("displayName")
    if isinstance(display, dict):
        display = display.get("text") or ""
    if not same_room(name, display):
        return None
    photos = place.get("photos") or []
    first = photos[0] if photos and isinstance(photos[0], dict) else {}
    credit = ""
    for a in first.get("authorAttributions") or []:
        if isinstance(a, dict) and a.get("displayName"):
            credit = str(a["displayName"]).strip()[:120]
            break
    return {
        "place_id": str(place.get("id") or "")[:200],
        "name": str(display or "")[:200],
        "address": str(place.get("formattedAddress") or "")[:300],
        "photo_name": str(first.get("name") or "")[:400],
        "credit": credit,
    }


def fetch_photo(photo_name):
    """The bytes of one Places photo (up to 480px wide) and their content
    type, or None. The endpoint redirects to the image; urllib follows."""
    if not configured() or not photo_name or not photo_name.startswith("places/"):
        return None
    try:
        body, ctype = _http(MEDIA_URL % (urllib.parse.quote(photo_name, safe="/"), urllib.parse.quote(_key())))
    except Exception:
        return None
    if not body or len(body) > MAX_BYTES or not ctype.startswith("image/"):
        return None
    return body, ctype
