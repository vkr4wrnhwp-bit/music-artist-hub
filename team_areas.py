"""Which rooms of an account a team seat may open (owner, 2026-09-19: "can
we have check boxes on when they invite the person and they an choose?").

The artist ticks rooms when inviting someone, and can change them later on
the Team page. A room is the sidebar's room: its pages are the room's cards
(rooms.ROOMS), plus the pages that belong with them but are not cards of
their own (EXTRA below). An unticked room leaves the member's sidebar and
its pages send them back.

Two more rules make an unticked box mean what it says:
  - the pages that gather every room into one view (the Command Center,
    Actions, notifications, search) are for a seat with every room; a seat
    with some rooms lands on its first room instead
  - with Money and business unticked, the money pages that sit outside any
    room close with it

Anything else follows the seat's access, read or edit, and the areas that
are never a seat's (billing, settings, the team) stay shut whatever is
ticked. "all" is stored when every box is ticked, so a room added later is
open to them too, as it is to the artist.
"""
import urllib.parse

import rooms

ALL = "all"

# The checkbox labels: the room names, with Business spelled out because it
# is where the money is.
LABELS = {
    "fans": "Fans",
    "studio": "Studio",
    "stage": "Stage",
    "analytics": "Analytics",
    "business": "Money and business",
    "publishing": "Publishing",
    "releases": "Releases",
    "marketing": "Marketing",
}

# Pages that belong to a room without being one of its cards.
EXTRA = {
    "fans": ("/audience", "/voice-of-fan", "/fan-label"),
    "studio": ("/creative-studio", "/stem-src"),
    "stage": ("/stage", "/showday", "/rider"),
    "analytics": ("/stats", "/benchmark", "/territories", "/playlists", "/release-signal",
                  "/world"),
    "business": ("/money-queue", "/royalty-lanes", "/lanes", "/royalty-recovery",
                 "/royalty-sweep", "/mechanicals", "/neighboring-rights", "/conflicts",
                 "/fraud-sentinel", "/spend-optimizer", "/funding", "/capital",
                 "/capital-score", "/documents", "/deal-room", "/sync"),
    "publishing": ("/tracks", "/isrc", "/identifiers", "/metadata", "/metadata-passport",
                   "/registration", "/publishing", "/cleared", "/ai-rights"),
    "releases": ("/releases", "/release-check", "/clean-release", "/pitch"),
    "marketing": ("/press", "/onesheet", "/sheet", "/rollout", "/rollout-studio"),
}

# Pages that gather every room: only for a seat that has every room.
WHOLE_ACCOUNT = ("/command-center", "/actions", "/notifications", "/inbox", "/search",
                 "/overview", "/dashboard", "/reminders", "/ai", "/tutor", "/artist-control",
                 "/opportunities", "/api/artist-signal-profile")

# Top rows of the sidebar that are whole-account pages.
WHOLE_ACCOUNT_KEYS = frozenset({"command-center", "actions"})


def keys():
    return [r[0] for r in rooms.ROOMS]


def parse(value):
    """The stored value as a set of room keys; ALL means every room."""
    v = ALL if value is None else str(value).strip()
    if v == ALL:
        return set(keys())
    return {k for k in v.split(",") if k in LABELS}


def is_all(value):
    return parse(value) >= set(keys())


def serialize(chosen):
    """What to store for the ticked boxes. Every box is ALL; none is ''."""
    chosen = {k for k in (chosen or ()) if k in LABELS}
    if chosen >= set(keys()):
        return ALL
    return ",".join(k for k in keys() if k in chosen)


def from_form(values):
    """The ticked boxes from a posted form (getlist('areas'))."""
    return serialize(values)


def _paths():
    cat = rooms.catalogue()
    out = {}
    for rkey, _name, _purpose, page_keys in rooms.ROOMS:
        found = set(EXTRA.get(rkey, ()))
        for k in page_keys:
            if k in cat:
                p = urllib.parse.urlsplit(cat[k][0]).path.rstrip("/")
                if p.startswith("/") and not p.startswith("/suites/go"):
                    found.add(p)
        out[rkey] = found
    return out


_PATHS = None


def room_paths():
    global _PATHS
    if _PATHS is None:
        _PATHS = _paths()
    return _PATHS


def _under(path, prefix):
    return path == prefix or path.startswith(prefix + "/")


def room_for_path(path):
    """The room a page belongs to, by the longest matching prefix, or None."""
    best, best_len = None, -1
    for rkey, prefixes in room_paths().items():
        for p in prefixes:
            if _under(path, p) and len(p) > best_len:
                best, best_len = rkey, len(p)
    return best


def allows(value, path):
    """May a seat with these rooms open this page?"""
    if is_all(value):
        return True
    granted = parse(value)
    if any(_under(path, p) for p in WHOLE_ACCOUNT):
        return False
    if path.startswith("/room/"):
        return path[len("/room/"):].split("/")[0] in granted
    room = room_for_path(path)
    return room is None or room in granted


def home(value):
    """Where a seat lands: the Command Center with every room, otherwise
    the first room it has."""
    if is_all(value):
        return "/command-center"
    for k in keys():
        if k in parse(value):
            return "/room/" + k
    return "/portal"


def hidden_page_keys(value):
    """Sidebar and palette keys to hide for this seat."""
    if is_all(value):
        return set()
    granted = parse(value)
    out = set(WHOLE_ACCOUNT_KEYS)
    for rkey, _name, _purpose, page_keys in rooms.ROOMS:
        if rkey not in granted:
            out.update(page_keys)
            out.update(rooms.parent_of(k) for k in page_keys)
    return out


def describe(value):
    """'Every room' or the rooms' names, for the Team page and the banner."""
    if is_all(value):
        return "Every room"
    granted = parse(value)
    names = [LABELS[k] for k in keys() if k in granted]
    return ", ".join(names) if names else "No rooms"
