"""The artist's own tour dates, read first-hand from TOUR.

Bandsintown declined to issue this platform an app_id (2026-09-07), so
`bandsintown_provider` stays dormant. Nothing is lost: every date the
artist plays is already held here, in TOUR, and it is the artist's own
word rather than a third party's listing. This module is the one seam
the EPK and Signal read - no HTTP, no key, no cache.

Honesty rules, in code: a hold is a hope, not a date, so it never
appears; a past date is never called upcoming; and every row names the
tour it came from so the page can say where the date is held.

"Today" is the tour's own day, not the server's: a show is upcoming
until the calendar turns in the tour's home timezone, the same clock
TOUR itself keeps (tour_engine.today_in). On a UTC server a Nashville
show would otherwise vanish from the kit at 7pm local, hours before
doors. Callers may pass `today` explicitly (tests do); then it applies
to every tour.

There is no display cap. The kit says "(N confirmed)" and lists N;
a limit that trimmed the list would make that number a lie above the
cap, so `limit` is None unless a caller asks for fewer.
"""

from datetime import date

import tour_engine as eng
import tour_store as ts

UPCOMING_STATUSES = ("confirmed", "advanced")
PLAYED_STATUSES = ("played", "settled")
DEFAULT_LIMIT = None   # every date; a cap would under-report the count

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _today(today):
    """'YYYY-MM-DD' from a date, a datetime (a date subclass whose
    isoformat carries a time - the day is still the first ten characters),
    or a string."""
    if isinstance(today, date):
        return today.isoformat()[:10]
    return str(today)[:10]


def _tour_today(tour, today):
    """The cutoff date for one tour: the caller's `today` when given, else
    today in the tour's home timezone (UTC when the tour names none)."""
    if today is not None:
        return _today(today)
    return eng.today_in(tour.get("home_tz") or "UTC")


def _norm(name):
    return " ".join((name or "").strip().lower().split())


def long_date(iso):
    """'2030-05-02' -> 'May 2, 2030'. Anything unparseable comes back as it
    was, never invented."""
    try:
        y, m, d = (iso or "")[:10].split("-")
        return "%s %d, %s" % (_MONTHS[int(m) - 1], int(d), y)
    except (ValueError, IndexError):
        return iso or ""


def _row(tour, show):
    return {
        "date": (show.get("date") or "")[:10],
        "venue": (show.get("venue") or "").strip() or "TBA",
        "city": (show.get("city") or "").strip(),
        "ticket_url": (show.get("ticket_url") or "").strip(),
        "tour_name": (tour.get("name") or "").strip(),
        "artist_name": (tour.get("artist_name") or "").strip(),
        "status": show.get("status") or "",
    }


def _rows(user_id, statuses, today, keep):
    """Every show on every tour the user owns, in the statuses named, that
    `keep(show_date, tour_today)` accepts - each tour judged by its own
    today."""
    out = []
    if not user_id:
        return out
    for tour in ts.list_tours(user_id):
        cutoff = _tour_today(tour, today)
        for show in ts.list_shows(tour["id"]):
            day = (show.get("date") or "")[:10]
            if day and (show.get("status") or "") in statuses and keep(day, cutoff):
                out.append(_row(tour, show))
    return out


def upcoming(user_id, today=None, limit=DEFAULT_LIMIT):
    """Confirmed and advanced dates from today on, soonest first. Holds
    never; past dates never. Today is the tour's own day (home_tz). All of
    them unless `limit` says fewer."""
    rows = _rows(user_id, UPCOMING_STATUSES, today, lambda day, cutoff: day >= cutoff)
    rows.sort(key=lambda r: (r["date"], r["venue"]))
    return rows[:limit]


def played(user_id, today=None, limit=DEFAULT_LIMIT):
    """The most recent played and settled dates, newest first."""
    rows = _rows(user_id, PLAYED_STATUSES, today, lambda day, cutoff: day < cutoff)
    rows.sort(key=lambda r: (r["date"], r["venue"]), reverse=True)
    return rows[:limit]


def epk_rows(user_id, today=None, limit=DEFAULT_LIMIT):
    """Upcoming dates in the EPK's row shape (the one Bandsintown's rows
    already use, so one template loop serves both sources). Uncapped like
    upcoming(), so the kit's "(N confirmed)" count is the count of dates
    it shows and the count /connections reports - sixty dates list sixty."""
    return [{"date": long_date(r["date"]), "iso": r["date"], "venue": r["venue"],
             "location": r["city"], "url": "", "tickets": r["ticket_url"],
             "tour_name": r["tour_name"]}
            for r in upcoming(user_id, today=today, limit=limit)]


def event_rows(user_id, artist_name=None, own_names=(), today=None, limit=DEFAULT_LIMIT):
    """Upcoming dates in Signal's row shape, for one artist.

    A tour names its artist; a row answers for the Signal artist whose
    name matches it, case-insensitively. A tour with no artist name is
    its owner's own, so it answers when the page is one of the owner's
    own names (their account name, their linked profile). Nothing else
    matches - another act's page never borrows these dates.
    """
    want = _norm(artist_name)
    own = {_norm(n) for n in own_names if _norm(n)}
    out = []
    for r in upcoming(user_id, today=today, limit=limit):
        tour_artist = _norm(r["artist_name"])
        if want and tour_artist and tour_artist != want:
            continue
        if want and not tour_artist and want not in own:
            continue
        out.append({"date": r["date"], "city": r["city"], "region": "", "country": "",
                    "venue": r["venue"], "url": "", "tickets": r["ticket_url"],
                    "lineup": [], "tour_name": r["tour_name"]})
    return out
