"""The Marketing Room: the Marketing room's opening screen (owner's design,
2026-09-21), built as the Fan Room's sibling.

The layout is his. Every figure is this account's own records, and a figure
the records cannot support is said in words rather than drawn:

  the hero band     visits, clicks and pre-saves from ml_events, joined to
                    this account's campaigns and filtered on the event's
                    own timestamp, so the range chooser governs all three
                    and the band says so. The ml_fans counters
                    total_visits and total_clicks are never read: nothing
                    in the application increments them
  the stage rail    Written, Pitched, Opened, Written about, Heard, each
                    counted over the whole record. The band above is a
                    window; the rail is everything, and the line under
                    the controls says which is which
  the actions       one row per thing the artist can do now, each with the
                    number of records it acts on. A row whose count is
                    zero is not an action, so it is left out rather than
                    drawn as a zero
  the map           media contacts by city, a constellation of the cities
                    the contact records name. There is no basemap in this
                    repository, so the panel draws dots and lines on the
                    bare panel exactly as the Fan Room does, and the
                    lines are drawing, not distance
  the tiles         Press Desk, Press kit and Referrals, the three his
                    design closes with, each with its own true state

His design's fifth action row was "Release with no smart link". Four
different things in this app wear the word release and none of them joins
to a smart link; the one stored join is ro_campaigns.ml_campaign_id, the
link a Release Rollout carries. So the row is a rollout with no link
connected, and the owner has ruled on its words (2026-09-21): "you should
not require them to use our smart link. If they need a different one or
they like using a different service they can. But we should push them for
ours." The row states the consequence, offers ours, and never implies
theirs is disallowed.
"""
import math

import board_taxonomy

RANGES = (7, 30, 90)
DEFAULT_RANGE = 30

# The event types the public smart link route actually writes. "Pre-saves"
# is presave_notify everywhere else in the app (links_analytics.html,
# app.py:4253), so it is presave_notify here too.
EVENT_VISIT = "page_view"
EVENT_CLICK = "service_click"
EVENT_PRESAVE = "presave_notify"

# His three closing tiles, in his order, with his words.
TILE_ORDER = ("press-desk", "epk", "referrals")
TILE_COPY = {
    "press-desk": ("Press Desk",
                   "Unify your media list, announcements, pitches and coverage"
                   " in one place. Move from writing to being heard."),
    "epk": ("Press kit", "Your public press kit link for media and industry."),
    "referrals": ("Referrals",
                  "Bring in other great artists to the Street Banker network."),
}

# The five stages of his rail: key, name, and the words of its one line.
# (figure key, singular, plural, what the line says with nothing counted)
STAGES = [
    ("written", "Written", "ready", "announcement", "announcements",
     "No announcements ready"),
    ("pitched", "Pitched", "sent", "pitch", "pitches", "No pitches sent"),
    ("opened", "Opened", "opens", "open", "opens", "No opens logged"),
    ("covered", "Written about", "coverage", "coverage hit", "coverage hits",
     "No coverage logged"),
    ("heard", "Heard", "visits_all", "smart link visit", "smart link visits",
     "No smart link visits"),
]
_STAGE_VERB = {"written": "ready", "pitched": "sent", "opened": "logged",
               "covered": "", "heard": ""}

# His five action rows, in his order and his words. The fifth is the
# substitute the stored data supports, worded to the owner's ruling.
ACTIONS = [
    ("never-pitched", "never-pitched", "Contacts never pitched",
     "These media contacts have not received a pitch yet.",
     "contact", "contacts", "View contacts", "/press-desk/contacts"),
    ("unsent", "announcement", "Announcement written but not sent",
     "You have announcements ready to pitch.",
     "announcement", "announcements", "Send now", "/press-desk/pitch/new"),
    ("silent", "opened", "Pitch opened several times with no coverage",
     "These pitches have multiple opens but no coverage logged.",
     "pitch", "pitches", "Review pitch", "/press-desk"),
    ("no_link", "link", "Rollout with no smart link connected",
     "Post attribution needs a Street Banker link. Connect ours to see which"
     " post did the work, or keep the service you already use.",
     "rollout", "rollouts", "Add link", "/rollout-studio"),
    ("no_quote", "quote", "Coverage with no quote",
     "These coverage items do not have a quote pulled out yet.",
     "item", "items", "Add quote", "/press-desk/coverage"),
]

MAP_W, MAP_H = 604, 306


def days_from(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RANGE
    return n if n in RANGES else DEFAULT_RANGE


def _fmt(n):
    return "{:,}".format(int(n or 0))


def _count(n, singular, plural):
    """"18 contacts", or "1 contact". Never a bare number."""
    n = int(n or 0)
    return "%s %s" % (_fmt(n), singular if n == 1 else plural)


# --- the cities ------------------------------------------------------------
# board_taxonomy.METROS is sixty metros with a real latitude and longitude,
# and it places every city his design names. The Fan Room's own lookup is
# the lower 48 only and cannot place four of them.

def _metro_coords():
    out = {}
    for _code, label, _region, aliases, lat, lon in board_taxonomy.METROS:
        for word in list(aliases) + [label.split(",")[0]]:
            out.setdefault(str(word).strip().lower(), (lat, lon))
    return out


_COORDS = _metro_coords()


def coords_for(city):
    """(lat, lon) for a contact's city, or None when the table has no such
    place. A city the table cannot place is never plotted, and the panel
    says how many were left off."""
    key = (city or "").strip().lower()
    return _COORDS.get(key)


def group_cities(rows):
    """[{city, country, count}] from contact records, largest first, plus
    how many records named no city at all. One group per city spelling,
    keeping the spelling the records use, because the map's links search
    the media list for exactly that word."""
    groups, order, blank = {}, [], 0
    for r in rows or ():
        city = (r.get("city") or "").strip()
        if not city:
            blank += 1
            continue
        key = city.lower()
        if key not in groups:
            groups[key] = {"city": city, "country": (r.get("country") or "").strip(),
                           "count": 0}
            order.append(key)
        groups[key]["count"] += 1
        if not groups[key]["country"]:
            groups[key]["country"] = (r.get("country") or "").strip()
    cities = [groups[k] for k in order]
    cities.sort(key=lambda c: (-c["count"], c["city"]))
    return cities, blank


# How far apart two dots must be before both may carry a name. Two of the
# largest cities are often neighbours (New York and Toronto, London and
# Berlin) and two names on one spot is mush. The unnamed one keeps its dot
# and its row in the ranked list beside the map; a dot is never moved off
# its coordinate to make room for a word.
LABEL_GAP = 78


def constellation(cities, labels=3):
    """The cities as a constellation: a dot per city sized by contacts, the
    largest few named, each joined to its nearest neighbours. There is no
    world basemap in this repository and this does not draw one, so the
    lines are drawing and the panel says so. Returns None when no city
    could be placed."""
    placed = []
    off_cities = off_contacts = 0
    for c in cities or ():
        ll = coords_for(c["city"])
        if ll is None:
            off_cities += 1
            off_contacts += int(c["count"] or 0)
            continue
        placed.append((c, ll))
    if not placed:
        return None
    # Equirectangular, then one scale for both axes so the cities keep
    # their places relative to each other, with room for the names.
    raw = [(((lon + 180.0) / 360.0) * MAP_W, ((90.0 - lat) / 180.0) * MAP_H)
           for _c, (lat, lon) in placed]
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    aspect = MAP_W / float(MAP_H)
    span_w = max(max(xs) - min(xs), MAP_W * .18)
    span_h = max(max(ys) - min(ys), MAP_H * .18)
    if span_w / span_h < aspect:
        span_w = span_h * aspect
    else:
        span_h = span_w / aspect
    span_w *= 1.4
    span_h *= 1.4
    x0 = (min(xs) + max(xs)) / 2.0 - span_w / 2.0
    y0 = (min(ys) + max(ys)) / 2.0 - span_h / 2.0
    k = MAP_W / span_w
    top = max(int(c["count"] or 0) for c, _ll in placed) or 1
    dots, named = [], []
    for (c, _ll), (px, py) in zip(placed, raw):
        x, y = (px - x0) * k, (py - y0) * k
        share = float(c["count"] or 0) / top
        name = (len(named) < labels
                and all(math.hypot(x - nx, y - ny) >= LABEL_GAP for nx, ny in named))
        if name:
            named.append((x, y))
        dots.append({"x": round(x, 1), "y": round(y, 1),
                     "r": round(3.0 + 5.0 * math.sqrt(share), 1),
                     "city": c["city"], "country": c["country"],
                     "count": int(c["count"] or 0), "label": name,
                     "right": x > MAP_W * .68})
    lines = set()
    for i, p in enumerate(dots):
        near = sorted((math.hypot(p["x"] - q["x"], p["y"] - q["y"]), j)
                      for j, q in enumerate(dots) if j != i)[:2]
        for _dist, j in near:
            lines.add((min(i, j), max(i, j)))
    return {"w": MAP_W, "h": MAP_H, "dots": dots,
            "lines": [(dots[a]["x"], dots[a]["y"], dots[b]["x"], dots[b]["y"])
                      for a, b in sorted(lines)],
            "off_cities": off_cities, "off_contacts": off_contacts}


# --- the page --------------------------------------------------------------

def stages(figures):
    out = []
    for key, name, fkey, singular, plural, empty in STAGES:
        n = int(figures.get(fkey) or 0)
        verb = _STAGE_VERB.get(key) or ""
        line = ("%s %s" % (_count(n, singular, plural), verb)).strip() if n else empty
        out.append({"key": key, "name": name, "line": line, "count": n})
    return out


def actions(figures):
    """His five rows, in his order, dropping the ones with nothing to act
    on. A zero is not an action (owner's zero rule)."""
    out = []
    for fkey, icon, title, desc, singular, plural, cta, href in ACTIONS:
        n = int(figures.get(fkey) or 0)
        if not n:
            continue
        if fkey == "no_link":
            href = figures.get("no_link_href") or href
        out.append({"icon": icon, "title": title, "desc": desc,
                    "figure": _count(n, singular, plural), "cta": cta,
                    "href": href})
    return out


def tile_status(key, state, kit_live=False):
    """(tone, text) for one closing tile: his pill, or the tile's own state
    when the account's record contradicts it."""
    if state == "hidden":
        return ("off", "Hidden")
    if state == "sample":
        return ("info", "Sample")
    if key == "press-desk":
        return ("gold", "All in one")
    if key == "epk":
        # His pill says Live. It says Live when the public kit link exists,
        # and says what is true when it does not.
        return ("good", "Live") if kit_live else ("off", "Not shared yet")
    return ("", "")


def build(figures, cards, days=DEFAULT_RANGE, showcase=False, artist_name="",
          kit_live=False):
    days = days_from(days)
    by_key = {c[0]: c for c in cards or ()}
    tiles = []
    for key in TILE_ORDER:
        card = by_key.get(key)
        if card is None:
            continue                      # switched off, or not this plan's
        _k, href, _icon, label, _desc, state = card
        tone, status = tile_status(key, state, kit_live)
        label, desc = TILE_COPY.get(key, (label, _desc))
        tiles.append({"key": key, "href": href, "label": label, "desc": desc,
                      "tone": tone, "status": status})
    cities = figures.get("cities") or []
    return {
        "showcase": showcase,
        "artist_name": artist_name,
        "days": days,
        "ranges": RANGES,
        "visits": int(figures.get("visits") or 0),
        "visits_label": _fmt(figures.get("visits")),
        "clicks": int(figures.get("clicks") or 0),
        "clicks_label": _fmt(figures.get("clicks")),
        "presaves": int(figures.get("presaves") or 0),
        "presaves_label": _fmt(figures.get("presaves")),
        "stages": stages(figures),
        "actions": actions(figures),
        "cities": cities,
        "contacts": int(figures.get("contacts") or 0),
        "no_city": int(figures.get("no_city") or 0),
        "map": constellation(cities),
        "tiles": tiles,
    }


# --- reading one account ---------------------------------------------------

def _window(now, days):
    from datetime import timedelta
    return (now - timedelta(days=days_from(days))).isoformat(timespec="seconds")


def for_account(user_id, days=DEFAULT_RANGE, now=None):
    """Every figure on the page for one real account, from its own rows
    only. The three hero figures are the chosen window; everything else is
    the whole record."""
    from datetime import datetime, timezone

    import db as store
    now = now or datetime.now(timezone.utc)
    cutoff = _window(now, days)
    with store.get_db() as db:
        def one(sql, *params):
            row = db.execute(sql, (user_id,) + params).fetchone()
            return int((row[0] if row else 0) or 0)

        windowed = {r["event_type"]: int(r["n"] or 0) for r in db.execute(
            "SELECT e.event_type, COUNT(*) AS n FROM ml_events e"
            " JOIN ml_campaigns c ON c.id = e.campaign_id"
            " WHERE c.user_id = ? AND e.created >= ?"
            " GROUP BY e.event_type", (user_id, cutoff)).fetchall()}
        figures = {
            "visits": windowed.get(EVENT_VISIT, 0),
            "clicks": windowed.get(EVENT_CLICK, 0),
            "presaves": windowed.get(EVENT_PRESAVE, 0),
            # the rail: the record, not the window
            "visits_all": one(
                "SELECT COUNT(*) FROM ml_events e JOIN ml_campaigns c"
                " ON c.id = e.campaign_id WHERE c.user_id = ?"
                " AND e.event_type = ?", EVENT_VISIT),
            "ready": one("SELECT COUNT(*) FROM press_releases"
                         " WHERE user_id = ? AND status = 'ready'"),
            "sent": one("SELECT COUNT(*) FROM press_pitches"
                        " WHERE user_id = ? AND sent_at != ''"),
            "opens": one("SELECT COALESCE(SUM(open_count), 0)"
                         " FROM press_recipients WHERE user_id = ?"),
            "coverage": one("SELECT COUNT(*) FROM press_coverage WHERE user_id = ?"),
            # the actions
            "never-pitched": one(
                "SELECT COUNT(*) FROM press_contacts c WHERE c.user_id = ?"
                " AND c.status = 'active' AND NOT EXISTS ("
                "  SELECT 1 FROM press_recipients r WHERE r.contact_id = c.id"
                "  AND r.user_id = c.user_id AND r.status != 'prepared')"),
            "unsent": one(
                "SELECT COUNT(*) FROM press_releases r WHERE r.user_id = ?"
                " AND r.status = 'ready' AND NOT EXISTS ("
                "  SELECT 1 FROM press_pitches p WHERE p.release_id = r.id"
                "  AND p.user_id = r.user_id AND p.sent_at != '')"),
            "silent": one(
                "SELECT COUNT(*) FROM press_pitches p WHERE p.user_id = ?"
                " AND EXISTS (SELECT 1 FROM press_recipients r"
                "  WHERE r.pitch_id = p.id AND r.open_count > 1)"
                " AND NOT EXISTS (SELECT 1 FROM press_coverage cv"
                "  WHERE cv.user_id = p.user_id AND cv.release_id = p.release_id)"),
            "no_link": one(
                "SELECT COUNT(*) FROM ro_campaigns WHERE user_id = ?"
                " AND (ml_campaign_id IS NULL OR ml_campaign_id = '')"),
            "no_quote": one("SELECT COUNT(*) FROM press_coverage"
                            " WHERE user_id = ? AND TRIM(quote) = ''"),
        }
        row = db.execute(
            "SELECT id FROM ro_campaigns WHERE user_id = ?"
            " AND (ml_campaign_id IS NULL OR ml_campaign_id = '')"
            " ORDER BY created DESC LIMIT 1", (user_id,)).fetchone()
        figures["no_link_href"] = "/rollout-studio/%s" % row[0] if row else ""
        contacts = [dict(r) for r in db.execute(
            "SELECT city, country FROM press_contacts WHERE user_id = ?",
            (user_id,)).fetchall()]
    figures["contacts"] = len(contacts)
    figures["cities"], figures["no_city"] = group_cities(contacts)
    return figures


# --- the showcase ----------------------------------------------------------
# His own example figures, for the demo account and nobody else. An
# in-memory literal in the same shape for_account() returns, exactly as
# fan_audience.SHOWCASE_REGIONS is: nothing is written to the database,
# and the route is the only thing that decides who is shown these.

# (visits, clicks, pre-saves) per window. His drawing is the 30-day view,
# and the example's whole history sits inside those thirty days, so the
# rail's Heard is the same 12,480 his design draws.
SHOWCASE_WINDOWS = {7: (2960, 510, 92), 30: (12480, 2140, 386), 90: (12480, 2140, 386)}
SHOWCASE_CITIES = [("Toronto", "CA", 28), ("New York", "US", 124),
                   ("London", "GB", 96), ("Berlin", "DE", 64),
                   ("Los Angeles", "US", 86), ("Nashville", "US", 42),
                   ("Sydney", "AU", 38)]
SHOWCASE_RAIL = {"ready": 3, "sent": 2, "opens": 47, "coverage": 6}
SHOWCASE_ACTIONS = {"never-pitched": 18, "unsent": 3, "silent": 5,
                    "no_link": 2, "no_quote": 4}


def showcase(days=DEFAULT_RANGE):
    days = days_from(days)
    visits, clicks, presaves = SHOWCASE_WINDOWS[days]
    cities = [{"city": c, "country": k, "count": n} for c, k, n in SHOWCASE_CITIES]
    cities.sort(key=lambda c: (-c["count"], c["city"]))
    figures = {"visits": visits, "clicks": clicks, "presaves": presaves,
               "visits_all": SHOWCASE_WINDOWS[30][0],
               "cities": cities, "no_city": 0,
               "contacts": sum(c["count"] for c in cities),
               "no_link_href": "/rollout-studio"}
    figures.update(SHOWCASE_RAIL)
    figures.update(SHOWCASE_ACTIONS)
    return figures
