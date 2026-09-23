"""The Analytics room, as one screen.

The owner's mockup, 2026-09-22. This room's own line is "What is measured,
by whom, and how it moved", and that is the whole brief: it is the room
that refuses to guess. Every reading on it names the provider that took it
and the day it was read, and anything nobody measured says so in words.

WHY THE ROOM IS SHAPED THIS WAY
-------------------------------
Six cards went in and three tiles came out, after reading what each one
actually holds:

  pulse        opens the room. It is the only feature here carrying
               measured figures WITH provenance, and its honesty machinery
               is real rather than decorative.
  insights     becomes the right-hand panel. It is the only feature in the
               room with no demo branch and no hardcoded figure anywhere.
  scores       a tile. Real, but a new account sees it empty.
  trust-score  folded into that tile: rooms.py already gives both the same
               parent, and they are two tabs of one page - three tiles
               would be three doors to one thing.
  artist-twin  a tile. It is a workspace (a consent matrix, a tone picker,
               five Generate buttons), not figures, and ten of its eleven
               panels read "awaiting" on a new account.
  reports      a tile. It is a drawer of exports and computes no figure of
               its own about the account.

WHAT IT REFUSES TO DO
---------------------
  * A figure nobody measured reads "Not measured", in words, and names the
    provider that would supply it. Never 0: a zero is a measurement.
  * Every reading carries its source and its date. No figure floats free.
  * Nothing here predicts, forecasts, or claims a cause.
  * Nothing on this screen is read live from a provider. A room door is
    opened constantly; it shows what is ON FILE and says how old that is.
    The Pulse page itself is where a fresh reading is taken.
"""
import urllib.parse
from datetime import date, timedelta

# The path from nothing measured to something read. Each rung is a stored
# fact, not a stage somebody ticks.
STEPS = (
    ("pinned", "Pinned", "Your artist is identified"),
    ("measuring", "Measuring", "Readings are being stored"),
    ("trending", "Trending", "Two days, so movement can be drawn"),
    ("compared", "Compared", "Peers to measure against"),
    ("read", "Read", "Observations from your own numbers"),
)

# How old a stored reading may be before the room calls it stale rather
# than fresh. The Pulse page uses the same one-day rule.
FRESH_DAYS = 1


def _n(value):
    return "{:,}".format(int(value))


def days_measured(snaps):
    """How many DISTINCT days have a reading on file.

    Distinct days, not rows: two snapshots taken on one afternoon are one
    day of history and cannot draw a line between them.
    """
    return len({(s.get("day") or "")[:10] for s in (snaps or ()) if s.get("day")})


def latest(snaps, key):
    """The most recent non-null reading of one measure, and its day.

    A null is skipped rather than read as 0. The snapshot columns were made
    nullable precisely because a 0 from a provider that had stopped
    counting is not a measurement.
    """
    for s in reversed(list(snaps or ())):
        value = s.get(key)
        if value is not None:
            return value, (s.get("day") or "")[:10]
    return None, ""


def reading(label, value, provider, as_of, today, why=""):
    """One row of the instrument panel.

    `value` None means nobody measured it, and then `why` says which
    provider would - an absence with a reason, rather than a blank.
    """
    state, lamp = "none", "not measured"
    if value is not None:
        old = None
        try:
            old = (today - date.fromisoformat(as_of)).days if as_of else None
        except ValueError:
            old = None
        if old is not None and old > FRESH_DAYS:
            state, lamp = "stale", "%d days old" % old
        else:
            state, lamp = "fresh", "fresh"
    return {
        "label": label,
        "shown": _n(value) if value is not None else "",
        "provider": provider,
        "as_of": as_of or "",
        "read": (as_of or "") if value is not None else (why or "not available"),
        "state": state,
        "lamp": lamp,
        "why": why,
    }


# --- THE RACK (owner, 2026-09-23) ---------------------------------------
# Every room's working page draws the rooms' shared three-window plate
# (templates/partials/cc_rack.html, static/img/room-plate.webp). The three
# readings sit on its three screens in this order; the trend line, which
# had the old analyser's long upper screen, is its own panel directly
# under the plate, so nothing is lost. The shared plate prints no names,
# so each screen carries its own label.
RACK_ORDER = ("visits", "followers", "listeners")


# --- THE PAGE FROM ZERO (owner's Analytics spec + mockup, 2026-09-23) -----
# An account with nothing connected, nothing synced, no link events and
# no peers does not meet an empty analyser. It meets an onboarding page:
# the Command Center's photographed three-screen plate drawn STATIC with
# this room's words, one card that opens Connections, the four lenses as
# doors to the rooms that own the next step, the five-step workflow as
# education, the two empties in words, help, and the tools in a drawer
# that starts open. No chart, no date filter, no comparison, no nought.
# The animated standby that used to run on the analyser is retired here,
# and since the working page moved onto the shared plate (2026-09-23) an
# unmeasured screen says so in words rather than rolling a reel.
ZERO_SUBTITLE = "Turn connected data into clear next moves."
ZERO_RACK = (
    ("Purpose", "Understand what changed and what to do next."),
    ("Start here", "Connect one trusted data source."),
    ("Good to know", "Unavailable data is never shown as zero."),
)
# The one door: Connections, carrying the way back. The way back carries
# ?from=connect so the room can say what happened - once a source is
# really on file, never from the param alone.
CONNECT_DOOR = "/connections?returnTo=" + urllib.parse.quote("/room/analytics?from=connect", safe="")
ZERO_PROJECT = {
    "heading": "Start with a trusted source",
    "title": "Connect your first data source",
    "desc": ("Choose a service or import a supported source so Street Banker "
             "can measure real activity."),
    "cta": "View connections",
    "note": "You will see what each source can provide before connecting it.",
    # A seat that may not write here is told who connects sources rather
    # than handed a door that bounces.
    "locked": ("Sources are connected by the account owner or a seat with edit "
               "access. Analytics opens here once one is connected."),
}
# The four lenses (spec: "explain what Analytics organizes"). Each is a
# door to the room that owns the next step; Analytics interprets and
# routes, it does not duplicate those rooms' tools.
LENSES = (
    ("audience", "Audience signals",
     "Fan capture, audience activity, smart-link activity, and campaign response.",
     "/room/fans", "Fans and Marketing"),
    ("release", "Release performance",
     "Releases, promotion periods, links, and connected performance signals.",
     "/room/releases", "Releases, Marketing and Studio"),
    ("live", "Live results",
     "Shows, tours, attendance, ticketing, and fan capture.",
     "/room/stage", "Stage and Fans"),
    ("revenue", "Revenue insights",
     "Connected revenue, statements, and recovery opportunities.",
     "/room/business", "Business and Publishing"),
)
# The five steps, EDUCATIONAL on a new account: Connect lit, the rest
# neutral, no percentage - "the workflow is not a profile-completion
# exercise". STEPS (Pinned .. Read) stays the populated room's rail.
WORKFLOW = (
    ("connect", "Connect", "Add a trusted source"),
    ("coverage", "Confirm coverage", "See what information is available"),
    ("lens", "Choose a lens", "Focus on what matters"),
    ("change", "Understand change", "Find what stands out"),
    ("action", "Create action", "Turn the insight into a next step"),
)
ZERO_INSIGHTS = ("Your insights will appear here",
                 "After a source finishes syncing, Street Banker will show what is "
                 "measured, what is missing, and what changed.")
ZERO_LANGUAGE = ("Nothing is measured yet",
                 "Analytics will use Not measured or Unavailable until real source "
                 "data exists. It will not turn missing data into zero.")
ZERO_HELP = ("Not sure what to connect first?",
             "Ask Street Banker which source best matches what you want to understand.")
# The two links under "Your insights will appear here": coverage is
# explained by the language panel on this page; the supported sources
# are the Connections page itself.
ZERO_LINKS = (("How data coverage works", "#an-z-lang-h"),
              ("Supported sources", CONNECT_DOOR))
# The drawer at the foot: the room's own tools, by their cards.
ZERO_TILES = ("pulse", "scores", "artist-twin", "reports")
# The sentence the room carries back from Connections.
DONE_LINE = ("Your first source is connected. Analytics will show what it "
             "measures once the first sync has finished.")


def new_account(profile, snaps, visits, peers):
    """The spec's brand-new account: confirmed empty on every count the
    room reads - no source connected (no pinned artist), no completed
    sync (no snapshot), no measurable internal event (no link visit),
    nobody to compare with. Every argument is what the store returned;
    an unreadable store never reaches here - the route shows the error
    page instead. Observations are not a count: insights_engine writes
    a general tip for an empty account, and a tip is not a measurement."""
    return not profile and not snaps and visits is None and not peers


def done_line(came_from, connected):
    """Said by the SAVED source, never by the param alone."""
    return DONE_LINE if came_from == "connect" and connected else ""


def zero_page(can_add=True, can_open=None):
    """The page from zero. A seat sees only the doors it can open; a lens
    whose room a seat cannot open is words, not a door."""
    def may(href):
        return can_open is None or bool(can_open(href))
    lenses = [{"key": k, "name": n, "line": l, "href": h if may(h) else "", "rooms": r}
              for k, n, l, h, r in LENSES]
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "door": CONNECT_DOOR,
        "project": dict(ZERO_PROJECT, can=can_add),
        "lenses": lenses,
        "workflow": WORKFLOW,
        "insights": ZERO_INSIGHTS,
        "language": ZERO_LANGUAGE,
        "help": ZERO_HELP,
        "links": ZERO_LINKS,
    }


def rack_screens(rows):
    """figures() on the rooms' shared plate: link visits, followers,
    monthly listeners, one per screen, each NAMED (the plate prints no
    names). A reading is set as a figure; an absence stays the words "Not
    measured", never a nought. The line under it is what the old window
    printed there: where the reading came from, or - when nobody measured
    it - what would fill it. No change arrow: the room keeps no prior
    period for these three, and it does not invent one."""
    by = {r["key"]: r for r in rows or ()}
    out = []
    for key in RACK_ORDER:
        r = by.get(key)
        if not r:
            continue
        out.append({"k": r["label"], "v": r["value"], "fig": r["measured"],
                    "none": not r["measured"], "sub": r["why"] or r["source"]})
    return out


def figures(visits, followers, listeners, sources=None):
    """The three across the top. Each may be unmeasured, and says why.

    `sources` names who took a reading when it is not the default - a
    metrics provider's followers or listeners say "From <its name>"."""
    sources = sources or {}
    out = []
    for key, label, source, value, why in (
        ("visits", "Link visits", "From your smart links", visits,
         "No smart links tracked yet"),
        ("followers", "Followers", "From the connected provider", followers,
         "Spotify stopped returning this"),
        ("listeners", "Monthly listeners", "From the connected provider", listeners,
         "Needs a metrics provider"),
    ):
        source = sources.get(key) or source
        out.append({"key": key, "label": label, "source": source,
                    "value": _n(value) if value is not None else "Not measured",
                    "measured": value is not None,
                    "why": "" if value is not None else why})
    return out


def path(pinned, snaps, peers, observations):
    """The five circles, each carrying what it actually counted."""
    days = days_measured(snaps)
    rows = len(snaps or ())
    state = {
        "pinned": (bool(pinned), "Artist pinned" if pinned else "Not pinned yet"),
        "measuring": (rows > 0,
                      ("%s reading%s stored" % (_n(rows), "" if rows == 1 else "s"))
                      if rows else "Nothing stored yet"),
        "trending": (days > 1,
                     "%s days of history" % _n(days) if days > 1 else "Needs a second day"),
        "compared": (peers > 0,
                     ("%s peer%s" % (_n(peers), "" if peers == 1 else "s"))
                     if peers else "No peers yet"),
        "read": (observations > 0,
                 ("%s observation%s" % (_n(observations), "" if observations == 1 else "s"))
                 if observations else "Nothing to read yet"),
    }
    out = []
    for i, (key, name, sub) in enumerate(STEPS, start=1):
        reached, line = state[key]
        out.append({"key": key, "n": i, "name": name, "sub": sub,
                    "line": line, "reached": bool(reached)})
    return out


def chart(snaps, key, label, provider):
    """The line over time, or the reason it cannot be drawn.

    Two readings on DIFFERENT days are the minimum: one point is not a
    line, and two points from one afternoon is not movement.
    """
    points = []
    for s in snaps or ():
        day = (s.get("day") or "")[:10]
        value = s.get(key)
        if day and value is not None:
            points.append({"day": day, "value": value})
    days = len({p["day"] for p in points})
    low = min([p["value"] for p in points]) if points else None
    high = max([p["value"] for p in points]) if points else None
    return {
        "label": label,
        "provider": provider,
        "points": points,
        "can_draw": days > 1,
        "why": ("" if days > 1 else
                "Needs two readings on different days before it can draw."),
        "low": low,
        "high": high,
        # The axis is printed, and it is the MEASURED range: the line is
        # never flattered by a zero baseline nobody measured, and the
        # labels say so rather than leaving the scale to be guessed.
        "axis": ({"high": _n(high), "low": _n(low),
                  "first": points[0]["day"], "last": points[-1]["day"]}
                 if days > 1 else None),
    }


# --- THE SHOWCASE (owner's ruling: the demo account is the showcase, never
# the page from zero) ----------------------------------------------------
# An in-memory example in the shapes build() reads, exactly as
# marketing_room.showcase() is: nothing is written to the database, and
# the route is the only thing that decides who is shown it. Every reading
# names SHOWCASE_SOURCE, not a real vendor, so no real provider's name
# stands beside an invented figure; the page carries the Sample data lamp.
SHOWCASE_SOURCE = "Sample provider"
# Link visits match the Marketing room's example (its 30-day Heard).
SHOWCASE_VISITS = 12480
# (followers, monthly listeners), one reading a day, oldest first.
SHOWCASE_SERIES = ((1184, 7640), (1190, 7702), (1203, 7755), (1211, 7810),
                   (1219, 7868), (1236, 7931), (1248, 7990), (1259, 8046),
                   (1271, 8103), (1286, 8177), (1298, 8236), (1311, 8290),
                   (1327, 8358), (1342, 8420))
SHOWCASE_PEERS = 3


def showcase(today=None, artist_name=""):
    """The example Analytics room: what an account with a pinned artist,
    a metrics provider, smart links and peers sees. Spotify's own
    snapshots stay empty, as they are for every real account since
    Spotify stopped sending counts to apps like this one."""
    today = today or date.today()
    n = len(SHOWCASE_SERIES)
    snapshots = [{"day": (today - timedelta(days=n - 1 - i)).isoformat(),
                  "followers": f, "popularity": None, "monthly_listeners": m}
                 for i, (f, m) in enumerate(SHOWCASE_SERIES)]
    return {
        "profile": {"artist_name": artist_name or "Synthwave Surfer"},
        "snaps": [],
        "peers": [{"artist_id": "sample-peer-%d" % i} for i in range(SHOWCASE_PEERS)],
        "visits": SHOWCASE_VISITS,
        "metrics": {"label": SHOWCASE_SOURCE,
                    "followers": SHOWCASE_SERIES[-1][0],
                    "monthly_listeners": SHOWCASE_SERIES[-1][1],
                    "as_of": today.isoformat(), "snapshots": snapshots},
    }


def build(profile, snaps, peers, visits, listeners, observations, cards,
          today=None, sample=False, can_open=None, zero=None, can_add=True,
          metrics=None):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route from every count the
    spec names (None here means: decide from the same counts); `can_add`
    is who may connect a source (see zero_page). `metrics` is a metrics
    provider's readings on file - {"label", "followers",
    "monthly_listeners", "as_of", "snapshots"} - or None; each reading it
    supplies is credited to its label with its own day."""
    today = today or date.today()
    snaps = list(snaps or ())
    msnaps = list((metrics or {}).get("snapshots") or ())

    followers, followers_day = latest(snaps, "followers")
    followers_by, sources = "Spotify for Artists", {}
    if followers is None and metrics:
        followers, followers_day = latest(msnaps, "followers")
        if followers is None and metrics.get("followers") is not None:
            followers, followers_day = metrics["followers"], metrics.get("as_of") or ""
        if followers is not None:
            followers_by = metrics["label"]
            sources["followers"] = "From %s" % metrics["label"]
    provider_name = (profile or {}).get("provider") or ""
    listeners_by, listeners_day = provider_name or "Metrics provider", ""
    if listeners is None and metrics:
        listeners, listeners_day = latest(msnaps, "monthly_listeners")
        if listeners is None and metrics.get("monthly_listeners") is not None:
            listeners, listeners_day = metrics["monthly_listeners"], metrics.get("as_of") or ""
        listeners_by = metrics["label"]
        if listeners is not None:
            sources["listeners"] = "From %s" % metrics["label"]

    rows = [
        reading("Followers", followers, followers_by, followers_day, today,
                why="Spotify no longer sends this to apps like this one"),
        reading("Monthly listeners", listeners, listeners_by,
                listeners_day, today, why="Needs a metrics provider key"),
        reading("Audience geography", None, provider_name or "Metrics provider",
                "", today, why="Needs a metrics provider key"),
        reading("Link visits", visits, "Street Banker Smart Links",
                today.isoformat() if visits is not None else "", today,
                why="No tracking rows yet"),
    ]

    tiles = []
    for key in ("scores", "artist-twin", "reports"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        # The owner's mark on a page they hid rides with the tile.
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3],
                      "state": card[4] if len(card) > 4 else ""})

    # The drawer on the page from zero: the room's own tools, each a card
    # of this room, and a seat sees only the ones it can open.
    zero_tiles = []
    for key in ZERO_TILES:
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        # The owner's mark on a page they hid rides with the tile
        # (rooms.build keeps a hidden page for the owner alone).
        zero_tiles.append({"key": key, "href": href, "icon": card[1],
                           "name": card[2], "line": card[3],
                           "state": card[4] if len(card) > 4 else ""})
    if zero is None:
        zero = new_account(profile, snaps, visits, peers)

    # The line over time: Spotify's own followers while it sent them, and
    # the metrics provider's when Spotify's snapshots carry none.
    trend = chart(snaps, "followers", "Followers over time", "Spotify")
    if not trend["points"] and metrics and msnaps:
        trend = chart(msnaps, "followers", "Followers over time", metrics["label"])

    return {
        # The profile row carries artist_name (db.save_pulse_profile); "name"
        # was never there, so a pinned artist read "Nobody pinned" in the
        # head band until the page-from-zero tests caught it (2026-09-23).
        "artist": (profile or {}).get("artist_name") or (profile or {}).get("name") or "",
        "pinned": bool(profile),
        "figures": figures(visits, followers, listeners, sources),
        # The rooms' shared plate: the same readings, one per screen. The
        # trend is the panel under it (chart below).
        "screens": rack_screens(figures(visits, followers, listeners, sources)),
        # Nothing connected, synced or counted: the page from zero. One
        # source, reading or visit and the analyser takes over untouched.
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open) if zero else None,
        "zero_tiles": zero_tiles,
        "path": path(bool(profile), snaps + msnaps, len(peers or ()), len(observations or ())),
        "readings": rows,
        "chart": trend,
        "observations": list(observations or ()),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }
