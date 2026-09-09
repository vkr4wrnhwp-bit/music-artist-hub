"""Which Eventbrite event is this date, and what has it sold.

The token reads a whole account's events; a tour is a handful of dates.
Nothing about either says which is which, so the join has to be earned
rather than assumed — a wrong join would print another act's sales
beside this act's date, which is worse than an empty field.

The rule, in order:

  1. A show that already carries an `eventbrite_event_id` uses it. An
     owner who linked a date by hand has said which event it is, and no
     later run gets to disagree.
  2. Otherwise, only events on the same local date are considered at
     all. One date, one show.
  3. Among those, an event counts as this show when the rooms' names
     share a real word (`venue_photos.same_room`, the same test that
     keeps a salon's photo off a club's date), OR when the event's title
     carries the tour's artist name and the cities agree.
  4. Exactly one survivor is the match. Zero or several is *unmatched*,
     and the run says so by name so the owner can link the right one
     (POST .../tickets/link), after which rule 1 holds it there.

What a match writes, and what it never touches:

  ticket_url        Eventbrite's own event URL — but only over an empty
                    field or over a link already on an Eventbrite host.
                    A URL the owner typed to another ticketer is theirs.
  tickets_sold      the sum of quantity_sold across the event's ticket
                    classes: measured, so it replaces a typed guess.
  capacity          the sum of quantity_total, only when the field is
                    empty. Capacity is the room, and the owner may know
                    it better than one event's allocation does.
  ticket_status     "on sale", "sold out" or "ended", from the event's
                    own status and its ticket_availability.
  eventbrite_event_id, tickets_synced_at
                    so the page can say the count is measured, when, and
                    which event it came from.
"""

import re
import time
from urllib.parse import urlparse

import eventbrite_provider as eb
import tour_store as ts
import venue_photos
from db import _now

_clock = time.monotonic

# Hosts Eventbrite itself hands out: the main sites and their country
# variants, an organizer's vanity subdomain, and their short links.
_EB_HOST = re.compile(r"(^|\.)(eventbrite(\.[a-z]{2,3}){1,2}|evbt\.co)$", re.I)
# Words that say nothing about which town it is.
_CITY_FILLER = {"the", "a", "an", "of", "st", "ft", "mt", "usa", "us", "uk"}


def _tokens(text):
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) > 1}


def same_city(a, b):
    """Whether two city strings name the same town. A tour writes
    'Nashville, TN' where Eventbrite answers city 'Nashville' and region
    'TN', so a shared real word is the test — a state code alone is not
    enough, or every date in Texas would match every other."""
    return bool((_tokens(a) & _tokens(b)) - _CITY_FILLER)


def names_artist(event_name, artist):
    """Whether the event's title carries the tour's artist name. Every
    word of the name has to be in the title, so 'Ada' does not match
    'Adam Smith Quartet'."""
    want = _tokens(artist)
    return bool(want) and want <= _tokens(event_name)


def plausible(show, artist, event):
    """Whether this event could be this show, the dates having already
    agreed: the same room, or this artist billed in the same city."""
    if venue_photos.same_room(show.get("venue") or "", event.get("venue") or ""):
        return True
    city = " ".join(p for p in ((event.get("city") or ""), (event.get("region") or "")) if p)
    return names_artist(event.get("name") or "", artist) and same_city(show.get("city") or "", city)


def match(show, artist, events):
    """(event, candidates) for one show. `event` is the single plausible
    event on the show's date, or None; `candidates` is every event on
    that date, so an unmatched show can be listed by name."""
    day = [e for e in events if e.get("date") and e["date"] == (show.get("date") or "")]
    fits = [e for e in day if plausible(show, artist, e)]
    return (fits[0] if len(fits) == 1 else None), day


def status_for(event):
    """The on-sale state, in the words the show page already uses."""
    if (event.get("status") or "") in ("ended", "completed", "canceled"):
        return "ended"
    if event.get("is_sold_out"):
        return "sold out"
    return "on sale"


def ours(url):
    """Whether a ticket link is one this sync may replace: an empty
    field, or a link already on an Eventbrite host. Anything else the
    owner typed points at their ticketer and is left alone."""
    url = (url or "").strip()
    if not url:
        return True
    try:
        host = (urlparse(url).netloc or "").split(":")[0].lower()
    except ValueError:
        return False
    return bool(_EB_HOST.search(host))


def fields_for(show, event, sold, total):
    """What a matched event writes onto the show, and nothing else."""
    fields = {"eventbrite_event_id": event["id"], "tickets_synced_at": _now(),
              "ticket_status": status_for(event)}
    if event.get("url") and ours(show.get("ticket_url")):
        fields["ticket_url"] = event["url"]
    if sold is not None:
        fields["tickets_sold"] = str(sold)
    if total and not str(show.get("capacity") or "").strip():
        fields["capacity"] = str(total)
    return fields


def unmatched_row(show, day):
    return {"show_id": show["id"], "date": show.get("date") or "",
            "venue": show.get("venue") or "", "city": show.get("city") or "",
            "candidates": [{"id": e["id"], "name": e.get("name") or "",
                            "venue": e.get("venue") or ""} for e in day[:6]]}


def sync(tour, shows, events=None, deadline=None):
    """Fill the ticket fields on every show that matches an Eventbrite
    event. Returns the report the page prints: how many were synced, the
    ones with no single match (with the candidate names beside them),
    how many the request's time budget did not reach, and Eventbrite's
    own words when it refused the token.

    Nothing here raises: a provider that answers nothing leaves every
    field exactly as it was."""
    report = {"synced": 0, "unmatched": [], "unreached": 0, "refused": "",
              "refused_status": "", "configured": eb.configured()}
    if not report["configured"]:
        return report
    eb.clear_refusal()
    if events is None:
        try:
            events = eb.list_events()
        except Exception:
            events = []
    by_id = {e["id"]: e for e in events if e.get("id")}
    artist = tour.get("artist_name") or ""
    for show in shows:
        if not (show.get("date") or ""):
            continue
        stored = str(show.get("eventbrite_event_id") or "").strip()
        if stored:
            event, day = (by_id.get(stored) or eb.get_event(stored)), []
        else:
            event, day = match(show, artist, events)
        if event is None:
            report["unmatched"].append(unmatched_row(show, day))
            continue
        if deadline is not None and _clock() > deadline:
            report["unreached"] += 1
            continue
        try:
            sold, total = eb.ticket_counts(event["id"])
            ts.update_show_ext(tour["id"], show["id"], fields_for(show, event, sold, total))
        except Exception:
            continue
        report["synced"] += 1
    refusal = eb.last_refusal() or {}
    report["refused"] = refusal.get("message") or ""
    report["refused_status"] = refusal.get("status") or ""
    return report


def report_line(report):
    """The one sentence a run leaves behind, in the page's own words."""
    if not report or not report.get("configured"):
        return "No Eventbrite token on this deployment (EVENTBRITE_TOKEN)"
    line = "Tickets synced for %d shows; %d had no match" % (
        report.get("synced", 0), len(report.get("unmatched") or []))
    if report.get("unreached"):
        line += "; %d not reached in time" % report["unreached"]
    if report.get("refused"):
        line += "; refused: %s" % report["refused"]
    return line
