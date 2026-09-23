"""The Fan Room: the Fans room's opening screen (owner's mockup, 2026-09-19:
"for the fans room opening screen use this image and build it to be a
exact replica almost since all other fan pages are done").

The layout is the mockup's. The figures are this account's own records,
read the same way the Audience screen reads them (fan_audience), and a
figure the records cannot support is left out rather than drawn:

  Your owned audience   fans on file
  new in N days         fans who joined through a smart link in the window;
                        an imported list is the artist moving a list they
                        had, not the audience growing, so it is not "new"
  reachable             fans with an email that has not bounced or
                        unsubscribed, as a share of everyone on file
  Next best moves       only moves the app can carry out, each with the
                        count it acts on
  Audience pulse        contactable fans by city, the Audience map's own
                        points; the lines between neighbouring cities are
                        drawing, not data, and say nothing about travel
  tool tiles            one true count per tool, or the tool's state

Nothing here sends anything. The mockup's "Send welcomes" and "Send
invites" became what the app can do today: hand over the list, or open
the fans in the Fan CRM.
"""
import csv
import io
import json
import math
from datetime import datetime, timedelta, timezone

import fan_audience
import fan_segments

RANGES = (7, 30, 90)
DEFAULT_RANGE = 30

# The mockup's five tiles, in its order, for the room's own cards. A card
# the room adds later (a parked page, for the owner) keeps the room's copy.
TILE_COPY = {
    "fans": ("Fans", "Audience overview"),
    # The mockup said "Profiles & segments"; /links/fans is the flat list
    # with search, export and remove, and nothing on it is called either
    # (walk, 2026-09-20). The card says what the page is.
    "fan-crm": ("Fan CRM", "Everyone on file, searchable and exportable"),
    "fan-club": ("Fan Club", "Memberships & exclusives"),
    "discover": ("Discover", "Find listeners and scenes"),
    "marketplace": ("Collab", "Artists, creators & brands"),
}

# The populated room's rail: the mockup's five stages, each with the count
# of what the records can say about it (lifecycle() below). Until
# 2026-09-23 the rail was these names and a line of aspiration each, with
# nothing counted behind any of them.
#   (key, name, singular, plural, what the line says with nothing counted)
LIFECYCLE = [
    ("discover", "Discover", "smart link visit", "smart link visits", "No smart link visits"),
    ("capture", "Capture", "fan on file", "fans on file", "Nobody on file"),
    ("know", "Know", "with a name or place", "with a name or place", "No names or places yet"),
    ("activate", "Activate", "clicked through", "clicked through", "Nobody has clicked through yet"),
    ("belong", "Belong", "Fan Club member", "Fan Club members", "No members yet"),
]

TOP_BANDS = ("Superfan", "Hot")


# --- THE PAGE FROM ZERO (owner's Fans spec, 2026-09-22) ------------------
# What the room says to an account with no fans. Words only - never a
# figure, not even an example one - and every line is the spec's own.
ZERO_RACK = {
    "purpose": ("Purpose", "Own the listener relationship",
                "Capture, organize, and activate an audience you can reach directly."),
    "start": ("Start here", "Choose how to add your first fans"),
    "know": ("Good to know", "Nothing is added until you review and confirm"),
}
# Two EQUAL ways to begin. Neither is drawn as the lesser (spec: "do not
# visually imply that importing is less legitimate than capturing").
STARTS = [
    ("capture", "Capture new fans",
     "Create a smart link or campaign that turns listeners into contacts you can reach.",
     "Launch fan campaign", "/links/new?type=bio&returnTo=/room/fans",
     "Best if you are starting from zero."),
    ("import", "Bring an audience you already have",
     "Import a permitted contact list. You will preview every record before anything is added.",
     "Import your list", "/fans?returnTo=/room/fans",
     "CSV, spreadsheet, or pasted contacts."),
]
# The five stages, EDUCATIONAL on a new account: no stage is complete, in
# progress or blocked, and there is no percentage. Capture is highlighted
# as the first step. LIFECYCLE (Discover .. Belong) stays the populated
# room's rail; this is the onboarding one.
WORKFLOW = [
    ("capture", "Capture", "Collect fans through a campaign or import."),
    ("consent", "Confirm consent", "Verify permission and review details."),
    ("organize", "Organize", "Segment and prepare your fans."),
    ("activate", "Activate", "Use your fans in marketing and releases."),
    ("measure", "Measure", "See what is working over time."),
]
CONTROL = ("Preview imports before adding anyone",
           "Record consent source and permission",
           "Nothing is sent without your approval")
HELP_QUESTIONS = ("How do I collect my first fans?",
                  "Can I import my existing email list?",
                  "What counts as permission to contact someone?")


def zero_page():
    return {"rack": ZERO_RACK, "starts": STARTS, "workflow": WORKFLOW,
            "control": CONTROL, "help": HELP_QUESTIONS,
            # the three screens of the rooms' shared rack (partials/cc_rack.html)
            "screens": [{"k": ZERO_RACK[key][0], "v": ZERO_RACK[key][1]}
                        for key in ("purpose", "start", "know")]}


# --- THE RACK ----------------------------------------------------------
# The working room draws the rooms' shared three-window plate
# (partials/cc_rack.html over static/img/room-plate.webp) like every other
# room (owner, 2026-09-23: "every room's rack uses the shorter
# three-window plate"). Its three screens carry the three readings - ON
# FILE, REACHABLE, NEW, left to right - and the big window of the old
# Audience Monitor plate (static/img/fans-plate.webp, no longer drawn)
# became its own panel directly under the plate: the map, nothing lost.
#
# The new plate prints no names, so each screen says what it is.


def windows(total_label, total, new_label, new, reachable_pct, days):
    """The three readings, in the order the rack draws them.

    None of them reads 0 for an absence: "None yet" is the words for
    nobody on file, while a real 0% is a measurement of an account whose
    every fan is suppressed or has no address.
    """
    return [
        {"key": "on-file", "name": "On file",
         "value": total_label, "measured": True,
         "sub": "fan" if total == 1 else "fans"},
        {"key": "reachable", "name": "Reachable",
         "value": ("%d%%" % reachable_pct) if reachable_pct is not None else "None yet",
         "measured": reachable_pct is not None,
         "sub": "can be emailed"},
        {"key": "new", "name": "New",
         "value": new_label, "measured": True,
         "sub": "in %d days" % days},
    ]


def rack_screens(wins):
    """The three windows as the shared rack's screens: the name as the
    screen's label, the reading set as a figure, an absence set as words
    (never a nought), and the window's own line under it."""
    return [{"k": w["name"], "v": w["value"], "fig": w["measured"],
             "none": not w["measured"], "sub": w["sub"]} for w in wins or ()]


def days_from(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RANGE
    return n if n in RANGES else DEFAULT_RANGE


def _tags(fan):
    raw = fan.get("tags") or "[]"
    try:
        tags = json.loads(raw) if isinstance(raw, str) else list(raw)
    except ValueError:
        return []
    return [str(t) for t in tags or ()]


def _day(stamp):
    s = str(stamp or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def new_fans(rows, days, today):
    """Fans who joined through a smart link within the last `days` days.
    Imports and Shopify pulls are not new fans (see the module note)."""
    cutoff = today - timedelta(days=days)
    out = []
    for f in rows or ():
        if {"imported", "shopify"} & set(_tags(f)):
            continue
        d = _day(f.get("created"))
        if d and d > cutoff:
            out.append(f)
    return out


def _fmt(n):
    return "{:,}".format(int(n or 0))


def moves(rows, audience, days, today, link_visits=0, shopify=False,
          can_open=None):
    """Up to three things the artist can do now, strongest first. Each is
    one the app carries out, with the number of fans it acts on. `shopify`
    is whether this account may import the connected store's customers
    (the owner alone); the move names Shopify only then."""
    total = audience["total"]
    out = []
    if not total:
        out.append({"icon": "import", "title": "Bring in the fans you already have",
                    "desc": ("Import a list or Shopify customers. You preview it first."
                             if shopify else "Import a list. You preview it first."),
                    # no "0 fans": an absence is words, not a nought
                    # (audit, 2026-09-22)
                    "reach_label": "", "reach": "",
                    "cta": "Import your list", "href": "/fans"})
    joined = new_fans(rows, days, today)
    fresh = fan_segments.contactable(joined)
    if fresh:
        # The hero counts everybody new; this acts on those with an email
        # that works, and says so when the two differ.
        desc = ("Joined through your links in the last %d days." % days if len(fresh) == len(joined)
                else "The new fans of the last %d days you can email." % days)
        out.append({"icon": "welcome", "title": "Welcome %s new fan%s" % (_fmt(len(fresh)), "" if len(fresh) == 1 else "s"),
                    "desc": desc,
                    "reach_label": "Reach", "reach": "%s fan%s" % (_fmt(len(fresh)), "" if len(fresh) == 1 else "s"),
                    "cta": "Get their emails", "href": "/room/fans/new.csv?days=%d" % days})
    no_email = sum(1 for f in rows or () if not (f.get("email") or "").strip())
    if no_email:
        out.append({"icon": "mail", "title": "Find %s missing email%s" % (_fmt(no_email), "" if no_email == 1 else "s"),
                    "desc": "On file with no email address yet.",
                    "reach_label": "Reach", "reach": "%s fan%s" % (_fmt(no_email), "" if no_email == 1 else "s"),
                    "cta": "Open Fan CRM", "href": "/links/fans?missing=email"})
    elif total and int(link_visits or 0) > total:
        out.append({"icon": "mail", "title": "Turn link views into known fans",
                    "desc": "Views on your links that left no email.",
                    "reach_label": "Link views", "reach": _fmt(link_visits),
                    "cta": "Add a capture", "href": "/links"})
    top = sum(s["count"] for s in audience.get("segments") or () if s["name"] in TOP_BANDS)
    if top:
        out.append({"icon": "diamond", "title": "Reward your %s most engaged fan%s" % (_fmt(top), "" if top == 1 else "s"),
                    "desc": "Scored Hot or Superfan on your links.",
                    "reach_label": "Reach", "reach": "%s fan%s" % (_fmt(top), "" if top == 1 else "s"),
                    "cta": "See them", "href": "/links/fans?intent=top"})
    if len(out) < 3:
        # The hero's gold button already goes to /links/new, so a filler
        # row pointing there put one destination on the screen twice under
        # two names. This row sends them to the links they have instead.
        out.append({"icon": "welcome", "title": "Capture more fans" if total else "Start capturing fans",
                    "desc": "Put an email capture on a smart link.",
                    "reach_label": "", "reach": "",
                    "cta": "See your links", "href": "/links"})
    if can_open:
        out = [m for m in out if can_open(m["href"].split("?")[0])]
    return out[:3]


PULSE_W, PULSE_H = fan_audience.MAP_W, fan_audience.MAP_H

# The names' sizes, in viewBox units, at each width the map is drawn:
# (name, count) at full size and then at each narrower step. They are
# fan-room.css's .fr-map-name / .fr-map-count and its frmap container
# steps, larger as the map narrows so they stay legible on the page;
# tests/test_fan_room.py holds the two to each other.
LABEL_STEPS = ((13, 12), (17, 15), (22, 20), (30, 28), (40, 37))
# Archivo at 700 runs about .52-.56em a character; this errs wide.
_EM_PER_CHAR = .58


def _label_box(p, side, fn, fc):
    """The box a city's name and the count under it fill, in viewBox units,
    with the name at fn and the count at fc: 10 units off the dot, the name
    on the baseline 2 units above it, the count one line (1.15em) under."""
    w = _EM_PER_CHAR * max(fn * len(p["city"]), fc * len("{:,}".format(p["count"])))
    x0 = p["x"] - 10 if side == "end" else p["x"] + 10
    left, right = (x0 - w, x0) if side == "end" else (x0, x0 + w)
    base = p["y"] - 2
    return (left, base - .8 * fn, right, base + 1.15 * fc + .25 * fc)


def _clear(box, placed):
    """On the drawing, and into no name already placed."""
    return (box[0] >= 0 and box[2] <= PULSE_W and box[1] >= 0 and box[3] <= PULSE_H
            and not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3]
                        for q in placed))


def _place_labels(pts):
    """Two names drawn over each other read as neither (New York and
    Chicago did, 2026-09-23). Biggest city first, each name takes its
    natural side - toward the middle of the drawing - or the other one when
    that side runs off the drawing or into a name already placed. The names
    grow at each narrower step, so at each step a name that would still
    collide with a bigger city's is not drawn there (nor at any narrower
    step): `off` is the first step it is left out, or None. The dot keeps
    its size and the reader's list keeps the name."""
    named = [p for p in pts if p["label"]]
    fn, fc = LABEL_STEPS[0]
    placed = []
    for p in named:
        first = "end" if p["right"] else "start"
        side = first
        for side in (first, "start" if first == "end" else "end"):
            if _clear(_label_box(p, side, fn, fc), placed):
                break
        else:
            side = first
        p["right"] = side == "end"
        placed.append(_label_box(p, side, fn, fc))
    for p in pts:
        p["off"] = None
    for step, (fn, fc) in enumerate(LABEL_STEPS):
        kept = []
        for p in named:
            if p["off"] is not None:
                continue
            box = _label_box(p, "end" if p["right"] else "start", fn, fc)
            if _clear(box, kept):
                kept.append(box)
            else:
                p["off"] = step


def pulse(audience, labels=4):
    """The Audience map's own points, drawn as a constellation: a dot per
    city sized by fans, the biggest few named, each joined to its nearest
    neighbours. Returns None when no city could be placed."""
    geo = audience.get("geo") or {}
    dots = sorted(geo.get("dots") or (), key=lambda d: -d["count"])
    if not dots:
        return None
    # Zoom to where the fans are, one scale for both axes so the cities
    # keep their places relative to each other, with room for the names.
    xs = [d["x"] for d in dots]
    ys = [d["y"] for d in dots]
    aspect = PULSE_W / float(PULSE_H)
    span_w = max(max(xs) - min(xs), PULSE_W * .25)
    span_h = max(max(ys) - min(ys), PULSE_H * .25)
    if span_w / span_h < aspect:
        span_w = span_h * aspect
    else:
        span_h = span_w / aspect
    span_w *= 1.35
    span_h *= 1.35
    x0 = (min(xs) + max(xs)) / 2.0 - span_w / 2.0
    y0 = (min(ys) + max(ys)) / 2.0 - span_h / 2.0
    k = PULSE_W / span_w
    pts = []
    for i, d in enumerate(dots):
        x, y = (d["x"] - x0) * k, (d["y"] - y0) * k
        pts.append({"x": round(x, 1), "y": round(y, 1), "r": round(max(2.5, d["core"] * .55), 1),
                    "city": d["city"], "count": d["count"], "label": i < labels,
                    "right": x > PULSE_W * .7})
    _place_labels(pts)
    lines = set()
    for i, p in enumerate(pts):
        near = sorted((math.hypot(p["x"] - q["x"], p["y"] - q["y"]), j)
                      for j, q in enumerate(pts) if j != i)[:2]
        for _dist, j in near:
            lines.add((min(i, j), max(i, j)))
    return {"w": PULSE_W, "h": PULSE_H, "dots": pts,
            "lines": [(pts[a]["x"], pts[a]["y"], pts[b]["x"], pts[b]["y"]) for a, b in sorted(lines)],
            "cities": geo.get("cities") or len(pts),
            "unplotted": geo.get("unplotted") or 0}


def _known(fan):
    """Something on file beyond the address: a name, a city or a country."""
    return any((fan.get(k) or "").strip() for k in ("name", "city", "country"))


def lifecycle(rows, link_visits=0, club=None):
    """The rail's five stages, each counted from the account's own records.

      Discover   views of the account's smart links (ml_events page_view),
                 the same figure the Audience funnel's Link visits row reads.
                 Views, not people: the app keeps no identity for a visitor
                 who has not signed up.
      Capture    fans on file.
      Know       fans whose record carries a name, a city or a country.
      Activate   fans who pressed a service button on a smart link
                 (total_clicks). A press is credited to a fan only when they
                 are known on the link (fan_mail). A sign-up before release
                 is a capture, not an activation, so pre-saves are not
                 counted here: most of them are email reminders.
      Belong     active Fan Club members; "No Fan Club yet" when the
                 account has none.

    A stage with nothing counted says so in words, never a nought.
    """
    rows = list(rows or ())
    club = club or {"on": False, "members": 0}
    counts = {
        "discover": int(link_visits or 0),
        "capture": len(rows),
        "know": sum(1 for f in rows if _known(f)),
        "activate": sum(1 for f in rows if int(f.get("total_clicks") or 0) > 0),
        "belong": int(club.get("members") or 0),
    }
    out = []
    for key, name, singular, plural, empty in LIFECYCLE:
        n = counts[key]
        if key == "belong" and not club.get("on"):
            line = "No Fan Club yet"
        elif n:
            line = "%s %s" % (_fmt(n), singular if n == 1 else plural)
        else:
            line = empty
        out.append({"key": key, "name": name, "count": n, "line": line})
    return out


def tile_status(key, audience, new_count, days, club, open_briefs, state):
    """(tone, text) for a tool tile: one true count, or the tool's state."""
    if state == "hidden":
        return ("off", "Hidden")
    if state == "sample":
        return ("info", "Sample")
    def count(n, word):
        # Green is a real, non-zero figure; a zero is stated, not lit.
        return ("good" if n else "off", "%s %s%s" % (_fmt(n), word, "" if n == 1 else "s"))
    if key == "fans":
        # The hero prints the new-fan count as its 66px headline
        # figure. A tile is a door, not a second readout of the same
        # number, so this one carries no figure at all.
        return ("off", "")
    if key == "fan-crm":
        n = int(audience.get("total") or 0)
        return count(n, "fan") if n else ("off", "Nobody yet")
    if key == "fan-club":
        if not club["on"]:
            return ("off", "Not set up")
        return count(club["members"], "member")
    if key == "marketplace":
        return count(open_briefs, "open brief")
    return ("off", "")


def build(rows, audience, cards, days=DEFAULT_RANGE, now=None, club=None,
          open_briefs=0, link_visits=0, showcase=False, artist_name="",
          shopify=False, can_open=None):
    now = now or datetime.now(timezone.utc)
    today = now.date()
    days = days_from(days)
    club = club or {"on": False, "members": 0}
    fresh = new_fans(rows, days, today)
    tiles = []
    for key, href, icon, label, desc, state in cards:
        # A seat sees only the doors it can open. Every other room has done
        # this since team rooms shipped; this one had no gate at all, so a
        # Fans-only seat was offered /links - a Marketing page - and bounced
        # (audit, 2026-09-22).
        if can_open and not can_open(href):
            continue
        tone, status = tile_status(key, audience, len(fresh), days, club, open_briefs, state)
        label, desc = TILE_COPY.get(key, (label, desc))
        tiles.append({"key": key, "href": href, "label": label,
                      "desc": desc, "tone": tone, "status": status,
                      # the raw state too: the drawer from zero shows the
                      # owner's Hidden mark and none of the counts
                      "state": state,
                      "external": href.startswith(("http://", "https://", "/suites/go/"))})
    total = audience["total"]
    return {
        "showcase": showcase,
        "artist_name": artist_name,
        "days": days,
        "ranges": RANGES,
        "total": total,
        "total_label": _fmt(total),
        "new": len(fresh),
        "new_label": _fmt(len(fresh)),
        "reachable_pct": audience.get("contactable_pct") if total else None,
        "lifecycle": lifecycle(rows, link_visits, club),
        "moves": moves(rows, audience, days, today, link_visits, shopify=shopify,
                       can_open=can_open),
        # The map, in its own panel directly under the rack.
        "pulse": pulse(audience),
        # Nothing captured at all: the page from zero. One real fan and
        # the working rack and its map take over for good.
        "idle": not total,
        "zero": zero_page(),
        # The hero's gold pill goes to /links/new, which is not this room's
        # page. A reader who cannot open it is offered the room's own list
        # instead of a button that turns them away.
        "can_capture": bool(can_open is None or can_open("/links/new")),
        # The working rack's three screens: On file, Reachable, New.
        "screens": rack_screens(windows(_fmt(total), total, _fmt(len(fresh)), len(fresh),
                                        audience.get("contactable_pct") if total else None,
                                        days)),
        "tiles": tiles,
    }


def new_fans_csv(rows, days, today):
    """The contactable fans who joined in the window: the list the "Get
    their emails" move hands over. Suppressed fans are never in it."""
    live = fan_segments.contactable(new_fans(rows, days, today))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Email", "Name", "City", "Country", "Joined"])
    for f in live:
        w.writerow([f.get("email") or "", f.get("name") or "", f.get("city") or "",
                    f.get("country") or "", str(f.get("created") or "")[:10]])
    return out.getvalue()
