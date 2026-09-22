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
                    drawn as a zero, and so is a row whose destination
                    this reader would be turned away from
  the map           media contacts by city and country, a constellation of
                    the cities the contact records name. There is no
                    basemap in this repository, so the panel draws dots
                    and lines on the bare panel exactly as the Fan Room
                    does, and the lines are drawing, not distance. A city
                    is placed only where the metro table's own country
                    agrees with the record's; anything else is left off
                    and counted in the footnote
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
#
# A metro carries no country column, so its country is read off its own row:
# every us- region is the United States and the ca region is Canada, and
# everywhere else the label's own suffix says it ("London, UK", "Dublin, IE",
# "Sydney, AU"). Both halves of the comparison are folded to a two-letter
# code first, so a record that says "United Kingdom" and a metro that says
# UK are the same country (honesty review, 2026-09-21).
COUNTRY_CODES = {
    "us": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US", "america": "US",
    "united states": "US", "united states of america": "US",
    "ca": "CA", "can": "CA", "canada": "CA",
    "gb": "GB", "uk": "GB", "u.k.": "GB", "great britain": "GB",
    "united kingdom": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "ie": "IE", "irl": "IE", "ireland": "IE",
    "de": "DE", "deu": "DE", "germany": "DE", "deutschland": "DE",
    "fr": "FR", "fra": "FR", "france": "FR",
    "nl": "NL", "nld": "NL", "netherlands": "NL", "holland": "NL",
    "au": "AU", "aus": "AU", "australia": "AU",
    "mx": "MX", "mex": "MX", "mexico": "MX", "méxico": "MX",
}


def country_code(value):
    """A contact's or a metro's country as one code, or "" when the record
    names none. An unknown spelling is left as it is, upper-cased, so it can
    still disagree with a metro rather than quietly matching one."""
    key = (value or "").strip().lower().rstrip(".")
    if not key:
        return ""
    return COUNTRY_CODES.get(key) or COUNTRY_CODES.get(key + ".") or key.upper()


def _metros():
    """{alias: metro} for every spelling board_taxonomy knows, so the six
    spellings of one place (new york, nyc, brooklyn, manhattan, queens, ny)
    resolve to one metro with one name, one country and one pair of
    coordinates."""
    out = {}
    for code, label, region, aliases, lat, lon in board_taxonomy.METROS:
        if region.startswith("us-"):
            country = "US"
        elif region == "ca":
            country = "CA"
        else:
            country = country_code(label.rsplit(",", 1)[-1])
        metro = {"code": code, "city": label.split(",")[0].strip(),
                 "country": country, "lat": lat, "lon": lon}
        for word in list(aliases) + [metro["city"]]:
            out.setdefault(str(word).strip().lower(), metro)
    return out


_METROS = _metros()


def metro_for(city, country=""):
    """The metro a contact's city names, or None.

    None when the table has no such place, and None when it has one whose
    own country is not the country on the record: London, Ontario is not
    London, England, and a Birmingham contact in the UK is not the one in
    Alabama. A record that names no country contradicts nothing, so it is
    placed. Anything that does not agree is left off the map and counted in
    the footnote, because a dot in the wrong hemisphere is worse than an
    honest omission (honesty review, 2026-09-21).
    """
    metro = _METROS.get((city or "").strip().lower())
    if metro is None:
        return None
    want = country_code(country)
    if want and want != metro["country"]:
        return None
    return metro


def coords_for(city, country=""):
    """(lat, lon) for a contact's city, or None when the table has no such
    place or its place is in another country. A city the table cannot place
    is never plotted, and the panel says how many were left off."""
    metro = metro_for(city, country)
    return (metro["lat"], metro["lon"]) if metro else None


def group_cities(rows):
    """[{city, country, count, q}] from contact records, largest first, plus
    how many records named no city at all.

    One group per city AND country, which is what the panel's footnote says
    it does. A city the metro table knows is grouped by that metro, so
    "New York", "NYC" and "Brooklyn" are one row under the metro's own name
    instead of three rows and three dots on one spot; a city it does not
    know keeps the spelling the records use. q is what the row's link
    searches the media list for: the one spelling the records hold, and
    nothing when the group gathered several or when another group holds the
    same spelling (London, Ontario beside London, England), so the link
    never opens a list that disagrees with the number beside it.
    """
    groups, order, blank = {}, [], 0
    for r in rows or ():
        city = (r.get("city") or "").strip()
        country = (r.get("country") or "").strip()
        if not city:
            blank += 1
            continue
        metro = metro_for(city, country)
        if metro is not None:
            key = ("metro", metro["code"])
            name, code = metro["city"], metro["country"]
        else:
            key = ("as-written", city.lower(), country_code(country))
            name, code = city, country_code(country)
        if key not in groups:
            groups[key] = {"city": name, "country": code, "count": 0,
                           "metro": metro is not None, "spellings": {}}
            order.append(key)
        g = groups[key]
        g["count"] += 1
        g["spellings"][city] = g["spellings"].get(city, 0) + 1
    shared = {}
    for key in order:
        for word in groups[key]["spellings"]:
            shared[word.lower()] = shared.get(word.lower(), 0) + 1
    cities = []
    for key in order:
        g = groups.pop(key)
        spellings = list(g.pop("spellings"))
        one = spellings[0] if len(spellings) == 1 else ""
        g["q"] = one if one and shared.get(one.lower(), 0) == 1 else ""
        cities.append(g)
    cities.sort(key=lambda c: (-c["count"], c["city"]))
    return cities, blank


# When two dots may both carry a name. Two of the largest cities are often
# neighbours (New York and Toronto, London and Berlin) and two names on one
# spot is mush. The unnamed one keeps its dot and its row in the ranked list
# beside the map; a dot is never moved off its coordinate to make room for a
# word.
#
# The rule is compared as rendered boxes, not as a distance in viewBox units
# (honesty review, 2026-09-21). A label is a fixed block of 13px type
# whatever the panel does, so a gap of 78 viewBox units is 78 screen pixels
# on a 604px panel and 33 on a 254px one, and at 320px New York and London
# were measured overlapping on both axes. So each name is given the box it
# will really occupy at MIN_LABEL_PANEL, the narrowest panel allowed to
# carry more than one name, and a name whose box meets a box already drawn
# is not drawn. Below that width the stylesheet draws the first name only,
# and it asks the panel rather than the viewport because the panel is 254px
# wide at a 320px viewport and 319px wide at 1181px, where the room turns
# two-column: viewport width cannot answer this question.
MIN_LABEL_PANEL = 420      # CSS px, the panel; marketing-room.css's @container
LABEL_CHAR_PX = 8.4        # one character of the 13.5px name line, measured
LABEL_MAX_PX = 120         # .mk-map-label's own cap
LABEL_H_PX = 34            # the two lines at 13.5px and 13px, measured 33
LABEL_OFFSET_PX = 14       # .mk-map-label's translate away from the dot


def _label_box(x, y, chars, right):
    """The box a name will occupy, in viewBox units, at the narrowest panel
    that draws more than one. Wider than the text really is, never
    narrower, so the guarantee holds for every name."""
    per = MAP_W / float(MIN_LABEL_PANEL)          # viewBox units per CSS px
    w = min(LABEL_MAX_PX, 2.0 + LABEL_CHAR_PX * chars) * per
    h = LABEL_H_PX * per
    off = LABEL_OFFSET_PX * per
    x0 = x - off - w if right else x + off
    return (x0, y - h / 2.0, x0 + w, y + h / 2.0)


def _boxes_meet(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def constellation(cities, labels=3):
    """The cities as a constellation: a dot per city sized by contacts, the
    largest few named, each joined to its nearest neighbours. There is no
    world basemap in this repository and this does not draw one, so the
    lines are drawing and the panel says so. Returns None when no city
    could be placed."""
    placed = []
    off_cities = off_contacts = 0
    for c in cities or ():
        ll = coords_for(c["city"], c.get("country") or "")
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
        count = int(c["count"] or 0)
        right = x > MAP_W * .68
        box = _label_box(x, y, max(len(c["city"]), len(_fmt(count))), right)
        name = (len(named) < labels
                and not any(_boxes_meet(box, drawn) for drawn in named))
        if name:
            named.append(box)
        dots.append({"x": round(x, 1), "y": round(y, 1),
                     "r": round(3.0 + 5.0 * math.sqrt(share), 1),
                     "city": c["city"], "country": c["country"],
                     "q": c.get("q") or "", "count": count, "label": name,
                     "right": right})
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

# --- THE PLATE --------------------------------------------------------
# static/img/marketing-plate.webp, 1859x846: a BROADCAST unit, one tall
# window beside a 2x2 grid. Each window is (x, y, w, h) as a PERCENTAGE
# of the plate, MEASURED off the file with PIL. RE-MEASURE ALL OF THEM if
# the plate is ever regenerated or re-cropped.
#
# The plate silkscreens THE STORY, READY, SENT HERE, VIEWS and COVERAGE,
# so the markup never prints those words.
#
# TWO LABELS THE AUDIT CHANGED BEFORE THE PLATE WAS EVER RENDERED:
#   SENT HERE, not "pitched". press_pitches.sent_at is written in exactly
#   one place - the platform's own send loop - so a pitch posted from the
#   artist's own inbox never lands here. The window is scoped to what
#   Street Banker sent, and says so.
#   VIEWS, not "opens". press_store.mark_opened fires when a journalist
#   LOADS the announcement page; it is not an email open, and a window
#   marked OPENS would be read as one every time.
PLATE = {
    "story":    (5.11, 19.03, 25.34, 63.24),
    "ready":    (33.35, 19.03, 29.69, 22.46),
    "sent":     (65.90, 19.03, 28.94, 22.46),
    "opens":    (33.35, 58.98, 29.69, 23.29),
    "coverage": (65.90, 59.10, 28.94, 23.17),
}
# The order the silkscreen prints them: left to right, top row first.
PLATE_ORDER = (
    ("ready", "Ready", "announcements ready to send"),
    ("sent", "Sent here", "pitches Street Banker sent"),
    ("opens", "Views", "reads of your announcement page"),
    ("coverage", "Coverage", "pieces you have logged"),
)


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# --- THE STANDBY DISPLAY, the owner's way (2026-09-22) -------------------
# "Slot machine-y": the big window sequences the room's FEATURES, each
# frame cutting in large and glitching out to the next; the small windows
# each do a different thing - icons rolling like a reel, a hint that
# changes, the feature names ticking through - and never carry a caption.
# One voice, phosphor green: the plate's own screen.
#
# The frames name cards that exist in rooms.ROOMS for this room, by what
# they actually do. The owner supplies the final text per room at the
# audit; until then nothing here claims more than the card does.
# WORDS ONLY - never a figure, not even an example one.
STANDBY_FRAMES = [('Press Desk', 'Write it once, pitch it to your list'), ('Smart Links', 'One link on every platform, every visit counted'), ('Announcements', 'Ready to send, or already out'), ('Referrals', 'A link that brings the next artist in')]
STANDBY_REELS = [('ready', 'Ready', ('press-desk', 'pitched', 'opened', 'covered', 'heard')), ('coverage', 'Coverage', ('announcement', 'link', 'referrals', 'epk', 'calendar'))]
STANDBY_TIPS = ('sent', 'Sent here', ['Write it once in the Press Desk', 'Pitch your list from here', 'A view is a journalist reading', 'Log coverage when it lands'])
STANDBY_TICKER = ('opens', 'Views', ['Press Desk', 'Smart Links', 'Rollout', 'Referrals', 'EPK'])
STANDBY_CINE = ('story', 'The story')
STANDBY_SIZE = ('clamp(20px, 3.4cqw, 52px)', 'clamp(10px, 1.15cqw, 16px)')
# One picture per frame, generated by the owner; a missing file draws
# nothing rather than a broken image. The ?v moves when one is replaced.
STANDBY_IMAGES = tuple("static/img/standby/marketing-%d.webp" % n for n in (1, 2, 3, 4))
STANDBY_IMAGE_V = 1


def _standby_image(n):
    import os
    path = STANDBY_IMAGES[n] if n < len(STANDBY_IMAGES) else ""
    return "/%s?v=%d" % (path, STANDBY_IMAGE_V) if path and os.path.exists(path) else ""


def standby():
    """The plate with nothing measured: a sequence, reels, a hint, a ticker."""
    key, name = STANDBY_CINE
    size, line = STANDBY_SIZE
    out = {
        "cine": {"box": box(key), "name": name, "size": size, "line": line},
        "frames": [{"n": i, "title": t, "line": l, "image": _standby_image(i)}
                   for i, (t, l) in enumerate(STANDBY_FRAMES)],
        "count": len(STANDBY_FRAMES),
        "reels": [{"box": box(k), "name": n, "icons": icons, "n": i}
                  for i, (k, n, icons) in enumerate(STANDBY_REELS, start=1)],
        "tips": None, "ticker": None,
    }
    if STANDBY_TIPS:
        k, n, lines = STANDBY_TIPS
        out["tips"] = {"box": box(k), "name": n, "lines": lines, "count": len(lines)}
    if STANDBY_TICKER:
        k, n, lines = STANDBY_TICKER
        out["ticker"] = {"box": box(k), "name": n, "lines": lines}
    return out


def plate_windows(figures):
    """The four small readings. A count is a count: 0 here is measured -
    we looked at the table and found nothing - so it prints as a figure."""
    out = []
    for key, name, sub in PLATE_ORDER:
        out.append({"key": key, "name": name, "sub": sub, "box": box(key),
                    "value": _fmt(int((figures or {}).get(key) or 0))})
    return out


def story(figures):
    """THE STORY: the newest announcement on file, or the words that say
    there is none. Never an invented headline."""
    row = (figures or {}).get("story")
    if not row:
        return None
    # headline is optional on the table and title is the required one,
    # so the window falls back rather than printing an empty pane.
    said = (row.get("headline") or "").strip() or (row.get("title") or "").strip()
    return {"headline": said or "Untitled announcement",
            "status": (row.get("status") or "draft").strip(),
            "box": box("story")}


def stages(figures):
    out = []
    for key, name, fkey, singular, plural, empty in STAGES:
        n = int(figures.get(fkey) or 0)
        verb = _STAGE_VERB.get(key) or ""
        line = ("%s %s" % (_count(n, singular, plural), verb)).strip() if n else empty
        out.append({"key": key, "name": name, "line": line, "count": n})
    return out


def actions(figures, can_open=None):
    """His five rows, in his order, dropping the ones with nothing to act
    on. A zero is not an action (owner's zero rule).

    can_open(href) drops a row this reader would be turned away from. A
    team seat given Marketing and not Releases is refused at the rollout
    page, and a button that bounces the person who presses it is worse
    than no button (honesty review, 2026-09-21).
    """
    out = []
    for fkey, icon, title, desc, singular, plural, cta, href in ACTIONS:
        n = int(figures.get(fkey) or 0)
        if not n:
            continue
        if can_open is not None and not can_open(href):
            continue
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
        # His pill says Live. Against "Not shared yet", Live means shared,
        # so it waits for a kit the artist has actually saved: the public
        # address alone is minted by a plain page view (app.py
        # _ensure_epk_slug), and on some accounts without one being opened
        # at all (honesty review, 2026-09-21).
        return ("good", "Live") if kit_live else ("off", "Not shared yet")
    return ("", "")


def build(figures, cards, days=DEFAULT_RANGE, showcase=False, artist_name="",
          kit_live=False, can_open=None):
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
        # The plate: the four funnel readings, and the newest announcement.
        "windows": plate_windows(figures),
        "story": story(figures),
        "story_box": box("story"),
        # Nothing written, sent, opened or logged: the unit introduces
        # the Press Desk rather than printing four zeroes.
        "idle": not any(int((figures or {}).get(k) or 0)
                        for k in ("ready", "sent", "opens", "coverage"))
                and not (figures or {}).get("story"),
        "standby": standby(),
        "actions": actions(figures, can_open),
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
            # THE STORY: the newest announcement on file, whatever its
            # state. One row, so the plate's tall window has something
            # true in it rather than a decorative pane.
            "story": (lambda r: dict(r) if r else None)(
                db.execute("SELECT title, headline, status FROM press_releases"
                           " WHERE user_id = ? ORDER BY updated DESC LIMIT 1",
                           (user_id,)).fetchone()),
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
    cities = [{"city": c, "country": k, "count": n, "q": c}
              for c, k, n in SHOWCASE_CITIES]
    cities.sort(key=lambda c: (-c["count"], c["city"]))
    figures = {"visits": visits, "clicks": clicks, "presaves": presaves,
               "visits_all": SHOWCASE_WINDOWS[30][0],
               "cities": cities, "no_city": 0,
               "contacts": sum(c["count"] for c in cities)}
    figures.update(SHOWCASE_RAIL)
    figures.update(SHOWCASE_ACTIONS)
    return figures
