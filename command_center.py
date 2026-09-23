"""Street Banker Command Center + global Actions.

The operating-system spine: unified scores computed live from the real
modules (Links, Rollout Engine, Fan CRM, Catalog, EPK), derived health
alerts that always point at a destination, a persistent action/task
system, and the registry of every OS module with an honest Live/Preview
status. Scores are derived fresh on every load rather than snapshotted —
no stale numbers, no fake data.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from db import get_db, _now
import links_engine
import links_store as mls
import rollout_store as ros

# --- Actions -------------------------------------------------------------------

ACTION_CATEGORIES = ["release", "metadata", "smart_link", "rollout", "fan_growth",
                     "royalty_recovery", "sync", "rights", "press", "show", "report",
                     "general"]
ACTION_PRIORITIES = ["high", "medium", "low"]
ACTION_STATUSES = ["new", "in_progress", "complete", "dismissed"]
ACTIVE_STATUSES = ("new", "in_progress")

# The words a person reads for each action type (the owner's mockup reads
# "Metadata", "Rights", "Press").
ACTION_TYPE_LABELS = {
    "release": "Release", "metadata": "Metadata", "smart_link": "Smart link",
    "rollout": "Rollout", "fan_growth": "Fan growth", "royalty_recovery": "Royalty recovery",
    "sync": "Sync", "rights": "Rights", "press": "Press", "show": "Show",
    "report": "Report", "general": "General",
}

# One name for each state, everywhere: the list, the filters, the board,
# the Command Center (crawl, 2026-09-23: the list said New and Complete,
# the board said To Do and Done).
STATUS_LABELS = {"new": "Not started", "in_progress": "In progress",
                 "complete": "Complete", "dismissed": "Dismissed"}

# Where an action came from, recorded when it is made and never guessed
# afterwards. A row made before sources were kept has none and says none.
ACTION_SOURCES = {
    "manual": "Created manually",
    "alert": "From a Command Center alert",
    "release_check": "From Release Check",
    "catalog_check": "From the Catalog check",
    "rights_conflict": "From Rights Conflict",
    "royalty_check": "From the Royalty check",
    "growth_score": "From the Growth score",
    "trust_score": "From the Trust score",
    "module": "From a preview module",
    "document": "From a contract reading",
    "tour_task": "From Tour tasks",
}

# Only work a person typed in can be deleted. An action a check, an alert
# or a contract reading raised stays on record as what was asked, and is
# dismissed instead (owner-approved, 2026-09-23). A row from before sources
# were kept counts as typed in when it points at nothing.
DELETABLE_SOURCES = ("manual", "tour_task")

# The room an action type belongs to when nobody chose one.
TYPE_ROOM = {"release": "releases", "smart_link": "releases", "rollout": "releases",
             "metadata": "publishing", "rights": "publishing", "sync": "publishing",
             "royalty_recovery": "business", "report": "business",
             "fan_growth": "fans", "press": "marketing", "show": "stage"}

# "Needs attention": still open, and high priority, overdue, or due within
# this many days. The page says so in words under the heading.
ATTENTION_DAYS = 3


def _room_keys():
    import rooms                      # rooms imports hubs; keep it lazy
    return [r[0] for r in rooms.ROOMS]


def _cut(text, limit):
    """Shorten at a word boundary and say so. A description that ends
    "SoundExchange: Sirius XM Radio, Inc, Sound" was cut mid-word by a
    plain slice (seen on the Action Center, 2026-09-12)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit - 2]
    for sep in (", ", " "):
        at = head.rfind(sep)
        if at > limit // 2:
            head = head[:at]
            break
    return head.rstrip(" ,;:") + " …"


def _clean_date(value):
    """A YYYY-MM-DD date or ''. A due date that is not a date would sort
    and compare as text and make "overdue" lie."""
    value = (value or "").strip()[:10]
    try:
        return date.fromisoformat(value).isoformat() if value else ""
    except ValueError:
        return ""


def _safe_href(href):
    """A same-site path or ''. The way back to a source is followed by a
    click, so it may never be another site."""
    href = (href or "").strip()[:300]
    if not href.startswith("/") or href.startswith("//") or "\\" in href:
        return ""
    return href


def create_action(user_id, title, category="general", priority="medium",
                  description="", entity_type="", entity_id="", due_date="",
                  room="", assignee_id="", source="", source_href="", created_by=""):
    aid = uuid.uuid4().hex
    now = _now()
    category = category if category in ACTION_CATEGORIES else "general"
    room = room if room in _room_keys() else ""
    with get_db() as db:
        db.execute(
            "INSERT INTO street_actions (id, user_id, title, category, priority,"
            " description, entity_type, entity_id, due_date, status, created, updated,"
            " room, assignee_id, source, source_href, created_by)"
            " VALUES (?,?,?,?,?,?,?,?,?,'new',?,?,?,?,?,?,?)",
            (aid, user_id, title[:200], category,
             priority if priority in ACTION_PRIORITIES else "medium",
             _cut(description, 600), entity_type[:40], entity_id[:64],
             _clean_date(due_date), now, now,
             room, (assignee_id or "")[:64],
             source if source in ACTION_SOURCES else "",
             _safe_href(source_href), (created_by or "")[:64]))
    return aid


def get_action(action_id, user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM street_actions WHERE id = ? AND user_id = ?",
                         (action_id, user_id)).fetchone()
    return dict(row) if row else None


# What an edit may change. Status has its own door (set_action_status), and
# where an action came from is history, not a setting.
_EDITABLE = ("title", "category", "priority", "description", "due_date", "room",
             "assignee_id", "entity_type", "entity_id")


def update_action(action_id, user_id, **fields):
    """Save an edit. Unknown fields are ignored; each known one is cleaned
    the way create_action cleans it. True when a row changed."""
    clean = {}
    for key, value in fields.items():
        if key not in _EDITABLE or value is None:
            continue
        value = (value or "").strip() if isinstance(value, str) else value
        if key == "title":
            if not value:
                continue                  # an action always has a name
            value = value[:200]
        elif key == "category":
            value = value if value in ACTION_CATEGORIES else "general"
        elif key == "priority":
            value = value if value in ACTION_PRIORITIES else "medium"
        elif key == "description":
            value = _cut(value, 600)
        elif key == "due_date":
            value = _clean_date(value)
        elif key == "room":
            value = value if value in _room_keys() else ""
        elif key == "entity_type":
            value = value[:40]
        else:
            value = value[:64]
        clean[key] = value
    if not clean:
        return False
    sets = ", ".join("%s = ?" % k for k in clean)
    with get_db() as db:
        cur = db.execute("UPDATE street_actions SET %s, updated = ? WHERE id = ? AND user_id = ?" % sets,
                         list(clean.values()) + [_now(), action_id, user_id])
    return cur.rowcount > 0


def deletable(action):
    """May this action be deleted, rather than dismissed?"""
    src = (action or {}).get("source") or ""
    if src:
        return src in DELETABLE_SOURCES
    return not (action or {}).get("entity_type")


def delete_action(action_id, user_id):
    """Delete an action typed in by hand. False, and nothing touched, for
    one a check, an alert or a reading raised."""
    action = get_action(action_id, user_id)
    if not action or not deletable(action):
        return False
    with get_db() as db:
        cur = db.execute("DELETE FROM street_actions WHERE id = ? AND user_id = ?",
                         (action_id, user_id))
    return cur.rowcount > 0


def _as_date(today=None):
    if isinstance(today, date):
        return today
    if today:
        return date.fromisoformat(str(today)[:10])
    return datetime.now(timezone.utc).date()


def is_overdue(action, today=None):
    due = (action or {}).get("due_date") or ""
    return bool(due) and action.get("status") in ACTIVE_STATUSES and due < _as_date(today).isoformat()


def needs_attention(action, today=None):
    """Open, and high priority, overdue, or due within ATTENTION_DAYS."""
    if (action or {}).get("status") not in ACTIVE_STATUSES:
        return False
    if action.get("priority") == "high":
        return True
    due = action.get("due_date") or ""
    return bool(due) and due <= (_as_date(today) + timedelta(days=ATTENTION_DAYS)).isoformat()


def board_summary(actions, today=None):
    """The figures over the board. Dismissed work is set aside, not
    counted as unfinished (crawl, 2026-09-23: one dismissed action read
    "0 of 1 complete, 0%"), and reported on its own."""
    live = [a for a in actions or () if a.get("status") != "dismissed"]
    done = sum(1 for a in live if a["status"] == "complete")
    return {
        "total": len(live),
        "complete": done,
        "in_progress": sum(1 for a in live if a["status"] == "in_progress"),
        "not_started": sum(1 for a in live if a["status"] == "new"),
        "open": sum(1 for a in live if a["status"] in ACTIVE_STATUSES),
        "overdue": sum(1 for a in live if is_overdue(a, today)),
        "attention": sum(1 for a in live if needs_attention(a, today)),
        "dismissed": sum(1 for a in actions or () if a.get("status") == "dismissed"),
        "pct": round(100 * done / len(live)) if live else 0,
    }


def rank_open(actions, today=None):
    """Open actions, the one that most needs doing first: needing
    attention, overdue, due soonest, then by priority, oldest first."""
    pr = {"high": 0, "medium": 1, "low": 2}
    live = [a for a in actions or () if a.get("status") in ACTIVE_STATUSES]
    return sorted(live, key=lambda a: (
        0 if needs_attention(a, today) else 1,
        0 if is_overdue(a, today) else 1,
        a.get("due_date") or "9999-99-99",
        pr.get(a.get("priority"), 1),
        a.get("created") or ""))


# Where an action points, by what it is about. An action that says "click
# this to set your reminders" has to be clickable, and a title alone is not;
# entity_type/entity_id were already on the row and nothing read them.
ACTION_LINKS = {
    "document": "/vault?view=contracts#doc-%s",
}


def action_link(action):
    """The page this action is about, or None."""
    kind = (action or {}).get("entity_type") or ""
    ident = (action or {}).get("entity_id") or ""
    shape = ACTION_LINKS.get(kind)
    return (shape % ident) if (shape and ident) else None


def complete_actions_for(user_id, entity_type, entity_id):
    """Close the open actions about one thing, because it is now done.

    The action that asks for a contract's dates is finished the moment
    those dates are saved; leaving it open would make the list lie."""
    with get_db() as db:
        # completed_at too: the details page says when it was finished, and
        # a row closed by its record was finished then (map, 2026-09-23).
        now = _now()
        cur = db.execute(
            "UPDATE street_actions SET status = 'complete', updated = ?, completed_at = ?"
            " WHERE user_id = ? AND entity_type = ? AND entity_id = ?"
            " AND status IN ('new', 'in_progress')",
            (now, now, user_id, entity_type[:40], entity_id[:64]))
        return cur.rowcount


def open_action_for(user_id, entity_type, entity_id):
    """Is there already one open for this thing? Re-reading a document
    must not stack a second identical action on the list."""
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM street_actions WHERE user_id = ? AND entity_type = ?"
            " AND entity_id = ? AND status IN ('new', 'in_progress') LIMIT 1",
            (user_id, entity_type[:40], entity_id[:64])).fetchone()
        return row["id"] if row else None


def set_action_status(action_id, user_id, status):
    if status not in ACTION_STATUSES:
        return False
    with get_db() as db:
        cur = db.execute(
            "UPDATE street_actions SET status = ?, updated = ?,"
            " completed_at = CASE WHEN ? = 'complete' THEN ? ELSE completed_at END"
            " WHERE id = ? AND user_id = ?",
            (status, _now(), status, _now(), action_id, user_id))
    return cur.rowcount > 0


def list_actions(user_id, status=None):
    q = "SELECT * FROM street_actions WHERE user_id = ?"
    args = [user_id]
    if status:
        q += " AND status = ?"
        args.append(status)
    q += (" ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,"
          " created DESC")
    with get_db() as db:
        rows = db.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def open_actions(user_id, limit=5, today=None):
    """The open actions, the one that most needs doing first."""
    return rank_open(list_actions(user_id), today)[:limit]


# --- Module registry: honest Live / Preview states ------------------------------

# (route, name, blurb, status, disclaimer_or_None)
_NOT_LEGAL = "Workflow support only — not legal advice. Have an attorney review agreements."
_NOT_FINANCIAL = "Estimates only — not financial advice."

MODULES = [
    ("/links", "Smart Links 2.0", "Campaigns, pre-saves, fan capture, variants, QR, attribution.", "live", None),
    ("/rollout-studio", "Rollout Engine", "Generated social rollouts with per-post tracked links.", "live", None),
    ("/links/fans", "Fan CRM", "Owned fan data with consent logs and intent scoring.", "live", None),
    ("/epk", "Press Office / EPK", "Editable press kit with public share link and media assets.", "live", None),
    ("/releases/autopilot", "Release Autopilot", "One release in: readiness, the arc, the plan, the kit, and the rights checks before it ships.", "live", None),
    ("/royalty-recovery/cases", "Royalty Recovery Cases", "Turn recovery insights into tracked cases with evidence and deadlines.", "live", None),
    ("/royalty-recovery/mlc", "MLC / Unmatched Recovery", "Find and claim unmatched mechanical royalties with claim packets.", "preview", None),
    ("/sync/clearance-packs", "Sync Clearance Packs", "One-click supervisor-safe pitch packages with clearance status.", "live", None),
    ("/sync/deal-simulator", "Sync Deal Simulator", "Evaluate sync terms, flag buyouts, draft counteroffers.", "live", _NOT_LEGAL),
    ("/deal-room", "Deal Room", "Splits, producer and feature agreements, document vault, deal board.", "live", _NOT_LEGAL),
    ("/revenue-os", "Revenue OS", "Real income from statements against tracked spend.", "live", _NOT_FINANCIAL),
    ("/capital-score", "Capital Readiness Score", "Funding readiness built from catalog health and income consistency.", "live", _NOT_FINANCIAL),
    ("/fraud-sentinel", "Fraud Sentinel", "Artificial streaming and shady playlist risk monitoring.", "preview", None),
    ("/metadata-passport", "Metadata Passport", "Identifier and credit completeness per track, with a clean export.", "live", None),
    ("/ai-rights", "AI Rights & Likeness", "Voice/likeness policies, do-not-train notices, takedown tracking.", "preview", _NOT_LEGAL),
    ("/pulse", "Artist Pulse", "Live Spotify followers, popularity, top tracks, and Deezer fans.", "live", None),
    ("/trust-score", "Trust Score", "One verifiable readiness score for partners, labels, and supervisors.", "live", None),
    ("/artist-twin", "Artist Twin", "Drafts from the data you approve, built from templates today.", "live", None),
    ("/opportunities", "Opportunity Feed", "Matched sync briefs, playlists, grants, and collaborations.", "preview", None),
    ("/voice-of-fan", "Voice of Fan", "Fan comments and behavior turned into campaign intelligence.", "preview", None),
    ("/spend-optimizer", "Spend Optimizer", "Where to put a limited release budget — and what to avoid.", "live", _NOT_FINANCIAL),
    ("/fan-club", "Fan Club", "Paid monthly memberships through Stripe with a members-only drops area, wired into the Fan CRM.", "live", None),
    ("/portal", "Partner Portal", "Team members see role-scoped, read-only views of your business.", "live", None),
    ("/tours", "TOUR", "The whole run, every show from hold to settled: dates, advance, travel, rooms, guests, money.", "live", None),
    ("/stage-plot", "Stage Plot", "Design your stage plot and auto-build the input list venues ask for.", "live", None),
    ("/tour-board", "Team-Up Board", "Artists seeking tour partners and venues seeking acts \u2014 real listings only.", "live", None),
    ("/rack", "The Rack", "Mix and master in the browser: 12-band EQ, tube stage, cab & mic sim, compressor, LUFS loudness against platform targets, WAV export \u2014 nothing is uploaded.", "live", None),
    ("/roster", "Label Mode", "Roster seats for the Label tier: invite artists, see the whole roster's real numbers.", "live", None),
    ("/referrals", "Referrals", "Half off each way: your link, your sign-ups, credits on your Stripe balance.", "live", None),
    ("/lights", "Light Designer", "Cue your light show to the song — stage preview plus real DMX out to an ENTTEC interface.", "live", None),
    ("/tracks", "Track Passports", "Per-track rights and metadata spine: passport, clean-release score, royalty lanes, lockbox.", "live", None),
    ("/money-queue", "Money Queue", "What is costing you money, criticals first — every action names its fix and its basis.", "live", None),
    ("/certified", "Street Banker Certified", "Six rungs from Verified to Upstream Ready, every one computed from your real record.", "live", None),
]

MODULE_BY_ROUTE = {route: (route, name, blurb, status, disc)
                   for route, name, blurb, status, disc in MODULES}

# Windows whose route the sidebar folds under a front, so they group with it.
FOLD_FRONTS = {
    "/links/fans": "/fans", "/fan-club": "/fans", "/epk": "/press-desk",
    # Sync packs group with the releases (owner, 2026-09-19: "You're
    # making a product for sale").
    "/sync/clearance-packs": "/releases/autopilot", "/sync/deal-simulator": "/deal-room",
    "/tracks": "/catalog", "/money-queue": "/royalties", "/trust-score": "/qualification",
    "/royalty-recovery/cases": "/recovery", "/royalty-recovery/mlc": "/recovery",
}
OTHER_GROUP = "Also on the board"


def module_groups(modules=None):
    """The board's windows, grouped by the hub each one lives in - the same
    hubs the sidebar renders, so the board cannot drift from the nav. A
    route the sidebar folds under a front groups with that front; a route
    nobody lists lands under 'Also on the board' rather than being hidden.
    Returns [(group name, [module tuples])] in sidebar order."""
    import hubs
    modules = modules or MODULES
    order, where = [], {}
    for _hkey, name, _tagline, items in hubs.HUBS:
        order.append(name)
        for _k, href, _icon, _label, _desc in items:
            where.setdefault(href, name)
    for name, items in (hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        order.append(name)
        for _k, href, _icon, _label, _desc in items:
            where.setdefault(href, name)

    def home(route):
        if route in where:
            return where[route]
        front = FOLD_FRONTS.get(route)
        if front and front in where:
            return where[front]
        for href, name in where.items():
            if href != "/" and route.startswith(href.rstrip("/") + "/"):
                return name
        return OTHER_GROUP

    groups = {}
    for m in modules:
        groups.setdefault(home(m[0]), []).append(m)
    out = [(name, groups[name]) for name in order if name in groups]
    if OTHER_GROUP in groups:
        out.append((OTHER_GROUP, groups[OTHER_GROUP]))
    return out

# Planned-feature bullets shown on preview pages, keyed by route.
PREVIEW_FEATURES = {
    "/royalty-recovery/cases": ["Case board with status, evidence, and deadlines", "Estimated amounts and confidence scores", "Recovery packet generator", "Results and payout tracking"],
    "/royalty-recovery/mlc": ["Unmatched recording search", "Claim checklist and packet generator", "Registration correction queue", "Deadline and status tracking"],
    "/sync/clearance-packs": ["Instrumental, clean, and stem uploads", "Master + publishing clearance status", "Private supervisor listening links", "Exportable PDF one-sheet"],
    "/sync/deal-simulator": ["Fee, term, territory, and exclusivity inputs", "Buyout and MFN risk flags", "Quote recommendations", "Counteroffer drafts"],
    "/deal-room": ["Split, producer, and feature agreement generators", "Document vault with revision history", "Advance offer comparison", "Recoupment simulator"],
    "/revenue-os": ["Income by source: streaming, publishing, sync, merch, tickets", "Expense and recoupment tracking", "Per-release break-even", "Campaign ROI tied to Links and Rollout spend"],
    "/capital-score": ["Score from royalty history and catalog health", "Funding strengths and risks", "Advance scenario modeling", "Cleanup actions that raise the score"],
    "/fraud-sentinel": ["Stream spike and geo anomaly warnings", "Playlist legitimacy scores", "Do-not-pitch flags", "Exportable evidence reports"],
    "/metadata-passport": ["ISRC / UPC / ISWC validation", "Credits and split completeness", "DDEX-ready export bundle", "Missing-data collaborator requests"],
    "/ai-rights": ["Voice and likeness policy registry", "Do-not-train notice generator", "AI-use disclosure labels", "Takedown case tracking"],
    "/trust-score": ["Metadata, splits, rights, and fraud inputs", "Partner-facing badge", "Blocking-factor breakdown", "Actions that raise the score"],
    "/artist-twin": ["Approved-sources list you control", "Captions, pitches, and reports in your voice", "Do-not-say list", "Outputs saved into Rollout and EPK"],
    "/opportunities": ["Sync briefs and playlist matches", "Grants and funding windows", "Fit scores and deadlines", "One-click submission workflows"],
    "/voice-of-fan": ["Fan comment and survey ingestion", "Which lyrics, cities, and CTAs resonate", "Buyer and live-show prospect signals", "Feeds Rollout recommendations"],
    "/spend-optimizer": ["Budget allocation across content, ads, street team", "Avoid-this-spend warnings", "ROI assumptions", "Release-day reserve planning"],
    "/fan-club": ["Free and paid membership tiers", "Early-access drops", "VIP segments from Fan CRM", "Member-only links and QR codes"],
    "/partner-portal": ["Scoped label and manager access", "Shared reports and dashboards", "API keys and access logs", "Revocable grants"],
}


# --- Derived health alerts --------------------------------------------------------

def _today():
    return date.today()


def _latest_period_end(rows):
    """The last day of the newest period the statements cover.

    royalty_lag asks how long it has been since a period ENDED, so a
    period label has to become a date. A row whose period nobody can
    parse is skipped rather than guessed at, and no dated period at all
    returns None: "there is no way to tell" is an answer, and it is not
    the same answer as "everything is fine".
    """
    import calendar
    from statements_engine import period_key
    best = None
    for row in rows or ():
        year, month = period_key(row.get("period") or "")
        if year == 9999 or not 1 <= month <= 12:
            continue
        if best is None or (year, month) > best:
            best = (year, month)
    if best is None:
        return None
    year, month = best
    return date(year, month, calendar.monthrange(year, month)[1])


def _overdue_gaps(summary, rows, today):
    """The coverage gaps worth chasing, biggest first, or none of them.

    A coverage gap on its own says almost nothing. Stores report months
    apart and each runs behind by a different amount, so "missing from
    Deezer" is only news when Deezer is late for Deezer. royalty_lag
    makes that call and royalty_lag.rank does the ordering, by money
    times how far the verdict is trusted. Neither is re-implemented
    here, and rank drops every store that is only being itself.

    One finding per (track, store), because the verdict is per store: a
    track missing from four stores can be three platforms running late
    and one real delivery failure, and collapsing them hides which.

    The money on a finding is the track's estimate split across the
    stores it is missing from, in proportion to what each store paid
    the catalogue. That is the weighting statements_engine already used
    to build the estimate, not a second one invented here.

    `observed` is deliberately not passed, so every verdict comes back
    on the published table and says so in its own detail line. Nothing
    in this app records when a distributor reported a period. The only
    date on file is when the ARTIST uploaded the CSV, and measuring
    "Spotify takes 60 days" from that would be measuring the artist's
    upload habits and printing the result under Spotify's name.
    """
    import royalty_lag
    import store_identity
    period_end = _latest_period_end(rows)
    if period_end is None:
        return None, []
    store_totals = {}
    for row in rows or ():
        store = store_identity.store_of(row.get("source"))
        store_totals[store] = store_totals.get(store, 0.0) + (row.get("amount") or 0.0)
    findings = []
    for gap in summary.get("coverage_gaps") or ():
        missing = gap.get("missing_sources") or []
        paid = {store: store_totals.get(store, 0.0) for store in missing}
        total = sum(paid.values())
        for store in missing:
            # No money known for this store is left as None. royalty_lag
            # treats an unknown amount as unknown rather than as nothing.
            estimate = None
            if total > 0:
                estimate = round((gap.get("estimated_value") or 0.0) * paid[store] / total, 2)
            findings.append({
                "title": gap.get("title"), "source": store, "estimate": estimate,
                "judgement": royalty_lag.judge(store, period_end, today),
            })
    return period_end, royalty_lag.rank(findings)


_SEVERITY_ORDER = ("high", "medium", "low")


def rank_alerts(alerts):
    """Biggest real problem first, without letting money reorder the
    things that are not money.

    Severity still decides the bands. A live link sending fans to a dead
    page is not a smaller problem than an estimate that happens to carry
    a bigger number, and it has no dollar figure to be compared with.

    Inside a band the alerts that DO carry money are ordered among
    themselves by value times confidence, and they are slotted back into
    the positions money alerts already held. So an alert with no money
    figure never moves: an amount nobody has is not a zero, and ranking
    by it would quietly put a dead page below a twelve dollar estimate.

    An alert may be a 5-tuple or a 6-tuple whose last item is that
    weight; callers always get the 5-tuple the template unpacks.
    """
    rows = [tuple(a) if len(a) > 5 else tuple(a) + (None,) for a in alerts]
    out = []
    for band in _SEVERITY_ORDER:
        in_band = [a for a in rows if a[0] == band]
        spots = [i for i, a in enumerate(in_band) if a[5] is not None]
        ranked = sorted((in_band[i] for i in spots), key=lambda a: -a[5])
        for spot, alert in zip(spots, ranked):
            in_band[spot] = alert
        out.extend(in_band)
    # A severity nobody listed keeps its place at the end rather than
    # being dropped off the page by a sort it was never given a band in.
    out.extend(a for a in rows if a[0] not in _SEVERITY_ORDER)
    return [a[:5] for a in out]


def build_alerts(user_id):
    """Live-derived alerts from real module state. Every alert carries a
    destination link and enough context to become an action."""
    alerts = []
    campaigns = mls.list_campaigns(user_id)
    rollouts = ros.list_campaigns(user_id)
    rollout_ml_ids = {r.get("ml_campaign_id") for r in rollouts}
    for c in campaigns:
        if c.get("archived_at"):
            continue
        dests = mls.get_destinations(c["id"])
        settings = c.get("settings") or {}
        if c["status"] == "live" and not dests:
            alerts.append(("high", "“%s” is live with no destinations" % c["title"],
                           "Fans hit a dead page. Add streaming links now.",
                           "/links/%s/edit" % c["id"], "smart_link"))
        if c["status"] == "live" and not settings.get("email_capture"):
            alerts.append(("medium", "“%s” isn't capturing fans" % c["title"],
                           "Traffic without capture is rented attention. Enable email capture.",
                           "/links/%s/edit" % c["id"], "fan_growth"))
        if c.get("release_date"):
            try:
                days = (datetime.strptime(c["release_date"], "%Y-%m-%d").date() - _today()).days
            except ValueError:
                days = None
            if days is not None and 0 <= days <= 7 and c["id"] not in rollout_ml_ids:
                alerts.append(("high", "“%s” drops in %d day%s with no rollout" % (
                                   c["title"], days, "s" if days != 1 else ""),
                               "Generate a rollout so release week isn't silent.",
                               "/rollout-studio/new", "rollout"))
        if settings.get("email_capture") and not settings.get("consent_text"):
            alerts.append(("medium", "“%s” captures emails without consent copy" % c["title"],
                           "Add consent text — it's logged with every signup.",
                           "/links/%s/edit" % c["id"], "rights"))
    # Real statement findings: money on the table beats everything else.
    import db as store
    from statements_engine import build_royalty_summary
    rows = store.get_statement_rows(user_id)
    summary = build_royalty_summary(rows) if rows else None
    # The catalog valuation is computed here every time the Command
    # Center loads and was stored nowhere, so the one number an artist
    # most wants a trend on had no history at all. Guarded - a history
    # write must never break the page it was computed for.
    if summary and (summary.get("valuation") or {}).get("mid"):
        try:
            store.record_score(user_id, "valuation",
                               summary["valuation"]["mid"],
                               {"low": summary["valuation"]["low"],
                                "high": summary["valuation"]["high"],
                                "annualized": summary.get("annualized")})
        except Exception:
            pass
    if summary and summary["unmatched_revenue"]:
        # Weighted at full confidence: this is not an estimate, it is a
        # figure added up off the artist's own statement rows.
        alerts.insert(0, ("high", "$%.2f unmatched revenue in your statements" % summary["unmatched_revenue"],
                          "Rows with no track title, so money paid but not attributed. Review and claim it.",
                          "/recovery", "royalty_recovery", summary["unmatched_revenue"]))
    if summary and summary["coverage_gaps"]:
        # Money first, then the count: "3 coverage gaps" alone told nobody
        # whether to care (owner notes, 2026-09-19). And a gap is only a
        # problem when the store is late FOR ITSELF, which royalty_lag
        # decides: a store still inside its usual reporting wait is a
        # store being a store, and calling that a finding sends artists
        # to their distributor over nothing.
        gaps = summary["coverage_gaps"]
        n = len(gaps)
        est = summary.get("gap_estimate_total") or 0
        plural = "s" if n != 1 else ""
        money = "{:,.2f}".format(est)
        period_end, late = _overdue_gaps(summary, rows, _today())
        if late:
            # At stake is the plain money; the weight that orders this
            # against the other alerts is that money times how far the
            # verdict behind it is trusted, which royalty_lag.rank set.
            stake = round(sum(f["estimate"] or 0 for f in late), 2)
            weight = round(sum(f["priority"]["weight"] for f in late), 2) or None
            top = late[0]
            verdict = top["judgement"]
            # The usual figure in the headline is the published one unless
            # this account's own history produced it, and the reader is
            # told which, because a table is not evidence about them.
            basis = ("That usual figure is measured from your own statement history."
                     if verdict.get("basis") == "measured" else
                     "That usual figure is the published one for that store, not your own.")
            if stake <= 0:
                title = ("A store is overdue on %d coverage gap%s, with no estimate of "
                         "what is at stake" % (n, plural))
            elif round(stake, 2) == round(est, 2):
                # One figure, not the same figure twice.
                title = ("Est. $%s at stake, and a store is overdue on %d coverage gap%s"
                         % ("{:,.2f}".format(stake), n, plural))
            else:
                title = ("Est. $%s at stake where a store is overdue, of $%s across %d "
                         "coverage gap%s" % ("{:,.2f}".format(stake), money, n, plural))
            rec = ("%s has reported nothing for the period ending %s: %s. %s Biggest: "
                   "“%s”. Estimates come from each track's share of what those stores "
                   "paid, not a guarantee."
                   % (top["source"], period_end.isoformat(), verdict.get("headline"),
                      basis, top["title"]))
            alerts.append(("high", title, rec, "/recovery", "royalty_recovery", weight))
        elif period_end is None:
            title = ("%d coverage gap%s across your royalty sources, and no dated period "
                     "to judge them by" % (n, plural))
            rec = ("Tracks earning on some sources but missing from others. Your "
                   "statements carry no period anyone can read, so there is no way to "
                   "say whether a store is late or simply has not reported yet.")
            alerts.append(("medium", title, rec, "/recovery", "royalty_recovery", None))
        else:
            # Gaps, but every store is still inside its own usual wait.
            # Worth knowing, not worth chasing, and the difference is the
            # whole point of saying it this way round.
            if est > 0:
                title = ("Est. $%s in %d coverage gap%s, none of the stores overdue yet"
                         % (money, n, plural))
            else:
                title = ("%d coverage gap%s, none of the stores overdue yet, and no "
                         "estimate of what is at stake" % (n, plural))
            rec = ("Tracks earning on some sources but missing from others. Every store "
                   "they are missing from is still inside the wait it usually takes to "
                   "report, so this is waiting rather than a problem. Estimates come "
                   "from each track's share of what those stores paid, not a guarantee.")
            alerts.append(("medium", title, rec, "/recovery", "royalty_recovery", None))
    # Catalog metadata gaps
    tracks = mls_catalog_tracks(user_id)
    missing_isrc = [t for t in tracks if not (t.get("meta") or {}).get("isrc")]
    if missing_isrc:
        alerts.append(("medium", "%d catalog track%s missing an ISRC" % (
                           len(missing_isrc), "s" if len(missing_isrc) != 1 else ""),
                       "Missing identifiers leak royalties. Re-check metadata.",
                       "/catalog", "metadata"))
    return rank_alerts(alerts)


def mls_catalog_tracks(user_id):
    import db as store
    return store.get_catalog_tracks(user_id)


# --- Unified summary ---------------------------------------------------------------

def setup_state(user_id):
    """The two answers the start-here checklist gives about links and
    tracks, asked the same way it asks them (app.py _firstrun_panel): a
    smart link lives in one of two tables depending on which door made
    it, and an account's songs are known from its passports OR from the
    statements it uploaded. The score tiles decide "has data" from this,
    so a tile never asks for a first campaign or a first track the
    checklist has already ticked (owner notes, 2026-09-19)."""
    import db as store
    legacy_links = store.get_db_links(user_id)
    passports = store.list_os_tracks(user_id)
    statement_songs = store.statement_titles(user_id, 500)
    return {
        "link": bool(legacy_links) or bool(mls.list_campaigns(user_id)),
        "track": bool(passports) or bool(statement_songs),
        "legacy_links": len(legacy_links),
        "legacy_opens": sum(int(l.get("clicks") or 0) for l in legacy_links),
        "passport_count": len(passports),
        "statement_songs": len(statement_songs),
    }


def get_summary(user_id):
    campaigns = [c for c in mls.list_campaigns(user_id) if not c.get("archived_at")]
    scores = []
    upcoming = []
    for c in campaigns:
        dests = mls.get_destinations(c["id"])
        s = links_engine.calculate_street_banker_score(c, dests)
        scores.append(s["total"])
        if c.get("release_date"):
            try:
                days = (datetime.strptime(c["release_date"], "%Y-%m-%d").date() - _today()).days
            except ValueError:
                continue
            if days >= 0:
                upcoming.append({"title": c["title"], "days": days, "id": c["id"],
                                 "score": s["total"], "warnings": s["warnings"]})
    upcoming.sort(key=lambda u: u["days"])
    events = mls.account_event_counts(user_id)
    fans = mls.list_fans(user_id)
    rollouts = ros.list_campaigns(user_id)
    tracks = mls_catalog_tracks(user_id)
    with_isrc = sum(1 for t in tracks if (t.get("meta") or {}).get("isrc"))
    setup = setup_state(user_id)
    import qualification
    return {
        "qualification": qualification.calculate(user_id)["total"],
        "links_score": round(sum(scores) / len(scores)) if scores else 0,
        "campaign_count": len(campaigns),
        # The checklist's answers, for the tiles' "has data" decisions.
        "has_link": setup["link"],
        "has_track": setup["track"],
        "setup": setup,
        "visits": events.get("page_view", 0),
        # Everyone who opened a link: campaign page views plus opens of the
        # older short links, which count in their own table.
        "link_opens": events.get("page_view", 0) + setup["legacy_opens"],
        "clicks": events.get("service_click", 0),
        "fan_count": len(fans),
        "hot_fans": sum(1 for f in fans if f["intent_level"] in ("Hot", "Superfan")),
        "rollout_count": len(rollouts),
        "catalog_count": len(tracks),
        "catalog_health": round(100 * with_isrc / len(tracks)) if tracks else 0,
        "upcoming": upcoming[:3],
        "next_release": upcoming[0] if upcoming else None,
    }
