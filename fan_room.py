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


def moves(rows, audience, days, today, link_visits=0, shopify=False):
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
                    "reach_label": "On file", "reach": "0 fans",
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
        out.append({"icon": "welcome", "title": "Capture more fans" if total else "Start capturing fans",
                    "desc": "Put an email capture on a smart link.",
                    "reach_label": "", "reach": "",
                    "cta": "Make a link", "href": "/links/new"})
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
        return ("good" if new_count else "off", "%s new" % _fmt(new_count))
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
          shopify=False):
    now = now or datetime.now(timezone.utc)
    today = now.date()
    days = days_from(days)
    club = club or {"on": False, "members": 0}
    fresh = new_fans(rows, days, today)
    tiles = []
    for key, href, icon, label, desc, state in cards:
        tone, status = tile_status(key, audience, len(fresh), days, club, open_briefs, state)
        label, desc = TILE_COPY.get(key, (label, desc))
        tiles.append({"key": key, "href": href, "label": label,
                      "desc": desc, "tone": tone, "status": status,
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
        "moves": moves(rows, audience, days, today, link_visits, shopify=shopify),
        "pulse": pulse(audience),
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
