"""What Ticketmaster's public listing says about a date - and what it does not.

Most club dates are never on Eventbrite. The rooms that sell through
Ticketmaster are listed in their free Discovery API, so a tour can fill
the same ticket fields from a second source: the link the public buys
through, the on-sale state, and the date as announced.

Verified against Ticketmaster's published Discovery API v2 reference and
their Getting Started page (2026-09-09):

    base        https://app.ticketmaster.com/discovery/v2/
    search      GET events.json?apikey=<key>
                &keyword= &attractionId= &venueId= &city= &stateCode=
                &countryCode= &startDateTime= &endDateTime=
                &classificationName= &size= &page=      (all of these exist)
    detail      GET events/{id}.json?apikey=<key>
    envelope    {"_embedded": {"events": [...]},
                 "page": {"size", "number", "totalPages", "totalElements"}}
    per event   name, id, url,
                dates.start.localDate / localTime / dateTime,
                dates.status.code -> onsale | offsale | canceled |
                                     postponed | rescheduled,
                _embedded.venues[].name / .city.name / .state.stateCode,
                priceRanges[] (type, currency, min, max),
                sales.public.startDateTime / endDateTime
    errors      {"fault": {"faultstring": "...",
                           "detail": {"errorcode": "..."}}} - the
                published shape: 401 oauth.v2.InvalidApiKey, 429
                policies.ratelimit.QuotaViolation. Some Ticketmaster
                endpoints answer {"errors": [{"code", "detail",
                "status"}]} instead, so both are read.
    limits      5 requests a second, 5,000 calls a day by default; deep
                paging is capped at the 1000th item (size x page < 1000).

WHAT DISCOVERY DOES NOT HAVE, said plainly: it is a public *listing*
API. No field anywhere in an event says how many tickets have sold, and
none says the room's capacity or remaining inventory - not on the event,
not on the venue, not in priceRanges. So this source fills a date's
ticket link, its on-sale status and its announced date, and it must
never write tickets_sold or capacity. A count Eventbrite measured is
never replaced by a source that cannot measure one, and a page that
showed a blank beside a Ticketmaster date would read as nobody came, so
the page says the count is not published instead.

Env-gated like every other provider: without TICKETMASTER_API_KEY
nothing is looked up and the page says so; in sandbox mode `configured()`
is False even with a key, so an experiment never makes an outbound call.
`_http` is the one seam every call goes through and the one tests
monkeypatch. Every failure here is a None or an empty list, never an
exception on a page: a date Ticketmaster says nothing about keeps
whatever was typed, which is honest.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import sandbox

_TIMEOUT = 10
BASE = "https://app.ticketmaster.com/discovery/v2"
EVENTS_URL = BASE + "/events.json"
EVENT_URL = BASE + "/events/%s.json"
# Music only: the keyword search alone would answer with a comedy night
# of the same name.
CLASSIFICATION = "music"
PAGE_SIZE = 50
# A ceiling on one walk. Discovery refuses past the 1000th item anyway
# (size x page < 1000), and a tour is a handful of dates, not a catalog.
MAX_PAGES = 4
MAX_EVENTS = 200
MAX_BYTES = 4 * 1024 * 1024
# The statuses Discovery publishes, in their own words.
STATUS_CODES = ("onsale", "offsale", "canceled", "cancelled", "postponed", "rescheduled")


def _key():
    return (os.environ.get("TICKETMASTER_API_KEY") or "").strip()


def configured():
    # A sandbox deployment reports no provider even when a key is
    # present: the whole app already knows how to behave without one.
    if sandbox.active():
        return False
    return bool(_key())


# The last time Ticketmaster refused the key outright, kept for the run
# that asked so its report can say so. A date they simply do not list is
# not a refusal and never lands here.
_REFUSAL = None


def clear_refusal():
    global _REFUSAL
    _REFUSAL = None


def last_refusal():
    """{'status', 'message', 'http'} for the last 401, 403 or 429
    Ticketmaster answered - the key wrong or not yet approved
    (oauth.v2.InvalidApiKey, "Invalid ApiKey"), or the daily quota spent
    (policies.ratelimit.QuotaViolation) - or None. The message is
    Ticketmaster's own, not one invented here."""
    return dict(_REFUSAL) if _REFUSAL else None


def _note(exc):
    """Keep a refusal; let every other failure stay a quiet None. A 404
    is an event that is gone, not a refusal, and a 400 is this code's
    fault rather than something the owner can act on."""
    global _REFUSAL
    if not isinstance(exc, urllib.error.HTTPError) or exc.code not in (401, 403, 429):
        return
    status, message = "", ""
    try:
        doc = json.loads((exc.read() or b"").decode("utf-8", "replace"))
    except Exception:
        doc = None
    if isinstance(doc, dict):
        fault = doc.get("fault") if isinstance(doc.get("fault"), dict) else None
        if fault:
            detail = fault.get("detail") if isinstance(fault.get("detail"), dict) else {}
            status = str(detail.get("errorcode") or "")[:60]
            message = str(fault.get("faultstring") or "")[:300]
        else:
            rows = doc.get("errors")
            first = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
            status = str(first.get("code") or "")[:60]
            message = str(first.get("detail") or "")[:300]
    _REFUSAL = {"status": status or ("HTTP %d" % exc.code),
                "message": message or str(exc.reason or "")[:300], "http": exc.code}


def _http(url):
    """One outbound GET. Returns the body bytes. Raises on any failure;
    the callers turn that into a None or an empty list."""
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "StreetBanker/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read(MAX_BYTES + 1)


def _get(url):
    """One call, parsed. None on anything that is not a JSON object. The
    key is a query parameter, which is the whole of Discovery's auth."""
    try:
        body = _http(url)
    except Exception as e:
        _note(e)
        return None
    if not body or len(body) > MAX_BYTES:
        return None
    try:
        doc = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None


def _url(params):
    merged = {"apikey": _key()}
    merged.update({k: v for k, v in params.items() if v not in ("", None)})
    return EVENTS_URL + "?" + urllib.parse.urlencode(merged)


def _day_start(date):
    """A YYYY-MM-DD turned into the ISO instant Discovery asks for."""
    date = (date or "").strip()[:10]
    return (date + "T00:00:00Z") if len(date) == 10 else ""


def _day_end(date):
    date = (date or "").strip()[:10]
    return (date + "T23:59:59Z") if len(date) == 10 else ""


def _venue(row):
    embedded = row.get("_embedded") if isinstance(row.get("_embedded"), dict) else {}
    rooms = embedded.get("venues") if isinstance(embedded.get("venues"), list) else []
    for v in rooms:
        if isinstance(v, dict):
            return v
    return {}


def _prices(row):
    """(min, max, currency) across the published ranges, or (None, None,
    '') - a listing with no price shown is common and is not an error."""
    rows = row.get("priceRanges") if isinstance(row.get("priceRanges"), list) else []
    lows, highs, currency = [], [], ""
    for r in rows:
        if not isinstance(r, dict):
            continue
        currency = currency or str(r.get("currency") or "")[:8]
        for key, bucket in (("min", lows), ("max", highs)):
            try:
                bucket.append(float(r.get(key)))
            except (TypeError, ValueError):
                pass
    return (min(lows) if lows else None), (max(highs) if highs else None), currency


def _event(row):
    """One Discovery event, flattened to what a match needs and nothing
    more: the local date the room is booked on, the room's name and
    city, the on-sale code in Ticketmaster's own word, and the public
    sale window. There is no sold count and no capacity to flatten -
    Discovery publishes neither."""
    dates = row.get("dates") if isinstance(row.get("dates"), dict) else {}
    start = dates.get("start") if isinstance(dates.get("start"), dict) else {}
    state = dates.get("status") if isinstance(dates.get("status"), dict) else {}
    venue = _venue(row)
    city = venue.get("city") if isinstance(venue.get("city"), dict) else {}
    region = venue.get("state") if isinstance(venue.get("state"), dict) else {}
    sales = row.get("sales") if isinstance(row.get("sales"), dict) else {}
    public = sales.get("public") if isinstance(sales.get("public"), dict) else {}
    low, high, currency = _prices(row)
    local_date = str(start.get("localDate") or "")[:10]
    local_time = str(start.get("localTime") or "")[:8]
    return {
        "source": "ticketmaster",
        "id": str(row.get("id") or "")[:60],
        "name": str(row.get("name") or "")[:200],
        "url": str(row.get("url") or "")[:300],
        "status": str(state.get("code") or "")[:20],
        "date": local_date,
        "start_local": (local_date + "T" + local_time) if local_date and local_time else local_date,
        "venue": str(venue.get("name") or "")[:200],
        "city": str(city.get("name") or "")[:120],
        "region": str(region.get("stateCode") or "")[:20],
        "onsale_start": str(public.get("startDateTime") or "")[:20],
        "onsale_end": str(public.get("endDateTime") or "")[:20],
        "price_min": low, "price_max": high, "currency": currency,
    }


def _rows(doc):
    embedded = doc.get("_embedded") if isinstance(doc.get("_embedded"), dict) else {}
    rows = embedded.get("events") if isinstance(embedded.get("events"), list) else []
    return [r for r in rows if isinstance(r, dict)]


def find_events(artist, date_from=None, date_to=None):
    """Every music event Ticketmaster lists for this artist in this
    window, up to MAX_EVENTS, or [] - no key, no artist name, a refusal.
    The walk is bounded: MAX_PAGES pages of PAGE_SIZE, and it stops as
    soon as Discovery says there are no more (page.totalPages)."""
    artist = (artist or "").strip()
    if not configured() or not artist:
        return []
    out = []
    for page in range(MAX_PAGES):
        doc = _get(_url({"keyword": artist, "classificationName": CLASSIFICATION,
                         "startDateTime": _day_start(date_from),
                         "endDateTime": _day_end(date_to),
                         "size": PAGE_SIZE, "page": page}))
        if doc is None:
            break
        for row in _rows(doc):
            ev = _event(row)
            if ev["id"] and ev["date"]:
                out.append(ev)
            if len(out) >= MAX_EVENTS:
                return out
        meta = doc.get("page") if isinstance(doc.get("page"), dict) else {}
        try:
            total = int(meta.get("totalPages"))
        except (TypeError, ValueError):
            total = page + 1
        if page + 1 >= total:
            break
    return out


def get_event(event_id):
    """One event by id, flattened the same way, or None. Used when a show
    already carries a Ticketmaster id: the owner's answer is honoured
    even when the event has fallen out of the keyword search."""
    if not configured() or not event_id:
        return None
    doc = _get(EVENT_URL % urllib.parse.quote(str(event_id)) +
               "?" + urllib.parse.urlencode({"apikey": _key()}))
    if not doc or not doc.get("id"):
        return None
    ev = _event(doc)
    return ev if ev["id"] else None
