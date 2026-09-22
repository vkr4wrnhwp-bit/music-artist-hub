"""The eight rooms: the sidebar as a map, each room a screen of cards.

Owner, 2026-09-15, by numbered mockup: Command Center and Actions stay at
the top as plain rows; then eight rooms - Fans, Studio, Stage, Analytics,
Business, Publishing, Releases, Marketing; the account group under them.
Clicking a room's name opens its screen, a grid of icon-and-title cards,
one per feature. The chevron expands the room in place, one click to
any of its pages. No double tabs: a page that was a tab of another page
is its own card here (Files and Contracts, Catalog and Track Passports,
Press and its Press Kit), so nothing hides inside something else.

This is a LAYOUT over the same definitions the hub sidebar reads
(hubs.HUBS and the groups). Every key, address, live flag and page
switch is the one the hubs use; a room only says where a card sits.
Rooms are on when the owner switches the layout in Settings, or when
the deployment sets NAV_ROOMS=1 (staging first, owner, 2026-09-15).
"""
import os

import hubs
import page_switches

ROOMS = [
    ("fans", "Fans", "The people who follow you and what they get.",
     ["fans", "fan-crm", "fan-club", "discover", "marketplace",
      # Apparel & Merch is parked here, not placed here. It left the
      # Marketing room on 2026-09-17 because the owner is taking merch to
      # Artifacts, and Artifacts has no page yet; a card in no room is an
      # address with no door, so it waits in the room whose people buy
      # merch. It is switched off in Settings > Pages meanwhile, so nobody
      # but an owner sees it. When Artifacts lands it moves there.
      "apparel"]),
    ("studio", "Studio", "Making the record and keeping its files.",
     # Release-Ready sits beside The Rack (owner's brief, 2026-09-19): the
     # Rack is mixing and mastering by hand in the browser, Release-Ready is
     # RoEx's check, previews and the finished master.
     # The Vault and its Contracts view left for Business (owner,
     # 2026-09-22): the paperwork that proves who gets paid is business,
     # not making the record. Artwork stays - cover art is made here.
     # Motion left this room on 2026-09-22 (owner: "motion needs to come out
     # of the studio room"). It is its own app on its own service and was
     # already on the suites strip; a card here as well made it look like a
     # page of Street Banker, which it is not.
     ["audio-studio", "rack", "release-ready", "remix-lab", "studio", "beats",
      "artwork"]),
    ("stage", "Stage", "Everything between the booking and the encore.",
     ["tours", "stage-plot", "lights", "live", "tour-board", "passports", "tour-suite"]),
    ("analytics", "Analytics", "What is measured, by whom, and how it moved.",
     # Signal left this room on 2026-09-17 (owner: "signal needs to be
     # removed from public view on analytics"). It is the catalog
     # intelligence the Operator Desk feeds, not something an artist
     # operates, and Analytics is a customer room. It is reached from the
     # desk, which links it. Access did not change: signal_hub.require()
     # guards every handler, and that was always the boundary.
     ["pulse", "scores", "trust-score", "insights", "artist-twin", "reports"]),
    ("business", "Business", "The money, the paperwork and the people.",
     # Tax is a view of Statements now, so its card sits beside that one
     # (owner, 2026-09-19: "move tax center with statements"). Sync packs
     # left for Releases the same day: "You're making a product for sale."
     ["royalties", "statements", "tax", "recovery", "money-queue", "cases", "disputes",
      "valuation", "revenue-os",
      "hours", "deals", "deal-simulator", "team", "portal",
      "services", "roster",
      # Documents are not a separate place: /documents has redirected to
      # /vault?view=contracts since 2026-09-09, so the Vault is the one
      # store and Contracts is its view of the paperwork.
      "vault", "contracts"]),
    ("publishing", "Publishing", "Rights, registrations and identifiers.",
     ["catalog", "track-passports", "conflicts", "fingerprints", "certified"]),
    ("releases", "Releases", "From finished master to the stores.",
     # Rollout Studio left Marketing for this room (owner, 2026-09-21): a
     # rollout is the plan for one release, and the Marketing room's own
     # screen already reaches it by the action that names the rollouts with
     # no smart link connected. The page and its address are unchanged.
     # Submit Music left this room for the footer (owner, 2026-09-22). It is
     # a door to the label desk, not a step in getting a release out, and a
     # card beside Autopilot and the calendar read as though it were one.
     ["autopilot", "release-calendar", "release-check", "rollout",
      "sync-packs", "distribution"]),
    ("marketing", "Marketing", "Getting heard and getting written about.",
     # Apparel & Merch left this room on 2026-09-17: merch is something you
     # make and sell, not a way of getting heard, and it moves to Artifacts
     # when that suite lands. The page and its address are unchanged; only
     # where it is listed has.
     # The one-sheet card left on 2026-09-19 (owner: "It just needs to be
     # an EPK"). /artist-profile redirects to the press kit.
     #
     # The room's own screen (room_marketing.html, owner's design,
     # 2026-09-21) closes with three tiles, so the card list is those three
     # plus links. Four moves got it there:
     #   - the four press cards collapsed into Press Desk, the one door to
     #     the media list, announcements, pitches and coverage. The three
     #     folded pages keep their addresses; their own tab strip comes
     #     back in this layout (templates/press/_shell.html), because the
     #     room no longer shows those destinations.
     #   - REACH left: hubs.tool_suites() already carries it in the suites
     #     strip at the foot of every page, at the same address.
     #   - Rollout Studio left for the Releases room.
     #   - links stays a card of this room, so /links keeps its way back
     #     here, but it is not a tile: the screen shows it as the hero's
     #     visits, clicks and pre-saves and as the rollout action.
     ["links", "press-desk", "epk", "referrals"]),
]

# Rows above the rooms, and the group under them.
TOP_KEYS = ("command-center", "actions")
ACCOUNT_KEYS = ("settings", "connections", "billing")

# Cards a Label plan sees; everybody else does not.
LABEL_ONLY = frozenset({"services", "roster", "submit", "apparel"})

ROOM_ICONS = {
    "fans": "M7 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM13 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z|M3 16c0-2.2 1.8-4 4-4M13 12c2.2 0 4 1.8 4 4",
    "studio": "M3 5h14v10H3z|M3 15h14|M6 8v4|M9 7v6|M12 9v3|M15 8v4",
    "stage": "M3 15h14|M5 15V9l5-4 5 4v6|M8 15v-3h4v3",
    "analytics": "M2 10h3l2-5 3 10 3-8 2 3h3",
    "business": "M3 6h14v8H3z|M3 9h14M6 12h3",
    "publishing": "M4 3h9l3 3v11H4z|M13 3v3h3|M7 9h6M7 12h6",
    "releases": "M10 3l7 7-7 7-7-7z|M10 7v6M7 10h6",
    "marketing": "M3 10a7 7 0 0114 0|M6 10a4 4 0 018 0|M10 10v7|M8 17h4",
}

# The pages that were tabs of another page, now cards of their own. Each
# names the sidebar entry it lived under, which is where its live flag
# and its page switch still come from. A card is a view of a page, never
# an anchor into one, and never a public document: the audit of
# 2026-09-15 found Track Passports and the Release Calendar jumping to
# the foot of another page, and Release check and Distribution opening
# public pages that asked a signed-in artist to create an account.
# Mechanicals and Neighbouring rights left the Publishing room the same
# day: both are folded into Royalties, so a card would only land on a
# page in another room.
_DOC = "M4 3h9l3 3v11H4z|M13 3v3h3|M7 9h6M7 12h6"
_LIST = "M4 5h12M4 10h12M4 15h8"
_CAL = "M3 5h14v12H3z|M3 9h14|M7 3v4M13 3v4"
_CHART = "M3 16h14|M5 13l3-4 3 2 4-6"
EXTRA = {
    "fan-crm": ("/links/fans", "M4 5h12v10H4z|M4 8h12|M7 11h3|M7 13h5", "Fan CRM", "Everyone who left a name or a number, in one list.", "fans"),
    "fan-club": ("/fan-club", "M10 3l2 4 4 .6-3 3 .7 4.4L10 13l-3.7 2 .7-4.4-3-3L8 7z", "Fan Club", "Paid membership, run by you.", "fans"),
    "contracts": ("/vault?view=contracts", "M5 3h8l3 3v11H5z|M13 3v3h3|M8 12l2 2 3-4|M8 8h4", "Contracts and licences", "The paperwork that proves who gets paid, with renewal reminders.", "vault"),
    # Deliberately in no room (2026-09-17). Signal is internal: the
    # Operator Desk links it, and no customer room holds it. The entry
    # stays so the card has one definition if it is ever placed again.
    "signal": ("/signal", "M3 12h3l2-6 3 10 2-5 2 2h2|M15 5a3 3 0 010 4", "Signal", "Early reads on where the music is moving, from the providers connected here.", "pulse"),
    "trust-score": ("/trust-score", "M10 2l2.4 4.9 5.6.8-4 3.9.9 5.4-4.9-2.6-4.9 2.6.9-5.4-4-3.9 5.6-.8z", "Trust score", "How complete and consistent your record is.", "scores"),
    "insights": ("/insights", "M10 3a5 5 0 00-3 9v2h6v-2a5 5 0 00-3-9z|M8 17h4", "Insights", "What your own numbers say this week.", "scores"),
    "deal-simulator": ("/sync/deal-simulator", "M3 15l4-5 3 3 4-6 3 4|M3 17h14", "Deal Simulator", "Try the terms before you sign them.", "deals"),
    # Sync packs is a sidebar entry of its own now (hubs.py, Launch Engine).
    # Tax is a view of Statements (owner, 2026-09-19).
    "tax": ("/statements?view=tax", "M6 3h8a1 1 0 011 1v13l-2-1.5L11 17l-2-1.5L7 17l-2-1.5V4a1 1 0 011-1z|M8 7h4M8 10h4", "Tax", "Your statement income filed by tax year.", "statements"),
    "track-passports": ("/catalog?view=passports", "M4 3h12v14H4z|M7 7h6|M7 10h6|M7 13h3|M13 13h.01", "Track Passports", "One page per recording: codes, splits, credits.", "catalog"),
    "release-calendar": ("/releases/autopilot?view=calendar", "M3 5h14v12H3z|M3 9h14|M7 3v4M13 3v4|M7 12h2M11 12h2", "Release Calendar", "Every scheduled drop on one calendar.", "autopilot"),
    "release-check": ("/releases/autopilot?view=ready", "M4 10l4 4 8-8", "Release check", "The store checks before a release goes out.", "autopilot"),
    "distribution": ("/distribution", "M3 10h14|M10 3v14|M5 5l10 10|M15 5L5 15", "Distribution", "How your releases reach the stores today.", None),
    # The three folded press pages. They are in NO room from 2026-09-21:
    # the Marketing room's screen closes with one Press Desk tile, and the
    # desk's own tab strip is the door to these three again. The entries
    # stay because the live flag and the page switch of each still come
    # from press-desk through parent_of(), and because a card has one
    # definition if one is ever placed again.
    "press-contacts": ("/press-desk/contacts", "M7 9a3 3 0 100-6 3 3 0 000 6z|M2 17c0-3 2.5-5 5-5s5 2 5 5|M13 5h5|M13 8h5|M13 11h3", "Media list", "The writers and outlets you pitch.", "press-desk"),
    "press-announcements": ("/press-desk/announcements", "M4 8h3l6-4v12l-6-4H4z|M7 12l1 4h2l-1-4|M15 8a3 3 0 010 4", "Announcements", "Press releases you write once and send to your media list.", "press-desk"),
    "press-coverage": ("/press-desk/coverage", "M4 4h9v12H4z|M13 7h3v7a2 2 0 11-2-2h2|M6 7h5M6 10h5|M6 13l2-2 3 2", "Coverage", "What has been written, kept in one place.", "press-desk"),
    "connections": ("/connections", "M6 10h8|M6 6l-3 4 3 4|M14 6l3 4-3 4", "Data and connections", "Which services this account is connected to.", "settings"),
}


def enabled():
    """Rooms are the layout when the owner has switched to them, or when
    the deployment says so. The owner's choice wins over the environment."""
    try:
        import db
        choice = db.get_kv("nav_layout")
    except Exception:
        choice = None
    if choice in ("rooms", "hubs"):
        return choice == "rooms"
    return (os.environ.get("NAV_ROOMS") or "").strip().lower() in ("1", "true", "yes", "on")


def set_layout(value):
    import db
    db.set_kv("nav_layout", "rooms" if value == "rooms" else "hubs")


# Cards this layout names differently from the classic sidebar. In the
# sidebar "Scores" is the parent of Trust and Insights, reached by the tab
# strip on its page; in a room each of the three is its own card, so the
# card says which score it is (owner, 2026-09-17). The page has read
# "Growth Score" all along, so this is the card catching up.
RENAMES = {
    "scores": ("Growth Score",
               "How ready you are to grow, scored from your own record."),
}


def catalogue():
    """{key: (href, icon, label, desc)} for every card any room can hold,
    read from the hub definitions and the groups, plus the unfolded pages."""
    out = {}
    for _hk, _name, _tag, items in hubs.nav_hubs():
        for key, href, icon, label, desc in items:
            out[key] = (href, icon, label, desc)
    for _gname, items in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        for key, href, icon, label, desc in items:
            out[key] = (href, icon, label, desc)
    for key, (href, icon, label, desc, _parent) in EXTRA.items():
        out[key] = (href, icon, label, desc)
    for key, (label, desc) in RENAMES.items():
        if key in out:
            href, icon, _l, _d = out[key]
            out[key] = (href, icon, label, desc)
    return out


def parent_of(key):
    """The sidebar entry an unfolded page lived under, or the key itself."""
    if key in EXTRA:
        return EXTRA[key][4] or key
    return key


def live_keys():
    """hubs.live_keys(), plus an unfolded page whose parent is live."""
    live = set(hubs.live_keys())
    for key, (_h, _i, _l, _d, parent) in EXTRA.items():
        if parent and parent in live:
            live.add(key)
    return live


def hidden_keys(base=None):
    """The owner's page switches, plus an unfolded page whose parent is off."""
    hidden = set(page_switches.hidden_keys() if base is None else base)
    for key, (_h, _i, _l, _d, parent) in EXTRA.items():
        if parent and parent in hidden:
            hidden.add(key)
    return hidden


# The owner's own drawn pictures for a room's icons (2026-09-15), one
# file per feature key under static/img/rooms/, e.g. rack.webp. A feature
# with a picture shows it; one without keeps its line mark. Read from the
# disk once per process, so dropping a file in is the whole change.
_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "rooms")
_IMAGE_EXTS = (".webp", ".avif", ".png", ".jpg", ".jpeg", ".svg")
_images = None


def images():
    """{feature key: /static path} for every picture on the disk."""
    global _images
    if _images is None:
        found = {}
        try:
            for name in sorted(os.listdir(_IMAGE_DIR)):
                stem, ext = os.path.splitext(name)
                if ext.lower() in _IMAGE_EXTS and stem not in found:
                    found[stem] = "/static/img/rooms/" + name
        except OSError:
            pass
        _images = found
    return _images


def image_for(key):
    return images().get(key, "")


def _state(key, href, live, hidden):
    if key in hidden:
        return "hidden"
    if page_switches.is_external(href):
        return "external"
    return "live" if key in live else "sample"


def build(user_plan=None, owner=False, demo=False):
    """The rooms for one person: [(key, name, purpose, icon, cards)], each
    card (key, href, icon, label, desc, state). A hidden page stays for
    an owner, badged; it leaves for everybody else. A locked demo loses
    the Sample pages as the hub sidebar does. Label-only cards show for a
    Label plan. The Signal card shows only to a login that holds a Signal
    seat (audit, 2026-09-15: it opened a refusal for everybody else)."""
    cat = catalogue()
    live = live_keys()
    hidden = hidden_keys()
    out = []
    for rkey, name, purpose, keys in ROOMS:
        cards = []
        for key in keys:
            if key not in cat:
                continue                       # a flag-gated entry this deployment lacks
            if key in LABEL_ONLY and user_plan != "label":
                continue
            href, icon, label, desc = cat[key]
            state = _state(key, href, live, hidden)
            if state == "hidden" and not owner:
                continue
            if demo and state == "sample":
                continue
            cards.append((key, href, icon, label, desc, state))
        out.append((rkey, name, purpose, ROOM_ICONS.get(rkey, ""), cards))
    return out


def top_rows(owner=False, demo=False):
    return _rows(TOP_KEYS, owner, demo)


def account_rows(owner=False, demo=False):
    return _rows(ACCOUNT_KEYS, owner, demo)


def _rows(keys, owner, demo):
    cat = catalogue()
    live = live_keys()
    hidden = hidden_keys()
    out = []
    for key in keys:
        if key not in cat:
            continue
        href, icon, label, desc = cat[key]
        state = _state(key, href, live, hidden)
        if state == "hidden" and not owner:
            continue
        if demo and (state == "sample" or key in hubs.DEMO_HIDDEN_ALWAYS):
            continue
        out.append((key, href, icon, label, desc, state))
    return out


def get_room(key, user_plan=None, owner=False, demo=False):
    for room in build(user_plan, owner, demo):
        if room[0] == key:
            return {"key": room[0], "name": room[1], "purpose": room[2],
                    "icon": room[3], "cards": room[4]}
    return None


def room_for_key(key):
    """Which room a page key sits in, or None."""
    for rkey, _name, _purpose, keys in ROOMS:
        if key in keys:
            return rkey
    return None


def back_map():
    """{page key: (room key, room name)} for every page a room holds, so
    a page opened from a room can offer the way back (owner, 2026-09-15:
    "we do need back buttons in the pages when you open the icon cards in
    the room"). An unfolded page's parent maps to the same room, since
    the page it opens names itself by the parent's key."""
    out = {}
    for rkey, name, _purpose, keys in ROOMS:
        for key in keys:
            out[key] = (rkey, name)
            parent = parent_of(key)
            out.setdefault(parent, (rkey, name))
    return out
