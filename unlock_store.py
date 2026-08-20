"""Progressive disclosure — per-user milestone state.

One row per account, read once per page render. The counters are kept as
running totals updated at write time rather than recomputed with COUNT()
queries, because this is read on every single request and a dashboard
that costs six aggregate queries per page is a dashboard that gets slow
quietly.

Three columns carry the whole system:

    flags       milestone -> the moment it first happened
    counters    running totals
    unlocked    module keys already opened, ever

`unlocked` is what makes an unlock permanent. Evaluation says what the
rules allow right now; this column remembers what they have allowed at
any point, and the two are unioned. So a release date passing, or a
statement being deleted, cannot take a module away from somebody who has
been using it.

Mode:
    simple  the disclosure system applies
    full    everything visible, the escape hatch

New accounts start simple. Every account that existed when this shipped
was backfilled to full, once, so nobody using the platform woke up with
features missing.
"""
import json

from db import get_db, _now

import unlock_rules

SIMPLE = "simple"
FULL = "full"
MODES = (SIMPLE, FULL)

# What an account created from here on starts as. Production ships SIMPLE:
# that is the whole feature. The test suite overrides it in conftest,
# because those ~950 tests assert what each module DOES given data, not
# what somebody sees on their first day — and an account that has to earn
# five milestones before it can assert anything about the money pages is
# a test of this system rather than of the money pages.
DEFAULT_MODE = SIMPLE

# Marks the one-time backfill so it cannot run twice and demote a new
# account that signed up between two restarts.
_BACKFILL_KEY = "unlocks:backfill:v1"


def _loads(text, default):
    try:
        value = json.loads(text or "null")
    except (ValueError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def init_unlocks():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS user_unlocks (
                user_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'simple',
                flags TEXT NOT NULL DEFAULT '{}',
                counters TEXT NOT NULL DEFAULT '{}',
                unlocked TEXT NOT NULL DEFAULT '[]',
                notices TEXT NOT NULL DEFAULT '[]',
                seen_notices TEXT NOT NULL DEFAULT '[]',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
        """)
        done = db.execute("SELECT value FROM app_kv WHERE key = ?",
                          (_BACKFILL_KEY,)).fetchone()
        if done:
            return
        # Everybody already here keeps everything. This is the promise in
        # the brief - no existing account loses access - and it is done
        # once, by row, rather than by comparing signup dates at read
        # time, which would quietly re-demote anyone whose row was lost.
        now = _now()
        for row in db.execute("SELECT id FROM users").fetchall():
            db.execute(
                "INSERT OR IGNORE INTO user_unlocks (user_id, mode, created,"
                " updated) VALUES (?, 'full', ?, ?)", (row["id"], now, now))
        db.execute("INSERT OR REPLACE INTO app_kv (key, value, updated) "
                   "VALUES (?, ?, ?)", (_BACKFILL_KEY, now, now))


def _row(user_id, create=True):
    with get_db() as db:
        row = db.execute("SELECT * FROM user_unlocks WHERE user_id = ?",
                         (user_id,)).fetchone()
        if row is None and create:
            now = _now()
            db.execute("INSERT OR IGNORE INTO user_unlocks (user_id, mode, "
                       "created, updated) VALUES (?, ?, ?, ?)",
                       (user_id, DEFAULT_MODE, now, now))
            row = db.execute("SELECT * FROM user_unlocks WHERE user_id = ?",
                             (user_id,)).fetchone()
    return dict(row) if row else None


def state(user_id):
    """Everything a page render needs, in one read."""
    row = _row(user_id)
    flags = _loads(row["flags"], {})
    counters = _loads(row["counters"], {})
    latched = set(_loads(row["unlocked"], []))
    mode = row["mode"] if row["mode"] in MODES else SIMPLE
    open_now = latched | unlock_rules.unlocked_keys(flags, counters)
    return {
        "mode": mode,
        "simple": mode == SIMPLE,
        "flags": flags,
        "counters": counters,
        # In full mode nothing is gated at all, so the locked set is
        # empty and every render below behaves as it did before.
        "unlocked": unlock_rules.gated_keys() if mode == FULL else open_now,
        "locked": set() if mode == FULL
                  else (unlock_rules.gated_keys() - open_now),
        "notices": _loads(row["notices"], []),
    }


def is_locked(user_id, key):
    if not unlock_rules.is_gated(key):
        return False
    return key in state(user_id)["locked"]


def set_mode(user_id, mode):
    if mode not in MODES:
        return False
    _row(user_id)
    with get_db() as db:
        db.execute("UPDATE user_unlocks SET mode = ?, updated = ? "
                   "WHERE user_id = ?", (mode, _now(), user_id))
    return True


# --- recording milestones ---------------------------------------------------

def _apply(user_id, flags, counters):
    """Write new milestone state and latch anything it opens.

    Returns the keys that opened on THIS call, so the caller can announce
    them. A key already latched returns nothing, which is what makes the
    announcement one-time without a second bookkeeping table.
    """
    row = _row(user_id)
    was = set(_loads(row["unlocked"], []))
    now_open = was | unlock_rules.unlocked_keys(flags, counters)
    newly = sorted(now_open - was)

    notices = _loads(row["notices"], [])
    seen = set(_loads(row["seen_notices"], []))
    # Only queue a notice for an account the system is actually shaping.
    # In full mode nothing was hidden, so nothing "opened". Queued by
    # group, so one action that opens five money modules is one sentence.
    if row["mode"] == SIMPLE:
        for group in dict.fromkeys(unlock_rules.group_of(k) for k in newly):
            if group not in seen and group not in notices:
                notices.append(group)

    with get_db() as db:
        db.execute(
            "UPDATE user_unlocks SET flags = ?, counters = ?, unlocked = ?, "
            "notices = ?, updated = ? WHERE user_id = ?",
            (json.dumps(flags), json.dumps(counters),
             json.dumps(sorted(now_open)), json.dumps(notices),
             _now(), user_id))
    return newly if row["mode"] == SIMPLE else []


def flag(user_id, name):
    """Latch a boolean milestone. Idempotent: the timestamp is the first
    time it happened, not the most recent."""
    if not user_id or name not in unlock_rules.FLAGS:
        return []
    row = _row(user_id)
    flags = _loads(row["flags"], {})
    if flags.get(name):
        return []
    flags[name] = _now()
    return _apply(user_id, flags, _loads(row["counters"], {}))


def bump(user_id, name, n=1):
    """Add to a running total."""
    if not user_id or name not in unlock_rules.COUNTERS or n == 0:
        return []
    row = _row(user_id)
    counters = _loads(row["counters"], {})
    counters[name] = int(counters.get(name) or 0) + n
    return _apply(user_id, _loads(row["flags"], {}), counters)


def set_count(user_id, name, value):
    """Set an absolute total, for counts derived from a real query rather
    than accumulated. Never lowers a total: the counters feed unlocks,
    and a deleted release should not close a module."""
    if not user_id or name not in unlock_rules.COUNTERS:
        return []
    row = _row(user_id)
    counters = _loads(row["counters"], {})
    if int(value) <= int(counters.get(name) or 0):
        return []
    counters[name] = int(value)
    return _apply(user_id, _loads(row["flags"], {}), counters)


# --- the unlock moment ------------------------------------------------------

def pending_notices(user_id):
    """Keys whose unlock has not been shown and dismissed yet."""
    return list(state(user_id)["notices"])


def dismiss_notice(user_id, key):
    row = _row(user_id)
    notices = [k for k in _loads(row["notices"], []) if k != key]
    seen = set(_loads(row["seen_notices"], []))
    seen.add(key)
    with get_db() as db:
        db.execute("UPDATE user_unlocks SET notices = ?, seen_notices = ?, "
                   "updated = ? WHERE user_id = ?",
                   (json.dumps(notices), json.dumps(sorted(seen)),
                    _now(), user_id))
    return True
