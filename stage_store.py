"""Stage Control - requests, and the event cursor that carries them.

Phase 4 of docs/STAGE_CONTROL_BRIEF.md: Request Mode. A performer asks for
more of themselves in their ears; an engineer decides. Nothing here touches a
console - that is phases 5 and 6, and this layer has to be complete and useful
without them, because on most nights it will be all there is.

THE STATE MACHINE IS THE SAFETY FEATURE. The brief's hardest rule is "never
present a requested change as applied until confirmation is received", and the
way that is guaranteed is that `applied` is not reachable from `pending`.
Every transition goes through `TRANSITIONS`, which is a whitelist: a state
this table does not allow cannot be written, however a caller asks. A rule
enforced by a dict is a rule; a rule enforced by remembering to check is a
comment.

THE CURSOR IS THE REALTIME. The audit found no websocket infrastructure and a
deployment that cannot host one - `--workers 2 --threads 4` is eight request
slots, so SSE would pin a thread per performer and take the whole site down at
nine of them. So `stage_events.seq` is an AUTOINCREMENT integer and clients
poll "everything after N". That is a worse transport and an equally good event
model: ids are server-generated, ordering is total, replays are idempotent,
and a client that misses a poll catches up rather than losing history.
"""
import json
import sqlite3
import uuid

from db import get_db, _now

# --- vocabulary --------------------------------------------------------------

# What a performer can ask for. Split into two groups because they are two
# different acts: an ADJUSTMENT names a source and a direction and could one
# day become a console command; a REPORT is a person telling you something is
# wrong and never becomes one.
ADJUSTMENTS = ("more", "less", "mute", "unmute")
REPORTS = ("distortion", "no_signal", "too_loud", "feedback", "equipment",
           "talkback", "note")
REQUEST_KINDS = ADJUSTMENTS + REPORTS

KIND_LABELS = {
    "more": "More", "less": "Less", "mute": "Mute", "unmute": "Unmute",
    "distortion": "Distortion", "no_signal": "No signal",
    "too_loud": "Too loud", "feedback": "Feedback",
    "equipment": "Equipment problem", "talkback": "Talkback",
    "note": "Note",
}

# Bounded steps in dB, never a slider. The brief is explicit - "no accidental
# horizontal sliders that can jump levels", "prefer bounded step controls" -
# and this is where that is actually enforced: a request carries one of these
# three numbers or it is refused.
STEPS_DB = (1, 2, 3)
STEP_LABELS = {1: "a touch", 2: "a bit", 3: "a lot"}

# Reports that should reach an engineer before an adjustment does. Feedback and
# a dead channel are happening to the audience too.
URGENT = ("feedback", "no_signal", "distortion", "too_loud")

STATES = ("pending", "acknowledged", "modified", "approved",
          "applied_manually", "queued_for_device", "sent",
          "device_acknowledged", "applied", "rejected", "failed",
          "reverted", "cancelled", "expired")

# The whitelist. Read it as "from -> what may happen next".
#
# Note what is NOT here: pending -> applied. A request cannot become applied
# without an engineer acting, and a device-routed one cannot become applied
# without the device answering. That is the brief's confirmation rule, written
# as data instead of as a promise.
TRANSITIONS = {
    "pending": ("acknowledged", "modified", "approved", "applied_manually",
                "rejected", "cancelled", "expired"),
    "acknowledged": ("modified", "approved", "applied_manually", "rejected",
                     "cancelled", "expired"),
    "modified": ("approved", "applied_manually", "rejected", "cancelled",
                 "expired"),
    "approved": ("applied_manually", "queued_for_device", "rejected",
                 "cancelled", "expired"),
    "queued_for_device": ("sent", "failed", "cancelled", "expired"),
    "sent": ("device_acknowledged", "failed", "expired"),
    "device_acknowledged": ("applied", "failed"),
    "applied": ("reverted",),
    "applied_manually": ("reverted",),
    # Terminal.
    "rejected": (), "failed": (), "reverted": (), "cancelled": (), "expired": (),
}

# States where the performer is still waiting on a person.
OPEN_STATES = ("pending", "acknowledged", "modified", "approved",
               "queued_for_device", "sent", "device_acknowledged")

# What the performer is told, in words that do not overclaim. "applied" is the
# only one that says the change happened, and it is only reachable when it did.
PERFORMER_WORDING = {
    "pending": "Sent",
    "acknowledged": "Seen by the engineer",
    "modified": "Engineer adjusted the amount",
    "approved": "Approved",
    "queued_for_device": "Going to the console",
    "sent": "Sent to the console",
    "device_acknowledged": "Console answered",
    "applied": "Done",
    "applied_manually": "Done",
    "rejected": "Not this time",
    "failed": "Did not go through",
    "reverted": "Put back",
    "cancelled": "Cancelled",
    "expired": "Timed out",
}


def _uid():
    return uuid.uuid4().hex


def _row(r):
    return dict(r) if r else None


# --- schema ------------------------------------------------------------------

def init_stage():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS stage_requests (
                id TEXT PRIMARY KEY,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                performer TEXT NOT NULL DEFAULT '',
                mix TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL,
                step_db INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                urgent INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'pending',
                engineer TEXT NOT NULL DEFAULT '',
                engineer_note TEXT NOT NULL DEFAULT '',
                approved_step_db INTEGER,
                command_id TEXT NOT NULL DEFAULT '',
                device_ack TEXT NOT NULL DEFAULT '',
                failure TEXT NOT NULL DEFAULT '',
                revert_of TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                closed_at TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_sreq_show
                ON stage_requests(show_id, state, created);
            CREATE INDEX IF NOT EXISTS idx_sreq_performer
                ON stage_requests(show_id, performer, created);

            /* The cursor. `seq` is the whole point: an INTEGER PRIMARY KEY on
               SQLite is a rowid alias, so it is monotonic and server-assigned,
               which is what makes "give me everything after N" correct even
               when two requests land in the same millisecond. */
            CREATE TABLE IF NOT EXISTS stage_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL DEFAULT '{}',
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sevents_show
                ON stage_events(show_id, seq);

            /* Presence, so the desk can say who is actually on stage with the
               app open. Deliberately last-seen only: a performer whose phone
               is in a pocket is not "offline", they are "not polling", and the
               desk should show the difference rather than guess. */
            CREATE TABLE IF NOT EXISTS stage_presence (
                show_id TEXT NOT NULL,
                who TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'performer',
                last_seen TEXT NOT NULL,
                PRIMARY KEY (show_id, who)
            );

            /* Locks. A performer, a mix, or the whole show. Held here rather
               than as a flag on the show so that lifting one is a delete and
               the audit trail keeps the fact it happened. */
            CREATE TABLE IF NOT EXISTS stage_locks (
                show_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                by_whom TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                PRIMARY KEY (show_id, scope, target)
            );
        """)


# --- events ------------------------------------------------------------------

def emit(show_id, user_id, kind, request_id="", actor="", detail="", payload=None):
    """Append to the log. Returns the new cursor position.

    Every state change in this module goes through here, so the event stream is
    a complete record rather than a convenience copy - the brief is explicit
    that realtime messages must not be the only durable record, and here they
    are not the record at all: the tables are, and this is the notification.
    """
    eid = _uid()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO stage_events (id, show_id, user_id, request_id, kind, "
            "actor, detail, payload, created) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, show_id, user_id, request_id, kind, (actor or "").strip(),
             (detail or "").strip(), json.dumps(payload or {}), _now()))
        return cur.lastrowid


def events_since(show_id, since=0, limit=200):
    """The poll. `since` is the last seq the client already has."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM stage_events WHERE show_id = ? AND seq > ? "
            "ORDER BY seq LIMIT ?", (show_id, int(since or 0), int(limit))).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        try:
            item["payload"] = json.loads(item["payload"] or "{}")
        except (TypeError, ValueError):
            item["payload"] = {}
        out.append(item)
    return out


def cursor(show_id):
    """Where the log currently ends, so a client can start from "now" without
    replaying the whole show."""
    with get_db() as db:
        row = db.execute("SELECT MAX(seq) AS s FROM stage_events WHERE show_id = ?",
                         (show_id,)).fetchone()
    return int(row["s"] or 0) if row else 0


# --- presence and locks ------------------------------------------------------

def touch_presence(show_id, who, role="performer"):
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_presence (show_id, who, role, last_seen) VALUES (?,?,?,?) "
            "ON CONFLICT(show_id, who) DO UPDATE SET last_seen = excluded.last_seen, "
            "role = excluded.role",
            (show_id, who, role, _now()))


def presence(show_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM stage_presence WHERE show_id = ? ORDER BY who",
            (show_id,)).fetchall()]


def lock(show_id, scope, target="", reason="", by_whom=""):
    """scope is 'show', 'mix' or 'performer'."""
    if scope not in ("show", "mix", "performer"):
        return False
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_locks (show_id, scope, target, reason, by_whom, created) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(show_id, scope, target) DO UPDATE SET "
            "reason = excluded.reason, by_whom = excluded.by_whom",
            (show_id, scope, target or "", (reason or "").strip(),
             (by_whom or "").strip(), _now()))
    emit(show_id, "", "lock", actor=by_whom,
         detail="Locked %s %s" % (scope, target or ""),
         payload={"scope": scope, "target": target})
    return True


def unlock(show_id, scope, target=""):
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM stage_locks WHERE show_id = ? AND scope = ? AND target = ?",
            (show_id, scope, target or ""))
    if cur.rowcount:
        emit(show_id, "", "unlock", detail="Unlocked %s %s" % (scope, target or ""),
             payload={"scope": scope, "target": target})
    return cur.rowcount > 0


def locks(show_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM stage_locks WHERE show_id = ?", (show_id,)).fetchall()]


def locked_reason(show_id, performer="", mix=""):
    """Why this performer cannot send right now, or None.

    Checked in order of breadth so the message names the widest lock in force:
    telling somebody their mix is locked when the whole show is locked sends
    them to the wrong person.
    """
    for row in locks(show_id):
        if row["scope"] == "show":
            return row["reason"] or "The engineer has locked the show."
    for row in locks(show_id):
        if row["scope"] == "performer" and performer and row["target"] == performer:
            return row["reason"] or "The engineer has paused your requests."
        if row["scope"] == "mix" and mix and row["target"] == mix:
            return row["reason"] or "The engineer has locked this mix."
    return None


# --- requests ----------------------------------------------------------------

class Refused(Exception):
    """A request that must not be created, with a reason a performer can read."""


def submit(show_id, user_id, performer, mix, kind, source="", step_db=0,
           note="", allowed_mixes=None, allowed_sources=None, rate_limit=6):
    """Create a request, or refuse it with a reason.

    Mix ownership is checked HERE rather than trusted from the form: the
    performer interface only offers a performer their own mixes, but a template
    that hides a control is not a check, and the brief asks for authorisation
    server-side.
    """
    if kind not in REQUEST_KINDS:
        raise Refused("That is not something you can ask for.")

    blocked = locked_reason(show_id, performer=performer, mix=mix)
    if blocked:
        raise Refused(blocked)

    if allowed_mixes is not None and mix not in allowed_mixes:
        raise Refused("That mix is not yours.")

    if kind in ADJUSTMENTS:
        if not (source or "").strip():
            raise Refused("Say what you want more or less of.")
        if allowed_sources is not None and source not in allowed_sources:
            raise Refused("That source is not in your mix.")
        if kind in ("more", "less"):
            if int(step_db or 0) not in STEPS_DB:
                raise Refused("Pick one of the fixed steps.")
        else:
            step_db = 0

    # Rate limit per performer, counted over what is still open rather than
    # over time: six unanswered requests is a person who needs the engineer to
    # look up, not a person who needs a seventh request.
    if rate_limit:
        open_now = len(for_performer(show_id, performer, open_only=True))
        if open_now >= rate_limit:
            raise Refused("You have %d requests still waiting. The engineer has them."
                          % open_now)

    rid = _uid()
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_requests (id, show_id, user_id, performer, mix, source, "
            "kind, step_db, note, urgent, state, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?,?)",
            (rid, show_id, user_id, performer, mix, (source or "").strip(), kind,
             int(step_db or 0), (note or "").strip(), 1 if kind in URGENT else 0,
             now, now))
    emit(show_id, user_id, "request.new", request_id=rid, actor=performer,
         detail=_describe(kind, source, step_db),
         payload={"mix": mix, "kind": kind, "urgent": kind in URGENT})
    return rid


def _describe(kind, source="", step_db=0):
    label = KIND_LABELS.get(kind, kind)
    if kind in ("more", "less"):
        return "%s %s - %s" % (label, source, STEP_LABELS.get(int(step_db or 0), ""))
    if kind in ("mute", "unmute"):
        return "%s %s" % (label, source)
    return label


def get(request_id, user_id=None):
    sql = "SELECT * FROM stage_requests WHERE id = ?"
    args = [request_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    with get_db() as db:
        return _row(db.execute(sql, args).fetchone())


def for_show(show_id, user_id=None, open_only=False):
    sql = "SELECT * FROM stage_requests WHERE show_id = ?"
    args = [show_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    if open_only:
        sql += " AND state IN (%s)" % ",".join("?" * len(OPEN_STATES))
        args.extend(OPEN_STATES)
    # Urgent first, then oldest: a feedback report behind four "more vocal"
    # requests is a queue that has failed at its job.
    sql += " ORDER BY urgent DESC, created"
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


def for_performer(show_id, performer, open_only=False):
    sql = "SELECT * FROM stage_requests WHERE show_id = ? AND performer = ?"
    args = [show_id, performer]
    if open_only:
        sql += " AND state IN (%s)" % ",".join("?" * len(OPEN_STATES))
        args.extend(OPEN_STATES)
    sql += " ORDER BY created DESC"
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


def can_move(from_state, to_state):
    return to_state in TRANSITIONS.get(from_state, ())


def advance(request_id, user_id, to_state, actor="", note="", step_db=None,
            failure="", device_ack="", command_id=""):
    """Move a request, or refuse.

    The single writer of `state`. Everything else - acknowledge, approve,
    reject, apply - is a thin call to this, so there is exactly one place where
    a transition can be allowed and it is the table.
    """
    req = get(request_id, user_id)
    if req is None:
        return None
    if to_state not in STATES or not can_move(req["state"], to_state):
        return None

    now = _now()
    sets = ["state = ?", "updated = ?"]
    args = [to_state, now]
    if actor:
        sets.append("engineer = ?")
        args.append(actor.strip())
    if note:
        sets.append("engineer_note = ?")
        args.append(note.strip())
    if step_db is not None:
        sets.append("approved_step_db = ?")
        args.append(int(step_db))
    if failure:
        sets.append("failure = ?")
        args.append(failure.strip())
    if device_ack:
        sets.append("device_ack = ?")
        args.append(device_ack.strip())
    if command_id:
        sets.append("command_id = ?")
        args.append(command_id.strip())
    if to_state not in OPEN_STATES:
        sets.append("closed_at = ?")
        args.append(now)
    args.append(request_id)

    with get_db() as db:
        db.execute("UPDATE stage_requests SET %s WHERE id = ?" % ", ".join(sets), args)

    emit(req["show_id"], user_id, "request." + to_state, request_id=request_id,
         actor=actor or req["performer"],
         detail=note or _describe(req["kind"], req["source"],
                                  step_db if step_db is not None else req["step_db"]),
         payload={"from": req["state"], "to": to_state, "mix": req["mix"]})
    return get(request_id, user_id)


# Named moves, so callers read like the desk's buttons rather than like a
# state machine.

def acknowledge(request_id, user_id, actor=""):
    return advance(request_id, user_id, "acknowledged", actor=actor)


def modify(request_id, user_id, step_db, actor="", note=""):
    if int(step_db) not in STEPS_DB:
        return None
    return advance(request_id, user_id, "modified", actor=actor, note=note,
                   step_db=step_db)


def approve(request_id, user_id, actor="", step_db=None):
    return advance(request_id, user_id, "approved", actor=actor, step_db=step_db)


def apply_manually(request_id, user_id, actor="", note=""):
    """The engineer moved the fader themselves. This is the honest end state
    for Request Mode and it is NOT the same as `applied`, which means a device
    confirmed it."""
    return advance(request_id, user_id, "applied_manually", actor=actor, note=note)


def reject(request_id, user_id, actor="", reason=""):
    return advance(request_id, user_id, "rejected", actor=actor,
                   note=reason or "Not this time")


def cancel(request_id, user_id, actor=""):
    return advance(request_id, user_id, "cancelled", actor=actor)


def revert(request_id, user_id, actor="", note=""):
    return advance(request_id, user_id, "reverted", actor=actor, note=note)


def summary(show_id, user_id=None):
    """What the desk shows above the queue."""
    rows = for_show(show_id, user_id)
    open_rows = [r for r in rows if r["state"] in OPEN_STATES]
    return {
        "open": len(open_rows),
        "urgent": len([r for r in open_rows if r["urgent"]]),
        "unseen": len([r for r in open_rows if r["state"] == "pending"]),
        "total": len(rows),
        "locks": locks(show_id),
    }
