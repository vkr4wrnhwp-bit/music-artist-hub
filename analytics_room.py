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
from datetime import date

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


# --- THE PLATE --------------------------------------------------------
# static/img/analytics-plate.webp, 1859x846: a TREND ANALYSER, its long
# oscilloscope screen across the top and the three readings beneath it.
# Each window is (x, y, w, h) as a PERCENTAGE of the plate, MEASURED off
# the file with PIL. RE-MEASURE ALL OF THEM if the plate is regenerated or
# re-cropped: the overlays would land beside their glass and nothing in
# code would say so.
#
# The plate silkscreens THE TREND, LINK VISITS, FOLLOWERS and LISTENERS,
# so the markup never prints those words - they ride along as
# screen-reader text and appear only under 560px.
PLATE = {
    "trend":     (5.65, 18.09, 88.60, 28.72),
    "visits":    (5.65, 64.54, 27.17, 17.49),
    "followers": (35.77, 65.37, 28.19, 16.55),
    "listeners": (67.35, 65.48, 26.90, 16.55),
}
# The order the silkscreen prints them in. Metal cannot be reordered.
PLATE_ORDER = ("visits", "followers", "listeners")


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# --- THE PAGE FROM ZERO (owner's Analytics spec + mockup, 2026-09-23) -----
# An account with nothing connected, nothing synced, no link events and
# no peers does not meet an empty analyser. It meets an onboarding page:
# the Command Center's photographed three-screen plate drawn STATIC with
# this room's words, one card that opens Connections, the four lenses as
# doors to the rooms that own the next step, the five-step workflow as
# education, the two empties in words, help, and the tools in a drawer
# that starts open. No chart, no date filter, no comparison, no nought.
# The animated standby that used to run on the analyser is retired here;
# the fill reel below stays for a populated analyser's empty windows.
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


# The reel a READING window shows while it has nothing to read (owner,
# 2026-09-22: no words in an empty window, icons). The one piece of the
# old standby still read: a populated analyser's empty windows.
STANDBY_FILL = ("pinned", "measuring", "trending", "compared", "read", "person")


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """What a populated analyser's empty windows fill with. The animated
    standby that once ran on an empty account is retired: that account
    meets the page from zero instead."""
    return {"fill": _six(STANDBY_FILL)}


def plate_windows(rows):
    """figures() again, each carrying the window it is printed in."""
    by = {r["key"]: r for r in rows or ()}
    return [dict(by[k], box=box(k)) for k in PLATE_ORDER if k in by]


def figures(visits, followers, listeners):
    """The three across the top. Each may be unmeasured, and says why."""
    out = []
    for key, label, source, value, why in (
        ("visits", "Link visits", "From your smart links", visits,
         "No smart links tracked yet"),
        ("followers", "Followers", "From the connected provider", followers,
         "Spotify stopped returning this"),
        ("listeners", "Monthly listeners", "From the connected provider", listeners,
         "Needs a metrics provider"),
    ):
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
    return {
        "label": label,
        "provider": provider,
        "points": points,
        "can_draw": days > 1,
        "why": ("" if days > 1 else
                "Needs two readings on different days before it can draw."),
        "low": min([p["value"] for p in points]) if points else None,
        "high": max([p["value"] for p in points]) if points else None,
    }


def build(profile, snaps, peers, visits, listeners, observations, cards,
          today=None, sample=False, can_open=None, zero=None, can_add=True):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route from every count the
    spec names (None here means: decide from the same counts); `can_add`
    is who may connect a source (see zero_page)."""
    today = today or date.today()
    snaps = list(snaps or ())

    followers, followers_day = latest(snaps, "followers")
    provider_name = (profile or {}).get("provider") or ""

    rows = [
        reading("Followers", followers, "Spotify for Artists", followers_day, today,
                why="Spotify no longer sends this to apps like this one"),
        reading("Monthly listeners", listeners, provider_name or "Metrics provider",
                "", today, why="Needs a metrics provider key"),
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

    return {
        # The profile row carries artist_name (db.save_pulse_profile); "name"
        # was never there, so a pinned artist read "Nobody pinned" in the
        # head band until the page-from-zero tests caught it (2026-09-23).
        "artist": (profile or {}).get("artist_name") or (profile or {}).get("name") or "",
        "pinned": bool(profile),
        "figures": figures(visits, followers, listeners),
        # The plate: the same readings, each on its own glass.
        "windows": plate_windows(figures(visits, followers, listeners)),
        "trend_box": box("trend"),
        # Nothing connected, synced or counted: the page from zero. One
        # source, reading or visit and the analyser takes over untouched.
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open) if zero else None,
        "zero_tiles": zero_tiles,
        "standby": standby(),
        "path": path(bool(profile), snaps, len(peers or ()), len(observations or ())),
        "readings": rows,
        "chart": chart(snaps, "followers", "Followers over time", "Spotify"),
        "observations": list(observations or ()),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }
