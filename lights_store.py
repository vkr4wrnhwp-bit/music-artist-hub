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
            CREATE INDEX IF NOT EXISTS idx_lsl_user ON light_show_library(user_id, updated);
            CREATE INDEX IF NOT EXISTS idx_lsv_show ON light_show_versions(show_id, saved_at);
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
