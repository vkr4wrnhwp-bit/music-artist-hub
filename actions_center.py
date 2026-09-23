"""The Action Center: what /actions and the Command Center SAY about an
action (owner's mockup + crawl, 2026-09-23).

The rows live in command_center.py (street_actions). This module turns a
row into what a person reads: the room it belongs to and the way back to
it, the record it is about, where it came from, who has it, when it is
due, and the one next step. Nothing here invents a value: a row that does
not know its source says nothing about one, a record that is gone says it
is gone, and "Assigned to you" is said only to the person it names.
"""

from datetime import date

import command_center as cc

# The filters, in the mockup's order. "All" is every action that is not
# dismissed; dismissed work has its own filter and its own count.
FILTERS = (("all", "All"), ("attention", "Needs attention"), ("new", "Not started"),
           ("in_progress", "In progress"), ("complete", "Complete"),
           ("dismissed", "Dismissed"))
FILTER_KEYS = {k for k, _ in FILTERS}

# The board's columns: the same four states, by the same names.
BOARD = ("new", "in_progress", "complete", "dismissed")

# What an action can be about: (label, room it belongs to, "Open ..." words).
RECORD_KINDS = {
    "release": ("Release", "releases", "Open Release"),
    "campaign": ("Campaign", "marketing", "Open Campaign"),
    "song": ("Song", "publishing", "Open Song"),
    "tour_show": ("Show", "stage", "Open Show"),
    "tour": ("Tour", "stage", "Open Tour"),
    "document": ("Document", "business", "Open Document"),
}

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
          "Nov", "Dec")


def rooms():
    """[(key, label)] for the eight rooms, in the sidebar's order."""
    import rooms as _rooms
    return [(r[0], r[1]) for r in _rooms.ROOMS]


def room_label(key):
    return dict(rooms()).get(key or "", "")


def _day(iso, today):
    d = date.fromisoformat(iso)
    words = "%s %d" % (MONTHS[d.month - 1], d.day)
    return words if d.year == today.year else "%s, %d" % (words, d.year)


def due(action, today):
    """(words, hot): "Due today", "Due tomorrow", "Due Oct 4", or
    "Overdue · was due Oct 2"; hot when overdue or inside the attention
    window. ("", False) with no due date. A closed action keeps its date
    without the alarm."""
    iso = (action or {}).get("due_date") or ""
    if not iso:
        return "", False
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return "", False
    active = action.get("status") in cc.ACTIVE_STATUSES
    delta = (d - today).days
    if active and delta < 0:
        return "Overdue · was due %s" % _day(iso, today), True
    if delta == 0:
        words = "Due today"
    elif delta == 1:
        words = "Due tomorrow"
    else:
        words = "Due %s" % _day(iso, today)
    return words, bool(active and delta <= cc.ATTENTION_DAYS)


# ---- who an action can be assigned to --------------------------------------

def assignees(account, team_rows, me_id):
    """[(user_id, label)]: the account holder and every confirmed team
    member. The signed-in person is "Me" and comes first."""
    people = [(account["id"], account.get("name") or account.get("email") or "Account owner")]
    for m in team_rows or ():
        uid = m.get("member_user_id")
        if uid and m.get("access") in ("read", "edit") and uid not in [p[0] for p in people]:
            people.append((uid, m.get("member_name") or m.get("email") or "Team member"))
    out = [(uid, "Me" if uid == me_id else name) for uid, name in people]
    out.sort(key=lambda p: 0 if p[0] == me_id else 1)
    return out


def assignee_words(action, people, me_id, others="Assigned to a former team member"):
    """Who has it. `others` is what to say for someone not in `people`:
    a member who left, or - on a team seat's screen, which is not shown the
    rest of the team (the Studio's rule) - "a teammate"."""
    aid = (action or {}).get("assignee_id") or ""
    if not aid:
        # A tour's crew member has no account, so no id, but a name: the
        # Tour tasks page and this board say the same person (audit,
        # 2026-09-23: "Book the van — Sam ... Unassigned").
        crew = ((action or {}).get("assignee_name") or "").strip()
        return ("Tour crew: %s" % crew) if crew else "Unassigned"
    if aid == me_id:
        return "Assigned to you"
    name = dict(people).get(aid)
    return ("Assigned to %s" % name) if name else others


# ---- the records an action can be about ------------------------------------

class Records(dict):
    """The records an action can be about, by "kind:id", plus the kinds
    whose store could not be read this time (`failed`). A record of a
    failed kind is not known to be gone, so nothing may say it is."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failed = set()


def records(user_id, store, mls, tour_store=None, is_mock=None):
    """{"kind:id": {kind, id, label, href, room, open}} for this account's
    releases, campaigns, songs, tours, shows and documents. Read once per
    page. A store that cannot be read contributes nothing rather than
    failing the board, and its kinds are named in `.failed`, so the page
    says it could not read the record rather than that the record is gone
    (audit, 2026-09-23: a failed campaigns read told the person their
    release was "no longer on file")."""
    out = Records()

    def put(kind, ident, label, href):
        name, room, open_words = RECORD_KINDS[kind]
        out["%s:%s" % (kind, ident)] = {
            "kind": kind, "id": ident, "label": "%s · %s" % (label or "Untitled", name),
            "href": href, "room": room, "open": open_words}

    try:
        for c in mls.list_campaigns(user_id):
            if c.get("archived_at"):
                continue
            if (c.get("campaign_type") or "release") == "release":
                put("release", c["id"], c.get("title"), "/releases/autopilot?campaign=%s" % c["id"])
            else:
                put("campaign", c["id"], c.get("title"), "/links/%s/edit" % c["id"])
    except Exception:
        out.failed.update(("release", "campaign"))
    try:
        for t in store.list_os_tracks(user_id):
            put("song", t["id"], t.get("title"), "/tracks/%s" % t["id"])
    except Exception:
        out.failed.add("song")
    if tour_store is not None:
        try:
            for tour in tour_store.list_tours(user_id):
                if is_mock and is_mock(tour["id"]):
                    continue
                put("tour", tour["id"], tour.get("name"), "/tours/%s" % tour["id"])
                for s in tour_store.list_shows(tour["id"]):
                    where = s.get("venue") or s.get("city") or "Show"
                    when = (s.get("date") or "")[:10]
                    put("tour_show", s["id"], ("%s, %s" % (where, when)) if when else where,
                        "/tours/%s/shows/%s" % (tour["id"], s["id"]))
        except Exception:
            out.failed.update(("tour", "tour_show"))
    else:
        out.failed.update(("tour", "tour_show"))
    try:
        for d in store.list_documents(user_id):
            put("document", d["id"], d.get("filename"), "/vault?view=contracts#doc-%s" % d["id"])
    except Exception:
        out.failed.add("document")
    return out


def related_options(recs):
    """[(group label, [(value, label)])] for the Related to select."""
    groups = []
    for kind, (name, _room, _open) in RECORD_KINDS.items():
        rows = [(k, r["label"].rsplit(" · ", 1)[0]) for k, r in recs.items() if r["kind"] == kind]
        if rows:
            groups.append((name + "s", rows))
    return groups


def related(action, recs):
    """The record this action is about: the resolved record, a note that
    it is gone, a note that it could not be read, or None when it is about
    nothing. `keep` marks the two notes: the edit form cannot offer that
    record, so it keeps the link as it is."""
    kind = (action or {}).get("entity_type") or ""
    ident = (action or {}).get("entity_id") or ""
    if not kind or not ident:
        return None
    rec = recs.get("%s:%s" % (kind, ident))
    if rec:
        return rec
    if kind in RECORD_KINDS:
        noun = RECORD_KINDS[kind][0].lower()
        base = {"kind": kind, "id": ident, "href": None, "room": RECORD_KINDS[kind][1],
                "open": None, "keep": True}
        # A store that failed to read says nothing about the record: it is
        # not gone, it is unread (the owner's rule: never turn a failed
        # request into a statement about the data).
        if kind in getattr(recs, "failed", ()):
            return dict(base, label="This %s could not be read right now" % noun,
                        unreadable=True)
        return dict(base, label="This %s is no longer on file" % noun, gone=True)
    return None


# ---- one row, as a person reads it -----------------------------------------

def row(action, recs, people, me_id, today, others="Assigned to a former team member"):
    a = action
    status = a["status"]
    rel = related(a, recs)
    room_key = a.get("room") or ""
    words, hot = due(a, today)
    if status == "new":
        step = ("in_progress", "Start")
    elif status == "in_progress":
        step = ("complete", "Complete")
    else:
        step = ("new", "Reopen")
    # The second button goes where the work is done: the record when
    # there is one, else the room.
    if rel and rel.get("href"):
        door = {"label": rel["open"], "href": rel["href"]}
    elif room_key:
        door = {"label": "Open %s" % room_label(room_key), "href": "/room/%s" % room_key}
    else:
        door = None
    overdue = cc.is_overdue(a, today)
    return {
        "id": a["id"],
        "title": a["title"],
        "description": a.get("description") or "",
        "status": status,
        "status_label": cc.STATUS_LABELS.get(status, status),
        "priority": a.get("priority") or "medium",
        "priority_label": (a.get("priority") or "medium").title(),
        "type_label": cc.ACTION_TYPE_LABELS.get(a.get("category"), "General"),
        "room": room_key,
        "room_label": room_label(room_key),
        "due": words,
        "due_hot": hot,
        "overdue": overdue,
        "assignee": assignee_words(a, people, me_id, others),
        "related": rel,
        "source": cc.ACTION_SOURCES.get(a.get("source") or "", ""),
        "source_noun": cc.SOURCE_NOUNS.get(a.get("source") or "", ""),
        "source_href": a.get("source_href") or "",
        "door": door,
        "step": step,
        "active": status in cc.ACTIVE_STATUSES,
        "attention": cc.needs_attention(a, today),
        "deletable": cc.deletable(a),
        "tone": ("crit" if (overdue or (a.get("priority") == "high" and status in cc.ACTIVE_STATUSES))
                 else ("warn" if a.get("priority") == "medium" and status in cc.ACTIVE_STATUSES else "idle")),
    }


def brief(action, today):
    """What the Command Center says about one open action: its title, the
    room it belongs to, when it is due, and the door to it."""
    words, hot = due(action, today)
    room = room_label(action.get("room"))
    bits = [b for b in (room, words) if b]
    return {"id": action["id"], "title": action["title"],
            "priority": action.get("priority") or "medium",
            "priority_label": (action.get("priority") or "medium").title(),
            "room_label": room, "due": words, "due_hot": hot,
            "attention": cc.needs_attention(action, today),
            "overdue": cc.is_overdue(action, today),
            "line": " \u00b7 ".join(bits),
            "href": "/actions/%s" % action["id"]}


def pick(actions, key, today):
    """The actions a filter shows."""
    if key == "attention":
        return [a for a in cc.rank_open(actions, today) if cc.needs_attention(a, today)]
    if key == "all":
        return [a for a in actions if a["status"] != "dismissed"]
    return [a for a in actions if a["status"] == key]


def counts(actions, today):
    """{filter key: how many} for the pills."""
    return {k: len(pick(actions, k, today)) for k in FILTER_KEYS}


def default_filter(actions, today):
    """The board opens on Needs attention when something does, else All."""
    return "attention" if any(cc.needs_attention(a, today) for a in actions) else "all"


# ---- where "Create action" buttons elsewhere came from ----------------------

# The page a Create-action form sits on, when the form did not say. Longest
# prefix wins. Rows made from any other page record no source.
SOURCE_BY_PATH = (
    ("/command-center", "alert"),
    ("/releases/autopilot", "release_check"),
    ("/release-check", "release_check"),
    ("/clean-release", "release_check"),
    ("/catalog", "catalog_check"),
    ("/conflicts", "rights_conflict"),
    ("/qualification", "growth_score"),
    ("/trust-score", "trust_score"),
    ("/modules", "module"),
)
# The money pages name no source: no Create-action form sits on them. The
# "royalty_check" source was produced by nothing - its forms lived in a
# band mode no page set (audit, 2026-09-23) - and on the Recovery desk a
# case is the action. Royalty work reaches the board from a Command
# Center alert, as "From a Command Center alert".


def source_for_path(path):
    path = (path or "").split("?")[0].split("#")[0]
    best, best_len = "", -1
    for prefix, kind in SOURCE_BY_PATH:
        if (path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?")) and len(prefix) > best_len:
            best, best_len = kind, len(prefix)
    return best
