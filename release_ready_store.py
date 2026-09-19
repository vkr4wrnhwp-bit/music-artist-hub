"""Release-Ready's tables and every query that touches them.

Five tables:

  release_ready_consents  one row per file an artist handed over: who (the
                          artist account, and the person who ticked the
                          boxes), when, the file's sha256, the consent text
                          version and a hash of the exact words shown
  release_ready_sources   one row per stored upload (a mix, or a vocal and a
                          beat sharing a pair_id)
  release_ready_jobs      one row per piece of RoEx work: a mix report, a
                          mastering preview, a vocal-and-beat recombine. The
                          brief's columns (id, organization_id, user_id,
                          type, roex_task_id, status, credits_estimate,
                          output_url, created_at) plus the working columns
  release_ready_payments  one row per Stripe checkout session claimed, so a
                          session is only ever counted once and a second
                          payment for the same master is caught. It keeps
                          the payment intent, so a refund or a dispute
                          Stripe reports later finds its row and stops
                          counting as revenue
  roex_rate               the RoEx rate limiter's counts (roex_client.init)

Whose rows these are is always user_id = the ARTIST's account
(current_user()), so a team member working inside the account sees and
adds to the artist's work. The person who acted is kept beside it
(created_by, uploaded_by, actor_id).

output_url only ever holds our own owner-checked route. RoEx's own links
expire in 24 hours and are kept server-side in roex_output_url only until
the file is stored with us.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import db
import roex_client

# Statuses a background step may pick up.
ADVANCEABLE = ("queued", "analysing", "processing", "paid", "retrieving")
IN_FLIGHT = ("queued", "analysing", "processing", "paid", "retrieving")
TYPES = ("mix_analysis", "master_preview", "recombine")

_JOB_COLUMNS = (
    "id", "organization_id", "user_id", "type", "roex_task_id", "status",
    "credits_estimate", "output_url", "created_at",
    "created_by", "source_id", "backing_source_id", "settings_json", "result_json",
    "preview_key", "preview_start", "master_key", "master_sha256", "master_bytes",
    "roex_output_url", "roex_output_expires", "credits_spent_estimate",
    "budget_reserved", "budget_month", "budget_artist", "price_cents",
    "checkout_session_id", "paid_session_id", "amount_paid_cents", "paid_at",
    "owner_release_by", "owner_release_at", "retrieve_called_at", "stored_at",
    "os_track_id", "webhook_token_hash", "webhook_seen_at", "webhook_count",
    "attempts", "submitted_at", "next_poll_at", "lease_until", "wait_for_job_id",
    "error_kind", "error_text", "updated_at",
)


def now():
    return datetime.now(timezone.utc)


def iso(t=None):
    return (t or now()).isoformat(timespec="seconds")


def parse(ts):
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def init():
    with db.get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS release_ready_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_email TEXT,
                file_sha256 TEXT NOT NULL,
                filename TEXT,
                role TEXT,
                rights_attested INTEGER NOT NULL,
                licence_granted INTEGER NOT NULL,
                text_version TEXT NOT NULL,
                text_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS release_ready_sources (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                uploaded_by TEXT,
                organization_id TEXT,
                pair_id TEXT,
                role TEXT NOT NULL,
                title TEXT,
                os_track_id TEXT,
                filename TEXT,
                ext TEXT,
                mime_type TEXT,
                storage_key TEXT,
                bytes INTEGER,
                sha256 TEXT,
                duration_s REAL,
                sample_rate INTEGER,
                bit_depth INTEGER,
                channels INTEGER,
                analysis_style TEXT,
                is_master INTEGER,
                consent_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                deleted_at TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_rr_sources_user ON release_ready_sources (user_id, created_at);
            CREATE INDEX IF NOT EXISTS ix_rr_sources_sha ON release_ready_sources (user_id, sha256);
            CREATE TABLE IF NOT EXISTS release_ready_jobs (
                id TEXT PRIMARY KEY,
                organization_id TEXT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                roex_task_id TEXT,
                status TEXT NOT NULL,
                credits_estimate INTEGER,
                output_url TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT,
                source_id TEXT,
                backing_source_id TEXT,
                settings_json TEXT,
                result_json TEXT,
                preview_key TEXT,
                preview_start REAL,
                master_key TEXT,
                master_sha256 TEXT,
                master_bytes INTEGER,
                roex_output_url TEXT,
                roex_output_expires TEXT,
                credits_spent_estimate INTEGER NOT NULL DEFAULT 0,
                budget_reserved INTEGER NOT NULL DEFAULT 0,
                budget_month TEXT,
                budget_artist INTEGER NOT NULL DEFAULT 0,
                price_cents INTEGER,
                checkout_session_id TEXT,
                paid_session_id TEXT,
                amount_paid_cents INTEGER,
                paid_at TEXT,
                owner_release_by TEXT,
                owner_release_at TEXT,
                retrieve_called_at TEXT,
                stored_at TEXT,
                os_track_id TEXT,
                webhook_token_hash TEXT,
                webhook_seen_at TEXT,
                webhook_count INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                submitted_at TEXT,
                next_poll_at TEXT,
                lease_until TEXT,
                wait_for_job_id TEXT,
                error_kind TEXT,
                error_text TEXT,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_rr_jobs_user ON release_ready_jobs (user_id, created_at);
            CREATE INDEX IF NOT EXISTS ix_rr_jobs_due ON release_ready_jobs (status, next_poll_at);
            CREATE INDEX IF NOT EXISTS ix_rr_jobs_source ON release_ready_jobs (source_id);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_rr_jobs_paid_session
                ON release_ready_jobs (paid_session_id) WHERE paid_session_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS release_ready_payments (
                session_id TEXT PRIMARY KEY,
                job_id TEXT,
                user_id TEXT,
                amount_cents INTEGER,
                currency TEXT,
                claimed_at TEXT NOT NULL,
                duplicate INTEGER NOT NULL DEFAULT 0,
                mismatch TEXT,
                payment_intent TEXT,
                refunded_cents INTEGER NOT NULL DEFAULT 0,
                refunded_at TEXT,
                disputed_at TEXT
            );
        """)
        # A database made before these columns existed gets them now.
        have = {r[1] for r in conn.execute("PRAGMA table_info(release_ready_payments)")}
        for col, decl in (("payment_intent", "TEXT"),
                          ("refunded_cents", "INTEGER NOT NULL DEFAULT 0"),
                          ("refunded_at", "TEXT"), ("disputed_at", "TEXT")):
            if col not in have:
                conn.execute("ALTER TABLE release_ready_payments ADD COLUMN %s %s" % (col, decl))
        conn.execute("CREATE INDEX IF NOT EXISTS ix_rr_payments_pi"
                     " ON release_ready_payments (payment_intent)")
    roex_client.init()


# --- rows ---------------------------------------------------------------------------

def _job(row):
    if row is None:
        return None
    d = dict(row)
    d["settings"] = _loads(d.get("settings_json"))
    d["result"] = _loads(d.get("result_json"))
    return d


def _loads(text):
    try:
        val = json.loads(text) if text else {}
    except ValueError:
        val = {}
    return val if isinstance(val, dict) else {}


# --- consents -------------------------------------------------------------------------

def add_consent(user_id, actor_id, actor_email, file_sha256, filename, role,
                text_version, text_sha256):
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO release_ready_consents (user_id, actor_id, actor_email, file_sha256,"
            " filename, role, rights_attested, licence_granted, text_version, text_sha256,"
            " created_at) VALUES (?,?,?,?,?,?,1,1,?,?,?)",
            (user_id, actor_id, (actor_email or "")[:200], file_sha256, (filename or "")[:200],
             role, text_version, text_sha256, iso()))
        return cur.lastrowid


def get_consent(consent_id):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM release_ready_consents WHERE id = ?",
                           (consent_id,)).fetchone()
    return dict(row) if row else None


def consents_for(user_id):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_consents WHERE user_id = ?"
                            " ORDER BY id", (user_id,)).fetchall()
    return [dict(r) for r in rows]


# --- sources ---------------------------------------------------------------------------

def add_source(**f):
    sid = f.get("id") or uuid.uuid4().hex
    cols = ("id", "user_id", "uploaded_by", "organization_id", "pair_id", "role", "title",
            "os_track_id", "filename", "ext", "mime_type", "storage_key", "bytes", "sha256",
            "duration_s", "sample_rate", "bit_depth", "channels", "analysis_style",
            "is_master", "consent_id", "created_at")
    vals = dict(f, id=sid, created_at=iso())
    with db.get_db() as conn:
        conn.execute("INSERT INTO release_ready_sources (%s) VALUES (%s)"
                     % (",".join(cols), ",".join("?" * len(cols))),
                     tuple(vals.get(c) for c in cols))
    return sid


def get_source(source_id):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM release_ready_sources WHERE id = ?",
                           (source_id,)).fetchone()
    return dict(row) if row else None


def source_for(user_id, source_id):
    """The source if it is this account's and not deleted, else None."""
    src = get_source(source_id)
    if not src or src["user_id"] != user_id or src.get("deleted_at"):
        return None
    return src


def pair_sources(user_id, pair_id):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_sources WHERE user_id = ? AND pair_id = ?"
                            " AND deleted_at IS NULL", (user_id, pair_id)).fetchall()
    out = {r["role"]: dict(r) for r in rows}
    return out.get("vocal"), out.get("beat")


def find_same_mix(user_id, sha256, analysis_style, is_master):
    """An earlier upload of the same bytes with the same settings: its
    report is reused, so nobody pays RoEx twice for one file."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM release_ready_sources WHERE user_id = ? AND sha256 = ? AND role = 'mix'"
            " AND analysis_style = ? AND is_master = ? AND deleted_at IS NULL"
            " ORDER BY created_at DESC LIMIT 1",
            (user_id, sha256, analysis_style, 1 if is_master else 0)).fetchone()
    return dict(row) if row else None


def list_sources(user_id, limit=100):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_sources WHERE user_id = ?"
                            " AND deleted_at IS NULL ORDER BY created_at DESC LIMIT ?",
                            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def mark_source_deleted(source_id):
    with db.get_db() as conn:
        conn.execute("UPDATE release_ready_sources SET deleted_at = ?, storage_key = NULL"
                     " WHERE id = ?", (iso(), source_id))


# --- jobs ---------------------------------------------------------------------------------

def add_job(**f):
    jid = f.get("id") or uuid.uuid4().hex
    t = iso()
    vals = dict(f, id=jid, created_at=t, updated_at=t)
    if isinstance(vals.get("settings"), dict):
        vals["settings_json"] = json.dumps(vals.pop("settings"))
    vals.pop("settings", None)
    cols = [c for c in _JOB_COLUMNS if c in vals]
    with db.get_db() as conn:
        conn.execute("INSERT INTO release_ready_jobs (%s) VALUES (%s)"
                     % (",".join(cols), ",".join("?" * len(cols))),
                     tuple(vals[c] for c in cols))
    return jid


def get_job(job_id):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM release_ready_jobs WHERE id = ?", (job_id,)).fetchone()
    return _job(row)


def job_for(user_id, job_id):
    job = get_job(job_id)
    if not job or job["user_id"] != user_id:
        return None
    return job


def update_job(job_id, **f):
    """Set columns on a job. `result` (a dict) is stored as result_json;
    `settings` as settings_json. Only known columns are written."""
    if "result" in f:
        f["result_json"] = json.dumps(f.pop("result"))
    if "settings" in f:
        f["settings_json"] = json.dumps(f.pop("settings"))
    f["updated_at"] = iso()
    cols = [c for c in f if c in _JOB_COLUMNS and c != "id"]
    if not cols:
        return 0
    with db.get_db() as conn:
        cur = conn.execute("UPDATE release_ready_jobs SET %s WHERE id = ?"
                           % ", ".join("%s = ?" % c for c in cols),
                           tuple(f[c] for c in cols) + (job_id,))
        return cur.rowcount


def set_status_if(job_id, from_statuses, **f):
    """Move a job only if it is still in one of from_statuses. Returns
    True when this call moved it."""
    if "result" in f:
        f["result_json"] = json.dumps(f.pop("result"))
    f["updated_at"] = iso()
    cols = [c for c in f if c in _JOB_COLUMNS and c != "id"]
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE release_ready_jobs SET %s WHERE id = ? AND status IN (%s)"
            % (", ".join("%s = ?" % c for c in cols), ",".join("?" * len(from_statuses))),
            tuple(f[c] for c in cols) + (job_id,) + tuple(from_statuses))
        return cur.rowcount == 1


def claim(job_id, seconds):
    """Take the job for one background step. Only one worker or thread
    holds it at a time; a lease that ran out (a restart) can be taken
    again. True when this caller holds it."""
    t = now()
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE release_ready_jobs SET lease_until = ?, updated_at = ?"
            " WHERE id = ? AND (lease_until IS NULL OR lease_until < ?)"
            " AND status IN (%s)" % ",".join("?" * len(ADVANCEABLE)),
            (iso(t + timedelta(seconds=seconds)), iso(t), job_id, iso(t)) + ADVANCEABLE)
        return cur.rowcount == 1


def release_lease(job_id):
    with db.get_db() as conn:
        conn.execute("UPDATE release_ready_jobs SET lease_until = NULL WHERE id = ?", (job_id,))


def jobs_for_source(source_id, types=None):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_jobs WHERE source_id = ?"
                            " ORDER BY created_at, rowid", (source_id,)).fetchall()
    jobs = [_job(r) for r in rows]
    return [j for j in jobs if not types or j["type"] in types]


def list_jobs(user_id, limit=200):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_jobs WHERE user_id = ?"
                            " ORDER BY created_at DESC, rowid DESC LIMIT ?",
                            (user_id, limit)).fetchall()
    return [_job(r) for r in rows]


# A preview that stopped on our side (RoEx out of credits, the key refused,
# no storage, RoEx unreachable) never reached the artist, and the artist
# could do nothing about it: it does not use up their free previews.
_OUR_SIDE = (" NOT (status IN ('credits_short', 'needs_owner') AND preview_key IS NULL"
             " AND paid_at IS NULL)"
             " AND NOT (status = 'failed' AND COALESCE(error_kind, '') IN"
             " ('auth', 'not_connected', 'storage', 'unreachable'))")


def previews_made(source_id, stale_before=None):
    """Previews that count toward the per-file cap: every one asked for,
    except those that failed or were cancelled, those that stopped on our
    side, and (with stale_before) unbought ones made before it, which can
    no longer be bought: the artist is told to make a fresh one."""
    sql = ("SELECT COUNT(*) FROM release_ready_jobs WHERE source_id = ?"
           " AND type IN ('master_preview', 'recombine')"
           " AND status NOT IN ('failed', 'cancelled') AND" + _OUR_SIDE)
    args = [source_id]
    if stale_before:
        sql += (" AND NOT (status = 'preview_ready' AND paid_at IS NULL"
                " AND COALESCE(submitted_at, created_at) < ?)")
        args.append(stale_before)
    with db.get_db() as conn:
        return conn.execute(sql, tuple(args)).fetchone()[0]


def previews_today(user_id):
    """Previews this account asked for in the last day, for the daily cap,
    leaving out those that stopped on our side."""
    since = iso(now() - timedelta(days=1))
    with db.get_db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM release_ready_jobs WHERE user_id = ?"
            " AND type IN ('master_preview', 'recombine') AND created_at >= ? AND" + _OUR_SIDE,
            (user_id, since)).fetchone()[0]


def due_jobs(limit=20, per_artist=4):
    """Jobs whose next step is due and that nobody holds, oldest first; at
    most per_artist in flight for one account, so one artist cannot take
    the whole rate budget."""
    t = iso()
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM release_ready_jobs WHERE status IN (%s)"
            " AND (next_poll_at IS NULL OR next_poll_at <= ?)"
            " AND (lease_until IS NULL OR lease_until < ?)"
            " ORDER BY COALESCE(next_poll_at, created_at) LIMIT ?"
            % ",".join("?" * len(ADVANCEABLE)),
            ADVANCEABLE + (t, t, limit * 4)).fetchall()
        held = {}
        for r in conn.execute("SELECT user_id, COUNT(*) FROM release_ready_jobs"
                              " WHERE lease_until IS NOT NULL AND lease_until >= ?"
                              " GROUP BY user_id", (t,)).fetchall():
            held[r[0]] = r[1]
    out = []
    for r in rows:
        uid = r["user_id"]
        if held.get(uid, 0) >= per_artist:
            continue
        held[uid] = held.get(uid, 0) + 1
        out.append(_job(r))
        if len(out) >= limit:
            break
    return out


def jobs_with_status(statuses, limit=200):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_jobs WHERE status IN (%s)"
                            " ORDER BY created_at LIMIT ?" % ",".join("?" * len(statuses)),
                            tuple(statuses) + (limit,)).fetchall()
    return [_job(r) for r in rows]


def stale_leases():
    """Jobs whose lease ran out mid-step: a restart, or a thread that died."""
    t = iso()
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_jobs WHERE lease_until IS NOT NULL"
                            " AND lease_until < ?", (t,)).fetchall()
    return [_job(r) for r in rows]


def take_reservation(job_id):
    """Take a job's budget reservation off it, once. Returns what was held
    ({user_id, budget_reserved, budget_month, budget_artist}) or None when
    there was nothing, or another step took it first."""
    with db.get_db() as conn:
        row = conn.execute("SELECT user_id, budget_reserved, budget_month, budget_artist"
                           " FROM release_ready_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row or not row["budget_reserved"]:
            return None
        cur = conn.execute("UPDATE release_ready_jobs SET budget_reserved = 0"
                           " WHERE id = ? AND budget_reserved = ?",
                           (job_id, row["budget_reserved"]))
        return dict(row) if cur.rowcount == 1 else None


def touch_webhook(job_id):
    with db.get_db() as conn:
        conn.execute("UPDATE release_ready_jobs SET webhook_seen_at = ?,"
                     " webhook_count = webhook_count + 1, updated_at = ? WHERE id = ?",
                     (iso(), iso(), job_id))


# --- payments ------------------------------------------------------------------------------

def claim_payment(session_id, job_id, user_id, amount_cents, currency, amount_ok,
                  payment_intent=None, fresh=True):
    """Record one paid checkout session and mark the job paid, in one
    transaction, whoever gets here first (the webhook or the redirect).
    Only a job still waiting to be bought (status preview_ready) can be
    marked paid: a job that was cancelled (its upload deleted), already
    stored (the owner released it) or anything else is never sent to RoEx
    for a paid final on the strength of a late payment.

    Returns:
      "paid"       this call marked the job paid
      "already"    this session was claimed before (a replay)
      "mismatch"   recorded, but the amount or currency is not the price
      "duplicate"  recorded, but the job was already paid by another
                   session: money to give back
      "stale"      recorded, but the job can no longer be bought (not
                   preview_ready, or fresh=False: its source link is too
                   old for RoEx to finish it): money to give back
    """
    t = iso()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO release_ready_payments (session_id, job_id, user_id,"
            " amount_cents, currency, claimed_at, payment_intent) VALUES (?,?,?,?,?,?,?)",
            (session_id, job_id, user_id, int(amount_cents or 0), (currency or "")[:8], t,
             (payment_intent or None)))
        if cur.rowcount == 0:
            return "already"
        if not amount_ok:
            conn.execute("UPDATE release_ready_payments SET mismatch = ? WHERE session_id = ?",
                         ("amount", session_id))
            return "mismatch"
        row = conn.execute("SELECT paid_at FROM release_ready_jobs WHERE id = ?",
                           (job_id,)).fetchone()
        if row is not None and row["paid_at"]:
            conn.execute("UPDATE release_ready_payments SET duplicate = 1 WHERE session_id = ?",
                         (session_id,))
            return "duplicate"
        cur = None
        if fresh:
            try:
                cur = conn.execute(
                    "UPDATE release_ready_jobs SET paid_at = ?, paid_session_id = ?,"
                    " amount_paid_cents = ?, status = 'paid', error_kind = NULL,"
                    " error_text = NULL, next_poll_at = ?, updated_at = ?"
                    " WHERE id = ? AND paid_at IS NULL AND roex_task_id IS NOT NULL"
                    " AND type IN ('master_preview', 'recombine') AND status = 'preview_ready'",
                    (t, session_id, int(amount_cents or 0), t, t, job_id))
            except sqlite3.IntegrityError:
                conn.execute("UPDATE release_ready_payments SET duplicate = 1"
                             " WHERE session_id = ?", (session_id,))
                return "duplicate"
        if cur is not None and cur.rowcount == 1:
            return "paid"
        conn.execute("UPDATE release_ready_payments SET mismatch = ? WHERE session_id = ?",
                     ("stale", session_id))
        return "stale"


def mark_money_back(payment_intent, what, refunded_cents=0):
    """Stripe says a payment was refunded (what="refunded", with the
    charge's total refunded so far) or disputed (what="disputed"). Marks
    the matching payment rows and returns them, as they now stand."""
    if not payment_intent:
        return []
    t = iso()
    with db.get_db() as conn:
        if what == "disputed":
            conn.execute("UPDATE release_ready_payments SET disputed_at = COALESCE(disputed_at, ?)"
                         " WHERE payment_intent = ?", (t, payment_intent))
        else:
            conn.execute("UPDATE release_ready_payments SET refunded_cents = ?,"
                         " refunded_at = ? WHERE payment_intent = ?",
                         (max(0, int(refunded_cents or 0)), t, payment_intent))
        rows = conn.execute("SELECT * FROM release_ready_payments WHERE payment_intent = ?",
                            (payment_intent,)).fetchall()
    return [dict(r) for r in rows]


def net_cents(p):
    """What a payment row still brings in: nothing once it is disputed,
    the amount less any refund otherwise."""
    if not p or p.get("disputed_at"):
        return 0
    return max(0, int(p.get("amount_cents") or 0) - int(p.get("refunded_cents") or 0))


def payments(limit=500):
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_payments ORDER BY claimed_at DESC"
                            " LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def payment_for_session(session_id):
    if not session_id:
        return None
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM release_ready_payments WHERE session_id = ?",
                           (session_id,)).fetchone()
    return dict(row) if row else None


def payment_problems():
    """Payments the owner has to act on: paid twice, the wrong amount, too
    late to be used, or disputed."""
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM release_ready_payments WHERE duplicate = 1"
                            " OR mismatch IS NOT NULL OR disputed_at IS NOT NULL"
                            " ORDER BY claimed_at DESC").fetchall()
    return [dict(r) for r in rows]


# --- what other pages read -----------------------------------------------------------------

_TYPE_WORDS = {"mix_analysis": "Mix report", "master_preview": "Master preview",
               "recombine": "Vocal and beat"}


def status_rows(artist_id, limit=50):
    """A label's read-only view of a roster artist's Release-Ready work:
    song, what ran, status and date. No audio, no links, no RoEx data."""
    import release_ready            # the artist-facing words live there
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT j.type, j.status, j.created_at, j.stored_at, j.paid_at, s.title"
            " FROM release_ready_jobs j LEFT JOIN release_ready_sources s ON s.id = j.source_id"
            " WHERE j.user_id = ? ORDER BY j.created_at DESC LIMIT ?",
            (artist_id, limit)).fetchall()
    return [{"song": r["title"] or "Untitled", "what": _TYPE_WORDS.get(r["type"], r["type"]),
             "status": release_ready.chip_for(r["type"], r["status"], bool(r["paid_at"])),
             "date": (r["created_at"] or "")[:10]} for r in rows]


def stored_masters(user_id):
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM release_ready_jobs WHERE user_id = ? AND status = 'stored'"
            " AND master_key IS NOT NULL ORDER BY stored_at DESC", (user_id,)).fetchall()
    return [_job(r) for r in rows]


def masters_by_track(user_id):
    """{os_track_id: job} for every stored master, newest first wins."""
    out = {}
    for job in stored_masters(user_id):
        if job.get("os_track_id") and job["os_track_id"] not in out:
            out[job["os_track_id"]] = job
    return out


# --- the owner's desk -------------------------------------------------------------------------

def all_jobs(limit=5000):
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT j.*, u.name AS artist_name, u.email AS artist_email, u.partner_id AS user_partner"
            " FROM release_ready_jobs j LEFT JOIN users u ON u.id = j.user_id"
            " ORDER BY j.created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_job(r) for r in rows]


def partner_names():
    try:
        with db.get_db() as conn:
            rows = conn.execute("SELECT id, name FROM partners").fetchall()
        return {r["id"]: r["name"] for r in rows}
    except sqlite3.Error:
        return {}
