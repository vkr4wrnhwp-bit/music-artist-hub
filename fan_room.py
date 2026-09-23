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

LIFECYCLE = [
    ("discover", "Discover", "Find new listeners"),
    ("capture", "Capture", "Turn interest into fans"),
    ("know", "Know", "Enrich profiles and data"),
    ("activate", "Activate", "Drive engagement and revenue"),
    ("belong", "Belong", "Create a lasting community"),
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
            "control": CONTROL, "help": HELP_QUESTIONS}


# --- THE PLATE --------------------------------------------------------
# static/img/fans-plate.webp, 1860x846. The hardware is ONE photograph and
# only the readings are drawn on it. Each window is (x, y, w, h) as a
# PERCENTAGE of the plate, MEASURED off the file itself with PIL.
#
# RE-MEASURE EVERY ONE IF THE PLATE IS REGENERATED OR RE-CROPPED. Cropping
# moves all of them and nothing in code will tell you - the overlays simply
# land beside their glass. tests/test_fan_room.py asserts these numbers, so
# a silent drift fails loudly instead.
#
# The plate SILKSCREENS each window's name - ON FILE, REACHABLE, NEW, and
# THE ROOM under the big one - so the markup never prints them. They ride
# along as screen-reader text and become visible only under 560px, where
# the photograph steps aside and the readings stand on their own.
PLATE = {
    "room":      (6.67, 18.56, 59.30, 62.29),
    "on-file":   (71.02, 14.78, 22.20, 13.95),
    "reachable": (71.02, 41.02, 22.20, 13.83),
    "new":       (71.02, 67.14, 22.20, 13.95),
}


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# STANDBY: what each window will hold, for an account that has nothing
# yet (owner, 2026-09-22). Words only - never an example figure, because
# a demonstration number sitting where the artist's own will appear is
# the defect this room exists to refuse.
# STANDBY, the owner's way (2026-09-22): "rendering just some video on
# them and letting them explain things inside the room is better... your
# text is so small and it's really cheap looking."
#
# He is right about the type. A caption at clamp(8px,.84cqw,12.5px) is
# about eleven pixels on a desktop - caption size, on a unit photographed
# at 1860px. So the small windows carry NO text at all; they breathe, and
# the big window does the talking in one large frame at a time.
#
# Words only, still: no figure ever appears here, not even an example one.
# And nothing repeats the silkscreen, which the plate prints in metal.
# The frames name the FEATURES in this room (owner, 2026-09-22: "sequence
# through some of what features are in the room"). Each is a card that
# exists in rooms.ROOMS["fans"], described by what it actually does.
STANDBY_FRAMES = (
    ("Smart Links", "One link. Whoever opens it becomes a name and an "
                    "address you own."),
    ("Fan CRM", "Everyone on file, searchable, filterable and yours to "
                "export."),
    ("Fan Club", "A paid membership you run, with your own perks and your "
                 "own price."),
    ("Collab", "Artists, creators and brands looking for somebody like "
               "you."),
)

# The three small windows, each doing a DIFFERENT thing (owner,
# 2026-09-22: "the top one on the right can be scrolling through icons.
# The middle one can be, you know, just hints and tips").
#
#   ON FILE    icons rolling past, like a reel
#   REACHABLE  a hint, changed every few seconds
#   NEW        the room's feature names, ticking through
#
# Everything is SHORT, because these windows are about 273x118 at a
# desktop plate width and the last cut tried to fit a sentence in one.
STANDBY_ICONS = ("capture", "know", "mail", "belong", "discover", "activate")

# No full stops: this is the unit's lettering, not prose.
STANDBY_TIPS = (
    "Import a list you already have",
    "One link works on every platform",
    "Tag a fan once, find them for ever",
    "Export anyone, any time",
)

# The names as the room's own tiles carry them.
STANDBY_TICKER = ("Smart Links", "Fan CRM", "Fan Club", "Discover", "Collab")


# One picture per frame, generated by the owner and cropped to the big
# window's own aspect (1103x527 at full plate width - 2.09:1). A frame
# whose file is not on disk draws without one rather than drawing a broken
# image, so the sequence never depends on the pictures having arrived.
# The ?v moves when a picture is replaced in place - see the plate <img>.
STANDBY_IMAGES = tuple("static/img/standby/fans-%d.webp" % n for n in (1, 2, 3, 4))
STANDBY_IMAGE_V = 1


def _image_for(n):
    import os
    path = STANDBY_IMAGES[n] if n < len(STANDBY_IMAGES) else ""
    if path and os.path.exists(path):
        return "/%s?v=%d" % (path, STANDBY_IMAGE_V)
    return ""

# The reel a READING window shows while it has nothing to read
# (owner, 2026-09-22: no words in an empty window, icons).
STANDBY_FILL = STANDBY_ICONS


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """The plate with nothing measured: a sequence, a reel, a hint and a
    ticker. No small print anywhere - the previous cut set a caption in
    every window at about eleven pixels, on a unit photographed at 1860px.
    """
    return {
        "lead_box": box("room"),
        "frames": [{"n": i, "title": t, "line": l, "image": _image_for(i)}
                   for i, (t, l) in enumerate(STANDBY_FRAMES)],
        "count": len(STANDBY_FRAMES),
        "reel": {"box": box("on-file"), "name": "On file",
                 "icons": _six(STANDBY_ICONS)},
        "fill": _six(STANDBY_FILL),
        # NOT "items": Jinja resolves foo.items to the dict's own method
        # before it looks for a key of that name, so {% for t in
        # tips.items %} iterated a built-in and 500'd.
        "tips": {"box": box("reachable"), "name": "Reachable",
                 "lines": STANDBY_TIPS, "count": len(STANDBY_TIPS)},
        "ticker": {"box": box("new"), "name": "New",
                   "lines": STANDBY_TICKER, "count": len(STANDBY_TICKER)},
    }


def windows(total_label, total, new_label, new, reachable_pct, days):
    """The three small readings, in the order the plate prints them.

    None of them reads 0 for an absence: "None yet" is the words for
    nobody on file, while a real 0% is a measurement of an account whose
    every fan is suppressed or has no address.
    """
    return [
        {"key": "on-file", "name": "On file", "box": box("on-file"),
         "value": total_label, "measured": True,
         "sub": "fan" if total == 1 else "fans", "tone": ""},
        {"key": "reachable", "name": "Reachable", "box": box("reachable"),
         "value": ("%d%%" % reachable_pct) if reachable_pct is not None else "None yet",
         "measured": reachable_pct is not None,
         "sub": "can be emailed", "tone": ""},
        {"key": "new", "name": "New", "box": box("new"),
         "value": new_label, "measured": True,
         "sub": "in %d days" % days, "tone": "is-up" if new else ""},
    ]


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
        "lifecycle": LIFECYCLE,
        "moves": moves(rows, audience, days, today, link_visits, shopify=shopify,
                       can_open=can_open),
        "pulse": pulse(audience),
        # The plate: the big window's own box, and the three readings.
        "room_box": box("room"),
        # Nothing captured at all: the plate explains itself instead of
        # printing four blanks. One real fan and this is gone for good.
        "idle": not total,
        "standby": standby(),
        "zero": zero_page(),
        # The hero's gold pill goes to /links/new, which is not this room's
        # page. A reader who cannot open it is offered the room's own list
        # instead of a button that turns them away.
        "can_capture": bool(can_open is None or can_open("/links/new")),
        "windows": windows(_fmt(total), total, _fmt(len(fresh)), len(fresh),
                           audience.get("contactable_pct") if total else None,
                           days),
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
