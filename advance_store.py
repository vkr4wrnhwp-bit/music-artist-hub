"""Show advancement - attaching a passport version to a show, and agreeing it.

Phase 3 of docs/STAGE_CONTROL_BRIEF.md. The audit (STAGE_CONTROL_PHASE1_AUDIT)
found that TOUR already owns shows, venues, crew, the advance and share links,
so this module deliberately adds NO second show system. It adds exactly the
three things TOUR does not have:

  1. the link from a show to ONE FROZEN passport version,
  2. the questions a venue asks about it,
  3. the conflicts between what the passport needs and what the room has.

THE POINT OF THE WHOLE MODULE is the word "frozen". `show_passports.version_id`
points at an immutable snapshot, so the input list a venue agreed to in January
is still the input list in March, however much the draft moved in between. A
row that pointed at `passport_id` alone would quietly rewrite history, which is
the failure the brief names twice.

`SHOW_STATUSES` in tour_store (hold/confirmed/advanced/played/settled) is NOT
touched. Advance state lives here, on the attachment, because it describes the
conversation about the passport rather than the state of the booking.
"""
import uuid

import passport_store as ps
from db import get_db, _now

# The advance conversation, in order. Deliberately does NOT include the brief's
# "Show Active / Completed / Archived" - those describe the BOOKING, and
# tour_store.SHOW_STATUSES already carries them. Two vocabularies for one fact
# is how a product starts disagreeing with itself.
ADVANCE_STATES = ("draft", "invited", "reviewing", "questions_open",
                  "changes_requested", "approved", "locked")

# Which states still allow the attached version to be swapped. Once a show is
# approved or locked, moving it to a different version is a re-advance, not an
# edit, and it has to be deliberate.
OPEN_STATES = ("draft", "invited", "reviewing", "questions_open",
               "changes_requested")

CONFLICT_KINDS = ("inputs", "outputs", "power", "backline", "access",
                  "playback", "other")


def _uid():
    return uuid.uuid4().hex


def _row(r):
    return dict(r) if r else None


def init_advance():
    with get_db() as db:
        db.executescript("""
            /* One passport version per show. PRIMARY KEY on show_id enforces
               that: a show advanced against two different technical documents
               is not a state anybody could act on. */
            CREATE TABLE IF NOT EXISTS show_passports (
                show_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                passport_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'draft',
                attached_by TEXT NOT NULL DEFAULT '',
                attached_at TEXT NOT NULL,
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_showpass_user
                ON show_passports(user_id, state);

            CREATE TABLE IF NOT EXISTS show_questions (
                id TEXT PRIMARY KEY,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                asked_by TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL DEFAULT '',
                answered_by TEXT NOT NULL DEFAULT '',
                answered_at TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_showq
                ON show_questions(show_id, created);

            CREATE TABLE IF NOT EXISTS show_conflicts (
                id TEXT PRIMARY KEY,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'other',
                detail TEXT NOT NULL,
                raised_by TEXT NOT NULL DEFAULT '',
                resolution TEXT NOT NULL DEFAULT '',
                resolved_at TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_showc
                ON show_conflicts(show_id, created);
        """)


# --- attaching ---------------------------------------------------------------

def attach(show_id, user_id, passport_id, version_id=None, attached_by=""):
    """Advance a show against a passport version.

    Defaults to the version currently in force, because that is what somebody
    means by "advance this show" - but the id is stored, not the pointer, so
    publishing a newer version afterwards leaves this show where it was.

    Refuses a passport with nothing published: there is no frozen document to
    advance against, and attaching a draft would be the exact silent-rewrite
    this module exists to prevent.
    """
    head = ps.get_passport(passport_id, user_id)
    if head is None:
        return None
    if version_id is None:
        version_id = head.get("current_version_id")
    if not version_id:
        return None
    version = ps.get_version(version_id, user_id)
    if version is None or version["passport_id"] != passport_id:
        return None

    existing = get_attachment(show_id, user_id)
    if existing and existing["state"] not in OPEN_STATES:
        # Approved or locked. Swapping the document under an agreement is a
        # re-advance; the caller has to reopen it first and be seen to.
        return None

    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO show_passports (show_id, user_id, passport_id, version_id, "
            "state, attached_by, attached_at) VALUES (?,?,?,?,'draft',?,?) "
            "ON CONFLICT(show_id) DO UPDATE SET passport_id = excluded.passport_id, "
            "version_id = excluded.version_id, attached_by = excluded.attached_by, "
            "attached_at = excluded.attached_at",
            (show_id, user_id, passport_id, version_id, (attached_by or "").strip(), now))
    return version_id


def get_attachment(show_id, user_id=None):
    sql = "SELECT * FROM show_passports WHERE show_id = ?"
    args = [show_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    with get_db() as db:
        return _row(db.execute(sql, args).fetchone())


def detach(show_id, user_id):
    """Only while the advance is still open. Detaching an approved show would
    delete the record of what was agreed."""
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM show_passports WHERE show_id = ? AND user_id = ? "
            "AND state IN (%s)" % ",".join("?" * len(OPEN_STATES)),
            [show_id, user_id] + list(OPEN_STATES))
    return cur.rowcount > 0


def set_state(show_id, user_id, state, actor=""):
    if state not in ADVANCE_STATES:
        return False
    now = _now()
    sets = ["state = ?"]
    args = [state]
    if state == "approved":
        sets += ["approved_by = ?", "approved_at = ?"]
        args += [(actor or "").strip(), now]
    args += [show_id, user_id]
    with get_db() as db:
        cur = db.execute("UPDATE show_passports SET %s WHERE show_id = ? AND user_id = ?"
                         % ", ".join(sets), args)
    return cur.rowcount > 0


def snapshot_for(show_id, user_id=None):
    """The technical document this show is actually working from.

    Read from the frozen version, never from the passport's working tables.
    Every consumer downstream - the engineer desk, the exports, the monitor
    mixes a performer may request against - comes through here so none of them
    can accidentally read the draft.
    """
    link = get_attachment(show_id, user_id)
    if link is None:
        return None
    version = ps.get_version(link["version_id"], user_id)
    return version.get("snapshot") if version else None


def newer_version_available(show_id, user_id=None):
    """Whether the passport has moved on since this show was advanced.

    Returns None when there is nothing to compare. This is deliberately only a
    NOTICE: it never re-attaches by itself, because that is the silent rewrite
    the whole design refuses.
    """
    link = get_attachment(show_id, user_id)
    if link is None:
        return None
    head = ps.get_passport(link["passport_id"], user_id)
    if not head or not head.get("current_version_id"):
        return None
    if head["current_version_id"] == link["version_id"]:
        return None
    current = ps.get_version(head["current_version_id"], user_id)
    attached = ps.get_version(link["version_id"], user_id)
    if not current or not attached:
        return None
    return {"attached": attached["number"], "available": current["number"],
            "version_id": current["id"],
            "diff": ps.compare(attached.get("snapshot"), current.get("snapshot"))}


# --- questions ---------------------------------------------------------------

def ask(show_id, user_id, body, section="", asked_by=""):
    body = (body or "").strip()
    if not body:
        return None
    qid = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO show_questions (id, show_id, user_id, section, body, "
            "asked_by, created) VALUES (?,?,?,?,?,?,?)",
            (qid, show_id, user_id, (section or "").strip(), body,
             (asked_by or "").strip(), _now()))
    # A question arriving is what moves an advance out of "reviewing", so the
    # state follows the fact rather than waiting for somebody to set it.
    link = get_attachment(show_id, user_id)
    if link and link["state"] in ("draft", "invited", "reviewing"):
        set_state(show_id, user_id, "questions_open")
    return qid


def answer(show_id, user_id, question_id, text, answered_by=""):
    text = (text or "").strip()
    if not text:
        return False
    with get_db() as db:
        cur = db.execute(
            "UPDATE show_questions SET answer = ?, answered_by = ?, answered_at = ? "
            "WHERE id = ? AND show_id = ? AND user_id = ?",
            (text, (answered_by or "").strip(), _now(), question_id, show_id, user_id))
    return cur.rowcount > 0


def questions(show_id, user_id=None, open_only=False):
    sql = "SELECT * FROM show_questions WHERE show_id = ?"
    args = [show_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    if open_only:
        sql += " AND answer = ''"
    sql += " ORDER BY created"
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


# --- conflicts ---------------------------------------------------------------

def raise_conflict(show_id, user_id, detail, kind="other", raised_by=""):
    detail = (detail or "").strip()
    if not detail:
        return None
    cid = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO show_conflicts (id, show_id, user_id, kind, detail, "
            "raised_by, created) VALUES (?,?,?,?,?,?,?)",
            (cid, show_id, user_id, kind if kind in CONFLICT_KINDS else "other",
             detail, (raised_by or "").strip(), _now()))
    return cid


def resolve_conflict(show_id, user_id, conflict_id, resolution):
    resolution = (resolution or "").strip()
    if not resolution:
        return False
    with get_db() as db:
        cur = db.execute(
            "UPDATE show_conflicts SET resolution = ?, resolved_at = ? "
            "WHERE id = ? AND show_id = ? AND user_id = ?",
            (resolution, _now(), conflict_id, show_id, user_id))
    return cur.rowcount > 0


def conflicts(show_id, user_id=None, open_only=False):
    sql = "SELECT * FROM show_conflicts WHERE show_id = ?"
    args = [show_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    if open_only:
        sql += " AND resolution = ''"
    sql += " ORDER BY created"
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


# --- readiness ---------------------------------------------------------------

def blockers(show_id, user_id=None):
    """What stands between this show and an approved advance.

    Facts, in the order somebody would fix them, and never a percentage - the
    same rule the passport's own gaps follow.
    """
    link = get_attachment(show_id, user_id)
    if link is None:
        return ["No passport attached. The venue has nothing to work from."]
    out = []
    snap = snapshot_for(show_id, user_id) or {}
    if not snap.get("inputs"):
        out.append("The attached version has no input list.")
    if not snap.get("outputs"):
        out.append("The attached version has no monitor mixes.")
    open_q = questions(show_id, user_id, open_only=True)
    if open_q:
        out.append("%d question%s unanswered." % (len(open_q), "" if len(open_q) == 1 else "s"))
    open_c = conflicts(show_id, user_id, open_only=True)
    if open_c:
        out.append("%d conflict%s unresolved." % (len(open_c), "" if len(open_c) == 1 else "s"))
    return out


def can_approve(show_id, user_id=None):
    """Approval is blocked while anything is open. A show approved with three
    unanswered questions on it is an approval nobody should trust."""
    return not blockers(show_id, user_id)


def approve(show_id, user_id, actor=""):
    if not can_approve(show_id, user_id):
        return False
    return set_state(show_id, user_id, "approved", actor=actor)
