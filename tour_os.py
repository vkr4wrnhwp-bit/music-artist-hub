"""TOUR — routes, permissions and the boundary.

Mounted at /tours. Since Phase 3 this is the one tour product: the old
Tour Hub addresses /tour and /tour/<show_id> redirect here, its POST
routes still answer old forms, and shows are the same tour_shows rows,
so the public /showday and /rider pages and the Money Queue keep
reading them.

Access model
  A tour is owned by one account (tours.user_id). Other people reach it
  through tour_members: invited by email, accepted with a token, active
  with a list of scopes. Scopes are checked in require_tour() before a
  handler runs, and again inside handlers for the sensitive subsets
  (money fields, private phones, private rooms, 'management'/'private'
  entries). Nothing is hidden by template alone — rows a viewer may not
  see are never loaded into the template context, and money fields are
  blanked out of the show dict before it is rendered.

  There is no named-person exception anywhere. The owner is whoever
  owns the row; admin is a scope on a membership.

Plan
  Owning a tour needs the artist tier, like the rest of the Live Stage
  Suite. Being invited to one does not: a driver on a free account still
  gets their day sheet.
"""
import hashlib
import hmac
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import (Blueprint, Response, abort, redirect, render_template,
                   request, session, url_for)

import blob_store
import command_center
import db as store
import email_provider as emailer
import plans
import press_store
import plot_images
import tour_advance_mail as tam
import tour_engine as eng
import tour_store as ts

bp = Blueprint("tours", __name__)

_base_url = lambda: ""
TOUR_PREFIX = "tour:"
ALLOWED_FILE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".csv", ".xlsx",
                     ".xls", ".doc", ".docx", ".txt", ".zip", ".ics", ".heic"}
MAX_UPLOAD = 25 * 1024 * 1024
MONEY_FILE_CATEGORIES = {"invoice", "tax", "settlement", "contract"}

SHOW_TABS = [
    ("overview", "Overview"), ("schedule", "Schedule"), ("advance", "Advance"),
    ("inbox", "Advance inbox"), ("send", "Send advance"), ("travel", "Travel"), ("hotel", "Hotel"),
    ("venue", "Venue"), ("people", "People"), ("guests", "Guest list"),
    ("vip", "VIP"), ("production", "Production"), ("money", "Money"),
    ("merch", "Merch"), ("marketing", "Marketing"), ("content", "Content"),
    ("setlist", "Set list"), ("files", "Files"), ("tasks", "Tasks"),
    ("notes", "Notes"), ("activity", "Activity"),
]
TAB_SCOPE = {"money": "financials", "merch": "merch", "guests": "guests",
             "vip": "vip", "marketing": "marketing", "content": "content",
             "inbox": "advance", "send": "advance", "files": "files"}

# --- the date page ----------------------------------------------------------
# One date, one page. The six CORE sections always render, in this order;
# every other former tab is OPTIONAL: a `+` chip until it is added to the
# date, has rows, or is reached by its old ?tab= deep link. The opted keys
# live in tour_show_ext.readiness_config (section keys), and readiness
# follows the same rule: core categories always, an optional section's
# categories only once it is on the page. SHOW_TABS stays as the deep-link
# vocabulary (the service worker caches by full URL, query included).
CORE_SECTIONS = [
    ("times", "Times", "clock"), ("advance", "Advance", "tick"),
    ("venue", "Venue & contacts", "compass"), ("deal", "Deal", "card"),
    ("notes", "Notes", "pencil"), ("activity", "Activity", "pulse"),
]
OPTIONAL_SECTIONS = [
    ("hotel", "Hotel", "bed", ("hotel",)),
    ("travel", "Travel", "van", ("travel", "ground")),
    ("guests", "Guest list", "people", ("guest_list",)),
    ("vip", "VIP", "star", ("vip",)),
    ("settlement", "Settlement", "receipt", ("settlement",)),
    ("merch", "Merch counts", "tag", ()),
    ("marketing", "Marketing", "megaphone", ("marketing",)),
    ("content", "Content plan", "camera", ("content",)),
    ("setlist", "Set list", "stems", ()),
    ("files", "Files", "folder", ()),
    ("tasks", "Tasks", "list-check", ()),
]
SECTION_KEYS = [k for k, _l, _i in CORE_SECTIONS] + [k for k, _l, _i, _c in OPTIONAL_SECTIONS]
CORE_CATEGORIES = ["confirmation", "contract", "deposit", "venue", "promoter",
                   "advance", "production", "catering", "hospitality"]
# Reading a section needs the scope its old tab needed; the deal and the
# settlement are the money tab.
SECTION_VIEW_SCOPE = dict(TAB_SCOPE, deal="financials", settlement="financials")
# Adding one needs `edit` or the scope that edits its rows.
SECTION_ADD_SCOPE = {"hotel": "hotel", "travel": "travel", "guests": "guests", "vip": "vip",
                     "settlement": "financials", "merch": "merch", "marketing": "marketing",
                     "content": "content", "setlist": "production", "files": "files",
                     "tasks": "schedule"}
# Old tab keys that land inside a section. The page scrolls to the tab's
# own id; this says which section it lives in.
TAB_SECTION = {"overview": None, "schedule": "times", "inbox": "advance", "send": "advance",
               "production": "advance", "people": "venue", "money": "deal"}
ADD_LABELS = {"hotel": "Add a hotel", "travel": "Add travel", "guests": "Set the allocation and add guests",
              "vip": "Add a VIP package", "merch": "Count merch for this date",
              "marketing": "Enter tickets and the local push", "content": "Assign the content plan",
              "setlist": "Start a set list", "files": "Attach a file", "tasks": "Add a task"}
SETTLEMENT_FIELDS = ["ticket_gross", "adjusted_gross", "vip_gross", "merch_gross", "venue_merch_cut",
                     "production_expenses", "local_expenses", "travel_allocation", "promoter_expenses",
                     "settlement_amount", "collected"]
PRODUCTION_FILE_CATEGORIES = ("stage_plot", "tech_pack", "rider", "production", "venue_map")

TOUR_TABS = [
    ("home", "Tour Home", ""), ("my-day", "My Day", "my-day"),
    ("calendar", "Calendar", "calendar"), ("shows", "Shows", "shows"),
    ("schedule", "Schedule", "schedule"), ("travel", "Travel", "travel"),
    ("hotels", "Hotels", "hotels"), ("venues", "Venues", "venues"),
    ("people", "People", "people"), ("guests", "Guests", "guests"),
    ("money", "Money", "money"), ("merch", "Merch", "merch"),
    ("marketing", "Marketing", "marketing"), ("content", "Content", "content"),
    ("setlists", "Set lists", "setlists"), ("vip", "VIP", "vip"),
    ("tasks", "Tasks", "tasks"), ("files", "Files", "files"),
    ("changes", "What changed", "changes"), ("ask", "Ask Tour", "ask"),
    ("map", "Route", "map"), ("import", "Import", "import"),
    ("exports", "Exports", "exports"), ("share", "Share links", "share"),
    ("team", "Team", "team"), ("settings", "Settings", "settings"),
    ("stage-plot", "Stage plot", "stage-plot"),
]
TOUR_TAB_SCOPE = {"money": "financials", "merch": "merch", "guests": "guests",
                  "vip": "vip",
                  "marketing": "marketing", "content": "content", "files": "files",
                  "share": "admin", "team": "admin", "settings": "admin",
                  "import": "edit"}

# The bar every tour page carries. Seven entries for the daily work; the
# once-a-tour utilities and the roll-ups sit under More. Keys are TOUR_TABS
# keys, so every route, scope and test path is unchanged - only the bar is.
PRIMARY_TABS = ("home", "shows", "people", "travel", "money", "files")
BAR_LABELS = {"home": "Home", "shows": "Dates", "people": "Crew", "travel": "Travel & hotels"}
# Pages that live under one primary entry, shown as a sub-row beneath it.
BAR_GROUPS = {"travel": (("travel", "Travel"), ("hotels", "Hotels"), ("map", "Route"))}
MORE_ORDER = ("my-day", "calendar", "schedule", "venues", "setlists", "stage-plot", "guests", "vip", "merch",
              "marketing", "content", "tasks", "changes", "ask", "import", "exports", "share",
              "team", "settings")


# --- identity & access ------------------------------------------------------

def _me():
    user_id = session.get("user_id")
    return store.get_user(user_id) if user_id else None


def _viewer_for(user, tour):
    if tour["user_id"] == user["id"]:
        person = None
        for p in ts.list_people(tour["id"]):
            if p.get("linked_user_id") == user["id"]:
                person = p
                break
        return {"is_owner": True, "scopes": list(ts.SCOPES), "member": None,
                "person": person, "user": user, "name": user.get("name") or user["email"]}
    m = ts.get_membership(tour["id"], user["id"])
    if m is None:
        return None
    return {"is_owner": False, "scopes": list(m["scopes"]), "member": m,
            "person": ts.person_for_user(tour["id"], user["id"]), "user": user,
            "name": m.get("name") or user.get("name") or user["email"]}


def can(viewer, scope):
    if viewer is None:
        return False
    if viewer.get("is_owner") or "admin" in viewer["scopes"]:
        return True
    return scope in viewer["scopes"]


def require_tour(*scopes):
    """Resolve the tour and the viewer's membership, enforce scopes, hand
    (user, tour, viewer) to the handler. Unknown tour or no membership is
    a 404 — the existence of a tour is not something to confirm."""
    def wrap(fn):
        def guarded(*args, **kwargs):
            user = _me()
            if user is None:
                return redirect(url_for("login", next=request.path))
            tour = ts.get_tour(kwargs.get("tour_id") or "")
            if tour is None:
                abort(404)
            viewer = _viewer_for(user, tour)
            if viewer is None:
                abort(404)
            if scopes and not any(can(viewer, s) for s in scopes):
                return render_template("tour/denied.html", tour=tour, viewer=viewer,
                                       needed=scopes, active_page="tours"), 403
            return fn(user, tour, viewer, *args, **kwargs)
        guarded.__name__ = fn.__name__
        return guarded
    return wrap


def _actor(viewer):
    return {"id": viewer["user"]["id"], "name": viewer["name"]}


# --- server-side filters ----------------------------------------------------

def _visible(viewer, rows):
    return [r for r in rows if eng.visible_to(viewer, r, viewer["scopes"])]


def _strip_money(viewer, show):
    """Money fields leave the dict entirely for anyone without the
    financials scope. Templates cannot print what is not there."""
    if show is None or can(viewer, "financials"):
        return show
    s = dict(show)
    for k in ts.MONEY_FIELDS:
        s[k] = ""
    s["settlement"] = {}
    return s


def _redact_people(viewer, people):
    """Phone numbers marked private are only for people-scope holders (and
    the person themself); emergency contacts the same."""
    full = can(viewer, "people")
    me_id = (viewer.get("person") or {}).get("id")
    out = []
    for p in people:
        q = dict(p)
        if not full and q["id"] != me_id:
            if q.get("phone_private"):
                q["phone"] = ""
            q["emergency"] = ""
            q["notes"] = ""
        out.append(q)
    return out


def _redact_rooms(viewer, rooms):
    if can(viewer, "hotel"):
        return rooms
    me_id = (viewer.get("person") or {}).get("id")
    return [dict(r, room_number=(r["room_number"] if r.get("person_id") == me_id else ""))
            for r in rooms]


def _redact_lodging(viewer, rows):
    rows = _visible(viewer, rows)
    if can(viewer, "hotel"):
        return rows
    out = []
    for l in rows:
        q = dict(l)
        q["confirmation"] = ""
        q["payment"] = ""
        q["reservation_name"] = ""
        out.append(q)
    return out


def _redact_travel(viewer, rows):
    rows = _visible(viewer, rows)
    if can(viewer, "travel"):
        return rows
    pid = (viewer.get("person") or {}).get("id")
    out = []
    for t in rows:
        trav = t.get("travelers") or ["all"]
        if "all" in trav or (pid and pid in trav):
            q = dict(t)
            q["confirmation"] = ""
            out.append(q)
    return out


def _changes_for(viewer, tour_id, rows):
    """The change log a viewer may read. Money, guest, VIP and expense
    changes need their scope; confirmation numbers need travel/hotel;
    and a change on a row the viewer cannot see (private schedule item,
    a leg they are not on, a management-only hotel) is not shown to them
    either — the log must not be a side door to the row."""
    boss = viewer["is_owner"] or "admin" in viewer["scopes"]
    if boss:
        return rows
    need = {"money": "financials", "expense": "financials", "guest": "guests", "vip": "vip",
            "member": "admin", "share": "admin", "file": "files"}
    hidden_fields = {"travel": {"confirmation", "seat"}, "lodging": {"confirmation", "payment", "reservation_name"}}
    sched = {r["id"]: r for r in ts.list_schedule(tour_id)}
    legs = {r["id"]: r for r in ts.list_travel(tour_id)}
    beds = {r["id"]: r for r in ts.list_lodging(tour_id)}
    out = []
    for c in rows:
        et = c["entity_type"]
        if et in need and not can(viewer, need[et]):
            continue
        if c["field"] in hidden_fields.get(et, ()) and not can(viewer, "travel" if et == "travel" else "hotel"):
            continue
        row = {"schedule": sched, "travel": legs, "lodging": beds}.get(et, {}).get(c["entity_id"])
        if row is not None and not eng.visible_to(viewer, row, viewer["scopes"]):
            continue
        if et == "travel" and row is not None:
            trav = row.get("travelers") or ["all"]
            pid = (viewer.get("person") or {}).get("id")
            if "all" not in trav and pid not in trav and not can(viewer, "travel"):
                continue
        out.append(c)
    return out


def _files_for(viewer, files):
    out = []
    for f in files:
        if f["visibility"] == "private" and not (viewer["is_owner"] or "admin" in viewer["scopes"]):
            continue
        if f["visibility"] == "management" and not (can(viewer, "edit") or can(viewer, "people")):
            continue
        if f["category"] in MONEY_FILE_CATEGORIES and not can(viewer, "financials"):
            continue
        out.append(f)
    return out


# --- shared context ---------------------------------------------------------

def _status_line(tour, shows):
    return eng.show_status_line(tour, shows, eng.today_in(tour["home_tz"]))


def _ctx(user, tour, viewer, nav, **extra):
    """`nav` is the tour-level tab; `tab` (optional, in extra) is the
    Show Command tab and defaults to nav."""
    shows = extra.pop("shows", None)
    tab = extra.pop("tab", nav)
    if shows is None:
        shows = ts.list_shows(tour["id"])
    today = eng.today_in(tour["home_tz"])
    base = {
        "active_page": "tours", "tour": tour, "viewer": viewer, "nav": nav, "tab": tab,
        "can": lambda s: can(viewer, s), "shows": [_strip_money(viewer, s) for s in shows],
        "mode": eng.tour_mode(tour, shows, today), "status_line": _status_line(tour, shows),
        "today": today, "tour_tabs": _tour_tabs(viewer), "tour_bar": _tour_bar(viewer, nav),
        "show_tabs": SHOW_TABS,
        "vocab": {
            "day_kinds": ts.DAY_KINDS, "schedule_categories": ts.SCHEDULE_CATEGORIES,
            "precision": ts.SCHEDULE_PRECISION, "visibility": ts.VISIBILITY,
            "advance_categories": ts.ADVANCE_CATEGORIES, "advance_statuses": ts.ADVANCE_STATUSES,
            "travel_modes": ts.TRAVEL_MODES, "travel_statuses": ts.TRAVEL_STATUSES,
            "room_kinds": ts.ROOM_KINDS, "people_categories": ts.PEOPLE_CATEGORIES,
            "guest_categories": ts.GUEST_CATEGORIES, "guest_statuses": ts.GUEST_STATUSES,
            "deal_types": ts.DEAL_TYPES, "settlement_statuses": ts.SETTLEMENT_STATUSES,
            "expense_categories": ts.EXPENSE_CATEGORIES, "file_categories": ts.FILE_CATEGORIES,
            "content_statuses": ts.CONTENT_STATUSES, "scopes": ts.SCOPES,
            "role_presets": ts.ROLE_PRESETS, "share_scopes": ts.SHARE_SCOPES,
            "tour_statuses": ts.TOUR_STATUSES, "show_statuses": ts.SHOW_STATUSES,
        },
        "fmt_time": eng.fmt_time, "fmt_day": eng.fmt_day_long,
    }
    base.update(extra)
    return base


def _tour_tabs(viewer):
    out = []
    for key, label, path in TOUR_TABS:
        need = TOUR_TAB_SCOPE.get(key)
        if need and not can(viewer, need):
            continue
        out.append((key, label, path))
    return out


def _tour_bar(viewer, nav):
    """The seven-entry bar, the More menu and the sub-row, scope-filtered.

    `nav` is the page's TOUR_TABS key. A page under a group (hotels, map)
    lights its primary entry and gets the group's sub-row; a page in More
    lights the More button with its own label.
    """
    allowed = {k: (label, path) for k, label, path in _tour_tabs(viewer)}
    grouped = {k for keys in BAR_GROUPS.values() for k, _ in keys}
    primary, more, sub = [], [], []
    for key in PRIMARY_TABS:
        if key not in allowed:
            continue
        label, path = allowed[key]
        members = tuple(k for k, _ in BAR_GROUPS.get(key, ((key, label),)))
        primary.append({"key": key, "label": BAR_LABELS.get(key, label), "path": path,
                        "on": nav in members})
        if nav in members and key in BAR_GROUPS:
            for k, sub_label in BAR_GROUPS[key]:
                if k in allowed:
                    sub.append({"key": k, "label": sub_label, "path": allowed[k][1], "on": nav == k})
    for key in MORE_ORDER:
        if key not in allowed or key in grouped:
            continue
        label, path = allowed[key]
        more.append({"key": key, "label": label, "path": path, "on": nav == key})
    active_more = next((m for m in more if m["on"]), None)
    return {"primary": primary, "more": more, "sub": sub, "active_more": active_more}


def _show_url(tour, show, tab=None):
    base = "/tours/%s/shows/%s" % (tour["id"], show["id"])
    return base + ("?tab=%s" % tab if tab else "")


def _back(default):
    ref = request.referrer or ""
    if ref and "/tours/" in ref and request.host in ref:
        return redirect(ref)
    return redirect(default)


def _date_rows(tour, show, full=False):
    """The rows that decide readiness and which optional sections have
    data. `full` adds the sections that own no readiness category."""
    tid, sid = tour["id"], show["id"]
    rows = {
        "travel": ts.list_travel(tid, show_id=sid) +
                  [t for t in ts.list_travel(tid, day_date=show["date"]) if not t.get("show_id")],
        "lodging": ts.list_lodging(tid, show_id=sid) or ts.list_lodging(tid, on_date=show["date"]),
        "files": ts.list_files(tid, entity_type="show", entity_id=sid),
        "guest_rows": ts.list_guests(tid, sid),
        "vip_rows": ts.list_vip(tid, sid),
        "content": ts.list_content(tid, show_id=sid),
        "expenses": ts.list_expenses(tid, show_id=sid),
    }
    if full:
        rows["counts"] = ts.list_merch_counts(tid, show_id=sid)
        rows["setlists"] = ts.list_setlists(tid, show_id=sid)
    return rows


def _has_data(show, rows, viewer=None, tasks=None):
    """Which optional sections have rows on this date. A section with
    rows is on the page whether or not anybody added it, and its
    readiness categories count."""
    mk = show.get("marketing") or {}

    def filled(*keys):
        return any(str(show.get(k) or "").strip() for k in keys)

    files = rows.get("files") or []
    if viewer is not None:
        files = _files_for(viewer, files)
    return {
        "hotel": bool(rows.get("lodging")),
        "travel": bool(rows.get("travel")),
        "guests": bool(rows.get("guest_rows")),
        "vip": bool(rows.get("vip_rows")),
        "settlement": filled(*SETTLEMENT_FIELDS) or bool(rows.get("expenses"))
                      or (show.get("settlement_status") or "open") != "open",
        "marketing": any(str(v or "").strip() for v in mk.values())
                     or filled("ticket_url", "ticket_status", "tickets_sold"),
        "content": any((c.get("assignee") or c.get("file_id") or c.get("due_time")
                        or c.get("status") not in ("", "planned", None))
                       for c in rows.get("content") or []),
        "merch": bool(rows.get("counts")),
        "setlist": bool(rows.get("setlists")),
        "files": bool(files),
        "tasks": bool(tasks),
    }


def _opted_sections(show):
    return [k for k in (show.get("readiness_config") or []) if k in SECTION_KEYS]


def _effective_categories(show, has):
    """Core categories always; an optional section's categories once it
    is opted in or has rows. Nothing else counts against the score, so a
    date with no hotel entered is not 'missing a hotel' until somebody
    says the date needs one."""
    cats = list(CORE_CATEGORIES)
    opted = set(_opted_sections(show))
    for key, _label, _icon, owned in OPTIONAL_SECTIONS:
        if owned and (key in opted or has.get(key)):
            cats.extend(owned)
    return cats


def _readiness_for(tour, show, viewer=None, rows=None, has=None):
    ts.ensure_advance_items(tour["id"], tour["user_id"], show["id"])
    adv = ts.list_advance(tour["id"], show["id"])
    rows = rows or _date_rows(tour, show)
    has = has or _has_data(show, rows)
    guests = ts.guest_summary(tour["id"], show["id"], show.get("guest_allocation"))
    return eng.show_readiness(show, adv, rows["travel"], rows["lodging"], rows["files"], guests,
                              rows["content"], len(rows["vip_rows"]), _effective_categories(show, has))


def _notify_members(tour, title, body, link, exclude_user_id=None, severity="info", scope=None):
    """In-app notification to everyone on the tour with an account — or,
    when `scope` is given, only to members holding that scope (the owner
    always). Email only for critical changes, only when a real sender is
    configured."""
    targets = {tour["user_id"]}
    for m in ts.list_members(tour["id"]):
        if m.get("member_user_id") and m["status"] == "active":
            if scope and not ("admin" in m["scopes"] or scope in m["scopes"]):
                continue
            targets.add(m["member_user_id"])
    targets.discard(exclude_user_id)
    for uid in targets:
        store.notify(uid, "tour", title, body, link)
    if severity == "critical" and emailer.configured() and not emailer.using_shared_test_sender():
        for uid in targets:
            u = store.get_user(uid)
            if u and u.get("email"):
                try:
                    emailer.send(u["email"], "[%s] %s" % (tour["name"], title),
                                 "<p>%s</p><p>%s</p><p><a href=\"%s%s\">Open in Street Banker</a></p>"
                                 % (_esc(title), _esc(body), _base_url(), link))
                except Exception:
                    pass


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_NOTIFY_SCOPE = {"money": "financials", "expense": "financials", "guest": "guests", "vip": "vip"}


def _log(tour, viewer, entity_type, entity_id, label, changes, source="manual", visibility="all"):
    """Write one tour_changes row per changed field, classify it, and
    notify on important/critical. Money and guest changes notify only
    the scopes that may read them; a change on a management-only or
    private row notifies admins only; and the notification body never
    carries values for scoped entities — the page does, behind the
    same check."""
    worst = None
    for field, (before, after) in (changes or {}).items():
        sev = eng.classify_change(entity_type, field)
        ts.log_change(tour["id"], tour["user_id"], _actor(viewer), entity_type, entity_id,
                      label, field, before, after, sev, source)
        if sev in ("important", "critical") and (worst is None or sev == "critical"):
            worst = (sev, field, before, after)
    if worst:
        sev, field, before, after = worst
        scope = _NOTIFY_SCOPE.get(entity_type)
        if visibility != "all":
            scope = "admin"
        body = "" if scope else "%s → %s" % (before or "—", after or "—")
        _notify_members(tour, "%s: %s changed" % (label, field.replace("_", " ")), body,
                        "/tours/%s/changes" % tour["id"], exclude_user_id=viewer["user"]["id"],
                        severity=sev, scope=scope)


def _artist_tier(user):
    return plans.allowed(user.get("plan") or "artist", "artist")


# --- index & create ---------------------------------------------------------

@bp.route("/tours")
def index():
    user = _me()
    if user is None:
        return redirect(url_for("login", next=request.path))
    ts.adopt_orphan_shows(user["id"])   # a Hub show on no tour joins one before the list is read
    mine = ts.list_tours(user["id"])
    shared = ts.tours_shared_with(user["id"])
    for t in mine + shared:
        shows = ts.list_shows(t["id"])
        t["show_count"] = len(shows)
        t["status_line"] = _status_line(t, shows)
        t["mode"] = eng.tour_mode(t, shows)
    unattached = [s for s in store.list_tour_shows(user["id"]) if not s.get("tour_id")]
    return render_template("tour/index.html", active_page="tours", mine=mine, shared=shared,
                           unattached=unattached, can_own=_artist_tier(user),
                           is_demo=_is_demo(user), tz_guess=_tz_guess(),
                           tour_statuses=ts.TOUR_STATUSES)


def _tz_guess():
    return "America/New_York"


def _is_demo(user):
    email = (user or {}).get("email") or ""
    return email == "demo@streetbanker.io" or (email.startswith("demo-") and email.endswith("@streetbanker.io"))


@bp.route("/tours/new", methods=["POST"])
def create():
    user = _me()
    if user is None:
        return redirect(url_for("login", next="/tours"))
    if not _artist_tier(user):
        return render_template("upgrade.html", required="artist", plans_list=plans.PLANS,
                               active_page="tours"), 402
    tz = request.form.get("home_tz") or "UTC"
    if not eng.valid_tz(tz):
        tz = "UTC"
    tour_id = ts.create_tour(user["id"], {
        "name": request.form.get("name"), "artist_name": request.form.get("artist_name") or user.get("name"),
        "start_date": request.form.get("start_date"), "end_date": request.form.get("end_date"),
        "home_tz": tz, "currency": request.form.get("currency") or "USD"})
    # Bring any existing Tour Hub shows in the window onto the tour
    if request.form.get("adopt"):
        for s in store.list_tour_shows(user["id"]):
            if s.get("tour_id"):
                continue
            ts.attach_show(tour_id, s["id"], tz)
    tour = ts.get_tour(tour_id)
    ts.log_change(tour_id, user["id"], {"id": user["id"], "name": user.get("name")}, "tour",
                  tour_id, tour["name"], "created", "", tour["name"], "info")
    return redirect("/tours/%s" % tour_id)


@bp.route("/tours/seed-demo", methods=["POST"])
def seed_demo():
    """Example data, for the demo showcase account only. Production
    workspaces never see it: any other account gets a 404."""
    user = _me()
    if user is None or not _is_demo(user):
        abort(404)
    import tour_seed
    tour_id = tour_seed.seed(user["id"])
    return redirect("/tours/%s" % tour_id)


# --- join -------------------------------------------------------------------

@bp.route("/tours/join/<token>")
def join(token):
    invite = ts.get_invite(token)
    if invite is None:
        return render_template("tour/join.html", invite=None, active_page="tours"), 404
    user = _me()
    if user is None:
        return redirect(url_for("login", next=request.path))
    if ts.accept_invite(token, user["id"]):
        m = ts.get_member_by_email(invite["tour_id"], invite["email"])
        # Link a person record by email so My Day can find them
        if m and not m.get("person_id"):
            for p in ts.list_people(invite["tour_id"]):
                if p["email"] and p["email"] == invite["email"]:
                    ts.link_member_person(invite["tour_id"], m["id"], p["id"])
                    break
        store.notify(ts.get_tour(invite["tour_id"])["user_id"], "tour",
                     "%s joined %s" % (user.get("name") or user["email"], invite["tour_name"]),
                     "", "/tours/%s/team" % invite["tour_id"])
    return redirect("/tours/%s" % invite["tour_id"])


# --- tour home --------------------------------------------------------------

@bp.route("/tours/<tour_id>")
@require_tour("view")
def home(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    today = eng.today_in(tour["home_tz"])
    schedule = _visible(viewer, ts.list_schedule(tour_id))
    travel = _redact_travel(viewer, ts.list_travel(tour_id))
    lodging = _redact_lodging(viewer, ts.list_lodging(tour_id))
    upcoming = [s for s in shows if s["date"] >= today][:5]
    readiness = {}
    per_show = []
    for s in shows:
        r = _readiness_for(tour, s, viewer)
        readiness[s["id"]] = r
        per_show.append({"show": s, "readiness": r})
    tour_ready = eng.tour_readiness(per_show)
    attention = eng.needs_attention(shows, readiness, today)
    sched_p, travel_p = eng.personal(viewer, viewer["scopes"], schedule, travel)
    nxt = eng.next_item(tour, shows, sched_p, travel_p)
    changes = _changes_for(viewer, tour_id, ts.list_changes(tour_id, severity_min="important", limit=40))[:8]
    acks = ts.ack_state(tour_id, [c["id"] for c in changes], user["id"])
    for c in changes:
        if c["id"] not in acks:
            ts.ack(tour_id, tour["user_id"], c["id"], user["id"], "delivered")
    unack = [c for c in changes if c["severity"] == "critical" and acks.get(c["id"]) != "acknowledged"]
    finance = None
    if can(viewer, "financials"):
        exp = {}
        for e in ts.list_expenses(tour_id):
            exp.setdefault(e.get("show_id") or "", []).append(e)
        finance = eng.tour_finance(shows, exp, tour["currency"], today=today)
    tasks = _tour_tasks(tour, shows)
    open_tasks = [t for t in tasks if t["status"] in ("new", "in_progress")]
    guests_pending = 0
    if can(viewer, "guests"):
        for s in upcoming:
            guests_pending += ts.guest_summary(tour_id, s["id"], s.get("guest_allocation"))["pending"]
    people_count = len(ts.list_people(tour_id))
    my_day = eng.my_day(viewer, viewer["scopes"], shows, schedule, travel, lodging, today)
    return render_template("tour/home.html", **_ctx(
        user, tour, viewer, "home", shows=shows, upcoming=upcoming, readiness=readiness,
        tour_ready=tour_ready, attention=attention[:10], nxt=nxt, changes=changes,
        acks=acks, unack=unack, finance=finance, open_tasks=open_tasks[:6],
        guests_pending=guests_pending, people_count=people_count, my_day=my_day,
        hotel_tonight=my_day["hotel"], today_show=next((s for s in shows if s["date"] == today), None)))


@bp.route("/tours/<tour_id>/mode", methods=["POST"])
@require_tour("edit")
def set_mode(user, tour, viewer, tour_id):
    mode = request.form.get("mode") or ""
    ts.update_tour(tour_id, {"mode_override": mode if mode in ("live", "planning") else ""})
    return _back("/tours/%s" % tour_id)


# --- my day -----------------------------------------------------------------

@bp.route("/tours/<tour_id>/my-day")
@require_tour("view")
def my_day(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    on = request.args.get("date") or eng.today_in(tour["home_tz"])
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", on):
        on = eng.today_in(tour["home_tz"])
    schedule = _visible(viewer, ts.list_schedule(tour_id))
    travel = _redact_travel(viewer, ts.list_travel(tour_id))
    lodging = _redact_lodging(viewer, ts.list_lodging(tour_id))
    day = eng.my_day(viewer, viewer["scopes"], shows, schedule, travel, lodging, on)
    show = next((s for s in shows if s["date"] == on), None)
    day_row = next((d for d in ts.list_days(tour_id) if d["date"] == on), None)
    venue = ts.get_venue(tour["user_id"], show["venue_id"]) if show and show.get("venue_id") else None
    sched_p, travel_p = eng.personal(viewer, viewer["scopes"], schedule, travel)
    nxt = eng.next_item(tour, shows, sched_p, travel_p)
    prev_d = (date.fromisoformat(on) - timedelta(days=1)).isoformat()
    next_d = (date.fromisoformat(on) + timedelta(days=1)).isoformat()
    contacts = []
    if show:
        people = _redact_people(viewer, ts.list_people(tour_id))
        contacts = [p for p in people if p["category"] in ("Tour Management", "Production", "Venue", "Drivers", "Security")
                    and (not p.get("shows") or show["id"] in p["shows"])][:6]
    return render_template("tour/my_day.html", **_ctx(
        user, tour, viewer, "my-day", shows=shows, day=day, on=on, show=_strip_money(viewer, show),
        day_row=day_row, venue=venue, nxt=nxt, prev_d=prev_d, next_d=next_d, contacts=contacts,
        now_local=eng.now_in((show or {}).get("tz") or tour["home_tz"]).strftime("%H:%M"),
        tz_shown=(show or {}).get("tz") or tour["home_tz"]))


# --- calendar & days --------------------------------------------------------

@bp.route("/tours/<tour_id>/calendar")
@require_tour("view")
def calendar(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    days = ts.list_days(tour_id)
    today = eng.today_in(tour["home_tz"])
    month = request.args.get("month") or (tour["start_date"][:7] if tour["start_date"] and tour["start_date"] > today else today[:7])
    if not re.match(r"^\d{4}-\d{2}$", month):
        month = today[:7]
    y, m = int(month[:4]), int(month[5:7])
    first = date(y, m, 1)
    start = first - timedelta(days=(first.weekday() + 1) % 7)   # weeks start Sunday
    cells = []
    readiness = {}
    if request.args.get("ready") != "0":
        for s in shows:
            if s["date"][:7] == month:
                readiness[s["id"]] = _readiness_for(tour, s, viewer)["pct"]
    by_date = {}
    for d in days:
        by_date.setdefault(d["date"], []).append(d)
    show_by_id = {s["id"]: s for s in shows}
    for i in range(42):
        d = start + timedelta(days=i)
        iso = d.isoformat()
        cells.append({"date": iso, "day": d.day, "in_month": d.month == m, "today": iso == today,
                      "items": by_date.get(iso, []), "show_by_id": show_by_id})
    prev_m = (first - timedelta(days=1)).strftime("%Y-%m")
    next_m = (first + timedelta(days=32)).replace(day=1).strftime("%Y-%m")
    view = request.args.get("view") or "month"
    return render_template("tour/calendar.html", **_ctx(
        user, tour, viewer, "calendar", shows=shows, cells=cells, month=month, prev_m=prev_m,
        next_m=next_m, month_label=first.strftime("%B %Y"), days=days, readiness=readiness,
        view=view, show_by_id=show_by_id))


@bp.route("/tours/<tour_id>/days/add", methods=["POST"])
@require_tour("edit", "schedule")
def day_add(user, tour, viewer, tour_id):
    f = request.form
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", f.get("date") or ""):
        return _back("/tours/%s/calendar" % tour_id)
    kind = f.get("kind") or "other"
    if kind == "show":
        show_id = store.add_tour_show(tour["user_id"], f.get("date"), f.get("venue") or "TBA",
                                      f.get("city") or "", f.get("notes") or "")
        ts.attach_show(tour_id, show_id, f.get("tz") or tour["home_tz"])
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "show", show_id,
                      f.get("venue") or "TBA", "created", "", f.get("date"), "info")
        return redirect(_show_url(tour, {"id": show_id}))
    day_id = ts.add_day(tour_id, tour["user_id"], f.get("date"), kind, f.get("title"),
                        f.get("city"), f.get("tz"), None, f.get("notes"))
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "day", day_id,
                  f.get("title") or kind, "created", "", f.get("date"), "info")
    return _back("/tours/%s/calendar?month=%s" % (tour_id, f.get("date")[:7]))


@bp.route("/tours/<tour_id>/days/<day_id>/edit", methods=["POST"])
@require_tour("edit", "schedule")
def day_edit(user, tour, viewer, tour_id, day_id):
    day = ts.get_day(tour_id, day_id)
    if day is None:
        abort(404)
    if request.form.get("action") == "delete":
        if day.get("show_id"):
            return _back("/tours/%s/calendar" % tour_id)   # shows are deleted from Show Command
        ts.delete_day(tour_id, day_id)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "day", day_id,
                      day.get("title") or day["kind"], "deleted", day["date"], "", "important")
        return _back("/tours/%s/calendar" % tour_id)
    fields = {k: request.form.get(k) for k in ("date", "kind", "title", "city", "tz", "notes") if k in request.form}
    before = day["date"]
    ts.update_day(tour_id, day_id, fields)
    if fields.get("date") and fields["date"] != before:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "day", day_id,
                      day.get("title") or day["kind"], "date", before, fields["date"], "important")
    return _back("/tours/%s/calendar" % tour_id)


# --- shows list -------------------------------------------------------------

@bp.route("/tours/<tour_id>/shows")
@require_tour("view")
def shows_list(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    readiness = {s["id"]: _readiness_for(tour, s, viewer) for s in shows}
    unattached = [s for s in store.list_tour_shows(tour["user_id"]) if not s.get("tour_id")] if viewer["is_owner"] else []
    venues = ts.list_venues(tour["user_id"])
    can_send = can(viewer, "advance") or can(viewer, "edit")
    return render_template("tour/shows.html", **_ctx(
        user, tour, viewer, "shows", shows=shows, readiness=readiness, unattached=unattached,
        venues=venues, sends=ts.advance_send_map(tour_id),
        advance_to=_advance_to(tour, shows) if can_send else {}, can_send=can_send,
        mail_ready=emailer.configured() and not emailer.using_shared_test_sender(),
        sender_address=emailer.sender(),
        advanced=request.args.get("advanced"), advance_failed=request.args.get("advance_failed"),
        advance_skipped=request.args.get("advance_skipped"),
        advance_fail=request.args.get("advance_fail")))


@bp.route("/tours/<tour_id>/shows/attach", methods=["POST"])
@require_tour("admin")
def shows_attach(user, tour, viewer, tour_id):
    show = store.get_tour_show(tour["user_id"], request.form.get("show_id") or "")
    if show is None:
        abort(404)
    ts.attach_show(tour_id, show["id"], request.form.get("tz") or tour["home_tz"])
    return redirect("/tours/%s/shows" % tour_id)


# --- show command -----------------------------------------------------------

def _show_or_404(tour, show_id):
    show = ts.get_show(tour["id"], show_id)
    if show is None:
        abort(404)
    return show


def _tour_tasks(tour, shows, show_id=None):
    ids = {s["id"] for s in shows}
    out = []
    for a in command_center.list_actions(tour["user_id"]):
        if a.get("entity_type") == "tour" and a.get("entity_id") == tour["id"]:
            if show_id is None:
                out.append(a)
        elif a.get("entity_type") == "tour_show" and a.get("entity_id") in ids:
            if show_id is None or a["entity_id"] == show_id:
                out.append(a)
    return out


@bp.route("/tours/<tour_id>/shows/<show_id>")
@require_tour("view")
def show(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    tab = request.args.get("tab") or "overview"
    if tab not in dict(SHOW_TABS) and tab not in SECTION_KEYS:
        tab = "overview"
    need = TAB_SCOPE.get(tab) or SECTION_VIEW_SCOPE.get(tab)
    if need and not can(viewer, need):
        return render_template("tour/denied.html", tour=tour, viewer=viewer, needed=(need,),
                               active_page="tours"), 403
    return _date_page(user, tour, viewer, show, tab)


def _plural(n, word, plural=None):
    return "%d %s" % (n, word if n == 1 else (plural or word + "s"))


def _section_status(key, d, show, tour):
    """The one line in a section head. Counts from rows, never a guess;
    money says 'no numbers entered' rather than zero."""
    if key == "times":
        sched, acts = d["schedule"], d["lineup"]
        if not sched and not acts:
            return "No times yet"
        parts = []
        if sched:
            parts.append("%s · %d confirmed" % (_plural(len(sched), "item"),
                                               sum(1 for r in sched if r.get("confirmed"))))
        if acts:
            parts.append(_plural(len(acts), "act") + " on the bill")
        return " · ".join(parts)
    if key == "advance":
        p = d["advance_progress"]
        out = "%d of %d" % (p["done"], p["total"])
        return out + (" · %d waiting" % p["waiting"] if p["waiting"] else "")
    if key == "venue":
        v = d["venue"]
        head = (v["name"] + (", " + v["city"] if v.get("city") else "")) if v else "No venue record linked"
        return "%s · %s" % (head, _plural(len(d["show_people"]), "contact"))
    if key == "deal":
        m = d.get("money")
        if not m or not m["has_numbers"]:
            return "No numbers entered"
        out = (show.get("deal_type") or "flat").replace("_", " ")
        if str(show.get("guarantee") or "").strip():
            out += " · guarantee %s %s" % (show["guarantee"], show.get("currency") or tour["currency"])
        return out
    if key == "notes":
        first = next((ln.strip() for ln in (show.get("notes") or "").splitlines() if ln.strip()), "")
        return (first[:80] + ("…" if len(first) > 80 else "")) if first else "No notes yet"
    if key == "activity":
        n = len(d.get("changes") or [])
        return _plural(n, "change") if n else "No activity yet"
    if key == "hotel":
        rows = d.get("lodging") or []
        if not rows:
            return "No hotel yet"
        out = "%s · %s" % (rows[0]["property"], rows[0]["status"].replace("_", " "))
        return out + (" · +%d more" % (len(rows) - 1) if len(rows) > 1 else "")
    if key == "travel":
        rows = d.get("travel") or []
        if not rows:
            return "No travel yet"
        return "%s · %d confirmed" % (_plural(len(rows), "leg"),
                                      sum(1 for t in rows if t.get("status") == "confirmed"))
    if key == "guests":
        g = d.get("guests")
        if not d.get("guest_rows"):
            return "No guests yet"
        alloc = " of %d" % g["allocation"] if g and g.get("allocation") is not None else ""
        return "%d%s approved · %d pending" % (g["used"], alloc, g["pending"])
    if key == "vip":
        v = d.get("vip") or {}
        if not d.get("vip_rows"):
            return "No VIP packages yet"
        return "%s sold · %d checked in" % (_plural(v.get("sold", 0), "package"), v.get("checked_in", 0))
    if key == "merch":
        products = d.get("products") or []
        if not products:
            return "No products on this tour"
        counted = len(d.get("counts") or {})
        return "%d of %d products counted" % (counted, len(products)) if counted else "No counts yet"
    if key == "marketing":
        tp = d.get("ticket_progress")
        if tp:
            return "%d of %d tickets · %d%%" % (tp["sold"], tp["cap"], tp["pct"])
        if str(show.get("ticket_url") or "").strip():
            return "Ticket link set"
        return "Nothing entered yet"
    if key == "content":
        rows = d.get("content") or []
        if not rows:
            return "No content plan yet"
        return "%d of %d assigned" % (sum(1 for c in rows if c.get("assignee")), len(rows))
    if key == "setlist":
        rows = d.get("setlists") or []
        return _plural(len(rows), "set list") if rows else "No set list yet"
    if key == "files":
        rows = d.get("show_files") or []
        return _plural(len(rows), "file") if rows else "No files yet"
    if key == "tasks":
        rows = d.get("tasks") or []
        if not rows:
            return "No tasks yet"
        open_n = sum(1 for t in rows if t.get("status") in ("new", "in_progress"))
        return "%d open · %d done" % (open_n, len(rows) - open_n)
    return ""


def _date_page(user, tour, viewer, show, tab, **extra):
    """Render one date as one page: every core section, the optional
    sections that are on (opted, have rows, or deep-linked), and a `+`
    chip for the rest. `tab` is the old deep link: it names the element
    the page opens and scrolls to."""
    tid, sid = tour["id"], show["id"]
    shows = ts.list_shows(tid)
    idx = next((i for i, s in enumerate(shows) if s["id"] == sid), 0)
    rows = _date_rows(tour, show, full=True)
    tasks = _tour_tasks(tour, shows, show_id=sid)
    has = _has_data(show, rows, viewer, tasks)
    readiness = _readiness_for(tour, show, viewer, rows=rows, has=has)
    opted = _opted_sections(show)
    people_all = _redact_people(viewer, ts.list_people(tid))
    sched_ids = {r["id"] for r in ts.list_schedule(tid, show_id=sid)}
    mine = [c for c in ts.list_changes(tid, limit=600) if c["entity_id"] == sid or c["entity_id"] in sched_ids]
    d = {
        "show": _strip_money(viewer, show), "readiness": readiness,
        "open_target": None if tab == "overview" else tab, "show_url": _show_url(tour, show),
        "venue": ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None,
        "prev_show": shows[idx - 1] if idx > 0 else None,
        "next_show": shows[idx + 1] if idx + 1 < len(shows) else None,
        "guests": ts.guest_summary(tid, sid, show.get("guest_allocation")) if can(viewer, "guests") else None,
        "day_row": next((dd for dd in ts.list_days(tid) if dd.get("show_id") == sid), None),
        # times
        "schedule": _visible(viewer, ts.list_schedule(tid, show_id=sid)),
        "people_names": [p["name"] for p in people_all], "people": people_all,
        "lineup": ts.seed_lineup_from_support(tid, show),
        # advance, with the production pack and the mail behind disclosures
        "advance": ts.list_advance(tid, sid), "advance_progress": ts.advance_progress(tid, sid),
        "prod_files": _files_for(viewer, [f for f in rows["files"] if f["category"] in PRODUCTION_FILE_CATEGORIES]),
        "prod_tour_files": _files_for(viewer, [f for f in ts.list_files(tid, entity_type="tour")
                                               if f["category"] in ("stage_plot", "tech_pack", "rider", "production")]),
        "sent": request.args.get("sent"), "fail": request.args.get("fail"),
        # venue & contacts
        "venues": ts.list_venues(tour["user_id"]),
        "show_people": [p for p in people_all if not p.get("shows") or sid in p["shows"]],
        # activity
        "changes": _changes_for(viewer, tid, mine)[:100],
    }
    d["lineup_warnings"] = ts.lineup_warnings(d["lineup"], fmt_time=eng.fmt_time)
    if can(viewer, "advance"):
        d["imports"] = [i for i in ts.list_imports(tid) if i["summary"].get("show_id") == sid][:10]
        d.update(_send_context(tour, show, viewer, user))
    if can(viewer, "financials"):
        d["expenses"] = rows["expenses"]
        d["money"] = eng.show_money(show, rows["expenses"])
        d["receipts"] = ts.list_files(tid, entity_type="expense")
        d["settlement_on"] = "settlement" in opted or has["settlement"] or tab == "settlement"
        d["settlement_removable"] = "settlement" in opted and not has["settlement"]
    # optional sections: shown, or offered as a chip
    shown, chips = [], []
    for key, label, icon, _owned in OPTIONAL_SECTIONS:
        need = SECTION_VIEW_SCOPE.get(key)
        if need and not can(viewer, need):
            continue
        can_add = can(viewer, "edit") or can(viewer, SECTION_ADD_SCOPE[key])
        on = key in opted or has[key] or tab == key
        sec = {"key": key, "label": label, "icon": icon, "optional": True, "opted": key in opted,
               "has_data": has[key], "target": tab == key, "open": True,
               "add_label": ADD_LABELS.get(key, "Add"),
               "removable": can_add and key in opted and not has[key]}
        if not on:
            if can_add:
                chips.append(sec)
            continue
        if key == "hotel":
            d["lodging"] = _redact_lodging(viewer, rows["lodging"])
            d["rooms"] = {l["id"]: _redact_rooms(viewer, ts.list_rooms(tid, l["id"])) for l in d["lodging"]}
            d["edit_hotel"] = (ts.get_lodging(tid, request.args.get("edit") or "")
                               if tab == "hotel" and can(viewer, "hotel") else None)
        elif key == "travel":
            d["travel"] = _redact_travel(viewer, rows["travel"])
            d["edit_travel"] = (ts.get_travel(tid, request.args.get("edit") or "")
                                if tab == "travel" and can(viewer, "travel") else None)
        elif key == "guests":
            d["guest_rows"] = rows["guest_rows"]
            d["contacts"] = press_store.list_contacts(tour["user_id"])[:200] if viewer["is_owner"] else []
        elif key == "vip":
            d["vip_rows"] = rows["vip_rows"]
            d["vip"] = ts.vip_summary(tid, sid)
        elif key == "merch":
            d["products"] = ts.list_products(tid)
            d["counts"] = {c["product_id"]: c for c in rows["counts"]}
        elif key == "marketing":
            d["marketing"] = show.get("marketing") or {}
            d["ticket_progress"] = _ticket_progress(show)
        elif key == "content":
            ts.ensure_content_plan(tid, tour["user_id"], sid)
            d["content"] = ts.list_content(tid, show_id=sid)
        elif key == "setlist":
            d["setlists"] = [ts.get_setlist(tid, x["id"]) for x in rows["setlists"]]
            d["tour_setlists"] = [x for x in ts.list_setlists(tid) if not x.get("show_id")]
            d["tracks"] = store.list_os_tracks(tour["user_id"])
        elif key == "files":
            d["show_files"] = _files_for(viewer, rows["files"])
        elif key == "tasks":
            d["tasks"] = tasks
        if key != "settlement":          # the settlement lives inside Deal
            sec["status"] = _section_status(key, d, show, tour)
            shown.append(sec)
    core = []
    for key, label, icon in CORE_SECTIONS:
        need = SECTION_VIEW_SCOPE.get(key)
        if need and not can(viewer, need):
            continue
        core.append({"key": key, "label": label, "icon": icon, "optional": False, "opted": True,
                     "has_data": True, "target": tab == key or TAB_SECTION.get(tab) == key,
                     "open": key != "activity" or tab == "activity", "removable": False,
                     "status": _section_status(key, d, show, tour)})
    d["sections"] = [c for c in core if c["key"] != "activity"] + shown
    d["tail_sections"] = [c for c in core if c["key"] == "activity"]
    d["chips"] = chips
    d.update(extra)
    return render_template("tour/show.html", **_ctx(user, tour, viewer, "shows", shows=shows, tab=tab, **d))


@bp.route("/tours/<tour_id>/shows/<show_id>/sections", methods=["POST"])
@require_tour("edit", *sorted(set(SECTION_ADD_SCOPE.values())))
def show_sections(user, tour, viewer, tour_id, show_id):
    """Add an optional section to this date, or take an empty one off.
    The opted keys are stored on the show; a section with rows is refused
    removal, because its rows would keep it on the page anyway and its
    readiness categories would keep counting."""
    show = _show_or_404(tour, show_id)
    key = request.form.get("key") or ""
    action = request.form.get("action") or "add"
    if key not in SECTION_ADD_SCOPE or action not in ("add", "remove"):
        abort(404)
    need = SECTION_VIEW_SCOPE.get(key)
    if not (can(viewer, "edit") or can(viewer, SECTION_ADD_SCOPE[key])) or (need and not can(viewer, need)):
        return render_template("tour/denied.html", tour=tour, viewer=viewer,
                               needed=(SECTION_ADD_SCOPE[key],), active_page="tours"), 403
    before = _opted_sections(show)
    after = list(before)
    if action == "add":
        if key not in after:
            after.append(key)
    else:
        has = _has_data(show, _date_rows(tour, show, full=True), viewer,
                        _tour_tasks(tour, ts.list_shows(tour_id), show_id=show_id))
        if has.get(key):
            return redirect(_show_url(tour, show, key))      # rows keep it on the page
        after = [k for k in after if k != key]
    if after != before:
        ts.update_show_ext(tour_id, show_id, {"readiness_config": after})
        _log(tour, viewer, "show", show_id, show["venue"],
             {"sections": (", ".join(before) or "—", ", ".join(after) or "—")})
    return redirect(_show_url(tour, show, key if action == "add" else None))


def _ticket_progress(show):
    try:
        sold = float(str(show.get("tickets_sold") or "").replace(",", ""))
        cap = float(str(show.get("capacity") or "").replace(",", ""))
    except ValueError:
        return None
    if not cap:
        return None
    return {"sold": int(sold), "cap": int(cap), "pct": round(100 * sold / cap)}


@bp.route("/tours/<tour_id>/shows/<show_id>/ext", methods=["POST"])
@require_tour("edit", "advance", "guests")
def show_ext(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    fields = {}
    for k in ("venue_id", "promoter", "capacity", "ticket_url", "ticket_status", "tickets_sold",
              "guest_allocation", "guest_cutoff", "tz"):
        if k in request.form:
            fields[k] = request.form.get(k)
    # The guests scope alone may set the allocation and cutoff (the guest
    # list tab offers exactly those); everything else needs edit/advance.
    full = can(viewer, "edit") or can(viewer, "advance")
    if not full:
        fields = {k: v for k, v in fields.items() if k in ("guest_allocation", "guest_cutoff")}
    if "tz" in fields and fields["tz"] and not eng.valid_tz(fields["tz"]):
        fields.pop("tz")
    if "venue_id" in fields and fields["venue_id"]:
        v = ts.get_venue(tour["user_id"], fields["venue_id"])
        if v is None:
            fields.pop("venue_id")
        elif not fields.get("tz") and v.get("tz"):
            fields["tz"] = v["tz"]
    changed = ts.update_show_ext(tour_id, show_id, fields)
    if full and "status" in request.form and request.form["status"] in ts.SHOW_STATUSES:
        if request.form["status"] != show["status"]:
            store.update_tour_show_status(tour["user_id"], show_id, request.form["status"])
            changed = dict(changed or {}, status=(show["status"], request.form["status"]))
    _log(tour, viewer, "show", show_id, show["venue"], changed or {})
    return _back(_show_url(tour, show))


@bp.route("/tours/<tour_id>/shows/<show_id>/notes", methods=["POST"])
@require_tour("edit")
def show_notes(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    with store.get_db() as db:
        db.execute("UPDATE tour_shows SET notes=? WHERE id=? AND user_id=?",
                   ((request.form.get("notes") or "")[:5000], show_id, tour["user_id"]))
    return redirect(_show_url(tour, show, "notes"))


@bp.route("/tours/<tour_id>/shows/<show_id>/delete", methods=["POST"])
@require_tour("admin")
def show_delete(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    if request.form.get("confirm") != show["venue"]:
        return redirect(_show_url(tour, show))
    ts.detach_show(tour_id, show_id)
    store.delete_tour_show(tour["user_id"], show_id)
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "show", show_id, show["venue"],
                  "deleted", show["date"], "", "critical")
    return redirect("/tours/%s/shows" % tour_id)


# --- schedule ---------------------------------------------------------------

def _schedule_fields():
    f = request.form
    return {k: f.get(k) for k in ("show_id", "day_date", "title", "category", "start_time",
                                  "end_time", "precision", "location", "address", "notes",
                                  "responsible", "visibility", "contact_id") if k in f} | \
        {"confirmed": bool(f.get("confirmed")),
         "audience": [a for a in f.getlist("audience") if a]}


@bp.route("/tours/<tour_id>/schedule")
@require_tour("view")
def schedule_all(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    rows = _visible(viewer, ts.list_schedule(tour_id))
    by_day = {}
    for r in rows:
        by_day.setdefault(r["day_date"], []).append(r)
    show_by_date = {s["date"]: s for s in shows}
    return render_template("tour/schedule.html", **_ctx(
        user, tour, viewer, "schedule", shows=shows, by_day=sorted(by_day.items()),
        show_by_date=show_by_date, people_names=[p["name"] for p in ts.list_people(tour_id)],
        people=_redact_people(viewer, ts.list_people(tour_id))))


@bp.route("/tours/<tour_id>/schedule/add", methods=["POST"])
@require_tour("schedule", "edit")
def schedule_add(user, tour, viewer, tour_id):
    fields = _schedule_fields()
    if fields.get("show_id"):
        show = ts.get_show(tour_id, fields["show_id"])
        if show is None:
            fields["show_id"] = None
        elif not fields.get("day_date"):
            fields["day_date"] = show["date"]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fields.get("day_date") or ""):
        return _back("/tours/%s/schedule" % tour_id)
    item_id = ts.add_schedule_item(tour_id, tour["user_id"], fields)
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", item_id,
                  fields.get("title") or "Item", "created", "", "%s %s" % (fields["day_date"], fields.get("start_time") or ""), "info")
    return _back("/tours/%s/schedule" % tour_id)


@bp.route("/tours/<tour_id>/schedule/<item_id>/edit", methods=["POST"])
@require_tour("schedule", "edit")
def schedule_edit(user, tour, viewer, tour_id, item_id):
    item = ts.get_schedule_item(tour_id, item_id)
    if item is None:
        abort(404)
    if request.form.get("action") == "delete":
        ts.delete_schedule_item(tour_id, item_id)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", item_id, item["title"],
                      "deleted", "%s %s" % (item["day_date"], item["start_time"]), "", "important")
        return _back("/tours/%s/schedule" % tour_id)
    if request.form.get("action") == "confirm":
        changed = ts.update_schedule_item(tour_id, item_id, {"confirmed": True})
    else:
        changed = ts.update_schedule_item(tour_id, item_id, _schedule_fields())
    after = ts.get_schedule_item(tour_id, item_id) or item
    _log(tour, viewer, "schedule", item_id, item["title"], changed or {},
         visibility=after.get("visibility") if after.get("visibility") == item.get("visibility") else "management")
    return _back("/tours/%s/schedule" % tour_id)


@bp.route("/tours/<tour_id>/shows/<show_id>/standard-day", methods=["POST"])
@require_tour("schedule", "edit")
def standard_day(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    n = ts.copy_standard_day(tour_id, tour["user_id"], show)
    if n:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", show_id, show["venue"],
                      "standard_day", "", "%d items" % n, "info")
    return redirect(_show_url(tour, show, "schedule"))


@bp.route("/tours/<tour_id>/shows/<show_id>/lineup", methods=["POST"])
@require_tour("schedule", "edit")
def lineup_set(user, tour, viewer, tour_id, show_id):
    """Set the bill for this date, in running order, one act per line.

    One box rather than a row of inputs: a tour manager pastes the running
    order out of an email, and re-typing five acts into five fields to move
    one of them is the reason people keep using a spreadsheet instead.
    """
    show = _show_or_404(tour, show_id)
    raw = request.form.get("acts") or ""
    acts = [line.strip() for line in raw.splitlines() if line.strip()][:20]
    ts.set_lineup(tour_id, show_id, acts,
                  headliner=request.form.get("headliner") or None)
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", show_id,
                  show["venue"], "lineup", "", ", ".join(acts), "info")
    return redirect(_show_url(tour, show, "schedule"))


@bp.route("/tours/<tour_id>/shows/<show_id>/lineup/times", methods=["POST"])
@require_tour("schedule", "edit")
def lineup_times(user, tour, viewer, tour_id, show_id):
    """Save every act's times in one submit.

    An advance arrives as one email with all the times in it, not five
    separate conversations, so the whole bill is one form. Fields are named
    `<field>:<lineup id>`; anything whose id is not on this show's bill is
    ignored rather than trusted, because the id comes from a form.
    """
    show = _show_or_404(tour, show_id)
    known = {row["id"] for row in ts.list_lineup(tour_id, show_id)}

    updates = {}
    for key, value in request.form.items():
        if ":" not in key:
            continue
        field, _, lineup_id = key.partition(":")
        if field not in ("line_check", "set_start", "set_end", "notes"):
            continue
        if lineup_id not in known:
            continue
        updates.setdefault(lineup_id, {})[field] = value or ""

    for lineup_id, fields in updates.items():
        ts.update_lineup_act(tour_id, show_id, lineup_id, fields)

    if updates:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", show_id,
                      show["venue"], "line_checks", "",
                      "%d act%s" % (len(updates), "" if len(updates) == 1 else "s"),
                      "info")
    return redirect(_show_url(tour, show, "schedule"))


@bp.route("/tours/<tour_id>/shows/<show_id>/lineup/schedule", methods=["POST"])
@require_tour("schedule", "edit")
def lineup_to_schedule(user, tour, viewer, tour_id, show_id):
    """Put the advanced line checks on the day sheet.

    Acts with no time are skipped rather than given a default - a line check
    nobody has advanced is not a 16:00 line check, and a day sheet that says
    otherwise sends somebody to the venue at the wrong time.
    """
    show = _show_or_404(tour, show_id)
    added = ts.lineup_schedule_items(tour_id, tour["user_id"], show)
    if added:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", show_id,
                      show["venue"], "line_checks", "", "%d added" % added, "info")
    return redirect(_show_url(tour, show, "schedule"))


@bp.route("/tours/<tour_id>/shows/<show_id>/copy-schedule", methods=["POST"])
@require_tour("schedule", "edit")
def copy_schedule(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    src = ts.get_show(tour_id, request.form.get("from_show_id") or "")
    if src is None:
        return redirect(_show_url(tour, show, "schedule"))
    template = [(r["category"], r["title"], r["start_time"]) for r in ts.list_schedule(tour_id, show_id=src["id"])]
    ts.copy_standard_day(tour_id, tour["user_id"], show, template=template)
    return redirect(_show_url(tour, show, "schedule"))


# --- advance ----------------------------------------------------------------

@bp.route("/tours/<tour_id>/shows/<show_id>/advance/<item_key>", methods=["POST"])
@require_tour("advance", "edit")
def advance_set(user, tour, viewer, tour_id, show_id, item_key):
    show = _show_or_404(tour, show_id)
    ts.ensure_advance_items(tour_id, tour["user_id"], show_id)
    fields = {k: request.form.get(k) for k in ("status", "value", "owner", "due_date", "comments") if k in request.form}
    changed = ts.set_advance_item(tour_id, show_id, item_key, fields)
    if changed is None:
        abort(404)
    if changed:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "advance", show_id,
                      "%s · %s" % (show["venue"], item_key.replace("_", " ")),
                      "status" if "status" in changed else "value",
                      changed.get("status", changed.get("value", ("", "")))[0],
                      changed.get("status", changed.get("value", ("", "")))[1], "info")
    return _back(_show_url(tour, show, "advance"))


@bp.route("/tours/<tour_id>/shows/<show_id>/advance-bulk", methods=["POST"])
@require_tour("advance", "edit")
def advance_bulk(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    ts.ensure_advance_items(tour_id, tour["user_id"], show_id)
    n = 0
    for row in ts.list_advance(tour_id, show_id):
        key = row["item_key"]
        fields = {}
        if "status__" + key in request.form:
            fields["status"] = request.form.get("status__" + key)
        if "value__" + key in request.form:
            fields["value"] = request.form.get("value__" + key)
        if fields:
            changed = ts.set_advance_item(tour_id, show_id, key, fields)
            n += 1 if changed else 0
    if n:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "advance", show_id, show["venue"],
                      "updated", "", "%d advance items" % n, "info")
    return redirect(_show_url(tour, show, "advance"))


# --- advance inbox (extraction with review) ---------------------------------

_EXTRACT_TO_ADVANCE = {"hotel": "hotel", "wifi": "wifi", "parking": "parking",
                       "catering": "catering", "dressing_rooms": "dressing_rooms",
                       "guest_cutoff": "guest_allotment", "settlement_location": "settlement_location",
                       "promoter": "promoter", "venue_contact": "venue_contact",
                       "driver": "driver", "flight": "airport"}


@bp.route("/tours/<tour_id>/shows/<show_id>/inbox", methods=["POST"])
@require_tour("advance", "edit")
def inbox(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    action = request.form.get("action")
    text = request.form.get("text") or ""
    up = request.files.get("file")
    if up and up.filename:
        raw = up.read(2_000_000)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", "ignore")
        if up.filename.lower().endswith(".pdf"):
            # No PDF text extraction library is installed; be honest.
            return _date_page(user, tour, viewer, show, "inbox", extract_error=(
                "PDF text extraction is not installed on this deployment. Open the PDF, "
                "copy its text and paste it here — the review step is the same."))
    if action == "extract":
        result = eng.extract(text)
        return _date_page(user, tour, viewer, show, "inbox", extract=result, extract_text=text)
    if action == "apply":
        ts.ensure_advance_items(tour_id, tour["user_id"], show_id)
        applied, skipped = [], 0
        existing = {r["category"]: r for r in ts.list_schedule(tour_id, show_id=show_id)}
        for i in request.form.getlist("pick"):
            kind = request.form.get("kind_%s" % i) or ""
            key = request.form.get("key_%s" % i) or ""
            value = (request.form.get("value_%s" % i) or "").strip()
            source = (request.form.get("source_%s" % i) or "")[:300]
            if not value:
                continue
            if kind == "time" and key in ts.SCHEDULE_CATEGORIES and re.match(r"^\d{2}:\d{2}$", value):
                if key in existing:
                    ch = ts.update_schedule_item(tour_id, existing[key]["id"], {"start_time": value})
                    _log(tour, viewer, "schedule", existing[key]["id"], existing[key]["title"], ch or {}, source="extract")
                else:
                    iid = ts.add_schedule_item(tour_id, tour["user_id"], {
                        "show_id": show_id, "day_date": show["date"], "category": key,
                        "title": key.replace("_", " ").title(), "start_time": value,
                        "precision": "exact", "location": show["venue"]})
                    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "schedule", iid,
                                  key.replace("_", " ").title(), "created", "", value, "info", "extract")
                applied.append("%s %s" % (key, eng.fmt_time(value)))
            elif kind == "fact" and key in _EXTRACT_TO_ADVANCE:
                target = _EXTRACT_TO_ADVANCE[key]
                ch = ts.set_advance_item(tour_id, show_id, target, {"value": value, "status": "complete",
                                                                   "comments": "From pasted advance: " + source})
                if ch:
                    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "advance", show_id,
                                  "%s · %s" % (show["venue"], target), "value", ch.get("value", ("", ""))[0],
                                  value, "info", "extract")
                applied.append("%s: %s" % (target, value[:40]))
            elif kind == "fact" and key == "capacity":
                ch = ts.update_show_ext(tour_id, show_id, {"capacity": value})
                _log(tour, viewer, "show", show_id, show["venue"], ch or {}, source="extract")
                applied.append("capacity " + value)
            elif kind == "contact":
                cur = next((r for r in ts.list_advance(tour_id, show_id) if r["item_key"] == "venue_contact"), None)
                if cur is not None:
                    comments = (cur["comments"] + "\n" if cur["comments"] else "") + value
                    ts.set_advance_item(tour_id, show_id, "venue_contact", {"comments": comments})
                    applied.append("contact " + value)
            else:
                skipped += 1
        ts.record_import(tour_id, tour["user_id"], "extract", "pasted advance", text,
                         {"show_id": show_id, "applied": applied, "skipped": skipped})
        return redirect(_show_url(tour, show, "inbox"))
    return redirect(_show_url(tour, show, "inbox"))


# --- send the advance -------------------------------------------------------
# One email to the venue, composed by tour_advance_mail from this show's
# rows, with the rider and plot attached. This is the only place the
# packet leaves the building, and it leaves through the same mailer as
# everything else.

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEND_FILE_CATEGORIES = ("rider", "stage_plot", "tech_pack", "production")
ATTACH_CAP = 18 * 1024 * 1024


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "artist"


def _rider_url(tour, show, create=False):
    """The Tour Hub's public tech-rider page for this show: plot, input
    list, times, backline. The token is minted on first send."""
    hub = store.get_tour_show(tour["user_id"], show["id"])
    if hub is None:
        return ""
    token = hub.get("share_token") or ""
    if not token and create:
        token = uuid.uuid4().hex
        store.set_show_share_token(tour["user_id"], show["id"], token)
    return "%s/rider/%s" % (_base_url(), token) if token else ""


def _production_url(tour, show, create=False):
    """A production-scope share link for this show, minted on first send.
    Password-protected links are never reused here: the venue was not
    told the password."""
    for link in ts.list_share_links(tour["id"]):
        if (link["scope"] == "production" and link.get("show_id") == show["id"]
                and not link.get("revoked") and not link.get("password_hash")):
            return "%s/tour-share/%s" % (_base_url(), link["token"])
    if create:
        token = ts.create_share_link(tour["id"], tour["user_id"], "production", show_id=show["id"])
        return "%s/tour-share/%s" % (_base_url(), token) if token else ""
    return ""


def _sender_for(viewer, user, people):
    """Who signs: the person sending, with the account's address for
    replies and the tour manager's phone if it is not marked private."""
    tm = next((p for p in people if p.get("category") == "Tour Management"), None)
    phone = ""
    if tm and tm.get("phone") and not tm.get("phone_private"):
        phone = tm["phone"]
    return {"name": viewer.get("name") or user.get("name") or "",
            "email": user.get("email") or "", "phone": phone,
            "role": (tm or {}).get("role") or ("Tour manager" if tm else "")}


def _send_files(tour, viewer, show):
    rows = [f for f in ts.list_files(tour["id"], entity_type="show", entity_id=show["id"])
            if f["category"] in SEND_FILE_CATEGORIES]
    rows += [f for f in ts.list_files(tour["id"], entity_type="tour")
             if f["category"] in SEND_FILE_CATEGORIES]
    return _files_for(viewer, rows)


def _send_context(tour, show, viewer, user, create_links=False):
    tid, sid = tour["id"], show["id"]
    ts.ensure_advance_items(tid, tour["user_id"], sid)
    advance_rows = ts.list_advance(tid, sid)
    schedule = _visible(viewer, ts.list_schedule(tid, show_id=sid))
    lineup = ts.seed_lineup_from_support(tid, show)
    people = ts.list_people(tid)
    files = _send_files(tour, viewer, show)
    plot = store.get_stage_plot(tour["user_id"]) or {}
    plot_image = store.get_stage_plot_image(tour["user_id"])
    channels = tam.channel_list(plot)
    sender = _sender_for(viewer, user, people)
    links = {"rider": _rider_url(tour, show, create_links),
             "production": _production_url(tour, show, create_links)}
    names = (["Stage plot (PNG)"] if plot_image else [])
    names += ["Input list (%d channels)" % len(channels)] if channels else []
    names += [f["file_name"] for f in files if f["category"] in ("rider", "tech_pack", "stage_plot")]
    venue = ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None
    composed = tam.compose(tour, show, schedule, lineup, advance_rows, sender, links, names,
                           fmt_time=eng.fmt_time, fmt_day=eng.fmt_day_long, venue=venue)
    return {"composed": composed,
            "recipients": tam.candidate_recipients(people, advance_rows, sid),
            "send_files": files, "plot_image": bool(plot_image), "channels": channels,
            "sender": sender, "sender_address": emailer.sender(),
            "mail_ready": emailer.configured() and not emailer.using_shared_test_sender(),
            "links": links, "sends": ts.list_advance_sends(tid, sid)}


def _file_bytes(record):
    path = record["path"]
    if blob_store.is_remote(path):
        return blob_store.fetch(path)
    if path.startswith(TOUR_PREFIX):
        try:
            with open(os.path.join(_tour_dir(), path[len(TOUR_PREFIX):]), "rb") as fh:
                return fh.read()
        except OSError:
            return None
    return None


def _build_attachments(tour, ctx, picks):
    """[{filename, content}] for the mailer, the names for the record, and
    what was left out and why. Empty files are left out rather than sent
    as empty; over the cap, the biggest offender is named."""
    import base64

    out, names, skipped, total = [], [], [], 0

    def add(name, data):
        nonlocal total
        if not data:
            skipped.append(name)
            return
        if total + len(data) > ATTACH_CAP:
            skipped.append(name + " (over the size limit)")
            return
        total += len(data)
        out.append({"filename": name, "content": base64.b64encode(data).decode("ascii")})
        names.append(name)

    artist = _slug(tour.get("artist_name") or tour.get("name"))
    if "plot" in picks and ctx["plot_image"]:
        add(artist + "-stage-plot.png", plot_images.read(tour["user_id"]))
    if "inputs" in picks and ctx["channels"]:
        add(artist + "-input-list.txt",
            tam.input_list_text(ctx["channels"], tour.get("artist_name") or tour.get("name") or "").encode("utf-8"))
    by_id = {f["id"]: f for f in ctx["send_files"]}
    for pick in picks:
        record = by_id.get(pick)
        if record is not None:
            add(record["file_name"], _file_bytes(record))
    return out, names, skipped


def _default_picks(ctx):
    """What goes with an advance when nobody chose: the plot, the input list,
    and every rider, tech pack or plot file on the show or the tour."""
    picks = ["plot", "inputs"]
    picks += [f["id"] for f in ctx["send_files"] if f["category"] in ("rider", "tech_pack", "stage_plot")]
    return picks


def _deliver_advance(tour, show, viewer, user, to, cc, subject, body, picks):
    """Compose (links minted), attach, send, record, log. One show, one
    email. Returns (ok, attachment names, what was left out)."""
    ctx = _send_context(tour, show, viewer, user, create_links=True)
    subject = (subject or "").strip()[:200] or ctx["composed"]["subject"]
    body = (body or "").strip() or ctx["composed"]["text"]
    if picks is None:
        picks = _default_picks(ctx)
    attachments, names, skipped = _build_attachments(tour, ctx, picks)
    ok = emailer.send(to, subject, tam.html_for(body), attachments=attachments or None,
                      reply_to=ctx["sender"]["email"] or None, cc=cc or None, text=body)
    ts.record_advance_send(tour["id"], tour["user_id"], show["id"], to, subject, body, names,
                           ctx["links"], status="sent" if ok else "failed",
                           error="" if ok else (emailer.last_send_error()
                                                or "The mail service did not accept the message."),
                           cc=", ".join(cc or []), sent_by=viewer.get("name") or "")
    ts.log_change(tour["id"], tour["user_id"], _actor(viewer), "advance", show["id"],
                  "%s · advance email" % show["venue"], "sent" if ok else "send failed", "",
                  to + ((" · %d attachment%s" % (len(names), "" if len(names) == 1 else "s")) if names else ""),
                  "info" if ok else "warn")
    return ok, names, skipped


@bp.route("/tours/<tour_id>/shows/<show_id>/advance/send", methods=["POST"])
@require_tour("advance", "edit")
def advance_send(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    back = _show_url(tour, show, "send")
    to = (request.form.get("to") or "").strip()
    if not _EMAIL_RE.match(to):
        return redirect(back + "&fail=to")
    if not emailer.configured() or emailer.using_shared_test_sender():
        # Never 'sent' when nobody but the owner could receive it.
        return redirect(back + "&fail=sender")
    cc = [x.strip() for x in (request.form.get("cc") or "").split(",") if _EMAIL_RE.match(x.strip())]
    ok, names, skipped = _deliver_advance(tour, show, viewer, user, to, cc,
                                          request.form.get("subject"), request.form.get("body"),
                                          request.form.getlist("attach"))
    if not ok:
        return redirect(back + "&fail=send")
    return redirect(back + "&sent=1" + ("&skipped=%d" % len(skipped) if skipped else ""))


def _advance_to(tour, shows):
    """show id -> the addresses each show already knows, for the Shows page.
    Read-only: no checklist rows are created here."""
    people = ts.list_people(tour["id"])
    return {s["id"]: tam.candidate_recipients(people, ts.list_advance(tour["id"], s["id"]), s["id"])
            for s in shows}


@bp.route("/tours/<tour_id>/advance/send-all", methods=["POST"])
@require_tour("advance", "edit")
def advance_send_all(user, tour, viewer, tour_id):
    """Advance every ticked show to the first address it knows, one email
    each, composed per show. A show with no address is skipped and said so;
    a failure is recorded on that show like a single send would be."""
    back = "/tours/%s/shows" % tour_id
    if not emailer.configured() or emailer.using_shared_test_sender():
        return redirect(back + "?advance_fail=sender")
    picks = set(request.form.getlist("show"))
    shows = [s for s in ts.list_shows(tour_id) if s["id"] in picks]
    addresses = _advance_to(tour, shows)
    sent = failed = skipped = 0
    for show in shows:
        to = (addresses.get(show["id"]) or [""])[0]
        if not to:
            skipped += 1
            continue
        ok, _names, _left = _deliver_advance(tour, show, viewer, user, to, [], "", "", None)
        sent += 1 if ok else 0
        failed += 0 if ok else 1
    return redirect(back + "?advanced=%d&advance_failed=%d&advance_skipped=%d" % (sent, failed, skipped))


# --- travel -----------------------------------------------------------------

def _travel_fields():
    f = request.form
    out = {k: f.get(k) for k in ts.TRAVEL_FIELDS if k in f}
    if "travelers" in f or f.getlist("travelers"):
        out["travelers"] = [t for t in f.getlist("travelers") if t] or ["all"]
    return out


@bp.route("/tours/<tour_id>/travel")
@require_tour("view")
def travel_all(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    rows = _redact_travel(viewer, ts.list_travel(tour_id))
    people = _redact_people(viewer, ts.list_people(tour_id))
    show_by_id = {s["id"]: s for s in shows}
    return render_template("tour/travel.html", **_ctx(
        user, tour, viewer, "travel", shows=shows, rows=rows, people=people, show_by_id=show_by_id,
        edit=ts.get_travel(tour_id, request.args.get("edit") or "") if can(viewer, "travel") else None))


@bp.route("/tours/<tour_id>/travel/add", methods=["POST"])
@require_tour("travel")
def travel_add(user, tour, viewer, tour_id):
    fields = _travel_fields()
    if fields.get("show_id") and not fields.get("day_date"):
        s = ts.get_show(tour_id, fields["show_id"])
        fields["day_date"] = s["date"] if s else ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fields.get("day_date") or ""):
        return _back("/tours/%s/travel" % tour_id)
    tid = ts.add_travel(tour_id, tour["user_id"], fields)
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "travel", tid,
                  "%s %s" % (fields.get("mode", "travel").title(), fields.get("number") or ""),
                  "created", "", fields["day_date"], "info")
    return _back("/tours/%s/travel" % tour_id)


@bp.route("/tours/<tour_id>/travel/<travel_id>/edit", methods=["POST"])
@require_tour("travel")
def travel_edit(user, tour, viewer, tour_id, travel_id):
    cur = ts.get_travel(tour_id, travel_id)
    if cur is None:
        abort(404)
    label = "%s %s" % (cur["mode"].title(), cur.get("number") or cur.get("arr_loc") or "")
    if request.form.get("action") == "delete":
        ts.delete_travel(tour_id, travel_id)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "travel", travel_id, label,
                      "deleted", cur["day_date"], "", "critical")
        _notify_members(tour, "%s removed" % label, cur["day_date"], "/tours/%s/travel" % tour_id,
                        exclude_user_id=user["id"], severity="critical")
        return _back("/tours/%s/travel" % tour_id)
    changed = ts.update_travel(tour_id, travel_id, _travel_fields())
    after = ts.get_travel(tour_id, travel_id) or cur
    vis = "all" if (cur["visibility"] == "all" and after["visibility"] == "all"
                    and "all" in (cur.get("travelers") or ["all"]) and "all" in (after.get("travelers") or ["all"])) else "management"
    _log(tour, viewer, "travel", travel_id, label, changed or {}, visibility=vis)
    return _back("/tours/%s/travel" % tour_id)


# --- hotels & rooms ---------------------------------------------------------

@bp.route("/tours/<tour_id>/hotels")
@require_tour("view")
def hotels(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    rows = _redact_lodging(viewer, ts.list_lodging(tour_id))
    rooms = {l["id"]: _redact_rooms(viewer, ts.list_rooms(tour_id, l["id"])) for l in rows}
    people = _redact_people(viewer, ts.list_people(tour_id))
    show_by_id = {s["id"]: s for s in shows}
    missing = {}
    if can(viewer, "hotel"):
        for l in rows:
            assigned = {r["person_id"] for r in rooms[l["id"]] if r.get("person_id")}
            missing[l["id"]] = [p for p in people if p["id"] not in assigned]
    return render_template("tour/hotels.html", **_ctx(
        user, tour, viewer, "hotels", shows=shows, rows=rows, rooms=rooms, people=people,
        show_by_id=show_by_id, missing=missing,
        edit=ts.get_lodging(tour_id, request.args.get("edit") or "") if can(viewer, "hotel") else None))


@bp.route("/tours/<tour_id>/hotels/add", methods=["POST"])
@require_tour("hotel")
def hotel_add(user, tour, viewer, tour_id):
    fields = {k: request.form.get(k) for k in ts.LODGING_FIELDS if k in request.form}
    lid = ts.add_lodging(tour_id, tour["user_id"], fields)
    if lid:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "lodging", lid, fields.get("property"),
                      "created", "", fields.get("checkin") or "", "info")
    return _back("/tours/%s/hotels" % tour_id)


@bp.route("/tours/<tour_id>/hotels/<lodging_id>/edit", methods=["POST"])
@require_tour("hotel")
def hotel_edit(user, tour, viewer, tour_id, lodging_id):
    cur = ts.get_lodging(tour_id, lodging_id)
    if cur is None:
        abort(404)
    if request.form.get("action") == "delete":
        ts.delete_lodging(tour_id, lodging_id)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "lodging", lodging_id, cur["property"],
                      "deleted", cur["checkin"], "", "critical")
        return _back("/tours/%s/hotels" % tour_id)
    changed = ts.update_lodging(tour_id, lodging_id, {k: request.form.get(k) for k in ts.LODGING_FIELDS if k in request.form})
    after = ts.get_lodging(tour_id, lodging_id) or cur
    _log(tour, viewer, "lodging", lodging_id, cur["property"], changed or {},
         visibility="all" if cur["visibility"] == "all" and after["visibility"] == "all" else "management")
    return _back("/tours/%s/hotels" % tour_id)


@bp.route("/tours/<tour_id>/hotels/<lodging_id>/rooms", methods=["POST"])
@require_tour("hotel")
def rooms(user, tour, viewer, tour_id, lodging_id):
    if ts.get_lodging(tour_id, lodging_id) is None:
        abort(404)
    if request.form.get("action") == "delete":
        ts.delete_room(tour_id, request.form.get("room_id") or "")
        return _back("/tours/%s/hotels" % tour_id)
    if request.form.get("action") == "assign_all":
        have = {r["person_id"] for r in ts.list_rooms(tour_id, lodging_id)}
        for p in ts.list_people(tour_id):
            if p["id"] not in have and p["category"] not in ("Venue", "Promoters", "Agents", "Guests", "VIP", "Label"):
                ts.set_room(tour_id, tour["user_id"], lodging_id, {"person_id": p["id"]})
        return _back("/tours/%s/hotels" % tour_id)
    ts.set_room(tour_id, tour["user_id"], lodging_id, {
        "room_id": request.form.get("room_id"), "person_id": request.form.get("person_id"),
        "guest_name": request.form.get("guest_name"), "room_number": request.form.get("room_number"),
        "room_kind": request.form.get("room_kind"), "notes": request.form.get("notes")})
    return _back("/tours/%s/hotels" % tour_id)


# --- venues -----------------------------------------------------------------

@bp.route("/tours/<tour_id>/venues")
@require_tour("view")
def venues(user, tour, viewer, tour_id):
    q = request.args.get("q") or ""
    rows = ts.list_venues(tour["user_id"], q)
    shows = ts.list_shows(tour_id)
    use = {}
    for s in shows:
        if s.get("venue_id"):
            use.setdefault(s["venue_id"], []).append(s)
    return render_template("tour/venues.html", **_ctx(
        user, tour, viewer, "venues", shows=shows, rows=rows, q=q, use=use,
        edit=ts.get_venue(tour["user_id"], request.args.get("edit") or "") if can(viewer, "edit") else None,
        venue_fields=ts.VENUE_FIELDS))


@bp.route("/tours/<tour_id>/venues/save", methods=["POST"])
@require_tour("edit", "advance")
def venue_save(user, tour, viewer, tour_id):
    vid = request.form.get("venue_id") or ""
    fields = {k: request.form.get(k) for k in ts.VENUE_FIELDS if k in request.form}
    if fields.get("tz") and not eng.valid_tz(fields["tz"]):
        fields["tz"] = ""
    if vid:
        changed = ts.update_venue(tour["user_id"], vid, fields)
        if changed is None:
            abort(404)
        _log(tour, viewer, "venue", vid, fields.get("name") or "Venue", changed)
    else:
        vid = ts.add_venue(tour["user_id"], fields)
        if vid:
            ts.log_change(tour_id, tour["user_id"], _actor(viewer), "venue", vid, fields.get("name"),
                          "created", "", fields.get("city") or "", "info")
    link_show = request.form.get("link_show_id")
    if vid and link_show and ts.get_show(tour_id, link_show):
        ts.update_show_ext(tour_id, link_show, {"venue_id": vid, "tz": fields.get("tz") or ""})
        return redirect(_show_url(tour, {"id": link_show}, "venue"))
    return _back("/tours/%s/venues" % tour_id)


@bp.route("/tours/<tour_id>/shows/<show_id>/venue/from-advance", methods=["POST"])
@require_tour("edit", "advance")
def venue_from_advance(user, tour, viewer, tour_id, show_id):
    """Promote this show's advance facts into the saved venue record, so
    the next time you play the room it is already known."""
    show = _show_or_404(tour, show_id)
    adv = {r["item_key"]: r["value"] for r in ts.list_advance(tour_id, show_id) if r["value"]}
    fields = {"name": show["venue"], "city": show.get("city") or "", "tz": show.get("tz") or "",
              "capacity": show.get("capacity") or "", "parking": adv.get("parking", ""),
              "bus_parking": adv.get("bus_parking", ""), "stage": adv.get("stage", ""),
              "loading": adv.get("load_in", ""), "dressing_rooms": adv.get("dressing_rooms", ""),
              "showers": adv.get("showers", ""), "catering": adv.get("catering", ""),
              "wifi": adv.get("wifi", ""), "settlement_location": adv.get("settlement_location", ""),
              "production_notes": " · ".join(v for k, v in adv.items() if k in ("power", "sound", "lighting", "backline", "rigging", "labor"))}
    existing = ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else \
        ts.find_venue_by_name(tour["user_id"], show["venue"], show.get("city") or "")
    if existing:
        merged = {k: (v if v else existing.get(k, "")) for k, v in fields.items()}
        ts.update_venue(tour["user_id"], existing["id"], merged)
        vid = existing["id"]
    else:
        vid = ts.add_venue(tour["user_id"], fields)
    if vid:
        ts.update_show_ext(tour_id, show_id, {"venue_id": vid})
    return redirect(_show_url(tour, show, "venue"))


# --- people -----------------------------------------------------------------

@bp.route("/tours/<tour_id>/people")
@require_tour("view")
def people(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    cat = request.args.get("category") or ""
    q = request.args.get("q") or ""
    rows = _redact_people(viewer, ts.list_people(tour_id, category=cat or None, search=q))
    members = ts.list_members(tour_id) if can(viewer, "admin") else []
    contacts = press_store.list_contacts(tour["user_id"])[:300] if viewer["is_owner"] else []
    return render_template("tour/people.html", **_ctx(
        user, tour, viewer, "people", shows=shows, rows=rows, cat=cat, q=q, members=members,
        contacts=contacts,
        edit=ts.get_person(tour_id, request.args.get("edit") or "") if can(viewer, "people") else None))


@bp.route("/tours/<tour_id>/people/save", methods=["POST"])
@require_tour("people")
def person_save(user, tour, viewer, tour_id):
    f = request.form
    pid = f.get("person_id") or ""
    fields = {k: f.get(k) for k in ts.PEOPLE_FIELDS if k in f}
    fields["phone_public"] = bool(f.get("phone_public"))
    fields["shows"] = [s for s in f.getlist("shows") if s]
    if "linked_contact_id" in f:
        fields["linked_contact_id"] = f.get("linked_contact_id") or None
    if f.get("action") == "delete" and pid:
        p = ts.get_person(tour_id, pid)
        ts.delete_person(tour_id, pid)
        if p:
            ts.log_change(tour_id, tour["user_id"], _actor(viewer), "person", pid, p["name"], "deleted", p["role"], "", "info")
        return _back("/tours/%s/people" % tour_id)
    if f.get("from_contact") and viewer["is_owner"]:
        c = press_store.get_contact(tour["user_id"], f.get("from_contact"))
        if c:
            fields.update({"name": c.get("name"), "email": c.get("email"), "company": c.get("outlet") or c.get("company") or "",
                           "role": c.get("role") or "", "category": fields.get("category") or "Other",
                           "linked_contact_id": c["id"]})
    if pid:
        if ts.update_person(tour_id, pid, fields) is None:
            abort(404)
    else:
        pid = ts.add_person(tour_id, tour["user_id"], fields)
        if pid:
            ts.log_change(tour_id, tour["user_id"], _actor(viewer), "person", pid, fields.get("name"), "created", "", fields.get("role") or "", "info")
    return _back("/tours/%s/people" % tour_id)


# --- guests -----------------------------------------------------------------

@bp.route("/tours/<tour_id>/guests")
@require_tour("guests")
def guests_all(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    today = eng.today_in(tour["home_tz"])
    summary = {s["id"]: ts.guest_summary(tour_id, s["id"], s.get("guest_allocation")) for s in shows}
    pending = []
    for s in shows:
        for g in ts.list_guests(tour_id, s["id"]):
            if g["status"] in ("pending", "request"):
                pending.append((s, g))
    return render_template("tour/guests.html", **_ctx(
        user, tour, viewer, "guests", shows=shows, summary=summary, pending=pending, today=today))


@bp.route("/tours/<tour_id>/shows/<show_id>/guests/add", methods=["POST"])
@require_tour("guests")
def guest_add(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    f = request.form
    fields = {k: f.get(k) for k in ts.GUEST_FIELDS if k in f}
    fields.update({"count": f.get("count") or 1, "backstage": bool(f.get("backstage")),
                   "meet_greet": bool(f.get("meet_greet")), "aftershow": bool(f.get("aftershow")),
                   "requested_by": f.get("requested_by") or viewer["name"],
                   "linked_contact_id": f.get("linked_contact_id") or None})
    if f.get("linked_contact_id") and viewer["is_owner"] and not fields.get("name"):
        c = press_store.get_contact(tour["user_id"], f.get("linked_contact_id"))
        if c:
            fields.update({"name": c.get("name"), "email": c.get("email"), "company": c.get("outlet") or ""})
    # A full list takes requests as pending, never silently over-approves
    summary = ts.guest_summary(tour_id, show_id, show.get("guest_allocation"))
    if summary["allocation"] is not None and summary["remaining"] is not None:
        if fields.get("status") == "approved" and int(fields["count"]) > summary["remaining"]:
            fields["status"] = "pending"
    gid = ts.add_guest(tour_id, tour["user_id"], show_id, fields)
    if gid:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "guest", gid,
                      "%s · %s" % (show["venue"], fields.get("name")), "created", "", fields.get("status") or "pending", "info")
    return redirect(_show_url(tour, show, "guests"))


@bp.route("/tours/<tour_id>/shows/<show_id>/guests/<guest_id>", methods=["POST"])
@require_tour("guests")
def guest_update(user, tour, viewer, tour_id, show_id, guest_id):
    show = _show_or_404(tour, show_id)
    g = ts.get_guest(tour_id, guest_id)
    if g is None or g["show_id"] != show_id:
        abort(404)
    if request.form.get("action") == "delete":
        ts.delete_guest(tour_id, guest_id)
        return redirect(_show_url(tour, show, "guests"))
    fields = {k: request.form.get(k) for k in ts.GUEST_FIELDS if k in request.form}
    if "count" in request.form:
        fields["count"] = request.form.get("count")
    for flag in ("backstage", "meet_greet", "aftershow"):
        if request.form.get("_flags"):
            fields[flag] = bool(request.form.get(flag))
    if fields.get("status") == "approved":
        fields["approved_by"] = viewer["name"]
    changed = ts.update_guest(tour_id, guest_id, fields)
    if changed:
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "guest", guest_id,
                      "%s · %s" % (show["venue"], g["name"]), "status", changed["status"][0], changed["status"][1], "info")
    return _back(_show_url(tour, show, "guests"))


@bp.route("/tours/<tour_id>/shows/<show_id>/guests.csv")
@require_tour("guests")
def guests_csv(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    rows = [(g["name"], g["count"], g["category"], g["ticket_type"], g["credentials"],
             "yes" if g["backstage"] else "", g["status"], g["requested_by"], g["notes"])
            for g in ts.list_guests(tour_id, show_id) if g["status"] in ("approved", "checked_in")]
    text = eng.csv_text(["Name", "Count", "Category", "Ticket type", "Credential", "Backstage",
                         "Status", "Requested by", "Notes"], rows)
    return _csv(text, "guest-list-%s-%s.csv" % (show["date"], _slug(show["venue"])))


# --- VIP --------------------------------------------------------------------

@bp.route("/tours/<tour_id>/shows/<show_id>/vip/add", methods=["POST"])
@require_tour("vip")
def vip_add(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    f = request.form
    fields = {k: f.get(k) for k in ("package", "price", "quantity", "purchaser", "guest", "email",
                                    "credentials", "schedule_time", "notes")}
    for flag in ("meet_greet", "early_entry", "merch", "photo"):
        fields[flag] = bool(f.get(flag))
    ts.add_vip(tour_id, tour["user_id"], show_id, fields)
    return redirect(_show_url(tour, show, "vip"))


@bp.route("/tours/<tour_id>/shows/<show_id>/vip/<vip_id>", methods=["POST"])
@require_tour("vip")
def vip_update(user, tour, viewer, tour_id, show_id, vip_id):
    show = _show_or_404(tour, show_id)
    ts.set_vip_status(tour_id, vip_id, request.form.get("status") or "sold",
                      fulfilled=(bool(request.form.get("fulfilled")) if "fulfilled_flag" in request.form else None))
    return _back(_show_url(tour, show, "vip"))


# --- money ------------------------------------------------------------------

@bp.route("/tours/<tour_id>/money")
@require_tour("financials")
def money(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    exp_all = ts.list_expenses(tour_id)
    exp = {}
    for e in exp_all:
        exp.setdefault(e.get("show_id") or "", []).append(e)
    finance = eng.tour_finance(shows, exp, tour["currency"], today=eng.today_in(tour["home_tz"]))
    receipts = {f["id"]: f for f in ts.list_files(tour_id, entity_type="expense")}
    return render_template("tour/money.html", **_ctx(
        user, tour, viewer, "money", shows=shows, finance=finance, expenses=exp_all, receipts=receipts,
        show_by_id={s["id"]: s for s in shows}))


@bp.route("/tours/<tour_id>/shows/<show_id>/money", methods=["POST"])
@require_tour("financials")
def show_money(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    fields = {k: request.form.get(k) for k in ts.MONEY_FIELDS if k in request.form}
    changed = ts.update_show_ext(tour_id, show_id, fields)
    _log(tour, viewer, "money", show_id, show["venue"], changed or {})
    return redirect(_show_url(tour, show, "money"))


@bp.route("/tours/<tour_id>/expenses/add", methods=["POST"])
@require_tour("financials")
def expense_add(user, tour, viewer, tour_id):
    f = request.form
    fields = {k: f.get(k) for k in ("show_id", "vendor", "category", "amount", "tax", "currency",
                                    "spend_date", "notes")}
    if fields.get("show_id") and ts.get_show(tour_id, fields["show_id"]) is None:
        fields["show_id"] = None
    up = request.files.get("receipt")
    if up and up.filename:
        fid = _store_upload(tour, viewer, up, "expense", "", "invoice", "management")
        if fid:
            fields["receipt_file_id"] = fid
    if not (fields.get("amount") or "").strip():
        return _back("/tours/%s/money" % tour_id)
    eid = ts.add_expense(tour_id, tour["user_id"], fields)
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "expense", eid,
                  fields.get("vendor") or fields.get("category") or "Expense", "created", "",
                  fields.get("amount"), "info")
    dest = _show_url(tour, {"id": fields["show_id"]}, "money") if fields.get("show_id") else "/tours/%s/money" % tour_id
    return redirect(dest)


@bp.route("/tours/<tour_id>/expenses/<expense_id>/delete", methods=["POST"])
@require_tour("financials")
def expense_delete(user, tour, viewer, tour_id, expense_id):
    ts.delete_expense(tour_id, expense_id)
    return _back("/tours/%s/money" % tour_id)


@bp.route("/tours/<tour_id>/money.csv")
@require_tour("financials")
def money_csv(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    exp = {}
    for e in ts.list_expenses(tour_id):
        exp.setdefault(e.get("show_id") or "", []).append(e)
    fin = eng.tour_finance(shows, exp, tour["currency"], today=eng.today_in(tour["home_tz"]))
    rows = [(r["show"]["date"], r["show"]["city"], r["show"]["venue"], r["deal"], r["guarantee"],
             r["backend"], r["earned"], r["merch_net"], r["vip"], r["expenses"], r["settlement"] or "",
             r["collected"], r["outstanding"], r["estimated_net"], r["actual_net"] if r["actual_net"] is not None else "",
             r["show"].get("settlement_status") or "open") for r in fin["rows"]]
    text = eng.csv_text(["Date", "City", "Venue", "Deal", "Guarantee", "Backend", "Earned", "Merch net",
                         "VIP", "Expenses", "Settlement", "Collected", "Outstanding", "Est. net",
                         "Actual net", "Status"], rows)
    return _csv(text, "tour-financials-%s.csv" % _slug(tour["name"]))


@bp.route("/tours/<tour_id>/shows/<show_id>/settlement-summary")
@require_tour("financials")
def settlement_summary(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    expenses = ts.list_expenses(tour_id, show_id=show_id)
    money = eng.show_money(show, expenses)
    merch = ts.list_merch_counts(tour_id, show_id=show_id)
    return render_template("tour/print_settlement.html", tour=tour, show=show, money=money,
                           expenses=expenses, merch=merch, fmt_day=eng.fmt_day_long)


# --- merch ------------------------------------------------------------------

@bp.route("/tours/<tour_id>/merch")
@require_tour("merch")
def merch(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    products = ts.list_products(tour_id)
    counts = ts.list_merch_counts(tour_id)
    per_show = {}
    per_product = {}
    for c in counts:
        per_show.setdefault(c["show_id"], []).append(c)
        per_product.setdefault(c["product_id"], []).append(c)
    totals = {}
    for p in products:
        rows = per_product.get(p["id"], [])
        sold = sum(eng._num(c["sold"]) for c in rows)
        gross = sum(eng._num(c["gross"]) for c in rows)
        inv = eng._num(p["tour_inventory"])
        low = eng._num(p["low_stock_at"])
        totals[p["id"]] = {"sold": sold, "gross": gross, "left": (inv - sold) if inv else None,
                           "low": bool(low and inv and (inv - sold) <= low)}
    return render_template("tour/merch.html", **_ctx(
        user, tour, viewer, "merch", shows=shows, products=products, per_show=per_show, totals=totals,
        show_by_id={s["id"]: s for s in shows}))


@bp.route("/tours/<tour_id>/merch/products/add", methods=["POST"])
@require_tour("merch")
def product_add(user, tour, viewer, tour_id):
    ts.add_product(tour_id, tour["user_id"], {k: request.form.get(k) for k in ("name", "sku", "price", "tour_inventory", "low_stock_at")})
    return _back("/tours/%s/merch" % tour_id)


@bp.route("/tours/<tour_id>/shows/<show_id>/merch", methods=["POST"])
@require_tour("merch")
def merch_counts(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    for p in ts.list_products(tour_id):
        pid = p["id"]
        if "sold__" + pid in request.form or "opening__" + pid in request.form:
            opening = request.form.get("opening__" + pid) or ""
            closing = request.form.get("closing__" + pid) or ""
            sold = request.form.get("sold__" + pid) or ""
            if not sold and opening and closing:
                sold = str(int(eng._num(opening) - eng._num(closing)))
            gross = request.form.get("gross__" + pid) or ""
            if not gross and sold and p["price"]:
                gross = "%.2f" % (eng._num(sold) * eng._num(p["price"]))
            ts.set_merch_count(tour_id, tour["user_id"], show_id, pid, {
                "opening": opening, "closing": closing, "sold": sold, "gross": gross,
                "venue_pct": request.form.get("venue_pct__" + pid) or "",
                "taxes": request.form.get("taxes__" + pid) or "", "fees": request.form.get("fees__" + pid) or "",
                "settled": bool(request.form.get("settled__" + pid))})
    total_gross = sum(eng._num(c["gross"]) for c in ts.list_merch_counts(tour_id, show_id=show_id))
    if total_gross and can(viewer, "financials"):
        ts.update_show_ext(tour_id, show_id, {"merch_gross": "%.2f" % total_gross})
    return redirect(_show_url(tour, show, "merch"))


# --- marketing & content ----------------------------------------------------

@bp.route("/tours/<tour_id>/marketing")
@require_tour("marketing")
def marketing(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    rows = [{"show": s, "progress": _ticket_progress(s), "mk": s.get("marketing") or {}} for s in shows]
    return render_template("tour/marketing.html", **_ctx(user, tour, viewer, "marketing", shows=shows, rows=rows))


@bp.route("/tours/<tour_id>/shows/<show_id>/marketing", methods=["POST"])
@require_tour("marketing")
def show_marketing(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    mk = dict(show.get("marketing") or {})
    for k in ("announce", "presale", "onsale", "ticket_link", "promo_assets", "local_press", "radio",
              "influencers", "paid_ads", "email_blast", "sms", "posts_scheduled", "street_team", "notes"):
        if k in request.form:
            mk[k] = (request.form.get(k) or "")[:500]
    fields = {"marketing": mk}
    for k in ("ticket_url", "ticket_status", "tickets_sold", "capacity"):
        if k in request.form:
            fields[k] = request.form.get(k)
    ts.update_show_ext(tour_id, show_id, fields)
    return _back(_show_url(tour, show, "marketing"))


@bp.route("/tours/<tour_id>/content")
@require_tour("content")
def content(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    for s in shows:
        ts.ensure_content_plan(tour_id, tour["user_id"], s["id"])
    rows = ts.list_content(tour_id)
    by_show = {}
    for r in rows:
        by_show.setdefault(r["show_id"], []).append(r)
    people = _redact_people(viewer, ts.list_people(tour_id))
    return render_template("tour/content.html", **_ctx(
        user, tour, viewer, "content", shows=shows, by_show=by_show, people=people,
        statuses=ts.CONTENT_STATUSES))


@bp.route("/tours/<tour_id>/content/<content_id>", methods=["POST"])
@require_tour("content")
def content_set(user, tour, viewer, tour_id, content_id):
    fields = {k: request.form.get(k) for k in ("assignee", "due_time", "status", "notes") if k in request.form}
    up = request.files.get("file")
    if up and up.filename and can(viewer, "files"):
        fid = _store_upload(tour, viewer, up, "content", content_id, "photo", "all")
        if fid:
            fields["file_id"] = fid
    if ts.set_content(tour_id, content_id, fields) is None:
        abort(404)
    return _back("/tours/%s/content" % tour_id)


@bp.route("/tours/<tour_id>/shows/<show_id>/content/bulk", methods=["POST"])
@require_tour("content")
def content_bulk(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    for row in ts.list_content(tour_id, show_id=show_id):
        cid = row["id"]
        fields = {}
        for k in ("assignee", "status", "due_time"):
            if "%s__%s" % (k, cid) in request.form:
                fields[k] = request.form.get("%s__%s" % (k, cid))
        if fields:
            ts.set_content(tour_id, cid, fields)
    return redirect(_show_url(tour, show, "content"))


# --- set lists --------------------------------------------------------------

def _setlist_items(text, tracks):
    """One song per line; "(3:45)" is a duration; "Encore:" / "Alt:" set the
    section; a title matching the catalog links to that track."""
    items = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        section = "main"
        if line.lower().startswith("encore:"):
            section, line = "encore", line[7:].strip()
        elif line.lower().startswith("alt:"):
            section, line = "alternate", line[4:].strip()
        title, dur = line, ""
        m = re.match(r"^(.*?)\s*\((\d{1,2}:\d{2})\)\s*$", line)
        if m:
            title, dur = m.group(1), m.group(2)
        track_id = next((tid for tid, t in tracks.items() if (t.get("title") or "").strip().lower() == title.lower()), None)
        items.append({"title": title, "duration": dur, "section": section, "os_track_id": track_id})
    return items


@bp.route("/tours/<tour_id>/shows/<show_id>/setlist", methods=["POST"])
@require_tour("edit", "production")
def setlist(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    action = request.form.get("action")
    if action == "new":
        ts.create_setlist(tour_id, tour["user_id"], request.form.get("name") or "Set list", show_id)
    elif action == "copy":
        ts.copy_setlist(tour_id, tour["user_id"], request.form.get("setlist_id") or "", show_id)
    elif action == "delete":
        ts.delete_setlist(tour_id, request.form.get("setlist_id") or "")
    elif action == "save":
        sid = request.form.get("setlist_id") or ""
        if ts.get_setlist(tour_id, sid) is None:
            abort(404)
        tracks = {t["id"]: t for t in store.list_os_tracks(tour["user_id"])}
        items = _setlist_items(request.form.get("items"), tracks)
        ts.replace_setlist_items(tour_id, tour["user_id"], sid, items)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "setlist", sid, show["venue"], "updated", "",
                      "%d songs" % len(items), "info")
    return redirect(_show_url(tour, show, "setlist"))


# --- tour-wide set lists ------------------------------------------------------
# A list with no show is the tour's: any date can copy it. Until now such
# lists could be copied but never created from a screen.

@bp.route("/tours/<tour_id>/setlists")
@require_tour("view")
def setlists(user, tour, viewer, tour_id):
    tour_lists = [ts.get_setlist(tour_id, sl["id"]) for sl in ts.list_setlists(tour_id)
                  if not sl.get("show_id")]
    shows = ts.list_shows(tour_id)
    show_lists = [(s, ts.list_setlists(tour_id, s["id"])) for s in shows]
    show_lists = [(s, lists) for s, lists in show_lists if lists]
    return render_template("tour/setlists.html", **_ctx(
        user, tour, viewer, "setlists", tour_lists=tour_lists, show_lists=show_lists,
        tracks=store.list_os_tracks(tour["user_id"])))


@bp.route("/tours/<tour_id>/setlists", methods=["POST"])
@require_tour("edit", "production")
def setlists_edit(user, tour, viewer, tour_id):
    action = request.form.get("action")
    if action == "new":
        sid = ts.create_setlist(tour_id, tour["user_id"], request.form.get("name") or "Set list", None)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "setlist", sid, tour["name"], "created", "",
                      request.form.get("name") or "Set list", "info")
    elif action == "delete":
        sid = request.form.get("setlist_id") or ""
        sl = ts.get_setlist(tour_id, sid)
        if sl is not None and not sl.get("show_id"):
            ts.delete_setlist(tour_id, sid)
    elif action == "save":
        sid = request.form.get("setlist_id") or ""
        sl = ts.get_setlist(tour_id, sid)
        if sl is None or sl.get("show_id"):
            abort(404)
        tracks = {t["id"]: t for t in store.list_os_tracks(tour["user_id"])}
        items = _setlist_items(request.form.get("items"), tracks)
        ts.replace_setlist_items(tour_id, tour["user_id"], sid, items)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "setlist", sid, tour["name"], "updated", "",
                      "%d songs" % len(items), "info")
    return redirect("/tours/%s/setlists" % tour_id)


# --- VIP across the run -------------------------------------------------------

@bp.route("/tours/<tour_id>/vip")
@require_tour("vip")
def vip(user, tour, viewer, tour_id):
    rows = []
    for s in ts.list_shows(tour_id):
        summary = ts.vip_summary(tour_id, s["id"])
        summary["show"] = s
        rows.append(summary)
    totals = {k: sum(r[k] for r in rows) for k in ("sold", "checked_in", "no_show", "unfulfilled")}
    totals["gross"] = round(sum(r["gross"] for r in rows), 2)
    totals["shows_with"] = len([r for r in rows if r["sold"]])
    return render_template("tour/vip.html", **_ctx(user, tour, viewer, "vip", rows=rows, totals=totals))


@bp.route("/tours/<tour_id>/setlists/<setlist_id>/print")
@require_tour("view")
def setlist_print(user, tour, viewer, tour_id, setlist_id):
    sl = ts.get_setlist(tour_id, setlist_id)
    if sl is None:
        abort(404)
    show = ts.get_show(tour_id, sl["show_id"]) if sl.get("show_id") else None
    return render_template("tour/print_setlist.html", tour=tour, setlist=sl, show=show, fmt_day=eng.fmt_day_long)


# --- tasks ------------------------------------------------------------------

@bp.route("/tours/<tour_id>/tasks")
@require_tour("view")
def tasks(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    rows = _tour_tasks(tour, shows)
    return render_template("tour/tasks.html", **_ctx(
        user, tour, viewer, "tasks", shows=shows, rows=rows, show_by_id={s["id"]: s for s in shows},
        people_names=[p["name"] for p in ts.list_people(tour_id)]))


@bp.route("/tours/<tour_id>/tasks/add", methods=["POST"])
@require_tour("edit", "schedule", "advance", "production")
def task_add(user, tour, viewer, tour_id):
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        return _back("/tours/%s/tasks" % tour_id)
    show_id = f.get("show_id") or ""
    show = ts.get_show(tour_id, show_id) if show_id else None
    if f.get("assignee"):
        title = "%s — %s" % (title, f.get("assignee"))
    command_center.create_action(
        tour["user_id"], title, category="general", priority=f.get("priority") or "medium",
        description=(f.get("description") or "")[:1000],
        entity_type="tour_show" if show else "tour", entity_id=show["id"] if show else tour_id,
        due_date=f.get("due_date") or "")
    return _back(_show_url(tour, show, "tasks") if show else "/tours/%s/tasks" % tour_id)


@bp.route("/tours/<tour_id>/tasks/<action_id>/status", methods=["POST"])
@require_tour("edit", "schedule", "advance", "production")
def task_status(user, tour, viewer, tour_id, action_id):
    mine = {a["id"] for a in _tour_tasks(tour, ts.list_shows(tour_id))}
    if action_id in mine:
        command_center.set_action_status(action_id, tour["user_id"], request.form.get("status") or "complete")
    return _back("/tours/%s/tasks" % tour_id)


# --- files ------------------------------------------------------------------

def _tour_dir():
    """Private upload dir next to the database (persistent disk on Render).
    If that path cannot be created - the disk is not mounted - degrade to
    the local instance dir exactly as db.get_db() and the public uploads
    dir do, instead of turning every upload into a 500."""
    path = os.path.join(os.path.dirname(store.db_path()), "tour_uploads")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tour_uploads")
        os.makedirs(path, exist_ok=True)
    return path


@bp.errorhandler(413)
def _too_large(_err):
    """Say so in the app's own voice rather than a bare 413.

    Reached two ways: Werkzeug refusing a body over the app-wide ceiling
    before any handler runs, and _store_upload refusing one over this
    module's own smaller MAX_UPLOAD after it does.
    """
    return render_template("tour/too_large.html", limit_mb=MAX_UPLOAD // (1024 * 1024),
                           active_page="tours"), 413


def _store_upload(tour, viewer, up, entity_type, entity_id, category, visibility):
    name = os.path.basename(up.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_FILE_EXTS:
        return None
    data = up.read(MAX_UPLOAD + 1)
    if not data:
        return None
    if len(data) > MAX_UPLOAD:
        # Raised rather than returned: this check only became reachable when
        # the app's request ceiling was lifted above MAX_UPLOAD. Before that
        # Werkzeug refused the body first and _too_large explained it, and
        # returning None here instead would drop the file with a redirect and
        # no message at all - the upload would look like it had worked.
        abort(413)
    fname = "%s%s" % (uuid.uuid4().hex, ext)
    path = None
    if blob_store.configured():
        try:
            if blob_store.put("tour/" + fname, data, up.mimetype):
                path = blob_store.PREFIX + "tour/" + fname
        except Exception:
            path = None
    if path is None:
        with open(os.path.join(_tour_dir(), fname), "wb") as fh:
            fh.write(data)
        path = TOUR_PREFIX + fname
    return ts.add_file(tour["id"], tour["user_id"], entity_type, entity_id, name, path, ext.lstrip("."),
                       category, visibility, viewer["name"])


@bp.route("/tours/<tour_id>/files")
@require_tour("files")
def files(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    q = request.args.get("q") or ""
    cat = request.args.get("category") or ""
    rows = _files_for(viewer, ts.list_files(tour_id, category=cat or None, search=q))
    return render_template("tour/files.html", **_ctx(
        user, tour, viewer, "files", shows=shows, rows=rows, q=q, cat=cat,
        show_by_id={s["id"]: s for s in shows}))


@bp.route("/tours/<tour_id>/files/upload", methods=["POST"])
@require_tour("files")
def file_upload(user, tour, viewer, tour_id):
    f = request.form
    entity_type = f.get("entity_type") or "tour"
    entity_id = f.get("entity_id") or ""
    if entity_type == "show" and ts.get_show(tour_id, entity_id) is None:
        entity_type, entity_id = "tour", ""
    if entity_type == "tour":
        entity_id = tour_id
    category = f.get("category") or "other"
    if category in MONEY_FILE_CATEGORIES and not can(viewer, "financials"):
        category = "other"
    up = request.files.get("file")
    if up and up.filename:
        fid = _store_upload(tour, viewer, up, entity_type, entity_id, category, f.get("visibility") or "all")
        if fid:
            ts.log_change(tour_id, tour["user_id"], _actor(viewer), "file", fid, up.filename, "uploaded", "", category, "info")
    if entity_type == "show":
        return redirect(_show_url(tour, {"id": entity_id}, "files"))
    return _back("/tours/%s/files" % tour_id)


@bp.route("/tours/<tour_id>/files/<file_id>/download")
@require_tour("view")
def file_download(user, tour, viewer, tour_id, file_id):
    record = ts.get_file(tour_id, file_id)
    if record is None or not _files_for(viewer, [record]):
        abort(404)
    return _serve(record)


def _serve(record):
    path = record["path"]
    if blob_store.is_remote(path):
        url = blob_store.url_for(path, ttl=300)
        if url == path:
            abort(503)
        return redirect(url)
    if path.startswith(TOUR_PREFIX):
        from flask import send_from_directory
        return send_from_directory(_tour_dir(), path[len(TOUR_PREFIX):], as_attachment=True,
                                   download_name=record["file_name"])
    abort(404)


@bp.route("/tours/<tour_id>/files/<file_id>/delete", methods=["POST"])
@require_tour("files")
def file_delete(user, tour, viewer, tour_id, file_id):
    record = ts.get_file(tour_id, file_id)
    if record is None or not _files_for(viewer, [record]):
        abort(404)
    if not (viewer["is_owner"] or "admin" in viewer["scopes"] or record["uploaded_by"] == viewer["name"]):
        abort(403)
    ts.delete_file(tour_id, file_id)
    path = record["path"]
    if path.startswith(TOUR_PREFIX):
        try:
            os.remove(os.path.join(_tour_dir(), path[len(TOUR_PREFIX):]))
        except OSError:
            pass
    return _back("/tours/%s/files" % tour_id)


# --- what changed -----------------------------------------------------------

@bp.route("/tours/<tour_id>/stage-plot")
@require_tour("view")
def stage_plot(user, tour, viewer, tour_id):
    """The owner's stage plot inside the tour frame. The plot is the act's,
    not the tour's - one per account, drawn at /stage-plot - so it is read
    from the tour owner and only the owner may change it; crew see the
    drawing and the input list it derives, which is what they need."""
    import json as _json
    plot = store.get_stage_plot(tour["user_id"])
    return render_template("tour/stage_plot.html", **_ctx(
        user, tour, viewer, "stage-plot",
        saved_plot=_json.dumps(plot) if plot else "null",
        editable=bool(viewer.get("is_owner"))))


@bp.route("/tours/<tour_id>/changes")
@require_tour("view")
def changes(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    level = request.args.get("level") or "important"
    rows = ts.list_changes(tour_id, severity_min=None if level == "all" else level, limit=300)
    out = _changes_for(viewer, tour_id, rows)
    acks = ts.ack_state(tour_id, [c["id"] for c in out], user["id"])
    for c in out:
        if acks.get(c["id"]) not in ("viewed", "acknowledged"):
            ts.ack(tour_id, tour["user_id"], c["id"], user["id"], "viewed")
    roster = {}
    if can(viewer, "admin"):
        for c in out[:50]:
            if c["severity"] == "critical":
                roster[c["id"]] = ts.ack_roster(tour_id, c["id"])
    members = ts.list_members(tour_id)
    name_by_user = {m.get("member_user_id"): (m.get("name") or m["email"]) for m in members if m.get("member_user_id")}
    name_by_user[tour["user_id"]] = (store.get_user(tour["user_id"]) or {}).get("name") or "Owner"
    return render_template("tour/changes.html", **_ctx(
        user, tour, viewer, "changes", shows=shows, rows=out, acks=acks, level=level, roster=roster,
        name_by_user=name_by_user))


@bp.route("/tours/<tour_id>/changes/<change_id>/ack", methods=["POST"])
@require_tour("view")
def change_ack(user, tour, viewer, tour_id, change_id):
    ts.ack(tour_id, tour["user_id"], change_id, user["id"], "acknowledged")
    return _back("/tours/%s/changes" % tour_id)


# --- ask tour ---------------------------------------------------------------

def _ask_context(user, tour, viewer):
    shows = ts.list_shows(tour["id"])
    today = eng.today_in(tour["home_tz"])
    schedule = _visible(viewer, ts.list_schedule(tour["id"]))
    travel = _redact_travel(viewer, ts.list_travel(tour["id"]))
    lodging = _redact_lodging(viewer, ts.list_lodging(tour["id"]))
    readiness = {s["id"]: _readiness_for(tour, s, viewer) for s in shows}
    attention = eng.needs_attention(shows, readiness, today)
    guests = {}
    if can(viewer, "guests"):
        for s in shows:
            guests[s["id"]] = ts.guest_summary(tour["id"], s["id"], s.get("guest_allocation"))
    finance = None
    if can(viewer, "financials"):
        exp = {}
        for e in ts.list_expenses(tour["id"]):
            exp.setdefault(e.get("show_id") or "", []).append(e)
        finance = eng.tour_finance(shows, exp, tour["currency"], today=today)
    return {"shows": [_strip_money(viewer, s) if not can(viewer, "financials") else s for s in shows],
            "today": today, "today_utc": datetime.now(timezone.utc).date().isoformat(),
            "schedule": schedule, "travel": travel, "lodging": lodging, "readiness": readiness,
            "attention": attention, "changes": _changes_for(viewer, tour["id"], ts.list_changes(tour["id"], limit=100)),
            "guests": guests, "money_allowed": can(viewer, "financials"), "finance": finance,
            "advance": {s["id"]: ts.list_advance(tour["id"], s["id"]) for s in shows},
            "people": _redact_people(viewer, ts.list_people(tour["id"]))}


@bp.route("/tours/<tour_id>/ask", methods=["GET", "POST"])
@require_tour("view")
def ask(user, tour, viewer, tour_id):
    q = (request.form.get("q") if request.method == "POST" else request.args.get("q")) or ""
    answer = eng.ask(q, _ask_context(user, tour, viewer)) if q.strip() else None
    examples = ["What time is lobby call tomorrow?", "Where are we staying in Atlanta?",
                "What is missing for Chicago?", "What changed today?", "How many guest spots remain tonight?",
                "Which shows have no photographer assigned?", "Who is the promoter in Nashville?",
                "What is the next flight?"]
    if can(viewer, "financials"):
        examples += ["Which deposits are outstanding?", "Which shows are unsettled?", "What is the projected net?"]
    return render_template("tour/ask.html", **_ctx(user, tour, viewer, "ask", q=q, answer=answer, examples=examples))


# --- route / map ------------------------------------------------------------

def _haversine_km(a, b):
    import math
    try:
        lat1, lon1 = float(a[0]), float(a[1]); lat2, lon2 = float(b[0]), float(b[1])
    except (TypeError, ValueError):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)))


@bp.route("/tours/<tour_id>/map")
@require_tour("view")
def route_map(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    venues = {v["id"]: v for v in ts.list_venues(tour["user_id"])}
    days = ts.list_days(tour_id)
    legs = []
    prev = None
    for s in shows:
        v = venues.get(s.get("venue_id") or "")
        stop = {"show": s, "venue": v,
                "address": (v or {}).get("address") or "", "city": s.get("city") or (v or {}).get("city") or "",
                "coords": ((v or {}).get("lat"), (v or {}).get("lng")) if v and v.get("lat") and v.get("lng") else None}
        if prev is not None:
            try:
                gap = (date.fromisoformat(s["date"]) - date.fromisoformat(prev["show"]["date"])).days
            except ValueError:
                gap = None
            km = _haversine_km(prev["coords"], stop["coords"]) if prev["coords"] and stop["coords"] else None
            origin = prev["address"] or prev["city"] or prev["show"]["venue"]
            dest = stop["address"] or stop["city"] or s["venue"]
            legs.append({"frm": prev, "to": stop, "gap_days": gap, "km": km,
                         "miles": round(km * 0.621371) if km else None,
                         # Routing flags from dates alone: two shows on one
                         # day, or on consecutive days. No drive time is
                         # guessed; the flag says look before locking both.
                         "back_to_back": gap == 1, "same_day": gap == 0,
                         "directions": "https://www.google.com/maps/dir/?api=1&origin=%s&destination=%s" % (
                             _urlq(origin), _urlq(dest))})
        prev = stop
    off_days = [d for d in days if d["kind"] in ("off", "travel")]
    # Fuel is computed from DRIVEN miles somebody entered on a travel leg,
    # never from the straight-line distances above. A crow-flight total
    # understates a real drive by something like a fifth, and a fuel
    # figure that quietly does that is worse than no figure at all.
    drives = [t for t in ts.list_travel(tour_id) if t.get("mode") == "ground"]
    fuel = eng.fuel_plan(tour, drives)
    fuel["per_show"] = eng.fuel_per_show(fuel, len(shows))
    return render_template("tour/map.html", **_ctx(
        user, tour, viewer, "map", shows=shows, legs=legs, off_days=off_days, venues=venues,
        fuel=fuel, drives=drives, first=shows[0] if shows else None))


@bp.route("/tours/<tour_id>/fuel", methods=["POST"])
@require_tour("travel")
def fuel_save(user, tour, viewer, tour_id):
    ts.update_fuel(tour_id, {k: request.form.get(k) for k in ts.FUEL_FIELDS})
    return redirect("/tours/%s/map" % tour_id)


def _urlq(s):
    from urllib.parse import quote_plus
    return quote_plus(s or "")


# --- import -----------------------------------------------------------------

# Forward only. A sheet that still says "hold" must not walk a show that
# has since been advanced or played back down the list.
_STATUS_ORDER = list(ts.SHOW_STATUSES)


def _fill_existing_show(tour, tour_id, row):
    """Fill the fields this show has NOT got from an imported row.

    Returns how many fields were filled. Existing values are left alone —
    a deal sheet can be weeks old, and whatever is on the show now was
    either typed by a person or imported from something newer.
    """
    show = ts.get_show(tour_id, row["match_id"])
    if show is None:
        return 0
    want = _import_ext(row)
    patch = {k: v for k, v in want.items() if v and not (show.get(k) or "").strip()}
    n = 0
    if patch:
        ts.update_show_ext(tour_id, row["match_id"], patch)
        n += len(patch)
    status = _import_status(row.get("status"))
    if status:
        now = (show.get("status") or "hold").strip()
        try:
            ahead = _STATUS_ORDER.index(status) > _STATUS_ORDER.index(now)
        except ValueError:
            ahead = False
        if ahead:
            store.update_tour_show_status(tour["user_id"], row["match_id"], status)
            n += 1
    return n


_MONEY_ONLY = re.compile(r"^\$?\s*([\d,]+(?:\.\d{1,2})?)\s*$")


def _import_ext(row):
    """The deal a routing sheet carries, filed where it stays readable.

    A fee is often a sentence, not a number — "15% NBOR capped at $500",
    "TBC". A merch rate almost always is: "90/10, 100% CD/DVD, Artist
    Sells". Forcing either into a numeric column loses the deal, so a
    plain amount goes to `guarantee` and anything else is kept verbatim
    in a text field beside it. Nothing is dropped and nothing is guessed.
    """
    out = {}
    for key in ("promoter", "capacity", "support"):
        if row.get(key):
            out[key] = row[key]
    url = (row.get("ticket_url") or "").strip()
    if re.match(r"^https?://", url, re.I):
        out["ticket_url"] = url
    fee = (row.get("fee") or "").strip()
    if fee:
        m = _MONEY_ONLY.match(fee)
        if m:
            out["guarantee"] = m.group(1).replace(",", "")
        else:
            out["fee_note"] = fee          # a percentage, a cap, or "TBC"
    if row.get("merch"):
        out["merch_rate"] = row["merch"]
    # Where a sheet said something the status vocabulary cannot hold — a
    # hold level, a challenge — keep the words so nobody has to go back to
    # the spreadsheet to find out what "hold" meant.
    status = (row.get("status") or "").strip()
    if status and _import_status(status) == "hold":
        out["source_note"] = status
    return out


def _import_status(raw):
    """A show status from what a deal sheet actually writes. Returns None
    when the sheet said nothing, so an import never overrides a status
    somebody set by hand with a guess."""
    s = (raw or "").strip().lower()
    if not s:
        return None
    if "confirm" in s:
        return "confirmed"
    if "cancel" in s or "dead" in s or "pass" in s:
        return None                        # not a status this module has
    if "settle" in s:
        return "settled"
    if "played" in s:
        return "played"
    if "advanc" in s:
        return "advanced"
    # "3H Challenged", "2H", "1H", "HOLD", "OPTION" — all still a hold.
    if re.search(r"\b\d\s*h\b|hold|challeng|option|pencil", s):
        return "hold"
    return None


@bp.route("/tours/<tour_id>/import", methods=["GET", "POST"])
@require_tour("edit")
def import_dates(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    days = ts.list_days(tour_id)
    history = ts.list_imports(tour_id)[:10]
    if request.method == "GET":
        return render_template("tour/import.html", **_ctx(user, tour, viewer, "import", shows=shows, history=history))
    source = request.form.get("source") or "paste"
    text = request.form.get("text") or ""
    filename = ""
    up = request.files.get("file")
    if up and up.filename:
        filename = up.filename
        raw = up.read(2_000_000)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", "ignore")
        if filename.lower().endswith(".ics"):
            source = "ics"
        elif filename.lower().endswith(".csv"):
            source = "csv"
    if source == "csv":
        rows, problems = eng.parse_csv_rows(text)
    elif source == "ics":
        rows, problems = eng.parse_ics(text)
    else:
        rows, problems = eng.parse_pasted(text)
    rows = eng.dedupe_against(rows, shows, days)
    if request.form.get("action") == "confirm":
        picked = set(request.form.getlist("pick"))
        created = {"shows": 0, "days": 0, "skipped": 0, "updated": 0, "filled": 0}
        fill_existing = request.form.get("fill_existing") == "1"
        for i, r in enumerate(rows):
            if str(i) not in picked:
                created["skipped"] += 1
                continue
            if r["verdict"] == "duplicate":
                # The date is already here. A re-sent deal sheet is how a
                # hold becomes a confirmation, so rather than only skipping
                # it, fill in what the show is MISSING. Never overwrite a
                # value somebody typed: a sheet can be stale, and a hand
                # edit is a decision.
                if fill_existing and r.get("match_id") and r["kind"] == "show":
                    filled = _fill_existing_show(tour, tour_id, r)
                    created["filled"] += filled
                    if filled:
                        created["updated"] += 1
                        continue
                created["skipped"] += 1
                continue
            if r["kind"] == "show":
                sid = store.add_tour_show(tour["user_id"], r["date"], r["venue"] or "TBA", r["city"], r["notes"])
                ts.attach_show(tour_id, sid, r["tz"] if eng.valid_tz(r["tz"]) else "")
                ext = _import_ext(r)
                if ext:
                    ts.update_show_ext(tour_id, sid, ext)
                # A deal sheet says which dates are actually confirmed. It
                # used to be read and thrown away, so every imported show
                # started as a hold no matter what the sheet said.
                status = _import_status(r.get("status"))
                if status:
                    store.update_tour_show_status(tour["user_id"], sid, status)
                created["shows"] += 1
            else:
                ts.add_day(tour_id, tour["user_id"], r["date"], r["kind"], r["venue"] or r["kind"].title(),
                           r["city"], r["tz"] if eng.valid_tz(r["tz"]) else "", None, r["notes"])
                created["days"] += 1
        ts.record_import(tour_id, tour["user_id"], source, filename, text,
                         {"created": created, "problems": problems[:20], "rows": len(rows)})
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "import", "", filename or source, "imported", "",
                      "%d shows, %d days, %d dates filled in (%d fields)"
                      % (created["shows"], created["days"], created["updated"], created["filled"]),
                      "info", "import")
        return redirect("/tours/%s/calendar" % tour_id)
    return render_template("tour/import.html", **_ctx(
        user, tour, viewer, "import", shows=shows, history=history, preview=rows, problems=problems,
        source=source, text=text, filename=filename))


# --- exports ----------------------------------------------------------------

def _csv(text, filename):
    return Response(text, mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % filename})


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "tour"


@bp.route("/tours/<tour_id>/exports")
@require_tour("view")
def exports(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    lodging = _redact_lodging(viewer, ts.list_lodging(tour_id))
    return render_template("tour/exports.html", **_ctx(user, tour, viewer, "exports", shows=shows, lodging=lodging))


@bp.route("/tours/<tour_id>/calendar.ics")
@require_tour("view")
def calendar_ics(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    text = eng.ics_text(tour, shows, ts.list_days(tour_id), _visible(viewer, ts.list_schedule(tour_id)))
    return Response(text, mimetype="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="%s.ics"' % _slug(tour["name"])})


@bp.route("/tours/<tour_id>/itinerary.csv")
@require_tour("view")
def itinerary_csv(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    show_by_id = {s["id"]: s for s in shows}
    rows = []
    for d in ts.list_days(tour_id):
        s = show_by_id.get(d.get("show_id") or "")
        rows.append((d["date"], d["kind"], d.get("city") or (s or {}).get("city") or "",
                     (s or {}).get("venue") or d.get("title") or "", (s or {}).get("status") or "",
                     d.get("tz") or (s or {}).get("tz") or "", d.get("notes") or ""))
    return _csv(eng.csv_text(["Date", "Type", "City", "Venue / Title", "Status", "Timezone", "Notes"], rows),
                "itinerary-%s.csv" % _slug(tour["name"]))


@bp.route("/tours/<tour_id>/itinerary")
@require_tour("view")
def itinerary_print(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    days = ts.list_days(tour_id)
    schedule = _visible(viewer, ts.list_schedule(tour_id))
    travel = _redact_travel(viewer, ts.list_travel(tour_id))
    lodging = _redact_lodging(viewer, ts.list_lodging(tour_id))
    show_by_id = {s["id"]: s for s in shows}
    by_day = []
    for d in days:
        by_day.append({"day": d, "show": show_by_id.get(d.get("show_id") or ""),
                       "schedule": [r for r in schedule if r["day_date"] == d["date"]],
                       "travel": [t for t in travel if t["day_date"] == d["date"]],
                       "hotel": next((l for l in lodging if l["checkin"] == d["date"]), None)})
    return render_template("tour/print_itinerary.html", tour=tour, by_day=by_day, fmt_time=eng.fmt_time,
                           fmt_day=eng.fmt_day_long)


@bp.route("/tours/<tour_id>/people.csv")
@require_tour("people")
def people_csv(user, tour, viewer, tour_id):
    rows = [(p["name"], p["role"], p["category"], p["company"], p["email"], p["phone"], p["emergency"])
            for p in ts.list_people(tour_id)]
    return _csv(eng.csv_text(["Name", "Role", "Category", "Company", "Email", "Phone", "Emergency"], rows),
                "personnel-%s.csv" % _slug(tour["name"]))


@bp.route("/tours/<tour_id>/travel.csv")
@require_tour("travel")
def travel_csv(user, tour, viewer, tour_id):
    people = {p["id"]: p["name"] for p in ts.list_people(tour_id)}
    rows = []
    for t in ts.list_travel(tour_id):
        who = "all" if "all" in (t["travelers"] or []) else ", ".join(people.get(x, "?") for x in t["travelers"])
        rows.append((t["day_date"], t["mode"], t["carrier"], t["number"], t["dep_loc"], t["dep_time"], t["dep_tz"],
                     t["arr_loc"], t["arr_time"], t["arr_tz"], t["confirmation"], t["driver"], t["phone"], who, t["status"]))
    return _csv(eng.csv_text(["Date", "Mode", "Carrier", "Number", "From", "Dep", "Dep TZ", "To", "Arr", "Arr TZ",
                              "Confirmation", "Driver", "Phone", "Travelers", "Status"], rows),
                "travel-%s.csv" % _slug(tour["name"]))


@bp.route("/tours/<tour_id>/hotels/<lodging_id>/rooming")
@require_tour("hotel")
def rooming_print(user, tour, viewer, tour_id, lodging_id):
    l = ts.get_lodging(tour_id, lodging_id)
    if l is None:
        abort(404)
    rooms = ts.list_rooms(tour_id, lodging_id)
    fmt = request.args.get("format")
    if fmt == "csv":
        rows = [(r.get("person_name") or r["guest_name"], r["room_number"], r["room_kind"], r["notes"]) for r in rooms]
        return _csv(eng.csv_text(["Name", "Room", "Type", "Notes"], rows),
                    "rooming-%s-%s.csv" % (l["checkin"], _slug(l["property"])))
    return render_template("tour/print_rooming.html", tour=tour, lodging=l, rooms=rooms, fmt_day=eng.fmt_day_long)


@bp.route("/tours/<tour_id>/shows/<show_id>/day-sheet")
@require_tour("view")
def day_sheet(user, tour, viewer, tour_id, show_id):
    show = _show_or_404(tour, show_id)
    data = _day_sheet_data(tour, show, viewer)
    return render_template("tour/print_day_sheet.html", **data)


def _day_sheet_data(tour, show, viewer=None, public=False):
    """What a day sheet shows. Public (share-link) sheets carry only
    visibility=all rows, no confirmation numbers, no money, no private
    rooms — the same filter an unscoped member would get."""
    if viewer is None:
        viewer = {"is_owner": False, "scopes": ["view"], "person": None, "user": {"id": ""}, "name": "share link"}
    schedule = _visible(viewer, ts.list_schedule(tour["id"], show_id=show["id"]))
    travel = _redact_travel(viewer, ts.list_travel(tour["id"], show_id=show["id"]) +
                            [t for t in ts.list_travel(tour["id"], day_date=show["date"]) if not t.get("show_id")])
    lodging = _redact_lodging(viewer, ts.list_lodging(tour["id"], show_id=show["id"]) or
                              ts.list_lodging(tour["id"], on_date=show["date"]))
    venue = ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None
    people = _redact_people(viewer, [p for p in ts.list_people(tour["id"])
                                     if p["category"] in ("Tour Management", "Production", "Venue", "Promoters", "Drivers", "Security")
                                     and (not p.get("shows") or show["id"] in p["shows"])])
    adv = {r["item_key"]: r for r in ts.list_advance(tour["id"], show["id"])}
    setlists = [ts.get_setlist(tour["id"], s["id"]) for s in ts.list_setlists(tour["id"], show_id=show["id"])]
    return {"tour": tour, "show": _strip_money(viewer, show), "schedule": schedule, "travel": travel,
            "lodging": lodging, "venue": venue, "people": people, "advance": adv, "setlists": setlists,
            "fmt_time": eng.fmt_time, "fmt_day": eng.fmt_day_long, "public": public,
            "wifi": adv.get("wifi", {}).get("value", ""), "parking": adv.get("parking", {}).get("value", ""),
            "curfew": adv.get("curfew", {}).get("value", "")}


# --- share links ------------------------------------------------------------

def _hash_pw(pw):
    salt = uuid.uuid4().hex[:16]
    return "%s$%s" % (salt, hashlib.sha256((salt + pw).encode()).hexdigest())


def _check_pw(stored, pw):
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    return hmac.compare_digest(hashlib.sha256((salt + (pw or "")).encode()).hexdigest(), digest)


@bp.route("/tours/<tour_id>/share")
@require_tour("admin")
def share(user, tour, viewer, tour_id):
    shows = ts.list_shows(tour_id)
    links = ts.list_share_links(tour_id)
    today = eng.today_in(tour["home_tz"])
    for l in links:
        l["expired"] = bool(l["expires"] and l["expires"] < today)
        l["url"] = "%s/tour-share/%s" % (_base_url(), l["token"])
    return render_template("tour/share.html", **_ctx(
        user, tour, viewer, "share", shows=shows, links=links, show_by_id={s["id"]: s for s in shows},
        scope_labels=SHARE_SCOPE_LABELS, lodging=ts.list_lodging(tour_id)))


SHARE_SCOPE_LABELS = {
    "day_sheet": "Day sheet (one show, times and venue only)",
    "photographer": "Photographer brief (times, content plan, venue)",
    "guest_checkin": "Guest-list check-in (names, counts, tap to check in)",
    "venue_guest_list": "Venue guest list (read-only names and counts)",
    "driver": "Driver sheet (ground legs, load-in, bus call, addresses)",
    "setlist": "Set list",
    "production": "Production pack (production advance, plot, tech files)",
    "vip_checkin": "VIP check-in",
    "rooming": "Rooming list (names and rooms, for the front desk)",
    "band": "Band itinerary (the WHOLE run — dates, times, hotels; no money, no rooms, no phone numbers)",
}


@bp.route("/tours/<tour_id>/share/new", methods=["POST"])
@require_tour("admin")
def share_new(user, tour, viewer, tour_id):
    scope = request.form.get("scope") or ""
    show_id = request.form.get("show_id") or None
    if scope in ("day_sheet", "photographer", "guest_checkin", "venue_guest_list", "driver", "setlist",
                 "production", "vip_checkin") and (not show_id or ts.get_show(tour_id, show_id) is None):
        return redirect("/tours/%s/share" % tour_id)
    if scope == "rooming":
        show_id = request.form.get("lodging_id") or None
        if not show_id or ts.get_lodging(tour_id, show_id) is None:
            return redirect("/tours/%s/share" % tour_id)
    if scope in ts.TOUR_WIDE_SCOPES:
        show_id = None          # the whole run, not one date
    pw = request.form.get("password") or ""
    ts.create_share_link(tour_id, tour["user_id"], scope, show_id,
                         _hash_pw(pw) if pw else "", request.form.get("expires") or "")
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "share", "", SHARE_SCOPE_LABELS.get(scope, scope),
                  "created", "", "expires %s" % (request.form.get("expires") or "never"), "info")
    return redirect("/tours/%s/share" % tour_id)


@bp.route("/tours/<tour_id>/share/<link_id>/revoke", methods=["POST"])
@require_tour("admin")
def share_revoke(user, tour, viewer, tour_id, link_id):
    ts.revoke_share_link(tour_id, link_id)
    return redirect("/tours/%s/share" % tour_id)


def _share_link_or_404(token):
    link = ts.get_share_link(token)
    if link is None or link["revoked"]:
        abort(404)
    tour = ts.get_tour(link["tour_id"])
    if tour is None:
        abort(404)
    if link["expires"] and link["expires"] < eng.today_in(tour["home_tz"]):
        abort(410)
    return link, tour


@bp.route("/tour-share/<token>", methods=["GET", "POST"])
def shared(token):
    link, tour = _share_link_or_404(token)
    if link["password_hash"]:
        key = "tsl:" + token
        if request.method == "POST" and request.form.get("password") is not None and not request.form.get("action"):
            if _check_pw(link["password_hash"], request.form.get("password")):
                session[key] = 1
            else:
                return render_template("tour/share_password.html", tour=tour, wrong=True, token=token), 401
        if not session.get(key):
            return render_template("tour/share_password.html", tour=tour, wrong=False, token=token)
    ts.touch_share_link(token)
    scope = link["scope"]
    base = {"tour": tour, "token": token, "scope": scope, "fmt_time": eng.fmt_time,
            "fmt_day": eng.fmt_day_long, "today": eng.today_in(tour["home_tz"])}
    if scope == "rooming":
        l = ts.get_lodging(tour["id"], link["show_id"])
        if l is None:
            abort(404)
        rooms = ts.list_rooms(tour["id"], l["id"])
        if request.args.get("format") == "csv":
            rows = [(r.get("person_name") or r["guest_name"], r["room_number"], r["room_kind"], r["notes"]) for r in rooms]
            return _csv(eng.csv_text(["Name", "Room", "Type", "Notes"], rows),
                        "rooming-%s-%s.csv" % (l["checkin"], _slug(l["property"])))
        return render_template("tour/share_rooming.html", lodging=l, rooms=rooms, **base)
    if scope == "band":
        # The whole run for somebody playing it. Assembled field by field
        # rather than by stripping a full tour object, so a column added
        # later cannot quietly start travelling to everyone with the link.
        pub = {"is_owner": False, "scopes": ["view"], "person": None, "user": {"id": ""}, "name": ""}
        shows = ts.list_shows(tour["id"])
        days = ts.list_days(tour["id"])
        sched = _visible(pub, ts.list_schedule(tour["id"]))
        # Departure and pickup, never the driver's phone or the booking.
        travel = [{"day_date": t["day_date"], "show_id": t.get("show_id") or "",
                   "mode": t["mode"], "dep_time": t["dep_time"], "arr_time": t["arr_time"],
                   "dep_loc": t["dep_loc"], "arr_loc": t["arr_loc"],
                   "pickup": t.get("pickup") or "", "status": t.get("status") or ""}
                  for t in _visible(pub, ts.list_travel(tour["id"]))]
        # Where the hotel is, never who is in which room or what it cost.
        lodging = [{"checkin": l["checkin"], "checkout": l.get("checkout") or "",
                    "property": l["property"], "address": l.get("address") or "",
                    "show_id": l.get("show_id") or ""}
                   for l in _visible(pub, ts.list_lodging(tour["id"]))]
        venues = {v["id"]: {"name": v["name"], "address": v.get("address") or "",
                            "city": v.get("city") or ""}
                  for v in ts.list_venues(tour["user_id"])}
        rows = []
        for s in shows:
            v = venues.get(s.get("venue_id") or "")
            rows.append({
                "kind": "show", "date": s["date"], "city": s.get("city") or "",
                "venue": s["venue"], "support": s.get("support") or "",
                "address": (v or {}).get("address") or "",
                "schedule": [r for r in sched if r.get("show_id") == s["id"]],
                "travel": [t for t in travel if t["show_id"] == s["id"] or t["day_date"] == s["date"]],
                "hotel": next((l for l in lodging if l["show_id"] == s["id"]
                               or l["checkin"] == s["date"]), None)})
        for d in days:
            rows.append({"kind": d["kind"], "date": d["date"], "city": d.get("city") or "",
                         "venue": "", "support": "", "address": "", "label": d.get("label") or "",
                         "schedule": [], "travel": [t for t in travel if t["day_date"] == d["date"]],
                         "hotel": next((l for l in lodging if l["checkin"] == d["date"]), None)})
        rows.sort(key=lambda r: r["date"])
        return render_template("tour/share_band.html", rows=rows, shows=shows, **base)
    show = ts.get_show(tour["id"], link["show_id"])
    if show is None:
        abort(404)
    show = _strip_money({"is_owner": False, "scopes": []}, show)
    if scope == "day_sheet":
        data = _day_sheet_data(tour, show, None, public=True)
        data.update(base)
        return render_template("tour/print_day_sheet.html", **data)
    if scope == "photographer":
        ts.ensure_content_plan(tour["id"], tour["user_id"], show["id"])
        pub = {"is_owner": False, "scopes": ["view"], "person": None, "user": {"id": ""}, "name": ""}
        return render_template("tour/share_photographer.html", show=show, venue=ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None,
                               schedule=_visible(pub, ts.list_schedule(tour["id"], show_id=show["id"])),
                               content=ts.list_content(tour["id"], show_id=show["id"]), **base)
    if scope in ("guest_checkin", "venue_guest_list"):
        if request.method == "POST" and scope == "guest_checkin" and request.form.get("action") == "checkin":
            g = ts.get_guest(tour["id"], request.form.get("guest_id") or "")
            if g and g["show_id"] == show["id"] and g["status"] in ("approved", "checked_in"):
                ts.update_guest(tour["id"], g["id"], {"status": "checked_in" if request.form.get("undo") != "1" else "approved"})
            return redirect("/tour-share/%s" % token)
        rows = [g for g in ts.list_guests(tour["id"], show["id"]) if g["status"] in ("approved", "checked_in")]
        summary = ts.guest_summary(tour["id"], show["id"], show.get("guest_allocation"))
        return render_template("tour/share_guests.html", show=show, rows=rows, summary=summary,
                               checkin=(scope == "guest_checkin"), **base)
    if scope == "vip_checkin":
        if request.method == "POST" and request.form.get("action") == "checkin":
            ts.set_vip_status(tour["id"], request.form.get("vip_id") or "",
                              "checked_in" if request.form.get("undo") != "1" else "sold")
            return redirect("/tour-share/%s" % token)
        return render_template("tour/share_vip.html", show=show, rows=ts.list_vip(tour["id"], show["id"]),
                               summary=ts.vip_summary(tour["id"], show["id"]), **base)
    if scope == "driver":
        pub = {"is_owner": False, "scopes": ["view"], "person": None, "user": {"id": ""}, "name": ""}
        travel = [t for t in _visible(pub, ts.list_travel(tour["id"], day_date=show["date"])) if t["mode"] in ("ground", "bus")]
        sched = [r for r in _visible(pub, ts.list_schedule(tour["id"], show_id=show["id"]))
                 if r["category"] in ("load_in", "bus_call", "call", "travel", "doors", "curfew", "set")]
        lodging = [dict(l, confirmation="", payment="", reservation_name="") for l in
                   _visible(pub, ts.list_lodging(tour["id"], show_id=show["id"]) or ts.list_lodging(tour["id"], on_date=show["date"]))]
        venue = ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None
        return render_template("tour/share_driver.html", show=show, travel=travel, schedule=sched, lodging=lodging,
                               venue=venue, **base)
    if scope == "setlist":
        sls = [ts.get_setlist(tour["id"], s["id"]) for s in ts.list_setlists(tour["id"], show_id=show["id"])]
        return render_template("tour/share_setlist.html", show=show, setlists=sls, **base)
    if scope == "production":
        adv = [r for r in ts.list_advance(tour["id"], show["id"]) if r["category"] == "production"]
        files = [f for f in ts.list_files(tour["id"], entity_type="show", entity_id=show["id"])
                 if f["category"] in ("stage_plot", "tech_pack", "rider", "production", "venue_map") and f["visibility"] == "all"]
        files += [f for f in ts.list_files(tour["id"], entity_type="tour")
                  if f["category"] in ("stage_plot", "tech_pack", "rider", "production") and f["visibility"] == "all"]
        pub = {"is_owner": False, "scopes": ["view"], "person": None, "user": {"id": ""}, "name": ""}
        venue = ts.get_venue(tour["user_id"], show["venue_id"]) if show.get("venue_id") else None
        return render_template("tour/share_production.html", show=show, advance=adv, files=files, venue=venue,
                               schedule=_visible(pub, ts.list_schedule(tour["id"], show_id=show["id"])), **base)
    abort(404)


@bp.route("/tour-share/<token>/file/<file_id>")
def shared_file(token, file_id):
    link, tour = _share_link_or_404(token)
    if link["scope"] != "production":
        abort(404)
    if link["password_hash"] and not session.get("tsl:" + token):
        abort(401)
    rec = ts.get_file(tour["id"], file_id)
    if rec is None or rec["visibility"] != "all" or rec["category"] not in ("stage_plot", "tech_pack", "rider", "production", "venue_map"):
        abort(404)
    if rec["entity_type"] == "show" and rec["entity_id"] != link["show_id"]:
        abort(404)
    return _serve(rec)


# --- team -------------------------------------------------------------------

@bp.route("/tours/<tour_id>/team")
@require_tour("admin")
def team(user, tour, viewer, tour_id):
    members = ts.list_members(tour_id)
    for m in members:
        m["join_url"] = "%s/tours/join/%s" % (_base_url(), m["invite_token"]) if m.get("invite_token") else ""
    people = ts.list_people(tour_id)
    return render_template("tour/team.html", **_ctx(
        user, tour, viewer, "team", members=members, people=people,
        email_live=emailer.configured() and not emailer.using_shared_test_sender()))


@bp.route("/tours/<tour_id>/team/invite", methods=["POST"])
@require_tour("admin")
def team_invite(user, tour, viewer, tour_id):
    f = request.form
    role = f.get("role") or "crew"
    scopes = [s for s in f.getlist("scopes") if s in ts.SCOPES] or list(ts.ROLE_PRESETS.get(role, ["view"]))
    if "admin" in scopes and not viewer["is_owner"]:
        scopes.remove("admin")        # only the owner hands out admin
    m = ts.add_member(tour_id, tour["user_id"], f.get("email"), f.get("name"), role, scopes)
    if m is None:
        return redirect("/tours/%s/team" % tour_id)
    if f.get("person_id"):
        ts.link_member_person(tour_id, m["id"], f.get("person_id"))
    join_url = "%s/tours/join/%s" % (_base_url(), m["invite_token"])
    existing = store.get_user_by_email(m["email"])
    if existing:
        store.notify(existing["id"], "tour", "You were added to %s" % tour["name"],
                     "Open the tour to accept.", "/tours/join/%s" % m["invite_token"])
    if emailer.configured() and not emailer.using_shared_test_sender():
        try:
            emailer.send(m["email"], "You're on the %s tour" % tour["name"],
                         "<p>%s added you to <b>%s</b> on Street Banker as %s.</p>"
                         "<p><a href=\"%s\">Accept and open the tour</a></p>"
                         % (_esc(viewer["name"]), _esc(tour["name"]), _esc(role.replace("_", " ")), join_url), reply_to=user.get("email") or None)
        except Exception:
            pass
    ts.log_change(tour_id, tour["user_id"], _actor(viewer), "member", m["id"], m["email"], "invited", "", role, "info")
    return redirect("/tours/%s/team" % tour_id)


@bp.route("/tours/<tour_id>/team/<member_id>", methods=["POST"])
@require_tour("admin")
def team_member(user, tour, viewer, tour_id, member_id):
    m = ts.get_member(tour_id, member_id)
    if m is None:
        abort(404)
    action = request.form.get("action")
    if action == "remove":
        ts.remove_member(tour_id, member_id)
        ts.log_change(tour_id, tour["user_id"], _actor(viewer), "member", member_id, m["email"], "removed", m["role"], "", "info")
    elif action == "scopes":
        scopes = [s for s in request.form.getlist("scopes") if s in ts.SCOPES]
        if "admin" in scopes and not viewer["is_owner"]:
            scopes.remove("admin")
        ts.set_member_scopes(tour_id, member_id, request.form.get("role") or m["role"], scopes)
        if request.form.get("person_id") is not None:
            ts.link_member_person(tour_id, member_id, request.form.get("person_id") or None)
    return redirect("/tours/%s/team" % tour_id)


# --- settings ---------------------------------------------------------------

@bp.route("/tours/<tour_id>/settings", methods=["GET", "POST"])
@require_tour("admin")
def settings(user, tour, viewer, tour_id):
    if request.method == "POST":
        if request.form.get("action") == "delete":
            if request.form.get("confirm") == tour["name"] and viewer["is_owner"]:
                ts.delete_tour(tour_id)
                return redirect("/tours")
            return redirect("/tours/%s/settings" % tour_id)
        fields = {k: request.form.get(k) for k in ("name", "artist_name", "status", "start_date", "end_date",
                                                  "home_tz", "currency", "notes") if k in request.form}
        if fields.get("home_tz") and not eng.valid_tz(fields["home_tz"]):
            fields.pop("home_tz")
        before = tour["status"]
        ts.update_tour(tour_id, fields)
        if fields.get("status") and fields["status"] != before:
            ts.log_change(tour_id, tour["user_id"], _actor(viewer), "tour", tour_id, tour["name"], "status", before, fields["status"], "important")
        return redirect("/tours/%s/settings" % tour_id)
    return render_template("tour/settings.html", **_ctx(
        user, tour, viewer, "settings", fan_capture=ts.fan_capture_summary(tour_id),
        imports=ts.list_imports(tour_id)[:20]))


# --- search -----------------------------------------------------------------

@bp.route("/tours/<tour_id>/search")
@require_tour("view")
def search(user, tour, viewer, tour_id):
    q = (request.args.get("q") or "").strip()
    shows = ts.list_shows(tour_id)
    hits = []
    if len(q) >= 2:
        ql = q.lower()
        for s in shows:
            if ql in (s["venue"] or "").lower() or ql in (s.get("city") or "").lower() or ql in s["date"]:
                hits.append({"kind": "Show", "label": "%s — %s, %s" % (s["date"], s["venue"], s.get("city") or ""), "href": _show_url(tour, s)})
        for p in _redact_people(viewer, ts.list_people(tour_id, search=q)):
            hits.append({"kind": "Person", "label": "%s · %s" % (p["name"], p["role"] or p["category"]), "href": "/tours/%s/people?q=%s" % (tour_id, q)})
        for v in ts.list_venues(tour["user_id"], q):
            hits.append({"kind": "Venue", "label": "%s, %s" % (v["name"], v["city"]), "href": "/tours/%s/venues?edit=%s" % (tour_id, v["id"])})
        for r in _visible(viewer, ts.list_schedule(tour_id)):
            if ql in r["title"].lower() or ql in (r.get("location") or "").lower():
                hits.append({"kind": "Schedule", "label": "%s %s — %s" % (r["day_date"], eng.fmt_time(r["start_time"]), r["title"]), "href": "/tours/%s/schedule" % tour_id})
        for l in _redact_lodging(viewer, ts.list_lodging(tour_id)):
            if ql in l["property"].lower() or ql in (l.get("city") or "").lower():
                hits.append({"kind": "Hotel", "label": "%s — %s" % (l["property"], l["checkin"]), "href": "/tours/%s/hotels" % tour_id})
        for t in _redact_travel(viewer, ts.list_travel(tour_id)):
            if ql in (t.get("number") or "").lower() or ql in (t.get("carrier") or "").lower() or ql in (t.get("arr_loc") or "").lower():
                hits.append({"kind": "Travel", "label": "%s %s %s → %s" % (t["day_date"], t["mode"], t.get("dep_loc") or "", t.get("arr_loc") or ""), "href": "/tours/%s/travel" % tour_id})
        if can(viewer, "files"):
            for f in _files_for(viewer, ts.list_files(tour_id, search=q)):
                hits.append({"kind": "File", "label": f["file_name"], "href": "/tours/%s/files/%s/download" % (tour_id, f["id"])})
        if can(viewer, "guests"):
            for s in shows:
                for g in ts.list_guests(tour_id, s["id"]):
                    if ql in g["name"].lower() or ql in (g.get("company") or "").lower():
                        hits.append({"kind": "Guest", "label": "%s — %s (%s)" % (g["name"], s["venue"], g["status"]), "href": _show_url(tour, s, "guests")})
    return render_template("tour/search.html", **_ctx(user, tour, viewer, "search", shows=shows, q=q, hits=hits[:80]))


# --- wiring -----------------------------------------------------------------

def init(app, base_url):
    global _base_url
    _base_url = base_url
    ts.init_tour()
    # The Hub folded into TOUR: any show still sitting on no tour joins one
    # now, so nothing anyone entered there is out of reach.
    try:
        ts.adopt_all_orphans()
    except Exception:   # a boot must never fail on the adoption sweep
        pass
    app.register_blueprint(bp)
