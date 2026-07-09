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


_FALLBACK_WARNED = False


@contextmanager
def get_db():
    path = db_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        # DATABASE_PATH points somewhere we cannot create (e.g. the disk
        # is not mounted yet). Fall back to the local instance dir so the
        # app still boots — degraded (ephemeral) beats down.
        global _FALLBACK_WARNED
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "instance", "streetbanker.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not _FALLBACK_WARNED:
            print("WARNING: DATABASE_PATH unusable; falling back to", path)
            _FALLBACK_WARNED = True
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
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'manager',
                status TEXT NOT NULL DEFAULT 'invited',
                invite_token TEXT UNIQUE,
                member_user_id TEXT,
                created TEXT NOT NULL,
                joined TEXT,
                UNIQUE(owner_id, email)
            );
            CREATE TABLE IF NOT EXISTS pulse_snapshots (
                user_id TEXT NOT NULL,
                day TEXT NOT NULL,
                followers INTEGER NOT NULL DEFAULT 0,
                popularity INTEGER NOT NULL DEFAULT 0,
                deezer_fans INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, day)
            );
            CREATE TABLE IF NOT EXISTS pulse_profiles (
                user_id TEXT PRIMARY KEY,
                artist_id TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                artist_image TEXT NOT NULL DEFAULT '',
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
            CREATE TABLE IF NOT EXISTS epk_assets (
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                public INTEGER NOT NULL DEFAULT 1,
                updated TEXT NOT NULL,
                PRIMARY KEY (user_id, kind)
            );
            CREATE TABLE IF NOT EXISTS ml_campaigns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                artist_name TEXT NOT NULL DEFAULT '',
                release_type TEXT NOT NULL DEFAULT 'Single',
                campaign_type TEXT NOT NULL DEFAULT 'release',
                status TEXT NOT NULL DEFAULT 'draft',
                release_date TEXT NOT NULL DEFAULT '',
                cover_url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                settings TEXT NOT NULL DEFAULT '{}',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                published_at TEXT,
                archived_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ml_destinations (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                service_key TEXT NOT NULL,
                service_name TEXT NOT NULL,
                url TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS ml_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                variant_id TEXT,
                event_type TEXT NOT NULL,
                service_key TEXT,
                fan_id TEXT,
                referrer TEXT,
                utm_source TEXT,
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ml_events_campaign
                ON ml_events (campaign_id, event_type);
            CREATE TABLE IF NOT EXISTS ml_fans (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                first_campaign_id TEXT,
                last_campaign_id TEXT,
                total_visits INTEGER NOT NULL DEFAULT 0,
                total_clicks INTEGER NOT NULL DEFAULT 0,
                total_presaves INTEGER NOT NULL DEFAULT 0,
                total_captures INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                intent_score INTEGER NOT NULL DEFAULT 0,
                intent_level TEXT NOT NULL DEFAULT 'Cold',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                UNIQUE(user_id, email)
            );
            CREATE TABLE IF NOT EXISTS ml_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fan_id TEXT NOT NULL,
                campaign_id TEXT,
                consent_type TEXT NOT NULL,
                consent_text TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ml_variants (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                utm_source TEXT NOT NULL DEFAULT '',
                utm_medium TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ro_campaigns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                ml_campaign_id TEXT,
                title TEXT NOT NULL,
                artist_name TEXT NOT NULL DEFAULT '',
                release_date TEXT NOT NULL DEFAULT '',
                rollout_length INTEGER NOT NULL DEFAULT 14,
                goal TEXT NOT NULL DEFAULT 'presaves',
                platforms TEXT NOT NULL DEFAULT '[]',
                tone TEXT NOT NULL DEFAULT 'premium',
                status TEXT NOT NULL DEFAULT 'draft',
                settings TEXT NOT NULL DEFAULT '{}',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ro_assets (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                file_path TEXT NOT NULL DEFAULT '',
                lyrics_text TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ro_posts (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                variant_id TEXT,
                platform TEXT NOT NULL,
                post_type TEXT NOT NULL DEFAULT 'post',
                phase TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                hashtags TEXT NOT NULL DEFAULT '',
                cta TEXT NOT NULL DEFAULT '',
                asset_id TEXT,
                edit_plan TEXT,
                scheduled_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                published_url TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS street_actions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                priority TEXT NOT NULL DEFAULT 'medium',
                description TEXT NOT NULL DEFAULT '',
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'system',
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                link TEXT NOT NULL DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                doc_type TEXT NOT NULL DEFAULT 'Agreement',
                note TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recovery_cases (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                estimated_amount REAL NOT NULL DEFAULT 0,
                confidence TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'open',
                deadline TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                evidence_doc_id TEXT,
                payout_result REAL,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                closed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                deal_type TEXT NOT NULL DEFAULT 'split',
                title TEXT NOT NULL,
                counterparty TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                terms TEXT NOT NULL DEFAULT '',
                doc_id TEXT,
                deadline TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_packs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                artist_name TEXT NOT NULL DEFAULT '',
                bpm TEXT NOT NULL DEFAULT '',
                song_key TEXT NOT NULL DEFAULT '',
                moods TEXT NOT NULL DEFAULT '',
                master_status TEXT NOT NULL DEFAULT 'unconfirmed',
                publishing_status TEXT NOT NULL DEFAULT 'unconfirmed',
                ownership_note TEXT NOT NULL DEFAULT '',
                contact_email TEXT NOT NULL DEFAULT '',
                main_url TEXT NOT NULL DEFAULT '',
                instrumental_url TEXT NOT NULL DEFAULT '',
                clean_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                views INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS twin_settings (
                user_id TEXT PRIMARY KEY,
                sources TEXT NOT NULL DEFAULT '[]',
                tone TEXT NOT NULL DEFAULT 'premium',
                do_not_say TEXT NOT NULL DEFAULT '',
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS twin_generations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                output TEXT NOT NULL,
                sources_used TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revenue_expenses (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                description TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL DEFAULT 0,
                spend_date TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spotify_presaves (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                spotify_user_id TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                refresh_token_enc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT NOT NULL DEFAULT '',
                retry_count INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(campaign_id, spotify_user_id)
            );
            CREATE TABLE IF NOT EXISTS api_cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created TEXT NOT NULL
            );
            """
        )
        # Migration: optional territory column on statement rows.
        try:
            db.execute("ALTER TABLE statement_rows ADD COLUMN territory TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
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
        # Migration: account plan tiers (fan / artist / pro / label).
        try:
            db.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'artist'")
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


def set_user_plan(user_id, plan):
    with get_db() as db:
        db.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))


def set_user_password(user_id, password_hash):
    with get_db() as db:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (password_hash, user_id))


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
            "INSERT INTO statement_rows (statement_id, title, source, amount, period, territory) VALUES (?,?,?,?,?,?)",
            [(statement_id, r.get("title"), r.get("source"), r["amount"],
              r.get("period"), r.get("territory") or "") for r in rows],
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


def save_epk_asset(user_id, kind, path):
    with get_db() as db:
        db.execute(
            "INSERT INTO epk_assets (user_id, kind, path, public, updated) VALUES (?,?,?,1,?) "
            "ON CONFLICT(user_id, kind) DO UPDATE SET path=excluded.path, updated=excluded.updated",
            (user_id, kind, path, _now()),
        )


def set_epk_asset_public(user_id, kind, public):
    with get_db() as db:
        cur = db.execute("UPDATE epk_assets SET public = ? WHERE user_id = ? AND kind = ?",
                         (1 if public else 0, user_id, kind))
    return cur.rowcount > 0


def get_epk_assets(user_id, public_only=False):
    q = "SELECT * FROM epk_assets WHERE user_id = ?"
    if public_only:
        q += " AND public = 1"
    with get_db() as db:
        rows = db.execute(q, (user_id,)).fetchall()
    return [dict(r) for r in rows]


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


# --- Pulse snapshots (real growth history) ----------------------------------------

def record_pulse_snapshot(user_id, followers, popularity, deezer_fans):
    """One snapshot per user per day; later same-day calls refresh it."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as db:
        db.execute(
            "INSERT INTO pulse_snapshots (user_id, day, followers, popularity, deezer_fans) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id, day) DO UPDATE SET followers=excluded.followers, "
            "popularity=excluded.popularity, deezer_fans=excluded.deezer_fans",
            (user_id, day, followers, popularity, deezer_fans))


def list_pulse_snapshots(user_id, limit=90):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM pulse_snapshots WHERE user_id = ? ORDER BY day DESC LIMIT ?",
            (user_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


# --- Team ------------------------------------------------------------------------

def add_team_invite(owner_id, email, role):
    """Create an invite; returns the row or None if already on the team."""
    member_id = uuid.uuid4().hex
    token = uuid.uuid4().hex
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO team_members (id, owner_id, email, role, status, invite_token, created) "
                "VALUES (?,?,?,?,'invited',?,?)",
                (member_id, owner_id, email.lower().strip(), role, token, _now()))
    except sqlite3.IntegrityError:
        return None
    return {"id": member_id, "invite_token": token}


def list_team(owner_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT t.*, u.name AS member_name FROM team_members t "
            "LEFT JOIN users u ON u.id = t.member_user_id "
            "WHERE t.owner_id = ? ORDER BY t.created", (owner_id,)).fetchall()
    return [dict(r) for r in rows]


def get_team_invite(token):
    with get_db() as db:
        row = db.execute(
            "SELECT t.*, u.name AS owner_name FROM team_members t "
            "JOIN users u ON u.id = t.owner_id "
            "WHERE t.invite_token = ? AND t.status = 'invited'", (token,)).fetchone()
    return dict(row) if row else None


def accept_team_invite(token, member_user_id):
    with get_db() as db:
        cur = db.execute(
            "UPDATE team_members SET status = 'active', member_user_id = ?, "
            "joined = ?, invite_token = NULL WHERE invite_token = ? AND status = 'invited'",
            (member_user_id, _now(), token))
    return cur.rowcount > 0


def remove_team_member(owner_id, member_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM team_members WHERE id = ? AND owner_id = ?",
                         (member_id, owner_id))
    return cur.rowcount > 0


# --- Artist Pulse ---------------------------------------------------------------

def save_pulse_profile(user_id, artist_id, artist_name, artist_image=""):
    with get_db() as db:
        db.execute(
            "INSERT INTO pulse_profiles (user_id, artist_id, artist_name, artist_image, updated) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET artist_id=excluded.artist_id, "
            "artist_name=excluded.artist_name, artist_image=excluded.artist_image, "
            "updated=excluded.updated",
            (user_id, artist_id, artist_name, artist_image, _now()),
        )


def get_pulse_profile(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM pulse_profiles WHERE user_id = ?",
                         (user_id,)).fetchone()
    return dict(row) if row else None


def clear_pulse_profile(user_id):
    with get_db() as db:
        db.execute("DELETE FROM pulse_profiles WHERE user_id = ?", (user_id,))


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

# --- Notifications -------------------------------------------------------------

def notify(user_id, kind, title, body="", link=""):
    with get_db() as db:
        db.execute(
            "INSERT INTO notifications (user_id, kind, title, body, link, created)"
            " VALUES (?,?,?,?,?,?)",
            (user_id, kind, title[:200], body[:400], link[:300], _now()))


def list_notifications(user_id, limit=50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def unread_notifications(user_id):
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)).fetchone()
    return row["n"]


def mark_notifications_read(user_id):
    with get_db() as db:
        db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))

# --- Documents vault -----------------------------------------------------------

def add_document(user_id, filename, path, doc_type, note=""):
    doc_id = uuid.uuid4().hex
    with get_db() as db:
        db.execute(
            "INSERT INTO documents (id, user_id, filename, path, doc_type, note, created)"
            " VALUES (?,?,?,?,?,?,?)",
            (doc_id, user_id, filename[:200], path, doc_type[:60], note[:300], _now()))
    return doc_id


def list_documents(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY created DESC",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_document(user_id, doc_id):
    with get_db() as db:
        row = db.execute("SELECT path FROM documents WHERE id = ? AND user_id = ?",
                         (doc_id, user_id)).fetchone()
        if row is None:
            return None
        db.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    return row["path"]

# --- Recovery cases + deal room --------------------------------------------------

def create_recovery_case(user_id, fields):
    case_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO recovery_cases (id, user_id, title, category, estimated_amount,"
            " confidence, status, deadline, notes, created, updated)"
            " VALUES (?,?,?,?,?,?,'open',?,?,?,?)",
            (case_id, user_id, fields.get("title", "Untitled case")[:200],
             fields.get("category", "other")[:40],
             float(fields.get("estimated_amount") or 0),
             fields.get("confidence", "medium")[:10],
             fields.get("deadline", "")[:10], fields.get("notes", "")[:600],
             now, now))
    return case_id


def update_recovery_case(user_id, case_id, fields):
    allowed = ("status", "notes", "deadline", "evidence_doc_id", "payout_result")
    sets, vals = [], []
    for key in allowed:
        if key in fields:
            sets.append("%s = ?" % key)
            vals.append(fields[key])
    if not sets:
        return False
    if fields.get("status") in ("won", "lost", "closed"):
        sets.append("closed_at = ?")
        vals.append(_now())
    sets.append("updated = ?")
    vals.extend([_now(), case_id, user_id])
    with get_db() as db:
        cur = db.execute("UPDATE recovery_cases SET %s WHERE id = ? AND user_id = ?"
                         % ", ".join(sets), vals)
    return cur.rowcount > 0


def list_recovery_cases(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM recovery_cases WHERE user_id = ? ORDER BY"
            " CASE status WHEN 'open' THEN 0 WHEN 'submitted' THEN 1 ELSE 2 END, updated DESC",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_recovery_case(user_id, case_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM recovery_cases WHERE id = ? AND user_id = ?",
                         (case_id, user_id)).fetchone()
    return dict(row) if row else None


def create_deal(user_id, fields):
    deal_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO deals (id, user_id, deal_type, title, counterparty, status,"
            " terms, doc_id, deadline, created, updated) VALUES (?,?,?,?,?,'draft',?,?,?,?,?)",
            (deal_id, user_id, fields.get("deal_type", "split")[:40],
             fields.get("title", "Untitled deal")[:200],
             fields.get("counterparty", "")[:120], fields.get("terms", "")[:600],
             fields.get("doc_id"), fields.get("deadline", "")[:10], now, now))
    return deal_id


def update_deal(user_id, deal_id, fields):
    allowed = ("status", "terms", "deadline", "doc_id", "counterparty")
    sets, vals = [], []
    for key in allowed:
        if key in fields:
            sets.append("%s = ?" % key)
            vals.append(fields[key])
    if not sets:
        return False
    sets.append("updated = ?")
    vals.extend([_now(), deal_id, user_id])
    with get_db() as db:
        cur = db.execute("UPDATE deals SET %s WHERE id = ? AND user_id = ?"
                         % ", ".join(sets), vals)
    return cur.rowcount > 0


def list_deals(user_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM deals WHERE user_id = ? ORDER BY updated DESC",
                          (user_id,)).fetchall()
    return [dict(r) for r in rows]

# --- Sync clearance packs --------------------------------------------------------

def create_sync_pack(user_id, slug, fields):
    pack_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO sync_packs (id, user_id, slug, title, artist_name, bpm, song_key,"
            " moods, master_status, publishing_status, ownership_note, contact_email,"
            " main_url, instrumental_url, clean_url, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pack_id, user_id, slug, fields.get("title", "Untitled")[:150],
             fields.get("artist_name", "")[:120], fields.get("bpm", "")[:10],
             fields.get("song_key", "")[:20], fields.get("moods", "")[:200],
             fields.get("master_status", "unconfirmed")[:20],
             fields.get("publishing_status", "unconfirmed")[:20],
             fields.get("ownership_note", "")[:400],
             fields.get("contact_email", "")[:120],
             fields.get("main_url", ""), fields.get("instrumental_url", ""),
             fields.get("clean_url", ""), now, now))
    return pack_id


def update_sync_pack(user_id, pack_id, fields):
    allowed = ("status", "master_status", "publishing_status", "ownership_note")
    sets, vals = [], []
    for key in allowed:
        if key in fields:
            sets.append("%s = ?" % key)
            vals.append(fields[key])
    if not sets:
        return False
    sets.append("updated = ?")
    vals.extend([_now(), pack_id, user_id])
    with get_db() as db:
        cur = db.execute("UPDATE sync_packs SET %s WHERE id = ? AND user_id = ?"
                         % ", ".join(sets), vals)
    return cur.rowcount > 0


def list_sync_packs(user_id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM sync_packs WHERE user_id = ? ORDER BY updated DESC",
                          (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_sync_pack_by_slug(slug, count_view=False):
    with get_db() as db:
        row = db.execute("SELECT * FROM sync_packs WHERE slug = ?", (slug,)).fetchone()
        if row and count_view:
            db.execute("UPDATE sync_packs SET views = views + 1 WHERE slug = ?", (slug,))
    return dict(row) if row else None

# --- Artist Twin -----------------------------------------------------------------

def save_twin_settings(user_id, sources, tone, do_not_say):
    with get_db() as db:
        db.execute(
            "INSERT INTO twin_settings (user_id, sources, tone, do_not_say, updated)"
            " VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET"
            " sources=excluded.sources, tone=excluded.tone,"
            " do_not_say=excluded.do_not_say, updated=excluded.updated",
            (user_id, json.dumps(sources), tone, do_not_say[:400], _now()))


def get_twin_settings(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM twin_settings WHERE user_id = ?",
                         (user_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["sources"] = json.loads(d["sources"] or "[]")
    return d


def save_twin_generation(user_id, kind, output, sources_used):
    gen_id = uuid.uuid4().hex
    with get_db() as db:
        db.execute(
            "INSERT INTO twin_generations (id, user_id, kind, output, sources_used, created)"
            " VALUES (?,?,?,?,?,?)",
            (gen_id, user_id, kind, output[:2000], sources_used[:200], _now()))
    return gen_id


def list_twin_generations(user_id, limit=20):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM twin_generations WHERE user_id = ? ORDER BY created DESC LIMIT ?",
            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]

# --- Revenue OS expenses ---------------------------------------------------------

def add_expense(user_id, category, description, amount, spend_date=""):
    exp_id = uuid.uuid4().hex
    with get_db() as db:
        db.execute(
            "INSERT INTO revenue_expenses (id, user_id, category, description, amount,"
            " spend_date, created) VALUES (?,?,?,?,?,?,?)",
            (exp_id, user_id, category[:40], description[:200], float(amount),
             spend_date[:10], _now()))
    return exp_id


def list_expenses(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM revenue_expenses WHERE user_id = ?"
            " ORDER BY spend_date DESC, created DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_expense(user_id, exp_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM revenue_expenses WHERE id = ? AND user_id = ?",
                         (exp_id, user_id))
    return cur.rowcount > 0

# --- Spotify pre-saves -----------------------------------------------------------

def add_spotify_presave(campaign_id, spotify_user_id, email, refresh_token_enc):
    """Returns the presave id, or None if this fan already pre-saved."""
    presave_id = uuid.uuid4().hex
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO spotify_presaves (id, campaign_id, spotify_user_id, email,"
                " refresh_token_enc, created) VALUES (?,?,?,?,?,?)",
                (presave_id, campaign_id, spotify_user_id, email,
                 refresh_token_enc, _now()))
    except sqlite3.IntegrityError:
        return None
    return presave_id


def pending_spotify_presaves(campaign_id, limit=10):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM spotify_presaves WHERE campaign_id = ? AND status = 'pending'"
            " AND retry_count < 5 LIMIT ?", (campaign_id, limit)).fetchall()
    return [dict(r) for r in rows]


def resolve_spotify_presave(presave_id, status, error=""):
    with get_db() as db:
        if status == "completed":
            db.execute(
                "UPDATE spotify_presaves SET status='completed', completed_at=?,"
                " refresh_token_enc='' WHERE id = ?", (_now(), presave_id))
        else:
            db.execute(
                "UPDATE spotify_presaves SET retry_count = retry_count + 1, error = ?,"
                " status = CASE WHEN retry_count >= 4 THEN 'failed' ELSE 'pending' END"
                " WHERE id = ?", (error[:200], presave_id))


def count_spotify_presaves(campaign_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT status, COUNT(*) AS n FROM spotify_presaves WHERE campaign_id = ?"
            " GROUP BY status", (campaign_id,)).fetchall()
    return {r["status"]: r["n"] for r in rows}
