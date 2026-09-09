"""Which listing is this date, and what may each source say about it.

Two sources sell the dates on a tour, and neither of them knows about
the other. Eventbrite has what an account has actually sold. Ticketmaster
lists the rooms most clubs sell through - the link and the on-sale state,
and nothing about numbers, because their Discovery API publishes no sold
count and no capacity at all. So the join is one rule with two providers
behind it, and each source writes only what it can honestly know.

A wrong join would print another act's sales beside this act's date,
which is worse than an empty field, so the rule is the same either way:

  1. A show that already carries an `eventbrite_event_id` uses it, and a
     show that carries a `ticketmaster_event_id` uses that. An owner who
     linked a date by hand has said which listing it is, and no later run
     gets to disagree.
  2. Otherwise, only events on the same local date are considered at
     all. One date, one show.
  3. Among those, an event counts as this show when the rooms' names
     share a real word (`venue_photos.same_room`, the same test that
     keeps a salon's photo off a club's date), OR when the event's title
     carries the tour's artist name and the cities agree.
  4. Exactly one survivor is the match. Zero or several is *unmatched*,
     and the run says so by name so the owner can link the right one
     (POST .../tickets/link, which carries the source), after which rule
     1 holds it there.
  5. Eventbrite is asked first, because it can measure. Ticketmaster is
     asked only for the dates Eventbrite could not match, so a date on
     both keeps the measured count.

What a match writes, and what it never touches:

  ticket_url        the listing's own URL - but only over an empty field
                    or over a link already on that source's own host. A
                    URL the owner typed to another ticketer is theirs,
                    and Ticketmaster never overwrites an Eventbrite link.
  ticket_status     "on sale", "sold out" or "ended" from Eventbrite's
                    own status and availability; from Ticketmaster, the
                    word their listing publishes ("on sale", "off sale",
                    "cancelled", "postponed", "rescheduled").
  tickets_sold      EVENTBRITE ONLY: the sum of quantity_sold across the
                    event's ticket classes. Measured, so it replaces a
                    typed guess.
  capacity          EVENTBRITE ONLY, and only when the field is empty.
  ticket_source     "eventbrite", "ticketmaster" or "typed" - so a page
                    never presents a listing that publishes no count as a
                    count of zero.
  eventbrite_event_id / ticketmaster_event_id, tickets_synced_at
                    so the page can say which listing it read, when.

Ticketmaster is never allowed to write `tickets_sold` or `capacity`:
Discovery does not publish either, and a source that cannot measure a
number must not be allowed to erase one from a source that did.
"""

import re
import time
from urllib.parse import urlparse

import eventbrite_provider as eb
import ticketmaster_provider as tm
import tour_store as ts
import venue_photos
from db import _now

_clock = time.monotonic

# Hosts Eventbrite itself hands out: the main sites and their country
# variants, an organizer's vanity subdomain, and their short links.
_EB_HOST = re.compile(r"(^|\.)(eventbrite(\.[a-z]{2,3}){1,2}|evbt\.co)$", re.I)
# The same for Ticketmaster: the main site and its country variants.
_TM_HOST = re.compile(r"(^|\.)ticketmaster(\.[a-z]{2,3}){1,2}$", re.I)
_HOSTS = {"eventbrite": _EB_HOST, "ticketmaster": _TM_HOST}
# Words that say nothing about which town it is.
_CITY_FILLER = {"the", "a", "an", "of", "st", "ft", "mt", "usa", "us", "uk"}
# The id column each source stores its answer in.
ID_FIELD = {"eventbrite": "eventbrite_event_id", "ticketmaster": "ticketmaster_event_id"}
SOURCES = ("eventbrite", "ticketmaster")
PROVIDER = {"eventbrite": eb, "ticketmaster": tm}


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
    agreed: the same room, or this artist billed in the same city. The
    test knows nothing about which source the event came from."""
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
    """The on-sale state of an Eventbrite event, in the words the show
    page already uses."""
    if (event.get("status") or "") in ("ended", "completed", "canceled"):
        return "ended"
    if event.get("is_sold_out"):
        return "sold out"
    return "on sale"


def tm_status_for(event):
    """The on-sale state of a Ticketmaster listing, from `dates.status.
    code`. Their `offsale` is not read as 'sold out': Discovery does not
    say why a listing came off sale, and a guess there would print a
    sell-out that never happened."""
    code = (event.get("status") or "").strip().lower()
    return {"onsale": "on sale", "offsale": "off sale", "canceled": "cancelled",
            "cancelled": "cancelled", "postponed": "postponed",
            "rescheduled": "rescheduled"}.get(code, "listed")


def ours(url, source="eventbrite"):
    """Whether a ticket link is one this source may replace: an empty
    field, or a link already on that source's own host. Anything else
    the owner typed points at their ticketer and is left alone — and an
    Eventbrite link is not Ticketmaster's to overwrite, or a date on
    both would flip its link every sync."""
    url = (url or "").strip()
    if not url:
        return True
    try:
        host = (urlparse(url).netloc or "").split(":")[0].lower()
    except ValueError:
        return False
    return bool(_HOSTS.get(source, _EB_HOST).search(host))


def fields_for(show, event, sold, total):
    """What a matched Eventbrite event writes onto the show, and nothing
    else."""
    fields = {"eventbrite_event_id": event["id"], "tickets_synced_at": _now(),
              "ticket_source": "eventbrite", "ticket_status": status_for(event)}
    if event.get("url") and ours(show.get("ticket_url")):
        fields["ticket_url"] = event["url"]
    if sold is not None:
        fields["tickets_sold"] = str(sold)
    if total and not str(show.get("capacity") or "").strip():
        fields["capacity"] = str(total)
    return fields


def tm_fields_for(show, event):
    """What a matched Ticketmaster listing writes onto the show: the
    link and the on-sale word, and never a number. Discovery publishes
    no sold count and no capacity, so neither field is touched — one
    that Eventbrite measured earlier stays exactly as it was."""
    fields = {"ticketmaster_event_id": event["id"], "tickets_synced_at": _now(),
              "ticket_source": "ticketmaster", "ticket_status": tm_status_for(event)}
    if event.get("url") and ours(show.get("ticket_url"), "ticketmaster"):
        fields["ticket_url"] = event["url"]
    return fields


def unmatched_row(show, day):
    return {"show_id": show["id"], "date": show.get("date") or "",
            "venue": show.get("venue") or "", "city": show.get("city") or "",
            "candidates": [{"id": e["id"], "name": e.get("name") or "",
                            "venue": e.get("venue") or "",
                            "source": e.get("source") or "eventbrite"} for e in day[:6]]}


def _window(shows):
    """(first date, last date) across the shows, for the one Ticketmaster
    search this run makes."""
    days = sorted(d for d in ((s.get("date") or "").strip() for s in shows) if d)
    return (days[0], days[-1]) if days else ("", "")


def _stored(show):
    """(source, id) for a listing the owner has already named, or
    (None, ''). Eventbrite first: it is the source that can measure. A
    source whose key is not on this deployment is passed over, so an id
    stored last year does not silence the source that is connected."""
    for source in SOURCES:
        eid = str(show.get(ID_FIELD[source]) or "").strip()
        if eid and PROVIDER[source].configured():
            return source, eid
    return None, ""


def sync(tour, shows, events=None, tm_events=None, deadline=None):
    """Fill the ticket fields on every show a source can match. Returns
    the report the page prints: how many each source matched, the dates
    with no single match (with the candidate names beside them), how many
    the request's time budget did not reach, and each provider's own
    words when it refused the key.

    Eventbrite is asked for every date first; Ticketmaster is asked only
    about the dates left over, and only for the link and the on-sale
    state. Nothing here raises: a provider that answers nothing leaves
    every field exactly as it was."""
    report = {"synced": 0, "unmatched": [], "unreached": 0, "refused": "",
              "refused_status": "", "configured": eb.configured() or tm.configured(),
              "eventbrite": 0, "ticketmaster": 0,
              "eb_ready": eb.configured(), "tm_ready": tm.configured(),
              "tm_refused": "", "tm_refused_status": ""}
    if not report["configured"]:
        return report
    eb.clear_refusal()
    tm.clear_refusal()
    if events is None:
        try:
            events = eb.list_events() if eb.configured() else []
        except Exception:
            events = []
    by_id = {e["id"]: e for e in events if e.get("id")}
    artist = tour.get("artist_name") or ""
    # Ticketmaster is searched at most once a run, and only when a date
    # actually needs it: a tour Eventbrite matched in full makes no
    # outbound call to a second source at all.
    tm_cache = {"rows": tm_events}

    def ticketmaster_events():
        if tm_cache["rows"] is None:
            if not tm.configured():
                tm_cache["rows"] = []
            else:
                start, end = _window(shows)
                try:
                    tm_cache["rows"] = tm.find_events(artist, start, end)
                except Exception:
                    tm_cache["rows"] = []
        return tm_cache["rows"]

    for show in shows:
        if not (show.get("date") or ""):
            continue
        source, stored = _stored(show)
        day = []
        if stored:
            event = _by_stored_id(source, stored, by_id, tm_cache)
        else:
            event, day = match(show, artist, events) if eb.configured() else (None, [])
            source = "eventbrite" if event is not None else None
            if event is None and tm.configured():
                tm_event, tm_day = match(show, artist, ticketmaster_events())
                day = day + tm_day
                if tm_event is not None:
                    event, source = tm_event, "ticketmaster"
        if event is None:
            report["unmatched"].append(unmatched_row(show, day))
            continue
        if deadline is not None and _clock() > deadline:
            report["unreached"] += 1
            continue
        try:
            if source == "ticketmaster":
                ts.update_show_ext(tour["id"], show["id"], tm_fields_for(show, event))
            else:
                sold, total = eb.ticket_counts(event["id"])
                ts.update_show_ext(tour["id"], show["id"], fields_for(show, event, sold, total))
        except Exception:
            continue
        report["synced"] += 1
        report[source] += 1
    refusal = eb.last_refusal() or {}
    report["refused"] = refusal.get("message") or ""
    report["refused_status"] = refusal.get("status") or ""
    refusal = tm.last_refusal() or {}
    report["tm_refused"] = refusal.get("message") or ""
    report["tm_refused_status"] = refusal.get("status") or ""
    return report


def _by_stored_id(source, stored, by_id, tm_cache):
    """The listing a show already names, from the walk this run already
    made when it is in there, and by id when it is not. A provider that
    is not configured answers nothing, and the date is left unmatched
    rather than half-written."""
    provider = PROVIDER.get(source)
    if provider is None or not provider.configured():
        return None
    if source == "eventbrite":
        return by_id.get(stored) or eb.get_event(stored)
    rows = tm_cache.get("rows") or []
    return next((e for e in rows if e.get("id") == stored), None) or tm.get_event(stored)


def report_line(report):
    """The one sentence a run leaves behind, in the page's own words. A
    deployment with both sources hears which one matched what, because
    only one of them can say how many tickets went."""
    if not report or not report.get("configured"):
        return ("No ticket source on this deployment "
                "(EVENTBRITE_TOKEN, TICKETMASTER_API_KEY)")
    unmatched = len(report.get("unmatched") or [])
    if report.get("tm_ready"):
        line = "Eventbrite matched %d; Ticketmaster matched %d; %d dates had no match" % (
            report.get("eventbrite", 0), report.get("ticketmaster", 0), unmatched)
    else:
        line = "Tickets synced for %d shows; %d had no match" % (
            report.get("synced", 0), unmatched)
    if report.get("unreached"):
        line += "; %d not reached in time" % report["unreached"]
    if report.get("refused"):
        line += "; refused: %s" % report["refused"]
    if report.get("tm_refused"):
        line += "; Ticketmaster refused: %s" % report["tm_refused"]
    return line
