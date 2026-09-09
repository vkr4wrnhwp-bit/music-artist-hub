"""What Eventbrite has actually sold, for the ticket fields on a date.

The owner holds a private token (Eventbrite's own words for it: an
account-wide OAuth token from their API Keys page). With it, TOUR can
read the events that account sells and fill a show's ticket link, its
on-sale state and its sold count from measured numbers instead of a
figure somebody typed a week ago.

Verified against Eventbrite's published API blueprint (2026-09-09):

    base            https://www.eventbriteapi.com/v3/
    auth            Authorization: Bearer <private token>
    organizations   GET /users/me/organizations/       -> organizations[]
    events          GET /organizations/{id}/events/    -> events[]
                    ?status=live,started,ended&expand=venue,ticket_availability
    ticket classes  GET /events/{id}/ticket_classes/   -> ticket_classes[]
                    each with quantity_total and quantity_sold
    pagination      pagination.has_more_items + pagination.continuation,
                    the token sent back as ?continuation=
    errors          {"error", "error_description", "status_code"};
                    401 ACCESS_DENIED / NO_AUTH, 403 NOT_AUTHORIZED,
                    429 HIT_RATE_LIMIT (2,000 calls an hour by default)

Env-gated like every other provider: without EVENTBRITE_TOKEN nothing is
looked up and the page says so; in sandbox mode `configured()` is False
even with a token, so an experiment never makes an outbound call. `_http`
is the one seam every call goes through and the one tests monkeypatch.
Every failure here is a None or an empty list, never an exception on a
page: a show Eventbrite says nothing about keeps whatever was typed,
which is honest.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import sandbox

_TIMEOUT = 10
BASE = "https://www.eventbriteapi.com/v3"
ORGS_URL = BASE + "/users/me/organizations/"
EVENTS_URL = BASE + "/organizations/%s/events/"
TICKET_CLASSES_URL = BASE + "/events/%s/ticket_classes/"
# Sold and unsold both matter: a date that ended still has a real count,
# and a draft event is not on sale to anybody, so it is left out.
EVENT_STATUS = "live,started,ended"
EVENT_EXPAND = "venue,ticket_availability"
PAGE_SIZE = 50
# A ceiling on one walk, so an account with thousands of events cannot
# turn one button press into an unbounded crawl.
MAX_EVENTS = 200
MAX_PAGES = 20
MAX_BYTES = 4 * 1024 * 1024


def _token():
    return (os.environ.get("EVENTBRITE_TOKEN") or "").strip()


def configured():
    # A sandbox deployment reports no provider even when a token is
    # present: the whole app already knows how to behave without one.
    if sandbox.active():
        return False
    return bool(_token())


# The last time Eventbrite refused the token outright, kept for the run
# that asked so its report can say so. An account with no matching event
# is not a refusal and never lands here.
_REFUSAL = None


def clear_refusal():
    global _REFUSAL
    _REFUSAL = None


def last_refusal():
    """{'status', 'message', 'http'} for the last 401, 403 or 429
    Eventbrite answered — the token revoked or wrong (ACCESS_DENIED),
    the account not allowed to read that organization (NOT_AUTHORIZED),
    or the hourly rate limit spent (HIT_RATE_LIMIT) — or None. The
    message is Eventbrite's own, not one invented here."""
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
        if isinstance(doc, dict):
            status = str(doc.get("error") or "")[:60]
            message = str(doc.get("error_description") or "")[:300]
    except Exception:
        pass
    _REFUSAL = {"status": status or ("HTTP %d" % exc.code),
                "message": message or str(exc.reason or "")[:300], "http": exc.code}


def _http(url, headers=None):
    """One outbound GET. Returns the body bytes. Raises on any failure;
    the callers turn that into a None or an empty list."""
    merged = {"Accept": "application/json", "User-Agent": "StreetBanker/1.0"}
    merged.update(headers or {})
    req = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read(MAX_BYTES + 1)


def _get(url):
    """One call, parsed. None on anything that is not a JSON object.
    The private token goes on every request as the bearer, which is the
    whole of Eventbrite's auth for an account's own data."""
    try:
        body = _http(url, {"Authorization": "Bearer %s" % _token()})
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


def _pages(url, key, cap=MAX_PAGES):
    """Every page of one paginated endpoint, following Eventbrite's
    continuation token until has_more_items is false or the cap is hit.
    A page that fails ends the walk with whatever came before it."""
    out = []
    seen = set()
    for _ in range(cap):
        doc = _get(url)
        if doc is None:
            break
        rows = doc.get(key)
        if isinstance(rows, list):
            out.extend(r for r in rows if isinstance(r, dict))
        page = doc.get("pagination") if isinstance(doc.get("pagination"), dict) else {}
        token = str(page.get("continuation") or "")
        if not page.get("has_more_items") or not token or token in seen:
            break
        seen.add(token)
        base = url.split("&continuation=")[0]
        url = base + "&continuation=" + urllib.parse.quote(token)
    return out


def _text(node):
    """Eventbrite's multipart-text: {'text', 'html'}."""
    if isinstance(node, dict):
        return str(node.get("text") or "")
    return str(node or "")


def _num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def organizations():
    """The ids of every organization this token is a member of, or []."""
    if not configured():
        return []
    return [str(o.get("id") or "") for o in _pages(ORGS_URL + "?page_size=%d" % PAGE_SIZE,
                                                   "organizations") if o.get("id")]


def _event(row):
    """One Eventbrite event, flattened to what a match needs: its local
    date in the venue's own timezone (the date a show is booked on), the
    room's name and city from the venue expansion, and whether tickets
    are still available."""
    start = row.get("start") if isinstance(row.get("start"), dict) else {}
    local = str(start.get("local") or "")
    venue = row.get("venue") if isinstance(row.get("venue"), dict) else {}
    address = venue.get("address") if isinstance(venue.get("address"), dict) else {}
    avail = row.get("ticket_availability") if isinstance(row.get("ticket_availability"), dict) else {}
    return {
        "id": str(row.get("id") or ""),
        "name": _text(row.get("name"))[:200],
        "url": str(row.get("url") or "")[:300],
        "status": str(row.get("status") or "")[:20],
        "date": local[:10],
        "start_local": local[:19],
        "timezone": str(start.get("timezone") or "")[:60],
        "capacity": _num(row.get("capacity")),
        "venue": str(venue.get("name") or "")[:200],
        "city": str(address.get("city") or "")[:120],
        "region": str(address.get("region") or "")[:20],
        "is_sold_out": bool(avail.get("is_sold_out")),
        "has_available_tickets": bool(avail.get("has_available_tickets")),
    }


def list_events():
    """Every event on sale, started or ended across every organization
    this token can read, up to MAX_EVENTS, or [] — no token, no answer,
    a refusal. Drafts and cancellations are not asked for: nobody holds
    a ticket to them."""
    if not configured():
        return []
    out = []
    for org in organizations():
        url = EVENTS_URL % urllib.parse.quote(org) + "?" + urllib.parse.urlencode({
            "status": EVENT_STATUS, "expand": EVENT_EXPAND,
            "order_by": "start_asc", "page_size": PAGE_SIZE})
        for row in _pages(url, "events"):
            ev = _event(row)
            if ev["id"] and ev["date"]:
                out.append(ev)
            if len(out) >= MAX_EVENTS:
                return out
    return out


def ticket_counts(event_id):
    """(sold, total) across an event's ticket classes, from Eventbrite's
    own quantity_sold and quantity_total, or (None, None) when the event
    has no classes or the call failed. A class with no total (an unlimited
    donation ticket) still counts its sales but adds nothing to the
    capacity, so a partial total is never presented as the room's size."""
    if not configured() or not event_id:
        return None, None
    rows = _pages(TICKET_CLASSES_URL % urllib.parse.quote(str(event_id)) +
                  "?page_size=%d" % PAGE_SIZE, "ticket_classes")
    if not rows:
        return None, None
    sold = total = 0
    seen_sold = seen_total = False
    for r in rows:
        n = _num(r.get("quantity_sold"))
        if n is not None:
            sold += n
            seen_sold = True
        n = _num(r.get("quantity_total"))
        if n:
            total += n
            seen_total = True
    return (sold if seen_sold else None), (total if seen_total else None)


def get_event(event_id):
    """One event by id, flattened the same way, or None. Used when a show
    already carries an Eventbrite id: the stored link is honoured even
    when the event has fallen out of the organization walk."""
    if not configured() or not event_id:
        return None
    doc = _get(BASE + "/events/%s/?expand=%s" % (urllib.parse.quote(str(event_id)),
                                                 urllib.parse.quote(EVENT_EXPAND)))
    if not doc or not doc.get("id"):
        return None
    ev = _event(doc)
    return ev if ev["id"] else None
