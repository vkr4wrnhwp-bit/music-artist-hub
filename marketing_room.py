"""The Marketing Room: the Marketing room's opening screen (owner's design,
2026-09-21), built as the Fan Room's sibling.

The layout is his. Every figure is this account's own records, and a figure
the records cannot support is said in words rather than drawn:

  the hero band     visits, clicks and pre-saves from ml_events, joined to
                    this account's campaigns and filtered on the event's
                    own timestamp, so the range chooser governs all three
                    and the band says so. It does not read the ml_fans
                    counters total_visits and total_clicks: those count
                    only what a known fan did (fan_mail), and the band is
                    every view and click, known or not
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
     # "Connect a link", not "Add link": the finding is a rollout with
     # no link CONNECTED, and "Add" read as "make me a new smart link"
     # (owner, 2026-09-22).
     "rollout", "rollouts", "Connect a link", "/rollout-studio"),
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

# --- THE RACK (owner, 2026-09-23) ---------------------------------------
# The working room draws the rooms' shared three-window plate
# (partials/cc_rack.html over static/img/room-plate.webp), as every room
# but Studio does. The owner approved three screens: Ready, Sent and
# Coverage. The plate prints no names, so each screen says what it is,
# and a count with nothing in it is the words "None yet", never a 0.
#
# The old BROADCAST plate (marketing-plate.webp) had five windows. The
# other two are kept, not dropped:
#   THE STORY, its tall window - the newest announcement on file - is its
#   own panel directly under the rack (story()).
#   VIEWS has no screen now; its figure rides on the Sent screen's line.
#
# TWO WORDS THE AUDIT CHOSE BEFORE THE OLD PLATE WAS EVER RENDERED, and
# the screens keep both:
#   Sent is what STREET BANKER sent, and its line says so.
#   press_pitches.sent_at is written in exactly one place - the platform's
#   own send loop - so a pitch posted from the artist's own inbox is not
#   in it.
#   VIEWS, not "opens". press_store.mark_opened fires when a journalist
#   LOADS the announcement page; it is not an email open, and a figure
#   called opens would be read as one every time. The foot line under the
#   rack says what a view is.
NONE_YET = "None yet"
# (figure key, the screen's name, its line for one, its line for several)
RACK = (
    ("ready", "Ready", "Announcement ready to send", "Announcements ready to send"),
    ("sent", "Sent", "Pitch Street Banker sent", "Pitches Street Banker sent"),
    ("coverage", "Coverage", "Piece you have logged", "Pieces you have logged"),
)


# --- THE PAGE FROM ZERO (owner's Marketing spec + mockup, 2026-09-23) -----
# An account with no campaign, no link event, no press activity and no
# contact does not meet a 30-day filter, empty figures, a press funnel,
# a contact-city report or a recommendation. It meets an onboarding
# page: the Command Center's photographed three-screen plate drawn
# STATIC with this room's words, one card that opens the campaign
# builder, the four areas as doors, the five-step workflow as education,
# the two empties in words, help, and the tools in a drawer that starts
# open. Results begin only after something is sent or published, and
# nothing here counts a draft as reach. The animated standby that used to
# run on the plate is retired here.
ZERO_SUBTITLE = "Plan the message, reach the right people, and know what to do next."
ZERO_RACK = (
    ("Purpose", "Turn one clear story into coordinated outreach."),
    ("Start here", "Choose what you want people to do."),
    ("Good to know", "Results begin only after something is sent or published."),
)
# The one door: the campaign builder, whose first question IS the goal
# (its campaign types: a release, a pre-save, a fan hub, a download gate,
# a reward, a tour page, a merch drop, a contest), carrying the way back.
DOOR = "/links/new?returnTo=/room/marketing&from=marketing-zero-state"
ZERO_PROJECT = {
    "heading": "Start with one goal",
    "title": "Choose your first marketing goal",
    "desc": ("Promote a release, announce news, grow your audience, or pitch the "
             "media. Street Banker will show only the tools that fit."),
    "cta": "Start planning",
    "compare": "Compare campaign goals",
    # A seat that may not write here is told who plans campaigns rather
    # than handed a door that bounces.
    "locked": ("Campaigns are planned by the account owner or a seat with edit "
               "access. Marketing opens here once one exists."),
}
# The goal choices (spec section 4), shown in place when "Compare
# campaign goals" is opened: each goal and the smallest useful toolset.
GOALS = (
    ("Promote a release", "Release rollout, Smart Link, announcement, media pitch, content, fan outreach."),
    ("Announce news", "An announcement, EPK assets, media contacts, press pitches, your own channels."),
    ("Grow the audience", "Smart Links, fan capture, content, and audience-building tools."),
    ("Pitch the media", "Press Desk, announcement, contacts, pitches, coverage tracking."),
    ("Promote a show", "Ticket links, the local audience, city media, content, and Stage."),
)
# The four areas (spec section 6). Each is a door: by its own room card
# where one exists, else by the page's address; a seat that cannot open
# the page gets the words alone.
LENSES = (
    ("plans", "Campaign plans",
     "Goal, subject, audience, message, call to action, channels, schedule, owner, next action.",
     "/links/new"),
    ("press", "Press & media",
     "Press Desk, announcements, contacts, pitches, responses, EPK, and coverage.",
     "press-desk"),
    ("links", "Smart links & fan capture",
     "Destination links, visits, clicks, confirmed pre-saves, and consent-aware fan capture.",
     "links"),
    ("content", "Content & rollout",
     "Assets, captions, approvals, scheduled content, milestones, and completion status.",
     "/rollout-studio"),
)
# The five steps, EDUCATIONAL on a new account: Choose goal lit, the rest
# neutral, numbered as the owner's mockup numbers them, no percentage.
# STAGES (the press funnel) stays the populated room's rail.
WORKFLOW = (
    ("goal", "Choose goal", "Define the outcome"),
    ("subject", "Pick subject", "Release, show, or story"),
    ("prepare", "Prepare", "Message & assets"),
    ("activate", "Activate", "Choose channels"),
    ("learn", "Learn", "Review real results"),
)
ZERO_PLAN = ("Your campaign plan will appear here",
             "Each campaign will show its audience, message, channels, schedule, and next action.")
ZERO_RESULTS = ("No results are measured yet",
                "Drafts and scheduled work are not counted as reach. Results appear after "
                "publishing or sending.")
ZERO_HELP = ("Not sure what to market first?",
             "Ask Street Banker to choose the smallest useful campaign for your goal.")
# What a campaign needs before it is activated (spec sections 8 and 9),
# shown in place as the "Marketing checklist".
CHECKLIST = ("One primary message",
             "One primary call to action: listen, pre-save, buy tickets, join the fan list, "
             "read the announcement, view the EPK, or reply",
             "An audience you may contact, with its consent basis recorded",
             "A channel, and what Street Banker sends on it versus what you finish elsewhere",
             "Your confirmation before anything is sent, published, scheduled, or exported")
# The link under "Your campaign plan will appear here": the workflow on
# this page says how campaigns work. The spec's second link, the
# Marketing checklist, is the details right under it, opened in place -
# one control, not a link and a summary to the same list.
ZERO_LINKS = (("How campaigns work", "#mk-z-flow-h"),)
CHECKLIST_LABEL = "Marketing checklist"
# The drawer at the foot: the room's tools by their cards, under the
# spec's areas; Referrals under its own heading as the spec places it.
ZERO_BANDS = (
    ("Press & media", ("press-desk", "epk")),
    ("Smart links & fan capture", ("links",)),
    ("Referrals", ("referrals",)),
)
# The sentence the room carries back from the builder.
DONE_LINE = ("Your first campaign is planned. Marketing will show its results once "
             "something is sent or published.")
# Every count the room reads. Any of them above zero is activity.
_COUNTS = ("visits", "clicks", "presaves", "visits_all", "ready", "sent", "opens",
           "coverage", "contacts", "no_city", "no_link", "never-pitched", "unsent",
           "silent", "no_quote")


def new_account(figures, campaigns):
    """The spec's new_account: no campaign, and nothing counted on any
    figure the room reads - no link event, no announcement, no pitch, no
    coverage, no contact, no rollout waiting on a link, no story. The
    arguments are what the stores returned; an unreadable store never
    reaches here - the route shows the error page."""
    figures = figures or {}
    if campaigns:
        return False
    if figures.get("story") or figures.get("cities"):
        return False
    return not any(int(figures.get(k) or 0) for k in _COUNTS)


def done_line(came_from, campaigns):
    """Said by the SAVED campaign, never by the param alone."""
    return DONE_LINE if came_from == "marketing-zero-state" and campaigns > 0 else ""


def _door(cards, key_or_href, can_open=None):
    """A door by a room card, or by an address; '' when the seat cannot
    open it or the card is not this account's."""
    if key_or_href.startswith("/"):
        href = key_or_href
    else:
        card = (cards or {}).get(key_or_href)
        if not card:
            return ""
        href = card[1] if len(card) > 5 else card[0]
    if can_open and not can_open(href):
        return ""
    return href


def zero_page(can_add=True, can_open=None, cards=None):
    """The page from zero. `cards` is rooms.build's list of card tuples
    (key, href, icon, label, desc, state), as the room hands them; a seat
    sees only the doors it can open."""
    by = {c[0]: c for c in cards or ()}
    lenses = [{"key": k, "name": n, "line": l, "href": _door(by, d, can_open)}
              for k, n, l, d in LENSES]
    bands = []
    for title, keys in ZERO_BANDS:
        got = []
        for key in keys:
            card = by.get(key)
            if not card:
                continue
            href = card[1]
            if can_open and not can_open(href):
                continue
            label, desc = TILE_COPY.get(key, (card[3], card[4]))
            # The owner's mark on a page they hid stays on the tile here as
            # it does on the populated room (rooms.build keeps a hidden
            # page for the owner alone); nothing else is judged from zero.
            got.append({"key": key, "href": href, "label": label, "desc": desc,
                        "state": card[5] if len(card) > 5 else ""})
        if got:
            bands.append({"title": title, "tiles": got})
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "door": DOOR,
        "project": dict(ZERO_PROJECT, can=can_add),
        "goals": GOALS,
        "checklist": CHECKLIST,
        "checklist_label": CHECKLIST_LABEL,
        "lenses": lenses,
        "workflow": WORKFLOW,
        "plan": ZERO_PLAN,
        "results": ZERO_RESULTS,
        "help": ZERO_HELP,
        "links": ZERO_LINKS,
        "bands": bands,
    }


def standby():
    """The animated standby that once ran on an empty account is retired:
    that account meets the page from zero instead. Nothing on the
    populated plate reads this any more; it stays for the build()
    contract."""
    return {"fill": []}


def rack_screens(figures):
    """The working room's three screens on the rooms' shared plate: Ready,
    Sent, Coverage, each a count over this account's own rows. Nothing
    counted is the words None yet (owner's zero rule), never a 0. Views of
    the announcement page, which lost their window, ride on Sent's line
    in words of their own."""
    figures = figures or {}
    out = []
    for key, name, one, several in RACK:
        n = int(figures.get(key) or 0)
        sub = one if n == 1 else several
        if key == "sent":
            views = int(figures.get("opens") or 0)
            sub += " · " + (_count(views, "view", "views") if views else "no views yet")
        out.append({"k": name, "v": _fmt(n) if n else NONE_YET,
                    "fig": bool(n), "none": not n, "sub": sub})
    return out


def story(figures):
    """THE STORY: the newest announcement on file, or the words that say
    there is none. Never an invented headline. It was the old plate's tall
    window; it is its own panel under the rack now."""
    row = (figures or {}).get("story")
    if not row:
        return None
    # headline is optional on the table and title is the required one,
    # so the panel falls back rather than printing an empty line.
    said = (row.get("headline") or "").strip() or (row.get("title") or "").strip()
    return {"headline": said or "Untitled announcement",
            "status": (row.get("status") or "draft").strip()}


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
          kit_live=False, can_open=None, zero=None, can_add=True):
    """`zero` is new_account() decided by the route (None here means: the
    old rule, nothing in the press funnel); `can_add` is who may plan a
    campaign (see zero_page)."""
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
        # The rack: the three funnel screens (views on Sent's line), and
        # under it the newest announcement in its own panel.
        "screens": rack_screens(figures),
        "story": story(figures),
        # Nothing on any count: the page from zero. One campaign, event,
        # announcement or contact and the room takes over untouched.
        "idle": bool(zero) if zero is not None else (
            not any(int((figures or {}).get(k) or 0) for k in ("ready", "sent", "opens", "coverage"))
            and not (figures or {}).get("story")),
        "zero": zero_page(can_add, can_open, cards) if zero else None,
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
