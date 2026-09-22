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
          today=None, sample=False, can_open=None):
    """Everything the screen renders. No page logic beyond this."""
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
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3]})

    return {
        "artist": (profile or {}).get("name") or "",
        "pinned": bool(profile),
        "figures": figures(visits, followers, listeners),
        "path": path(bool(profile), snaps, len(peers or ()), len(observations or ())),
        "readings": rows,
        "chart": chart(snaps, "followers", "Followers over time", "Spotify"),
        "observations": list(observations or ()),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }
