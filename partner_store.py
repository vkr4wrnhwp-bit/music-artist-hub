"""Partner OS - storage.

WHAT A PARTNER IS
-----------------
A reseller. They put their own name, logo and domain on this software and
sell it to their own artists, who never see Street Banker at all. The
partner is the tenant; the artists are accounts the partner owns.

TENANCY BOUNDARY (read this before adding a table)
--------------------------------------------------
The rule, inherited from Signal and worth restating: if a row would tell
one partner what another partner is DOING, it is tenant-owned and carries
`partner_id`, and every query in this module filters on it.

`users.partner_id` is the spine. An account belongs to at most one partner
(NULL = a direct Street Banker account, which is what every existing row
is). Everything an artist owns is already scoped by `user_id`, so scoping
the USER to a partner scopes the artist's whole workspace without touching
the ~75 tables underneath. That is the point of doing it here rather than
adding a column to everything.

WHY MEMBERS ARE KEYED ON user_id, NOT EMAIL
-------------------------------------------
Signal's members are keyed on a lowercased email string with a `user_id`
column that nothing reads. The consequence is written into that module: if
somebody changes their email in the main app, their seat orphans. Here the
account id is the key when it is known, and email is only the invite
address for a seat whose person has not signed up yet. `claim_seats` binds
them at first login.

FAIL CLOSED
-----------
`can()` returns False for an unknown permission, an unknown role, a
missing member and a suspended partner. A partner that is not `active`
grants nothing at all, so switching one off is one column write.
"""
import sqlite3
import uuid

import plans
from db import get_db, _now

# --- vocabulary -------------------------------------------------------------

ROLES = ["owner", "admin", "manager", "support", "viewer"]
ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Admin",
    "manager": "Manager",
    "support": "Support",
    "viewer": "Viewer",
}

# Permission -> the roles that hold it. The decorator and the templates read
# this one table, so a template can never offer a button the server refuses.
PERMS = {
    "view":            {"owner", "admin", "manager", "support", "viewer"},
    "roster_view":     {"owner", "admin", "manager", "support", "viewer"},
    "roster_invite":   {"owner", "admin", "manager"},
    "roster_remove":   {"owner", "admin"},
    # Acting inside an artist's own desk. Deliberately narrow: it is the
    # partner reading and writing somebody else's workspace, and every use
    # of it is written to partner_audit.
    "act_as_artist":   {"owner", "admin", "support"},
    "branding_edit":   {"owner", "admin"},
    "billing_view":    {"owner", "admin"},
    # Setting an artist's tier. A reseller's artist cannot buy their own
    # plan, so somebody at the partner has to hold this, and it is the
    # partner who carries the cost of what it unlocks.
    "entitlement_grant": {"owner", "admin"},
    "manage_members":  {"owner"},
}

STATUSES = ("active", "suspended")

# A seat_limit of 0 means "no cap". It is the default so that adding seats to
# an existing deployment changes nothing until somebody sets a number.
SEAT_UNLIMITED = 0


def _uid():
    return uuid.uuid4().hex


# Resolution runs on every request, and on an instance with no resellers
# it would be two queries per page for an answer that is always None. The
# flag makes that path free; any write that could make it true clears it.
_any_partners = None


def any_partners():
    global _any_partners
    if _any_partners is None:
        with get_db() as db:
            _any_partners = db.execute(
                "SELECT 1 FROM partners LIMIT 1").fetchone() is not None
    return _any_partners


def _forget_partner_count():
    global _any_partners
    _any_partners = None


def _row(r):
    return dict(r) if r is not None else None


def normalize_slug(text):
    """Lowercase, hyphenated, and safe to put in front of a domain."""
    out = []
    for ch in (text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_." and out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:60]


# --- schema ------------------------------------------------------------------

def init_partners():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS partners (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                domain TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS partner_members (
                id TEXT PRIMARY KEY,
                partner_id TEXT NOT NULL,
                user_id TEXT,
                email TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'viewer',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_seen TEXT,
                UNIQUE(partner_id, email)
            );
            /* Every act-on-behalf, every seat change, every branding edit.
               A partner reading an artist's workspace is a thing the artist
               is entitled to see a record of. */
            CREATE TABLE IF NOT EXISTS partner_audit (
                id TEXT PRIMARY KEY,
                partner_id TEXT NOT NULL,
                actor_user_id TEXT,
                actor_email TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                subject_user_id TEXT,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pmembers_partner
                ON partner_members(partner_id, status);
            CREATE INDEX IF NOT EXISTS idx_pmembers_user
                ON partner_members(user_id);
            CREATE INDEX IF NOT EXISTS idx_paudit_partner
                ON partner_audit(partner_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_paudit_subject
                ON partner_audit(subject_user_id, created_at);
        """)
        # How many artists this partner may seat. 0 is unlimited, and every
        # partner that existed before seats did keeps that - a cap arriving
        # in a migration must not retroactively lock somebody out of their
        # own roster.
        try:
            db.execute("ALTER TABLE partners ADD COLUMN seat_limit INTEGER "
                       "NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        # The spine. NULL for every account that exists today, which is
        # exactly right: they are direct Street Banker accounts.
        try:
            db.execute("ALTER TABLE users ADD COLUMN partner_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            db.execute("CREATE INDEX IF NOT EXISTS idx_users_partner ON users(partner_id)")
        except sqlite3.OperationalError:
            pass


# --- partners ----------------------------------------------------------------

def create_partner(name, slug=None, domain=None):
    """Returns the new id, or None if the slug or domain is taken."""
    slug = normalize_slug(slug or name) or _uid()[:8]
    domain = (domain or "").strip().lower() or None
    with get_db() as db:
        if db.execute("SELECT 1 FROM partners WHERE slug = ?", (slug,)).fetchone():
            return None
        if domain and db.execute("SELECT 1 FROM partners WHERE domain = ?", (domain,)).fetchone():
            return None
        pid = _uid()
        db.execute(
            "INSERT INTO partners (id, name, slug, domain, status, created_at) "
            "VALUES (?,?,?,?,'active',?)",
            (pid, (name or "Partner").strip()[:120], slug, domain, _now()))
    _forget_partner_count()
    return pid


def get_partner(partner_id):
    with get_db() as db:
        return _row(db.execute("SELECT * FROM partners WHERE id = ?", (partner_id,)).fetchone())


def partner_by_slug(slug):
    with get_db() as db:
        return _row(db.execute("SELECT * FROM partners WHERE slug = ?",
                               (normalize_slug(slug),)).fetchone())


def partner_by_domain(domain):
    with get_db() as db:
        return _row(db.execute("SELECT * FROM partners WHERE domain = ?",
                               ((domain or "").strip().lower(),)).fetchone())


def list_partners():
    """Street Banker's own view of its resellers. Not tenant-scoped by
    design: only the vendor calls this."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM partners ORDER BY created_at").fetchall()]


def set_partner_status(partner_id, status):
    if status not in STATUSES:
        return False
    with get_db() as db:
        cur = db.execute("UPDATE partners SET status = ? WHERE id = ?", (status, partner_id))
    return cur.rowcount > 0


# --- members -----------------------------------------------------------------

def add_member(partner_id, email, name="", role="viewer", user_id=None):
    """Seat somebody at a partner. Idempotent per (partner, email)."""
    if role not in ROLES:
        role = "viewer"
    email = (email or "").strip().lower()
    if not email:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM partner_members WHERE partner_id = ? AND email = ?",
            (partner_id, email)).fetchone()
        if row:
            db.execute(
                "UPDATE partner_members SET role = ?, name = ?, status = 'active', "
                "user_id = COALESCE(?, user_id) WHERE id = ?",
                (role, (name or "")[:120], user_id, row["id"]))
            return row["id"]
        mid = _uid()
        db.execute(
            "INSERT INTO partner_members (id, partner_id, user_id, email, name, role, "
            "status, created_at) VALUES (?,?,?,?,?,?,'active',?)",
            (mid, partner_id, user_id, email, (name or "")[:120], role, _now()))
    return mid


def get_member(partner_id, user_id=None, email=None):
    """The account id is the key when we have it; email is the fallback for
    a seat whose person has not signed up yet."""
    with get_db() as db:
        if user_id:
            r = db.execute(
                "SELECT * FROM partner_members WHERE partner_id = ? AND user_id = ? "
                "AND status = 'active'", (partner_id, user_id)).fetchone()
            if r:
                return dict(r)
        if email:
            r = db.execute(
                "SELECT * FROM partner_members WHERE partner_id = ? AND email = ? "
                "AND status = 'active'", (partner_id, (email or "").strip().lower())).fetchone()
            if r:
                return dict(r)
    return None


def member_for_user(user_id):
    """Which partner this account holds a seat at, if any. Joined so a seat
    at a suspended partner reads as no seat."""
    if not user_id:
        return None
    with get_db() as db:
        return _row(db.execute(
            "SELECT m.*, p.name AS partner_name, p.slug AS partner_slug, p.status AS partner_status "
            "FROM partner_members m JOIN partners p ON p.id = m.partner_id "
            "WHERE m.user_id = ? AND m.status = 'active' AND p.status = 'active' "
            "ORDER BY m.created_at LIMIT 1", (user_id,)).fetchone())


def list_members(partner_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM partner_members WHERE partner_id = ? AND status = 'active' "
            "ORDER BY created_at", (partner_id,)).fetchall()]


def remove_member(partner_id, member_id):
    """Soft delete, like Signal: the row stays for the audit trail, the seat
    stops working at the next request."""
    with get_db() as db:
        cur = db.execute(
            "UPDATE partner_members SET status = 'removed' WHERE id = ? AND partner_id = ?",
            (member_id, partner_id))
    return cur.rowcount > 0


def claim_seats(user_id, email):
    """Bind seats invited by email to a real account, at first sight.

    This is the fix for the orphaning Signal documents in its own module:
    a seat created before the person signed up has user_id NULL, and would
    stay unreachable if they later changed their email."""
    email = (email or "").strip().lower()
    if not user_id or not email:
        return 0
    with get_db() as db:
        cur = db.execute(
            "UPDATE partner_members SET user_id = ? WHERE email = ? AND user_id IS NULL",
            (user_id, email))
    return cur.rowcount


def touch_member(member_id):
    with get_db() as db:
        db.execute("UPDATE partner_members SET last_seen = ? WHERE id = ?", (_now(), member_id))


def can(member, permission):
    """Fail closed: unknown permission, unknown role or no member -> False."""
    return bool(member) and member.get("role") in PERMS.get(permission, ())


# --- the roster: accounts a partner owns -------------------------------------

def seat_limit(partner_id):
    """How many artists this partner may seat. 0 means no cap."""
    with get_db() as db:
        row = db.execute("SELECT seat_limit FROM partners WHERE id = ?",
                         (partner_id,)).fetchone()
    if row is None:
        return SEAT_UNLIMITED
    return int(row["seat_limit"] or SEAT_UNLIMITED)


def set_seat_limit(partner_id, limit):
    """Set the cap. A limit below the seats already taken is allowed and is
    not retroactive: nobody is evicted, but no more can be added until the
    roster comes back under the number. Evicting an artist to satisfy a
    billing change is not a decision this function gets to make."""
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        return False
    with get_db() as db:
        cur = db.execute("UPDATE partners SET seat_limit = ? WHERE id = ?",
                         (limit, partner_id))
    return cur.rowcount > 0


def seats_used(partner_id):
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) AS n FROM users WHERE partner_id = ?",
                         (partner_id,)).fetchone()
    return row["n"] if row else 0


def seats_left(partner_id):
    """Seats still available, or None when the partner is uncapped. None
    rather than a big number, so a caller has to decide what "no cap" means
    on screen instead of printing a fake ceiling."""
    limit = seat_limit(partner_id)
    if limit == SEAT_UNLIMITED:
        return None
    return max(0, limit - seats_used(partner_id))


def attach_user(partner_id, user_id):
    """Put an account under a partner. Refuses to move an account that
    already belongs to a different one - that is a transfer, and a transfer
    should be a deliberate two-step, not a side effect of an invite.

    Also refuses once the seat cap is full. The count and the write happen
    inside one connection so two invites racing cannot both read the last
    free seat and both take it.
    """
    with get_db() as db:
        row = db.execute("SELECT partner_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return False
        current = row["partner_id"] if "partner_id" in row.keys() else None
        if current and current != partner_id:
            return False
        if current != partner_id:
            # Only a NEW seat consumes one; re-attaching an artist the partner
            # already owns must stay idempotent even at a full cap.
            prow = db.execute("SELECT seat_limit FROM partners WHERE id = ?",
                              (partner_id,)).fetchone()
            limit = int((prow["seat_limit"] if prow else 0) or SEAT_UNLIMITED)
            if limit != SEAT_UNLIMITED:
                taken = db.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE partner_id = ?",
                    (partner_id,)).fetchone()["n"]
                if taken >= limit:
                    return False
        db.execute("UPDATE users SET partner_id = ? WHERE id = ?", (partner_id, user_id))
    return True


def grant_plan(partner_id, user_id, plan):
    """Set an artist's tier on behalf of the partner that owns them.

    Ownership is asked of the database here as well as at the route, because
    this is the function that writes, and a store function that trusts its
    caller to have checked is one refactor away from not being checked at
    all. Returns the plan actually written, or None if refused.
    """
    if not owns_user(partner_id, user_id):
        return None
    if plan not in plans.TIER_RANK:
        return None
    with get_db() as db:
        db.execute("UPDATE users SET plan = ? WHERE id = ? AND partner_id = ?",
                   (plan, user_id, partner_id))
    return plan


def detach_user(partner_id, user_id):
    with get_db() as db:
        cur = db.execute(
            "UPDATE users SET partner_id = NULL WHERE id = ? AND partner_id = ?",
            (user_id, partner_id))
    return cur.rowcount > 0


def roster(partner_id):
    """Every account this partner owns. Scoped, and the password hash never
    leaves the database."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT id, email, name, plan, created, last_seen FROM users "
            "WHERE partner_id = ? ORDER BY created DESC", (partner_id,)).fetchall()]


def roster_detail(partner_id):
    """The roster, plus the few facts a partner actually manages against.

    A list of names and emails answers "who is on this" and nothing else. What
    a reseller needs before opening somebody's workspace is whether the
    account has been used, whether there is anything in it yet, and what plan
    it is on - so the roster is where you decide who to help, not just who
    exists.

    Counts are read per artist rather than joined, because the tables live
    across modules and a join here would tie this file to their schemas. The
    roster is tens of rows, not thousands.
    """
    rows = roster(partner_id)
    for row in rows:
        row["songs"] = _count("songs", row["id"])
        row["links"] = _count("ml_campaigns", row["id"])
        row["never_signed_in"] = not (row.get("last_seen") or "").strip()
    return rows


def _count(table, user_id):
    """Rows this account owns in one table, or None when the table is absent.

    None rather than 0: a module that has not initialised its schema on this
    deployment is not the same as an artist with nothing, and showing a
    confident zero for it would be a small lie on a management screen.
    """
    try:
        with get_db() as db:
            row = db.execute(
                "SELECT COUNT(*) AS n FROM %s WHERE user_id = ?" % table,
                (user_id,)).fetchone()
        return row["n"] if row else 0
    except sqlite3.OperationalError:
        return None


def owns_user(partner_id, user_id):
    """The gate every act-on-behalf must pass before it does anything."""
    if not partner_id or not user_id:
        return False
    with get_db() as db:
        return db.execute(
            "SELECT 1 FROM users WHERE id = ? AND partner_id = ?",
            (user_id, partner_id)).fetchone() is not None


# --- audit -------------------------------------------------------------------

def audit(partner_id, action, actor=None, subject_user_id=None, detail=""):
    with get_db() as db:
        db.execute(
            "INSERT INTO partner_audit (id, partner_id, actor_user_id, actor_email, "
            "action, subject_user_id, detail, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (_uid(), partner_id,
             (actor or {}).get("id"), ((actor or {}).get("email") or "").lower(),
             action[:60], subject_user_id, (detail or "")[:500], _now()))


def audit_trail(partner_id, subject_user_id=None, limit=200):
    q = "SELECT * FROM partner_audit WHERE partner_id = ?"
    args = [partner_id]
    if subject_user_id:
        q += " AND subject_user_id = ?"
        args.append(subject_user_id)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with get_db() as db:
        return [dict(r) for r in db.execute(q, args).fetchall()]
