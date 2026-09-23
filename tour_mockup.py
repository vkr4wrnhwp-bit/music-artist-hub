"""The Mock Up Tour: a full routing every new Tour account opens with.

Owner, 2026-09-17: rather than one shared demo account, every account that
arrives at Tour with no tours of its own gets its own copy of this run. It
is a real van routing (44 days, 36 shows, off days, a festival, holds and
confirmations, flat fees and a percentage deal, six merch splits), imported
through the same parser and the same store calls as the Import page, so the
demo exercises exactly what a pasted deal sheet does.

The owner's words: "just name it mock up tour". No artist is named, and
on 2026-09-17 the rooms were invented too: the sheet began as a real
routing, and real venues on real dates can be read as somebody's actual
tour even with the act unnamed. The cities are real because a routing
has to teach how far apart the nights are. It runs in April 2027 so it
does not quietly become a tour of the past.
"""

import tour_engine as eng
import tour_store as ts
import db as store

NAME = "Mock Up Tour"


def enabled():
    """Built on a deployed service, and wherever MOCK_UP_TOUR=on.

    Off on a laptop and in the tests unless one asks for it. Three thousand
    tests make fresh accounts, and a demonstration tour appearing inside
    every one of them turns "this account has nothing yet" into a thing
    that is never true, which is a trap rather than a feature.
    """
    import os
    mode = (os.environ.get("MOCK_UP_TOUR") or "").strip().lower()
    if mode in ("on", "off"):
        return mode == "on"
    return bool(os.environ.get("RENDER"))

# Tab-separated, as the deal sheet arrived. START/END rows carry no city and
# are dropped by the parser; OFF rows become off days.
SHEET = "\n".join("\t".join(row) for row in [
    ("DAY", "DATE", "CITY", "VENUE", "CAPACITY", "STATUS", "GUARANTEE", "MERCH RATE"),
    ("Monday", "April 5, 2027", "OFF", "", "", "", "", ""),
    ("Tuesday", "April 6, 2027", "St. Paul, MN", "The Paper Mill", "350", "3H Challenged", "TBC", "100%, Artist Sells"),
    ("Wednesday", "April 7, 2027", "Iowa City, IA", "Cicada Hall", "400", "2H Challenged", "TBC", ""),
    ("Thursday", "April 8, 2027", "Milwaukee, WI", "Ninth Ward Social", "275", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Friday", "April 9, 2027", "Indianapolis, IN", "The Gilded Ox", "400", "CONFIRMED", "$350", "100%, Artist Sells"),
    ("Saturday", "April 10, 2027", "Chicago, IL", "Longwave", "700", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Sunday", "April 11, 2027", "Louisville, KY", "The Foundry Room", "350", "3H Challenged", "$350", "100%, Artist Sells"),
    ("Monday", "April 12, 2027", "Cleveland, OH", "Harbor & Vine", "250", "1H", "$500", "100%, Artist Sells"),
    ("Tuesday", "April 13, 2027", "OFF", "", "", "", "", ""),
    ("Wednesday", "April 14, 2027", "Columbus, OH", "Static Hall", "500", "CONFIRMED", "15% NBOR capped at $500", "100%, Artist Sells"),
    ("Thursday", "April 15, 2027", "Ferndale, MI", "The Marigold", "450", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Friday", "April 16, 2027", "OFF", "", "", "", "", ""),
    ("Saturday", "April 17, 2027", "Rochester, NY", "Wire & Wheel", "430", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Sunday", "April 18, 2027", "Pittsburgh, PA", "Cold Spring Club", "350", "CONFIRMED", "$500", "90/10, 100% CD/DVD, Artist Sells"),
    ("Monday", "April 19, 2027", "OFF", "", "", "", "", ""),
    ("Tuesday", "April 20, 2027", "Philadelphia, PA", "The Velvet Anchor", "650", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Wednesday", "April 21, 2027", "Providence, RI", "Pressroom East", "280", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Thursday", "April 22, 2027", "Hamden, CT", "The Tin Lantern", "300", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Friday", "April 23, 2027", "Brooklyn, NY", "Rosewater Room (1 of 2)", "280", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Saturday", "April 24, 2027", "Brooklyn, NY", "Rosewater Room (2 of 2)", "280", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Sunday", "April 25, 2027", "Washington, DC", "The Ember Works", "300", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Monday", "April 26, 2027", "OFF", "", "", "", "", ""),
    ("Tuesday", "April 27, 2027", "Atlanta, GA", "Halcyon Social", "625", "CONFIRMED", "$300", "85/15, 100% CD/DVD, Artist Sells"),
    ("Wednesday", "April 28, 2027", "Baton Rouge, LA", "Northgate Rooms", "602", "CONFIRMED", "$300", "100%, Artist Sells"),
    ("Thursday", "April 29, 2027", "Houston, TX", "The Brass Kettle", "750", "CONFIRMED", "$350", "80/20, Artist Sells"),
    ("Friday", "April 30, 2027", "Austin, TX", "Sable Room", "500", "CONFIRMED", "$350", "TBC"),
    ("Saturday", "May 1, 2027", "San Antonio, TX", "Lowland Hall", "750", "CONFIRMED", "$350", "80/20, Artist Sells"),
    ("Sunday", "May 2, 2027", "Dallas, TX", "The Copper Fox", "700", "CONFIRMED", "$350", "90/10, 100% CD/DVD, Artist Sells"),
    ("Monday", "May 3, 2027", "OFF", "", "", "", "", ""),
    ("Tuesday", "May 4, 2027", "El Paso, TX", "Dust & Dial", "700", "CONFIRMED", "$350", "TBC"),
    ("Wednesday", "May 5, 2027", "Tucson, AZ", "The Amber Vault", "550", "CONFIRMED", "$350", "90/10, 100% CD/DVD, Artist Sells"),
    ("Thursday", "May 6, 2027", "Las Vegas, NV", "Sixth Street Annex", "250", "CONFIRMED", "$350", "100%, Artist Sells"),
    ("Friday", "May 7, 2027", "San Diego, CA", "The Lantern Yard", "705", "CONFIRMED", "$350", "100%, Artist Sells"),
    ("Saturday", "May 8, 2027", "Huntington Beach, CA", "Wildline Festival 2027 (festival, no support)", "", "CONFIRMED", "", "Festival"),
    ("Sunday", "May 9, 2027", "Fresno, CA", "Bluewater Club", "400", "CONFIRMED", "$500", "90/10, Artist Sells"),
    ("Monday", "May 10, 2027", "San Francisco, CA", "The Hollow", "700", "CONFIRMED", "$500", "80/20, 100% CD/DVD, Artist Sells"),
    ("Tuesday", "May 11, 2027", "Sacramento, CA", "Saltfield Hall", "475", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Wednesday", "May 12, 2027", "OFF", "", "", "", "", ""),
    ("Thursday", "May 13, 2027", "Tacoma, WA", "The Ivory Gate", "500", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Friday", "May 14, 2027", "Portland, OR", "Union Line", "500", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Saturday", "May 15, 2027", "Boise, ID", "The Standing Stone", "700", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Sunday", "May 16, 2027", "Salt Lake City, UT", "Pinewood Social", "400", "CONFIRMED", "$500", "90/10, 100% CD/DVD, Artist Sells. Reverts to 100% at 400 paid attendance (sellout)."),
    ("Monday", "May 17, 2027", "OFF", "", "", "", "", ""),
    ("Tuesday", "May 18, 2027", "Denver, CO", "The Drift", "478", "CONFIRMED", "$500", "100%, Artist Sells"),
    ("Wednesday", "May 19, 2027", "OFF", "", "", "", "", ""),
])


def ensure_for(user):
    """Give an account with no tours its own Mock Up Tour. Returns the tour id
    when one was created, else None. Never touches an account that already has
    a tour, so a real routing is never mixed with the demo."""
    if not user or not enabled() or ts.list_tours(user["id"]):
        return None
    # Imported lazily: tour_os imports the Flask app's pieces at module load.
    from tour_os import _import_ext, _import_status

    rows, _problems = eng.parse_csv_rows(SHEET)
    tour_id = ts.create_tour(user["id"], {
        "name": NAME, "status": "planning",
        "start_date": "2027-04-05", "end_date": "2027-05-19",
        "home_tz": "America/Chicago", "currency": "USD",
        "notes": "A demonstration routing. Every venue on it is invented and every date is an example to click through, not a booking of yours."})
    for r in rows:
        if r["kind"] == "show":
            sid = store.add_tour_show(user["id"], r["date"], r["venue"] or "TBA", r["city"], r["notes"])
            ts.attach_show(tour_id, sid, r["tz"] if eng.valid_tz(r["tz"]) else "")
            ext = _import_ext(r)
            if ext:
                ts.update_show_ext(tour_id, sid, ext)
            status = _import_status(r.get("status"))
            if status:
                store.update_tour_show_status(user["id"], sid, status)
        else:
            ts.add_day(tour_id, user["id"], r["date"], r["kind"], r["venue"] or r["kind"].title(),
                       r["city"], r["tz"] if eng.valid_tz(r["tz"]) else "", None, r["notes"])
    ts.record_import(tour_id, user["id"], "csv", IMPORT_FILENAME, SHEET,
                     {"created": {"rows": len(rows)}, "problems": [], "rows": len(rows)})
    return tour_id


IMPORT_FILENAME = "mock-up-tour.tsv"


def sheet_show_keys():
    """(date, venue) for every show the sheet invents."""
    rows, _problems = eng.parse_csv_rows(SHEET)
    return {(r["date"], r["venue"] or "TBA") for r in rows if r["kind"] == "show"}


def is_mock(tour_id):
    """Was this tour built by ensure_for? Read from its import record, so a
    renamed Mock Up Tour is still recognised."""
    with store.get_db() as db:
        row = db.execute("SELECT 1 FROM tour_imports WHERE tour_id = ? AND filename = ?",
                         (tour_id, IMPORT_FILENAME)).fetchone()
    return row is not None


def mock_tour_ids(user_id):
    """The ids of every Mock Up Tour this account owns, recognised the way
    is_mock() recognises one (its import record), in one query."""
    if not user_id:
        return set()
    with store.get_db() as db:
        rows = db.execute("SELECT DISTINCT i.tour_id FROM tour_imports i "
                          "JOIN tours t ON t.id = i.tour_id "
                          "WHERE t.user_id = ? AND i.filename = ?",
                          (user_id, IMPORT_FILENAME)).fetchall()
    return {r["tour_id"] for r in rows}


def real_shows(user_id, shows):
    """`shows` (tour_shows rows, or anything carrying their tour_id) less
    every show on this account's Mock Up Tour.

    The one filter every reader outside Tour passes through: the press
    kit's dates, the Artist Hub, the Team-Up Board's chips, /connections,
    a label's roster, the Fans screen. The Mock Up Tour is a sample; its
    CONFIRMED rows are invented, and a sample never reaches a public page
    (owner's standing rule). The whole tour is excluded, not just the
    sheet's own rows, so an invented show the member renamed while
    clicking through cannot slip out either; the tour's own pages say
    that nothing on it is shown publicly."""
    mock = mock_tour_ids(user_id)
    if not mock:
        return list(shows)
    return [s for s in shows if (s.get("tour_id") or "") not in mock]


def discard_invented_shows(tour_id):
    """Delete the shows this tour's sheet invented, before the tour goes.

    Deleting a tour sets its shows loose (tour_id = NULL) so a real show is
    never lost with its tour, and the next visit to Tour adopts loose shows
    into the account's other tour. For the Mock Up Tour that poured all 36
    invented rooms into the artist's real routing (found by the 2026-09-18
    launch check). Only the sheet's own (date, venue) pairs go: a show the
    artist added to the Mock Up Tour themselves is theirs, and stays loose
    to be adopted like any other. Returns how many were deleted."""
    if not is_mock(tour_id):
        return 0
    keys = sheet_show_keys()
    with store.get_db() as db:
        rows = db.execute("SELECT id, date, venue FROM tour_shows WHERE tour_id = ?",
                          (tour_id,)).fetchall()
        doomed = [r["id"] for r in rows if (r["date"], r["venue"]) in keys]
        for sid in doomed:
            db.execute("DELETE FROM tour_shows WHERE id = ?", (sid,))
    return len(doomed)
