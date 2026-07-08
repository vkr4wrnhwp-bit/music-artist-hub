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
            """
        )


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

def create_db_link(slug, user_id, title, target, platforms):
    base, n = slug, 1
    with get_db() as db:
        while db.execute("SELECT 1 FROM smart_links WHERE slug = ?", (slug,)).fetchone():
            n += 1
            slug = f"{base}-{n}"
        db.execute(
            "INSERT INTO smart_links (slug, user_id, title, target, platforms, created) VALUES (?,?,?,?,?,?)",
            (slug, user_id, title, target, json.dumps(platforms or []), _now()),
        )
    return slug


def get_db_links():
    with get_db() as db:
        rows = db.execute(
            "SELECT l.*, (SELECT COUNT(*) FROM link_clicks c WHERE c.slug = l.slug) AS clicks "
            "FROM smart_links l ORDER BY created DESC"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["platforms"] = json.loads(d.get("platforms") or "[]")
        out.append(d)
    return out


def get_db_link(slug):
    with get_db() as db:
        row = db.execute("SELECT * FROM smart_links WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def log_click(slug):
    with get_db() as db:
        db.execute("INSERT INTO link_clicks (slug, ts) VALUES (?,?)", (slug, _now()))


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
    return {"data": json.loads(row["data"] or "{}"), "photo": row["photo"]}


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
