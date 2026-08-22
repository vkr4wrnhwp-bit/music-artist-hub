"""Light Studio library — named shows with versions.

`light_shows` (one working copy per user, db.py) stays exactly as it was:
the page loads it, autosave writes it, the old /lights/save keeps working.
This adds the library on top: many named shows per account, each linked
to a catalog track and optionally a tour date, with a version snapshot
taken on every explicit save (autosave updates in place and takes none).
"""
import json
import uuid

from db import get_db, _now

MAX_VERSIONS = 20


def init_lights():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS light_show_library (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                track_id TEXT,
                tour_show_id TEXT,
                data TEXT NOT NULL,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS light_show_versions (
                id TEXT PRIMARY KEY,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                data TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                saved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS light_rigs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                venue_key TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS light_setlists (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                gap_color TEXT NOT NULL DEFAULT '#1a1712',
                gap_intensity INTEGER NOT NULL DEFAULT 12,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS light_setlist_items (
                id TEXT PRIMARY KEY,
                setlist_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                show_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                advance TEXT NOT NULL DEFAULT 'manual',
                gap_seconds REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_lset_user ON light_setlists(user_id, updated);
            CREATE INDEX IF NOT EXISTS idx_lseti ON light_setlist_items(setlist_id, position);
            CREATE INDEX IF NOT EXISTS idx_lsl_user ON light_show_library(user_id, updated);
            CREATE INDEX IF NOT EXISTS idx_lsv_show ON light_show_versions(show_id, saved_at);
            CREATE INDEX IF NOT EXISTS idx_lr_user ON light_rigs(user_id, updated);
            CREATE INDEX IF NOT EXISTS idx_lr_venue ON light_rigs(user_id, venue_key);
        """)


def _row(r):
    d = dict(r)
    try:
        d["data"] = json.loads(d.get("data") or "{}")
    except ValueError:
        d["data"] = {}
    d["cue_count"] = len((d["data"] or {}).get("cues") or [])
    return d


def list_shows(user_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM light_show_library WHERE user_id = ? ORDER BY updated DESC",
                          (user_id,)).fetchall()
    return [_row(r) for r in rows]


def get_show(user_id, show_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM light_show_library WHERE id = ? AND user_id = ?",
                         (show_id, user_id)).fetchone()
    return _row(row) if row else None


def save_show(user_id, show_id, name, data, track_id=None, tour_show_id=None,
              version=True, note=""):
    """Upsert. Returns the id. A version row is written only when
    `version` is true (explicit saves); autosave passes False."""
    name = (name or "Untitled show").strip()[:120]
    blob = json.dumps(data if isinstance(data, dict) else {})
    now = _now()
    with get_db() as db:
        existing = None
        if show_id:
            existing = db.execute("SELECT id FROM light_show_library WHERE id=? AND user_id=?",
                                  (show_id, user_id)).fetchone()
        if existing:
            db.execute("UPDATE light_show_library SET name=?, track_id=?, tour_show_id=?, data=?, "
                       "updated=? WHERE id=? AND user_id=?",
                       (name, track_id or None, tour_show_id or None, blob, now, show_id, user_id))
        else:
            show_id = uuid.uuid4().hex
            db.execute("INSERT INTO light_show_library (id, user_id, name, track_id, tour_show_id, "
                       "data, created, updated) VALUES (?,?,?,?,?,?,?,?)",
                       (show_id, user_id, name, track_id or None, tour_show_id or None, blob, now, now))
        if version:
            db.execute("INSERT INTO light_show_versions (id, show_id, user_id, data, note, saved_at) "
                       "VALUES (?,?,?,?,?,?)",
                       (uuid.uuid4().hex, show_id, user_id, blob, (note or "")[:200], now))
            # keep the newest MAX_VERSIONS
            ids = [r["id"] for r in db.execute(
                "SELECT id FROM light_show_versions WHERE show_id=? ORDER BY saved_at DESC",
                (show_id,)).fetchall()]
            for old in ids[MAX_VERSIONS:]:
                db.execute("DELETE FROM light_show_versions WHERE id=?", (old,))
    return show_id


def delete_show(user_id, show_id):
    with get_db() as db:
        db.execute("DELETE FROM light_show_versions WHERE show_id=? AND user_id=?", (show_id, user_id))
        cur = db.execute("DELETE FROM light_show_library WHERE id=? AND user_id=?", (show_id, user_id))
    return cur.rowcount > 0


def list_versions(user_id, show_id):
    with get_db() as db:
        rows = db.execute("SELECT id, note, saved_at, data FROM light_show_versions "
                          "WHERE show_id=? AND user_id=? ORDER BY saved_at DESC",
                          (show_id, user_id)).fetchall()
    out = []
    for r in rows:
        try:
            cues = len(json.loads(r["data"]).get("cues") or [])
        except (ValueError, AttributeError):
            cues = 0
        out.append({"id": r["id"], "note": r["note"], "saved_at": r["saved_at"], "cue_count": cues})
    return out


# --- setlists ----------------------------------------------------------
# A setlist chains saved shows in order. Between songs the rig holds a
# "gap look" rather than going black, because a black stage between songs
# reads as a fault.

MAX_SETLIST_ITEMS = 60
ADVANCE_MODES = ("manual", "auto")


def list_setlists(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM light_setlist_items i WHERE i.setlist_id = s.id) AS item_count "
            "FROM light_setlists s WHERE s.user_id = ? ORDER BY s.updated DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_setlist(user_id, setlist_id):
    """The setlist with its items resolved to library shows, in order."""
    with get_db() as db:
        row = db.execute("SELECT * FROM light_setlists WHERE id=? AND user_id=?",
                         (setlist_id, user_id)).fetchone()
        if row is None:
            return None
        items = db.execute(
            "SELECT i.*, l.name AS show_name FROM light_setlist_items i "
            "LEFT JOIN light_show_library l ON l.id = i.show_id "
            "WHERE i.setlist_id=? AND i.user_id=? ORDER BY i.position", (setlist_id, user_id)).fetchall()
    out = dict(row)
    out["items"] = [dict(i) for i in items]
    return out


def save_setlist(user_id, setlist_id, name, items, gap_color="#1a1712", gap_intensity=12):
    """Upsert a setlist and replace its items.

    Every show id is checked against this user's own library, so a setlist
    can never reference another account's show.
    """
    name = (name or "Setlist").strip()[:120]
    now = _now()
    with get_db() as db:
        if setlist_id and db.execute("SELECT 1 FROM light_setlists WHERE id=? AND user_id=?",
                                     (setlist_id, user_id)).fetchone():
            db.execute("UPDATE light_setlists SET name=?, gap_color=?, gap_intensity=?, updated=? "
                       "WHERE id=? AND user_id=?",
                       (name, gap_color, int(gap_intensity or 0), now, setlist_id, user_id))
        else:
            setlist_id = uuid.uuid4().hex
            db.execute("INSERT INTO light_setlists (id, user_id, name, gap_color, gap_intensity, created, updated) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (setlist_id, user_id, name, gap_color, int(gap_intensity or 0), now, now))
        mine = {r["id"] for r in db.execute("SELECT id FROM light_show_library WHERE user_id=?",
                                            (user_id,)).fetchall()}
        db.execute("DELETE FROM light_setlist_items WHERE setlist_id=? AND user_id=?", (setlist_id, user_id))
        pos = 0
        for it in (items or [])[:MAX_SETLIST_ITEMS]:
            show_id = (it or {}).get("show_id") or ""
            if show_id not in mine:            # not this user's show: drop it
                continue
            advance = it.get("advance") if it.get("advance") in ADVANCE_MODES else "manual"
            try:
                gap = max(0.0, min(600.0, float(it.get("gap_seconds") or 0)))
            except (TypeError, ValueError):
                gap = 0.0
            db.execute("INSERT INTO light_setlist_items (id, setlist_id, user_id, show_id, position, advance, "
                       "gap_seconds) VALUES (?,?,?,?,?,?,?)",
                       (uuid.uuid4().hex, setlist_id, user_id, show_id, pos, advance, gap))
            pos += 1
    return setlist_id


def delete_setlist(user_id, setlist_id):
    with get_db() as db:
        db.execute("DELETE FROM light_setlist_items WHERE setlist_id=? AND user_id=?", (setlist_id, user_id))
        cur = db.execute("DELETE FROM light_setlists WHERE id=? AND user_id=?", (setlist_id, user_id))
    return cur.rowcount > 0


# --- rig profiles ------------------------------------------------------
# A rig is bar count, fixture type, layout and patch. Shows store looks and
# group roles, so the same show compiles onto any rig; a rig can be bound to
# a venue by name so picking a tour date at that venue selects it.

MAX_RIGS = 40


def venue_key(name):
    """Loose match on a venue name: case, spacing and punctuation are noise."""
    out = []
    prev_space = False
    for ch in (name or "").lower():
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        elif not prev_space:
            out.append(" ")
            prev_space = True
    return "".join(out).strip()[:120]


def _rig_row(r):
    d = dict(r)
    try:
        d["data"] = json.loads(d.get("data") or "{}")
    except ValueError:
        d["data"] = {}
    return d


def list_rigs(user_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM light_rigs WHERE user_id = ? ORDER BY updated DESC",
                          (user_id,)).fetchall()
    return [_rig_row(r) for r in rows]


def get_rig(user_id, rig_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM light_rigs WHERE id = ? AND user_id = ?",
                         (rig_id, user_id)).fetchone()
    return _rig_row(row) if row else None


def save_rig(user_id, rig_id, name, data, venue=""):
    """Upsert a rig. Returns (id, error). Refuses to create past MAX_RIGS."""
    name = (name or "Untitled rig").strip()[:80]
    blob = json.dumps(data if isinstance(data, dict) else {})
    key = venue_key(venue)
    now = _now()
    with get_db() as db:
        existing = None
        if rig_id:
            existing = db.execute("SELECT id FROM light_rigs WHERE id=? AND user_id=?",
                                  (rig_id, user_id)).fetchone()
        if existing:
            db.execute("UPDATE light_rigs SET name=?, venue_key=?, data=?, updated=? "
                       "WHERE id=? AND user_id=?", (name, key, blob, now, rig_id, user_id))
        else:
            count = db.execute("SELECT COUNT(*) AS n FROM light_rigs WHERE user_id=?",
                               (user_id,)).fetchone()["n"]
            if count >= MAX_RIGS:
                return (None, "You have %d saved rigs — delete one first." % MAX_RIGS)
            rig_id = uuid.uuid4().hex
            db.execute("INSERT INTO light_rigs (id, user_id, name, venue_key, data, created, updated) "
                       "VALUES (?,?,?,?,?,?,?)", (rig_id, user_id, name, key, blob, now, now))
        # one rig per venue: the newest binding wins, older ones are unbound
        if key:
            db.execute("UPDATE light_rigs SET venue_key='' WHERE user_id=? AND venue_key=? AND id<>?",
                       (user_id, key, rig_id))
    return (rig_id, None)


def delete_rig(user_id, rig_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM light_rigs WHERE id=? AND user_id=?", (rig_id, user_id))
    return cur.rowcount > 0


def rig_for_venue(user_id, venue):
    """The rig bound to this venue name, or None. Used when a show is
    linked to a tour date so the layout follows the room."""
    key = venue_key(venue)
    if not key:
        return None
    with get_db() as db:
        row = db.execute("SELECT * FROM light_rigs WHERE user_id=? AND venue_key=? "
                         "ORDER BY updated DESC LIMIT 1", (user_id, key)).fetchone()
    return _rig_row(row) if row else None


def get_version(user_id, version_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM light_show_versions WHERE id=? AND user_id=?",
                         (version_id, user_id)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["data"] = json.loads(d["data"])
    except ValueError:
        d["data"] = {}
    return d
