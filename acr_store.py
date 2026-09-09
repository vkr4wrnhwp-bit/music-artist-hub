"""What the ACRCloud desk remembers: registrations, scans, and scan hits.

Three tables, and one rule shared by all of them.

REGISTRATIONS ARE FACTS ABOUT ACRCLOUD, NOT INTENTIONS. A row in
`acr_registrations` means ACRCloud answered with an id for that file. A refusal
writes nothing at all - not a "failed" row, not a "pending" row - because a
list of registrations that contains things that were never registered is worse
than a shorter list. What failed and why is told to the person who pressed the
button, in ACRCloud's own words, and then it is gone; pressing again is the
retry, and there is nothing stale to clean up.

NEVER TWICE. `UNIQUE(user_id, vault_file_id)` is the guarantee, not a check in
the route. Two tabs, a double-click and a resubmitted POST all end at the same
constraint, and the second one is caught and reported as "already registered"
rather than sending the master a second time and paying for it twice.

A HIT IS THEIRS UNTIL IT IS PROVED MINE. `acr_scan_hits.mine` is not written
from the vendor's answer. It is computed at read time by matching the hit's
acrid against this account's own registrations, so a master registered after a
scan ran lights up on the scan that already happened, and a registration
deleted stops lighting one. A stored boolean would have frozen the first
answer and been wrong from then on.
"""

import uuid

from db import get_db, _now

# Vault kinds this desk will send. A photo or a contract is not a recording,
# and the picker must not offer one.
REGISTERABLE_KINDS = ("master", "stems")

# Extensions ACRCloud fingerprints. The vault stores whatever was uploaded, so
# the filter is on the file, not only on the label somebody typed.
AUDIO_EXTS = ("wav", "mp3", "m4a", "aac", "flac", "ogg", "aif", "aiff", "wma")


def init_acr():
    with get_db() as db:
        db.executescript("""
            /* One row per (account, vault file) that ACRCloud accepted.
               acr_audio_id is their `data.id`, the handle for the audio
               inside the bucket; acr_id is their `data.acr_id`, the
               fingerprint identity a scan reports back. They are different
               strings and both are kept: the first addresses the file, the
               second is what a detection is matched on. */
            CREATE TABLE IF NOT EXISTS acr_registrations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                vault_file_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                bucket_id TEXT NOT NULL DEFAULT '',
                bucket_name TEXT NOT NULL DEFAULT '',
                acr_audio_id TEXT NOT NULL DEFAULT '',
                acr_id TEXT NOT NULL DEFAULT '',
                state INTEGER,
                state_word TEXT NOT NULL DEFAULT '',
                bytes_sent INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                UNIQUE(user_id, vault_file_id)
            );
            CREATE INDEX IF NOT EXISTS idx_acr_reg_user
                ON acr_registrations(user_id, created);
            CREATE INDEX IF NOT EXISTS idx_acr_reg_acrid
                ON acr_registrations(user_id, acr_id);

            /* One long recording handed to a file-scanning container.
               job_id is acr_console's "<container>:<file>" pair. */
            CREATE TABLE IF NOT EXISTS acr_scans (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_id TEXT NOT NULL DEFAULT '',
                container_id TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                source_kind TEXT NOT NULL DEFAULT 'file',
                state TEXT NOT NULL DEFAULT 'queued',
                message TEXT NOT NULL DEFAULT '',
                hits INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_acr_scan_user
                ON acr_scans(user_id, created);

            /* One detected track. Offsets are the RECORDING's clock in
               milliseconds - where in the file the owner scrubs to - and the
               db_* pair beside them is where inside the released track the
               match sits. Both are stored so neither has to be guessed back
               out of the other. */
            CREATE TABLE IF NOT EXISTS acr_scan_hits (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                acrid TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                artists TEXT NOT NULL DEFAULT '',
                album TEXT NOT NULL DEFAULT '',
                label TEXT NOT NULL DEFAULT '',
                isrc TEXT NOT NULL DEFAULT '',
                start_ms INTEGER,
                end_ms INTEGER,
                db_begin_ms INTEGER,
                db_end_ms INTEGER,
                score INTEGER,
                kind TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_acr_hit_scan
                ON acr_scan_hits(scan_id, start_ms);
        """)


# --- registrations -------------------------------------------------------------

def registration_for(user_id, vault_file_id):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM acr_registrations WHERE user_id = ? AND vault_file_id = ?",
            (user_id, vault_file_id)).fetchone()
    return dict(row) if row else None


def list_registrations(user_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM acr_registrations WHERE user_id = ? ORDER BY created DESC",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def record_registration(user_id, vault_file_id, answer, title="", filename="",
                        bucket_name="", bytes_sent=0):
    """Write the row ACRCloud's answer earned. Returns the row, or None when
    this file is already registered - the caller says so rather than sending
    the audio again."""
    import sqlite3
    reg_id = uuid.uuid4().hex
    now = _now()
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO acr_registrations (id, user_id, vault_file_id, title,"
                " filename, bucket_id, bucket_name, acr_audio_id, acr_id, state,"
                " state_word, bytes_sent, created, updated)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (reg_id, user_id, vault_file_id, (title or "")[:200],
                 (filename or "")[:200], str(answer.get("bucket_id") or "")[:80],
                 (bucket_name or "")[:120], str(answer.get("audio_id") or "")[:80],
                 str(answer.get("acr_id") or "")[:120], answer.get("state"),
                 (answer.get("state_word") or "")[:40], int(bytes_sent or 0),
                 now, now))
    except sqlite3.IntegrityError:
        return None
    return registration_for(user_id, vault_file_id)


def update_registration_state(user_id, reg_id, state, state_word):
    with get_db() as db:
        db.execute(
            "UPDATE acr_registrations SET state = ?, state_word = ?, updated = ?"
            " WHERE id = ? AND user_id = ?",
            (state, (state_word or "")[:40], _now(), reg_id, user_id))


def registered_acr_ids(user_id):
    """Every fingerprint identity this account owns, lowercased.

    Both columns, because a match can come back naming either: a custom-bucket
    detection reports the `acr_id`, and some answers carry the audio id in the
    user_defined block instead. Matching on the union is the difference
    between the lamp lighting and the owner never seeing their own record.
    """
    out = set()
    for row in list_registrations(user_id):
        for value in (row.get("acr_id"), row.get("acr_audio_id")):
            if value:
                out.add(str(value).strip().lower())
    return out


# --- scans ---------------------------------------------------------------------

def create_scan(user_id, job_id, container_id, source_name, source_kind="file",
                state="queued", message=""):
    scan_id = uuid.uuid4().hex
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO acr_scans (id, user_id, job_id, container_id, source_name,"
            " source_kind, state, message, hits, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (scan_id, user_id, (job_id or "")[:200], (container_id or "")[:80],
             (source_name or "")[:200], (source_kind or "file")[:20],
             (state or "queued")[:20], (message or "")[:400], now, now))
    return scan_id


def get_scan(user_id, scan_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM acr_scans WHERE id = ? AND user_id = ?",
                         (scan_id, user_id)).fetchone()
    return dict(row) if row else None


def list_scans(user_id, limit=50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM acr_scans WHERE user_id = ? ORDER BY created DESC LIMIT ?",
            (user_id, int(limit))).fetchall()
    return [dict(r) for r in rows]


def set_scan_state(user_id, scan_id, state, message=""):
    with get_db() as db:
        db.execute(
            "UPDATE acr_scans SET state = ?, message = ?, updated = ?"
            " WHERE id = ? AND user_id = ?",
            ((state or "")[:20], (message or "")[:400], _now(), scan_id, user_id))


def replace_hits(user_id, scan_id, hits):
    """A scan's results, rewritten whole.

    Rewritten rather than appended because a refresh asks ACRCloud the same
    question again: appending would double every hit on the second press, and
    a scan has exactly one true answer at any moment.
    """
    now = _now()
    with get_db() as db:
        db.execute("DELETE FROM acr_scan_hits WHERE scan_id = ? AND user_id = ?",
                   (scan_id, user_id))
        for hit in hits or []:
            db.execute(
                "INSERT INTO acr_scan_hits (id, scan_id, user_id, acrid, title,"
                " artists, album, label, isrc, start_ms, end_ms, db_begin_ms,"
                " db_end_ms, score, kind, created)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, scan_id, user_id,
                 (hit.get("acrid") or "")[:120], (hit.get("title") or "")[:300],
                 (hit.get("artists") or "")[:300], (hit.get("album") or "")[:300],
                 (hit.get("label") or "")[:200], (hit.get("isrc") or "")[:40],
                 hit.get("start_ms"), hit.get("end_ms"), hit.get("db_begin_ms"),
                 hit.get("db_end_ms"), hit.get("score"),
                 (hit.get("kind") or "")[:40], now))
        db.execute("UPDATE acr_scans SET hits = ?, updated = ? WHERE id = ? AND user_id = ?",
                   (len(hits or []), now, scan_id, user_id))


def list_hits(user_id, scan_id):
    """The scan's hits, each marked `mine` against today's registrations.

    See the module docstring: `mine` is computed here every time rather than
    stored, so the lamp tells the truth about the account as it is now.
    """
    mine = registered_acr_ids(user_id)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM acr_scan_hits WHERE scan_id = ? AND user_id = ?"
            " ORDER BY CASE WHEN start_ms IS NULL THEN 1 ELSE 0 END, start_ms",
            (scan_id, user_id)).fetchall()
    out = []
    for row in rows:
        hit = dict(row)
        hit["mine"] = bool(hit.get("acrid")
                           and str(hit["acrid"]).strip().lower() in mine)
        out.append(hit)
    return out


def count_mine(hits):
    return sum(1 for h in hits or [] if h.get("mine"))


# --- what the vault offers -----------------------------------------------------

def eligible_vault_files(vault_rows, registrations):
    """The masters and stems that could be registered, each marked with the
    registration it already has.

    The filter is deliberately narrow. A vault holds contracts, cover art and
    press photos beside the audio, and a button offering to fingerprint a PDF
    would be the page lying about what it can do.
    """
    by_file = {r["vault_file_id"]: r for r in registrations or []}
    out = []
    for row in vault_rows or []:
        kind = (row.get("kind") or "").strip().lower()
        name = (row.get("path") or "").split("?")[0]
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if kind not in REGISTERABLE_KINDS or ext not in AUDIO_EXTS:
            continue
        item = dict(row)
        item["registration"] = by_file.get(row.get("id"))
        out.append(item)
    return out


def evidence_line(scan, hit):
    """The sentence a usage case carries instead of a bare amount.

    A case with no evidence is a note to self. This one names the file, the
    moment inside it, the confidence ACRCloud reported and the ISRC when
    there was one - everything a person would need to check the claim
    themselves, months later, without this page in front of them.
    """
    import acr_console
    where = acr_console.clock(hit.get("start_ms"))
    until = acr_console.clock(hit.get("end_ms"))
    span = where if not until else "%s-%s" % (where, until)
    parts = ["ACRCloud file scan of \"%s\" detected \"%s\"%s%s."
             % (scan.get("source_name") or "an uploaded recording",
                hit.get("title") or "an untitled recording",
                " by %s" % hit["artists"] if hit.get("artists") else "",
                " at %s" % span if span else "")]
    if hit.get("score") is not None:
        parts.append("ACRCloud's confidence was %d out of 100." % hit["score"])
    else:
        parts.append("ACRCloud reported no confidence figure.")
    if hit.get("isrc"):
        parts.append("ISRC %s." % hit["isrc"])
    if hit.get("acrid"):
        parts.append("ACRCloud id %s." % hit["acrid"])
    parts.append("It matches a master registered to this account's ACRCloud "
                 "bucket, so the recording used here is one of yours.")
    return " ".join(parts)


def case_fields(scan, hit):
    """Title and note for `/royalty-recovery/cases/from-finding`.

    Amount stays 0 and the form says so: nothing here measures money.
    An MLC gap can be priced - the title's own statement earnings are
    what is at risk behind an unregistered work - but somebody else's
    use of your master is not measured by anything this account holds,
    and a case with an invented figure on it is worse than one with none.
    """
    title = "Your master detected in %s: %s" % (
        scan.get("source_name") or "a scanned recording",
        hit.get("title") or "an untitled recording")
    return title[:200], evidence_line(scan, hit)

