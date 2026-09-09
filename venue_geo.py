"""Where the room actually is: coordinates, its time zone, and the drive.

The venue book already knows a room's name and address. It did not know
where that address *is*, so the route page could only say "no address"
and every show carried the tour's home time zone whether or not the room
was in it. Three Google APIs on the one `GOOGLE_MAPS_API_KEY` the venue
photos already use answer that:

    Geocoding API   an address (or a Places place_id) -> lat, lng
    Time Zone API   a lat/lng -> the IANA zone that point is in
    Routes API v2   two points -> a real driving distance and duration

The first two are enabled on the owner's key (project devora-live,
2026-09-09) alongside Places API (New). The third is **not**, and this
module is built for that: `drive()` asks once, keeps Google's refusal,
latches itself off for the rest of the process, and the route page falls
back to the straight line it can compute itself — labelled as a straight
line, never as a drive. A distance is a fact either way; a duration is
only ever printed when Google measured one.

Shaped exactly like `venue_photos.py`, on purpose:

  * `configured()` is False under `sandbox.active()` even with a key, so
    an experiment never makes an outbound call.
  * `_http` is the one seam every call goes through and the one tests
    monkeypatch.
  * Every failure is a None, never an exception on a page.
  * A refusal is kept with Google's own status and message
    (`last_refusal()`) so the run that asked can say what Google said,
    instead of reporting "not found" about rooms that were never looked
    up. That mistake was made once with the photos and is not repeated.

The classic (non-New) Google web services answer HTTP 200 with a
`status` field in the body, so a refused key is not an HTTPError here:
REQUEST_DENIED arrives as a perfectly successful 200. Routes v2 is the
newer shape and answers a real 4xx with `{"error": {...}}`. Both are
read.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

import sandbox

_TIMEOUT = 10
MAX_BYTES = 1024 * 1024

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
TIMEZONE_URL = "https://maps.googleapis.com/maps/api/timezone/json"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTES_FIELD_MASK = "routes.distanceMeters,routes.duration"

# Verified against Google's own documentation, 2026-09-09:
#   Geocoding  OK / ZERO_RESULTS / OVER_DAILY_LIMIT / OVER_QUERY_LIMIT /
#              REQUEST_DENIED / INVALID_REQUEST / UNKNOWN_ERROR
#   Time Zone  the same set, ZERO_RESULTS meaning no zone for that point
# OK is an answer and ZERO_RESULTS is an answer ("Google does not know
# this address"), so neither is a refusal. UNKNOWN_ERROR is Google's own
# word for "try again" and says nothing about the key, so it is a quiet
# None too. What is left cannot succeed until somebody changes something
# in the Cloud console, and that is what the report has to say out loud.
REFUSAL_STATUSES = ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT",
                    "INVALID_REQUEST", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED")


def _key():
    return (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()


def configured():
    # A sandbox deployment reports no provider even when a key is present:
    # the whole app already knows how to behave without one.
    if sandbox.active():
        return False
    return bool(_key())


# The last time Google refused the key outright, kept for the run that
# asked so its report can say so. An address Google simply does not know
# is not a refusal and never lands here.
_REFUSAL = None
# Routes API v2 is a separate API on the same key and is not enabled on
# the owner's project. One refusal switches it off for this process so a
# twenty-date tour does not spend twenty timeouts learning the same fact
# twice; the page then says "straight line" for every leg, which is true.
_ROUTES_OK = True


def clear_refusal():
    global _REFUSAL
    _REFUSAL = None


def last_refusal():
    """{'status', 'message', 'http'} for the last answer that means the
    key cannot do this until something is changed in Google Cloud
    (REQUEST_DENIED when the API is off for the project or the key is
    restricted to websites, OVER_QUERY_LIMIT past quota), or None."""
    return dict(_REFUSAL) if _REFUSAL else None


def routes_available():
    """Whether Routes API v2 has answered anything but a refusal so far
    in this process. False means every distance on the page is the
    straight line and says so."""
    return _ROUTES_OK


def reset_routes():
    global _ROUTES_OK
    _ROUTES_OK = True


def _keep(status, message, http=0):
    global _REFUSAL
    _REFUSAL = {"status": str(status or "")[:40] or ("HTTP %d" % http),
                "message": str(message or "")[:300], "http": int(http or 0)}


def _note_http(exc):
    """Keep a refusal out of a 4xx body; let every other failure stay a
    quiet None. Only Routes v2 answers this way."""
    if not isinstance(exc, urllib.error.HTTPError) or not (400 <= exc.code < 500):
        return
    status, message = "", ""
    try:
        doc = json.loads((exc.read() or b"").decode("utf-8", "replace"))
        err = doc.get("error") if isinstance(doc, dict) else None
        if isinstance(err, dict):
            status = str(err.get("status") or "")
            message = str(err.get("message") or "")
    except Exception:
        pass
    _keep(status, message or str(exc.reason or ""), exc.code)


def _http(url, payload=None, headers=None):
    """One outbound call: POST when `payload` is given, else GET. Returns
    (body bytes, content type). Raises on any failure; the callers turn
    that into None."""
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


def _get_json(url, params):
    """A classic web-service call. Returns the parsed document, or None
    when nothing came back at all. The `status` inside is the caller's to
    read: a refused key arrives here as a successful 200."""
    try:
        body, _ct = _http(url + "?" + urllib.parse.urlencode(params))
        return json.loads(body.decode("utf-8")) if body else None
    except Exception as e:
        _note_http(e)
        return None


def _read_status(doc):
    """(status, error_message) from a classic answer, and a refusal kept
    when the status is one only the console can fix."""
    if not isinstance(doc, dict):
        return "", ""
    status = str(doc.get("status") or "")
    message = str(doc.get("error_message") or "")
    if status in REFUSAL_STATUSES:
        _keep(status, message or "Google gave no message with this status.", 200)
    return status, message


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if -180.0 <= f <= 180.0 else None


def _coord(v):
    """A coordinate as it is stored on the venue: a plain decimal string,
    seven places, which is under a centimetre and the most any of these
    services returns."""
    return ("%.7f" % v).rstrip("0").rstrip(".") or "0"


def geocode(query, place_id=""):
    """Where an address is: {'lat', 'lng', 'formatted_address', 'place_id'}
    as strings, or None for no key, no answer, or an address Google does
    not know (ZERO_RESULTS — a fact about the address, not an error).

    `place_id`, when the venue already carries one from the Places lookup
    the photo made, is asked instead of the text: it names one exact
    record rather than the best match for a string, so a room whose name
    also belongs to a hair salon two states away cannot drift."""
    if not configured():
        return None
    pid = (place_id or "").strip()
    text = (query or "").strip()
    if pid:
        params = {"place_id": pid, "key": _key()}
    elif text:
        params = {"address": text, "key": _key()}
    else:
        return None
    doc = _get_json(GEOCODE_URL, params)
    status, _msg = _read_status(doc)
    if status != "OK":
        return None
    results = doc.get("results") or []
    first = results[0] if results and isinstance(results[0], dict) else None
    if not first:
        return None
    loc = ((first.get("geometry") or {}).get("location")) or {}
    lat, lng = _num(loc.get("lat")), _num(loc.get("lng"))
    if lat is None or lng is None or not (-90.0 <= lat <= 90.0):
        return None
    return {"lat": _coord(lat), "lng": _coord(lng),
            "formatted_address": str(first.get("formatted_address") or "")[:300],
            "place_id": str(first.get("place_id") or "")[:200]}


def _stamp(when):
    """The Unix second the Time Zone API wants. The IANA id it answers
    does not change with the season, but the request will not be served
    without a timestamp, so the show's own date is sent when there is
    one and today otherwise."""
    if isinstance(when, datetime):
        dt = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    if isinstance(when, date):
        return int(datetime(when.year, when.month, when.day, 12, tzinfo=timezone.utc).timestamp())
    if isinstance(when, (int, float)):
        return int(when)
    if isinstance(when, str) and len(when) >= 10:
        try:
            d = date.fromisoformat(when[:10])
            return int(datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass
    return int(datetime.now(timezone.utc).timestamp())


def timezone_at(lat, lng, when=None):
    """The IANA zone a point is in ('America/Chicago'), or None. A point
    at sea answers ZERO_RESULTS, which is not an error and not a refusal:
    it is Google saying it has no zone there."""
    if not configured():
        return None
    a, b = _num(lat), _num(lng)
    if a is None or b is None or not (-90.0 <= a <= 90.0):
        return None
    doc = _get_json(TIMEZONE_URL, {"location": "%s,%s" % (_coord(a), _coord(b)),
                                   "timestamp": _stamp(when), "key": _key()})
    status, _msg = _read_status(doc)
    if status != "OK":
        return None
    tz = str(doc.get("timeZoneId") or "").strip()
    return tz[:60] or None


def _dur_seconds(raw):
    """Routes answers a duration as protobuf seconds: the string '165s'."""
    text = str(raw or "").strip()
    if not text.endswith("s"):
        return None
    try:
        return int(round(float(text[:-1])))
    except ValueError:
        return None


def drive(frm, to):
    """The real driving distance and duration between two (lat, lng)
    pairs: {'meters', 'seconds'}, or None. None means the caller shows
    the straight line and says so — it never means "assume a speed".

    Routes API v2 is a POST with the key and the field mask in headers,
    documented at developers.google.com/maps/documentation/routes. It is
    a separate API from Geocoding on the same key, so a project with the
    other two switched on still refuses this one; the first refusal
    switches this function off for the process."""
    global _ROUTES_OK
    if not configured() or not _ROUTES_OK:
        return None
    a_lat, a_lng = _num((frm or (None, None))[0]), _num((frm or (None, None))[1])
    b_lat, b_lng = _num((to or (None, None))[0]), _num((to or (None, None))[1])
    if None in (a_lat, a_lng, b_lat, b_lng):
        return None
    payload = {"origin": {"location": {"latLng": {"latitude": a_lat, "longitude": a_lng}}},
               "destination": {"location": {"latLng": {"latitude": b_lat, "longitude": b_lng}}},
               "travelMode": "DRIVE"}
    try:
        body, _ct = _http(ROUTES_URL, payload,
                          {"X-Goog-Api-Key": _key(), "X-Goog-FieldMask": ROUTES_FIELD_MASK})
        doc = json.loads(body.decode("utf-8")) if body else {}
    except Exception as e:
        _note_http(e)
        if (last_refusal() or {}).get("http"):
            _ROUTES_OK = False
        return None
    routes = doc.get("routes") if isinstance(doc, dict) else None
    first = routes[0] if routes and isinstance(routes[0], dict) else None
    if not first:
        return None
    seconds = _dur_seconds(first.get("duration"))
    try:
        meters = int(first.get("distanceMeters"))
    except (TypeError, ValueError):
        return None
    if seconds is None or meters <= 0:
        return None
    return {"meters": meters, "seconds": seconds}
