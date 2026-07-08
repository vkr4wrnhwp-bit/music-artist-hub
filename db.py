"""SQLite persistence layer.

Real storage for the features that graduated from demo to functional:
user accounts, uploaded royalty statements (+ parsed rows), smart links
(+ click logs), and the submissions inbox. Path is configurable via
DATABASE_PATH so tests and hosted deploys can point elsewhere.

Note for hosting: on ephemeral-disk hosts (e.g. Render free tier) the
file survives requests but not redeploys/restarts — attach a persistent
disk or move to Postgres for durable production data.
"""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def db_path():
    return os.environ.get("DATABASE_PATH") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "instance", "streetbanker.db"
    )


@contextmanager
def get_db():
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS statements (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                uploaded TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                total REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS statement_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id TEXT NOT NULL,
                title TEXT,
                source TEXT,
                amount REAL NOT NULL,
                period TEXT
            );
            CREATE TABLE IF NOT EXISTS smart_links (
                slug TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT NOT NULL,
                target TEXT NOT NULL,
                platforms TEXT,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS link_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                ts TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inbox (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS epk_profiles (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL DEFAULT '{}',
                photo TEXT,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_tracks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT '',
                album TEXT NOT NULL DEFAULT '',
                art TEXT NOT NULL DEFAULT '',
                preview TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                added TEXT NOT NULL,
                UNIQUE(user_id, title, artist)
            );
            CREATE TABLE IF NOT EXISTS api_cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created TEXT NOT NULL
            );
            """
        )
        # Migration: universal-link metadata on smart links.
        try:
            db.execute("ALTER TABLE smart_links ADD COLUMN meta TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration: industry identifiers (ISRC/UPC/label) on catalog tracks.
        try:
            db.execute("ALTER TABLE catalog_tracks ADD COLUMN meta TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration: public share slug on EPK profiles.
        try:
            db.execute("ALTER TABLE epk_profiles ADD COLUMN slug TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Users -------------------------------------------------------------------

def create_user(email, name, password_hash):
    user_id = uuid.uuid4().hex
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO users (id, email, name, password_hash, created) VALUES (?,?,?,?,?)",
                (user_id, email.lower().strip(), name.strip(), password_hash, _now()),
            )
    except sqlite3.IntegrityError:
        return None
    return user_id


def get_user_by_email(email):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    return dict(row) if row else None


def get_user(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# --- Statements --------------------------------------------------------------

def save_statement(user_id, filename, rows):
    statement_id = uuid.uuid4().hex
    total = round(sum(r["amount"] for r in rows), 2)
    with get_db() as db:
        db.execute(
            "INSERT INTO statements (id, user_id, filename, uploaded, row_count, total) VALUES (?,?,?,?,?,?)",
            (statement_id, user_id, filename, _now(), len(rows), total),
        )
        db.executemany(
            "INSERT INTO statement_rows (statement_id, title, source, amount, period) VALUES (?,?,?,?,?)",
            [(statement_id, r.get("title"), r.get("source"), r["amount"], r.get("period")) for r in rows],
        )
    return statement_id


def get_statements(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM statements WHERE user_id = ? ORDER BY uploaded DESC", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_statement_rows(user_id, statement_id=None):
    q = ("SELECT sr.* FROM statement_rows sr JOIN statements s ON s.id = sr.statement_id "
         "WHERE s.user_id = ?")
    args = [user_id]
    if statement_id:
        q += " AND sr.statement_id = ?"
        args.append(statement_id)
    with get_db() as db:
        rows = db.execute(q, args).fetchall()
    return [dict(r) for r in rows]


# --- Smart links -------------------------------------------------------------

def create_db_link(slug, user_id, title, target, platforms, meta=None):
    base, n = slug, 1
    with get_db() as db:
        while db.execute("SELECT 1 FROM smart_links WHERE slug = ?", (slug,)).fetchone():
            n += 1
            slug = f"{base}-{n}"
        db.execute(
            "INSERT INTO smart_links (slug, user_id, title, target, platforms, meta, created) VALUES (?,?,?,?,?,?,?)",
            (slug, user_id, title, target, json.dumps(platforms or []),
             json.dumps(meta) if meta else None, _now()),
        )
    return slug


def _link_row(d):
    d["platforms"] = json.loads(d.get("platforms") or "[]")
    d["meta"] = json.loads(d["meta"]) if d.get("meta") else None
    return d


def get_db_links():
    with get_db() as db:
        rows = db.execute(
            "SELECT l.*, (SELECT COUNT(*) FROM link_clicks c WHERE c.slug = l.slug) AS clicks "
            "FROM smart_links l ORDER BY created DESC"
        ).fetchall()
    return [_link_row(dict(r)) for r in rows]


def get_db_link(slug):
    with get_db() as db:
        row = db.execute("SELECT * FROM smart_links WHERE slug = ?", (slug,)).fetchone()
    return _link_row(dict(row)) if row else None


def log_click(slug):
    with get_db() as db:
        db.execute("INSERT INTO link_clicks (slug, ts) VALUES (?,?)", (slug, _now()))


# --- API cache -----------------------------------------------------------------

def add_catalog_track(user_id, track):
    """Save a Discover track to the user's catalog. Returns the row id,
    or None if the same title+artist is already in their catalog."""
    track_id = uuid.uuid4().hex
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO catalog_tracks (id, user_id, title, artist, album, art, preview, url, added)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (track_id, user_id, (track.get("title") or "").strip(),
                 (track.get("artist") or "").strip(), track.get("album") or "",
                 track.get("art") or "", track.get("preview") or "",
                 track.get("url") or "", _now()),
            )
    except sqlite3.IntegrityError:
        return None
    return track_id


def set_catalog_track_meta(user_id, track_id, meta):
    with get_db() as db:
        db.execute("UPDATE catalog_tracks SET meta = ? WHERE id = ? AND user_id = ?",
                   (json.dumps(meta), track_id, user_id))


def get_catalog_tracks(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM catalog_tracks WHERE user_id = ? ORDER BY added DESC",
            (user_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d["meta"]) if d.get("meta") else None
        out.append(d)
    return out


def remove_catalog_track(user_id, track_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM catalog_tracks WHERE id = ? AND user_id = ?",
                         (track_id, user_id))
    return cur.rowcount > 0


def cache_get(key, max_age_seconds):
    with get_db() as db:
        row = db.execute("SELECT value, created FROM api_cache WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    created = datetime.fromisoformat(row["created"])
    if (datetime.now(timezone.utc) - created).total_seconds() > max_age_seconds:
        return None
    return json.loads(row["value"])


def cache_set(key, value):
    with get_db() as db:
        db.execute(
            "INSERT INTO api_cache (key, value, created) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, created=excluded.created",
            (key, json.dumps(value), _now()),
        )


# --- EPK profiles --------------------------------------------------------------

def save_epk(user_id, data):
    with get_db() as db:
        db.execute(
            "INSERT INTO epk_profiles (user_id, data, updated) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
            (user_id, json.dumps(data), _now()),
        )


def save_epk_photo(user_id, photo_path):
    with get_db() as db:
        db.execute(
            "INSERT INTO epk_profiles (user_id, data, photo, updated) VALUES (?, '{}', ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET photo=excluded.photo, updated=excluded.updated",
            (user_id, photo_path, _now()),
        )


def get_epk(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM epk_profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return {"data": json.loads(row["data"] or "{}"), "photo": row["photo"],
            "slug": row["slug"]}


def set_epk_slug(user_id, slug):
    with get_db() as db:
        db.execute(
            "INSERT INTO epk_profiles (user_id, data, slug, updated) VALUES (?,'{}',?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET slug=excluded.slug, updated=excluded.updated",
            (user_id, slug, _now()),
        )


def get_epk_by_slug(slug):
    with get_db() as db:
        row = db.execute(
            "SELECT p.*, u.name AS user_name FROM epk_profiles p "
            "JOIN users u ON u.id = p.user_id WHERE p.slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    return {"data": json.loads(row["data"] or "{}"), "photo": row["photo"],
            "slug": row["slug"], "user_id": row["user_id"],
            "user_name": row["user_name"]}


# --- Inbox -------------------------------------------------------------------

def add_inbox(kind, payload):
    with get_db() as db:
        db.execute(
            "INSERT INTO inbox (id, kind, payload, created) VALUES (?,?,?,?)",
            (uuid.uuid4().hex, kind, json.dumps(payload), _now()),
        )


def get_inbox():
    with get_db() as db:
        rows = db.execute("SELECT * FROM inbox ORDER BY created DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out
