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
     ["fans", "fan-crm", "fan-club", "discover", "marketplace"]),
    ("studio", "Studio", "Making the record and keeping its files.",
     ["audio-studio", "rack", "remix-lab", "studio", "noise-lab", "the-room", "beats",
      "vault", "contracts", "artwork"]),
    ("stage", "Stage", "Everything between the booking and the encore.",
     ["tours", "stage-plot", "lights", "live", "tour-board", "passports"]),
    ("analytics", "Analytics", "What is measured, by whom, and how it moved.",
     ["pulse", "signal", "scores", "trust-score", "insights", "artist-twin", "reports"]),
    ("business", "Business", "The money, the paperwork and the people.",
     ["royalties", "statements", "recovery", "cases", "disputes", "valuation", "revenue-os",
      "tax", "hours", "deals", "deal-simulator", "sync-packs", "team", "portal",
      "services", "roster"]),
    ("publishing", "Publishing", "Rights, registrations and identifiers.",
     ["catalog", "track-passports", "fingerprints", "mechanicals", "neighboring", "certified"]),
    ("releases", "Releases", "From finished master to the stores.",
     ["autopilot", "release-calendar", "release-check", "distribution", "submit"]),
    ("marketing", "Marketing", "Getting heard and getting written about.",
     ["links", "rollout", "press-desk", "press-contacts", "press-coverage", "epk", "onesheet",
      "reach", "referrals", "apparel"]),
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
# and its page switch still come from.
_DOC = "M4 3h9l3 3v11H4z|M13 3v3h3|M7 9h6M7 12h6"
_LIST = "M4 5h12M4 10h12M4 15h8"
_CAL = "M3 5h14v12H3z|M3 9h14|M7 3v4M13 3v4"
_CHART = "M3 16h14|M5 13l3-4 3 2 4-6"
EXTRA = {
    "fan-crm": ("/links/fans", _LIST, "Fan CRM", "Everyone who left a name or a number, in one list.", "fans"),
    "fan-club": ("/fan-club", ROOM_ICONS["fans"], "Fan Club", "Paid membership, run by you.", "fans"),
    "contracts": ("/vault?view=contracts", _DOC, "Contracts and licences", "The paperwork that proves who gets paid, with renewal reminders.", "vault"),
    "signal": ("/signal", _CHART, "Signal", "Early reads on where the music is moving, from the providers connected here.", "pulse"),
    "trust-score": ("/trust-score", "M10 2l2.4 4.9 5.6.8-4 3.9.9 5.4-4.9-2.6-4.9 2.6.9-5.4-4-3.9 5.6-.8z", "Trust score", "How complete and consistent your record is.", "scores"),
    "insights": ("/insights", _CHART, "Insights", "What your own numbers say this week.", "scores"),
    "deal-simulator": ("/sync/deal-simulator", _CHART, "Deal Simulator", "Try the terms before you sign them.", "deals"),
    "sync-packs": ("/sync/clearance-packs", _DOC, "Sync packs", "Cleared, ready-to-send packs for a sync request.", "deals"),
    "track-passports": ("/catalog#passports", _DOC, "Track Passports", "One page per recording: codes, splits, credits.", "catalog"),
    "mechanicals": ("/mechanicals", _LIST, "Mechanicals", "What the MLC holds and pays for your songs.", "income"),
    "neighboring": ("/neighboring-rights", _LIST, "Neighbouring rights", "Performance income on the recording, by territory.", "income"),
    "release-calendar": ("/releases/autopilot#calendar", _CAL, "Release Calendar", "Every scheduled drop on one calendar.", "autopilot"),
    "release-check": ("/release-check", "M4 10l4 4 8-8", "Release check", "The store checks before a release goes out.", "autopilot"),
    "distribution": ("/distribution", "M3 10h14|M10 3v14|M5 5l10 10|M15 5L5 15", "Distribution", "How your releases reach the stores today.", None),
    "press-contacts": ("/press-desk/contacts", _LIST, "Media list", "The writers and outlets you pitch.", "press-desk"),
    "press-coverage": ("/press-desk/coverage", _LIST, "Coverage", "What has been written, kept in one place.", "press-desk"),
    "onesheet": ("/artist-profile", _DOC, "One-sheet", "The one-page artist profile you send.", "epk"),
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
    Label plan."""
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
