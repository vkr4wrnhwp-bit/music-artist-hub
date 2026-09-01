"""Street Banker Studio - the project record, and everything hung off it.

WHAT THIS IS FOR
----------------
A song does not arrive finished. It arrives as a bounce, gets notes, gets
bounced again, gets approved by somebody, gets mastered, gets alternate
versions cut for a sync brief, and then somebody has to say which of the
eleven files on the drive is the one that ships. Street Banker already held
every OTHER part of that story - the release, the credits, the splits, the
rollout, the money - and held nothing at all about which audio file was
current. This module is the missing spine.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It is not a DAW and does not try to be. Nothing here edits audio. The Rack
already previews and renders in the browser; this stores the decisions made
around that - which version, whose approval, what changed, what ships.

TENANCY
-------
Same rule as audio_store, unchanged: every table carries `partner_id`, NULL
means Street Banker itself, and every query filters on it. `inbox` shipped
once with no user_id at all and every account read every row; that is the
precedent for why this is not optional and why the tests check it directly.

WHY THIS EXTENDS audio_assets RATHER THAN ADDING ITS OWN ASSET TABLE
--------------------------------------------------------------------
audio_assets already stores uploaded audio with tenancy, rights status,
consent status, checksum and retention. A second asset table would mean two
answers to "where is this artist's audio", two retention policies, and two
places to fix the next tenancy bug. Studio adds columns to the existing one
instead. The cost is that some columns are meaningless for an Audio Studio
row and some are meaningless for a Studio row; that is cheaper than a fork.

SOURCE IMMUTABILITY
-------------------
An uploaded source is never overwritten and never edited. Every processed
result is a NEW asset carrying parent_asset_id back to what it came from,
so the chain from "what the artist sent" to "what shipped" is walkable in
both directions and cannot be broken by a later render.
"""
import sqlite3
import uuid

from db import get_db, _now

# --- vocabulary --------------------------------------------------------------
# Capability keys extend the Partner OS permission set rather than starting a
# third system. audio_store.CAPS is the precedent.
CAPS = [
    "studio.projects", "studio.upload", "studio.analysis",
    "studio.mix_review", "studio.master_preview", "studio.master_render",
    "studio.album_mode", "studio.delivery", "studio.human_review",
]

PROJECT_TYPES = (
    "stereo_mix_review", "vocal_instrumental", "stem_mix", "master_single",
    "master_project", "remix", "imported_rack",
)

PROJECT_STATUSES = ("draft", "in_progress", "approved", "delivered", "archived")

# The roles a piece of audio can play in a project. Deliberately a closed list:
# "what kind of file is this" is the question the whole Deliver checklist is
# built on, and a free-text field would make it unanswerable.
ASSET_ROLES = (
    "original", "rough_mix", "mix", "approved_mix", "premaster", "master",
    "alternate_master", "clean", "instrumental", "acapella", "tv_track",
    "performance_track", "stem", "reference", "proxy", "spatial_master",
    "immersive_asset", "social_edit", "remix", "other",
)

VERSION_STATUSES = ("draft", "in_review", "approved", "locked", "delivered", "rejected")

FINDING_SEVERITIES = ("blocking", "review", "informational")

# Where a recommendation came from. Every finding must say, because a
# rule-of-thumb presented as a measurement is the failure this whole product
# is supposed to avoid.
EVIDENCE_SOURCES = ("measured", "user_supplied", "reference", "convention", "inferred")
CONFIDENCE_LEVELS = ("strong", "moderate", "limited")


def _uid():
    return uuid.uuid4().hex


def _pk(partner_id):
    """Street Banker itself is '' here, never NULL.

    SQLite treats NULLs as distinct in UNIQUE and PRIMARY KEY constraints, so
    a NULL tenant column silently defeats any uniqueness built on top of it.
    audio_store learned this the hard way; the same convention applies here.
    """
    return partner_id or ""


def _row(r):
    return dict(r) if r is not None else None


# --- schema ------------------------------------------------------------------

_PROJECTS_DDL = """
    CREATE TABLE IF NOT EXISTS studio_projects (
        id TEXT PRIMARY KEY,
        partner_id TEXT,
        partner_key TEXT NOT NULL DEFAULT '',
        user_id TEXT NOT NULL,
        artist_name TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        project_type TEXT NOT NULL DEFAULT 'stereo_mix_review',
        status TEXT NOT NULL DEFAULT 'draft',
        release_id TEXT NOT NULL DEFAULT '',
        track_id TEXT NOT NULL DEFAULT '',
        active_asset_id TEXT NOT NULL DEFAULT '',
        active_version_id TEXT NOT NULL DEFAULT '',
        rights_confirmed_at TEXT,
        rights_confirmed_by TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        archived_at TEXT
    )
"""


def init_studio():
    """Create the Studio schema, then migrate it. Returns the applied steps.

    Returning the steps rather than nothing is the only honest way for a test
    to tell whether a migration ran: SQLite reuses freed page numbers after a
    drop-and-rename, so a table's rootpage can be identical either side of a
    full rebuild and a test watching rootpage passes while the schema is
    quietly being copied on every boot.
    """
    with get_db() as db:
        db.executescript(_PROJECTS_DDL + ";")
        db.executescript("""
            CREATE INDEX IF NOT EXISTS idx_st_proj_user
                ON studio_projects(user_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_st_proj_partner
                ON studio_projects(partner_key, updated_at);

            -- A version is a decision about an asset, not a copy of it. The
            -- asset holds the bytes; this holds who said it was ready.
            CREATE TABLE IF NOT EXISTS studio_versions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                asset_id TEXT NOT NULL DEFAULT '',
                version_number INTEGER NOT NULL DEFAULT 1,
                version_name TEXT NOT NULL DEFAULT '',
                asset_role TEXT NOT NULL DEFAULT 'mix',
                status TEXT NOT NULL DEFAULT 'draft',
                parent_version_id TEXT NOT NULL DEFAULT '',
                change_summary TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at TEXT,
                locked_at TEXT,
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_ver_project
                ON studio_versions(project_id, version_number);

            -- One row per analyzer run. analyzer_version is stored because a
            -- measurement is only comparable against another from the same
            -- code, and "the numbers changed" must be answerable with "the
            -- analyzer changed" rather than a shrug.
            CREATE TABLE IF NOT EXISTS studio_analysis (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                analyzer_name TEXT NOT NULL DEFAULT '',
                analyzer_version TEXT NOT NULL DEFAULT '',
                analysis_type TEXT NOT NULL DEFAULT 'technical',
                measurements TEXT NOT NULL DEFAULT '{}',
                findings TEXT NOT NULL DEFAULT '[]',
                confidence TEXT NOT NULL DEFAULT '{}',
                warnings TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_analysis_asset
                ON studio_analysis(asset_id, created_at);

            -- A finding always carries its evidence and where that evidence
            -- came from. A recommendation with no source is an opinion, and
            -- this product does not present opinions as measurements.
            CREATE TABLE IF NOT EXISTS studio_findings (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                start_seconds REAL,
                end_seconds REAL,
                severity TEXT NOT NULL DEFAULT 'informational',
                evidence_source TEXT NOT NULL DEFAULT 'measured',
                confidence TEXT NOT NULL DEFAULT 'moderate',
                measured_evidence TEXT NOT NULL DEFAULT '{}',
                explanation TEXT NOT NULL DEFAULT '',
                recommendation TEXT NOT NULL DEFAULT '',
                missing_inputs TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'open',
                resolved_by_version_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_find_asset
                ON studio_findings(asset_id, start_seconds);

            -- Comments are pinned to an ASSET, not a project: a note about
            -- 1:42 of Mix 3 is meaningless against Mix 4, and letting it
            -- follow the project would silently re-point it at audio nobody
            -- was listening to when they wrote it.
            CREATE TABLE IF NOT EXISTS studio_comments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL DEFAULT '',
                start_seconds REAL NOT NULL DEFAULT 0,
                end_seconds REAL,
                body TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'note',
                status TEXT NOT NULL DEFAULT 'open',
                assigned_to TEXT NOT NULL DEFAULT '',
                parent_comment_id TEXT NOT NULL DEFAULT '',
                resolved_by TEXT NOT NULL DEFAULT '',
                resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_comment_asset
                ON studio_comments(asset_id, start_seconds);

            CREATE TABLE IF NOT EXISTS studio_approvals (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                version_id TEXT NOT NULL DEFAULT '',
                partner_key TEXT NOT NULL DEFAULT '',
                approval_type TEXT NOT NULL DEFAULT 'mix',
                requested_from TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                note TEXT NOT NULL DEFAULT '',
                asset_checksum TEXT NOT NULL DEFAULT '',
                requested_by TEXT NOT NULL DEFAULT '',
                responded_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_appr_project
                ON studio_approvals(project_id, created_at);

            -- Append-only. Nothing in this module updates or deletes a
            -- provenance row; the point of the table is that it records what
            -- happened even when what happened was a mistake.
            -- Who is on this record. A member row can bind to an accepted
            -- team_members row (then that person can OPEN the project) or be
            -- a named credit with no login. Access is re-checked per request
            -- against BOTH rows, so removing either ends it immediately - the
            -- Partner OS rule, applied here.
            CREATE TABLE IF NOT EXISTS studio_members (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                owner_user_id TEXT NOT NULL,
                team_member_id TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'collaborator',
                added_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_members_project
                ON studio_members(project_id, created_at);

            CREATE TABLE IF NOT EXISTS studio_provenance (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT NOT NULL DEFAULT '',
                partner_key TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL,
                actor_id TEXT NOT NULL DEFAULT '',
                service_actor TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_st_prov_project
                ON studio_provenance(project_id, created_at);
        """)
        return _migrate(db)


def _add_column(db, table, column, decl, applied, step):
    """ALTER TABLE ADD COLUMN, once. CREATE TABLE IF NOT EXISTS does nothing
    at all to a table that already exists, so a column added to the DDL above
    never reaches a database created before it."""
    try:
        cols = {r[1] for r in db.execute("PRAGMA table_info(%s)" % table).fetchall()}
    except sqlite3.OperationalError:
        return          # table absent on this deployment; nothing to migrate
    if not cols or column in cols:
        return
    db.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))
    applied.append(step)


def _migrate(db):
    """Bring an existing schema up to date. Returns the steps applied, which
    is empty on a database that is already current.

    ROLLBACK: every step here is an additive ALTER TABLE ADD COLUMN with a
    default. Nothing is dropped, renamed or retyped, so an older build reading
    this database simply ignores the new columns. To roll back, deploy the
    previous revision - no down-migration is required. See docs/STUDIO.md.
    """
    applied = []

    # Studio's columns on the shared asset table. Added rather than forked so
    # there is one answer to "where is this artist's audio".
    for column, decl, step in (
        ("parent_asset_id", "TEXT NOT NULL DEFAULT ''", "asset_parent"),
        ("asset_role", "TEXT NOT NULL DEFAULT ''", "asset_role"),
        ("version_label", "TEXT NOT NULL DEFAULT ''", "asset_version_label"),
        ("sha256", "TEXT NOT NULL DEFAULT ''", "asset_sha256"),
        ("proxy_storage_key", "TEXT NOT NULL DEFAULT ''", "asset_proxy"),
        ("waveform_storage_key", "TEXT NOT NULL DEFAULT ''", "asset_waveform"),
        ("sample_rate", "INTEGER", "asset_sample_rate"),
        ("channels", "INTEGER", "asset_channels"),
        ("bit_depth", "INTEGER", "asset_bit_depth"),
        ("lossless", "INTEGER NOT NULL DEFAULT 0", "asset_lossless"),
    ):
        _add_column(db, "audio_assets", column, decl, applied, step)

    return applied


# --- projects ----------------------------------------------------------------

def create_project(partner_id, user_id, title, project_type="stereo_mix_review",
                   artist_name="", release_id="", track_id="", created_by=""):
    if project_type not in PROJECT_TYPES:
        project_type = "stereo_mix_review"
    pid = _uid()
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_projects (id, partner_id, partner_key, user_id,"
            " artist_name, title, project_type, status, release_id, track_id,"
            " created_by, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,'draft',?,?,?,?,?)",
            (pid, partner_id, _pk(partner_id), user_id, artist_name, title,
             project_type, release_id, track_id, created_by or user_id, now, now))
    record_event(partner_id, pid, "", "project.created", actor_id=created_by or user_id)
    return pid


def get_project(partner_id, user_id, project_id):
    """Both keys required. A project id alone is not an authorisation, and a
    lookup that accepts one invites every caller to forget the check."""
    with get_db() as db:
        return _row(db.execute(
            "SELECT * FROM studio_projects"
            " WHERE id = ? AND partner_key = ? AND user_id = ? AND archived_at IS NULL",
            (project_id, _pk(partner_id), user_id)).fetchone())


def list_projects(partner_id, user_id, limit=100, include_archived=False):
    sql = ("SELECT * FROM studio_projects"
           " WHERE partner_key = ? AND user_id = ?")
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY updated_at DESC LIMIT ?"
    with get_db() as db:
        return [dict(r) for r in
                db.execute(sql, (_pk(partner_id), user_id, limit)).fetchall()]


def update_project(partner_id, user_id, project_id, **fields):
    allowed = {"title", "status", "release_id", "track_id", "artist_name",
               "active_asset_id", "active_version_id", "project_type"}
    sets, args = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("%s = ?" % key)
            args.append(value)
    if not sets:
        return False
    sets.append("updated_at = ?")
    args.extend([_now(), project_id, _pk(partner_id), user_id])
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_projects SET %s"
            " WHERE id = ? AND partner_key = ? AND user_id = ?" % ", ".join(sets), args)
        return cur.rowcount > 0


def archive_project(partner_id, user_id, project_id):
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_projects SET archived_at = ?, updated_at = ?"
            " WHERE id = ? AND partner_key = ? AND user_id = ?",
            (_now(), _now(), project_id, _pk(partner_id), user_id))
    return cur.rowcount > 0


def confirm_rights(partner_id, user_id, project_id, confirmed_by):
    """Recorded with who and when, not as a boolean. The question asked later
    is 'what exactly did they confirm, and when', and a flag cannot answer it."""
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_projects"
            " SET rights_confirmed_at = ?, rights_confirmed_by = ?, updated_at = ?"
            " WHERE id = ? AND partner_key = ? AND user_id = ?",
            (_now(), confirmed_by, _now(), project_id, _pk(partner_id), user_id))
    if cur.rowcount:
        record_event(partner_id, project_id, "", "rights.confirmed",
                     actor_id=confirmed_by)
    return cur.rowcount > 0


# --- versions ----------------------------------------------------------------

def create_version(partner_id, user_id, project_id, asset_id, asset_role="mix",
                   version_name="", parent_version_id="", change_summary="",
                   created_by=""):
    """A new version never overwrites the one before it.

    version_number is derived from what already exists rather than passed in,
    so two callers racing cannot both claim to be version 4 - and a caller
    cannot renumber history by supplying a number.
    """
    if asset_role not in ASSET_ROLES:
        asset_role = "other"
    with get_db() as db:
        row = db.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS n FROM studio_versions"
            " WHERE project_id = ?", (project_id,)).fetchone()
        number = (row["n"] if row else 0) + 1
        vid = _uid()
        db.execute(
            "INSERT INTO studio_versions (id, project_id, partner_key, user_id,"
            " asset_id, version_number, version_name, asset_role, status,"
            " parent_version_id, change_summary, created_by, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,'draft',?,?,?,?)",
            (vid, project_id, _pk(partner_id), user_id, asset_id, number,
             version_name or ("Version %d" % number), asset_role,
             parent_version_id, change_summary, created_by or user_id, _now()))
    record_event(partner_id, project_id, asset_id, "version.created",
                 actor_id=created_by or user_id)
    return vid


def get_version(partner_id, project_id, version_id):
    with get_db() as db:
        return _row(db.execute(
            "SELECT * FROM studio_versions"
            " WHERE id = ? AND project_id = ? AND partner_key = ?",
            (version_id, project_id, _pk(partner_id))).fetchone())


def list_versions(partner_id, project_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM studio_versions"
            " WHERE project_id = ? AND partner_key = ?"
            " ORDER BY version_number DESC",
            (project_id, _pk(partner_id))).fetchall()]


def set_version_status(partner_id, project_id, version_id, status,
                       actor_id="", note=""):
    """Refuses to change a locked version.

    Locking is the whole point of the vault: 'this exact file is the one that
    ships'. A lock that a later status write can silently step over is not a
    lock, so the guard is in the WHERE clause rather than in the caller.
    """
    if status not in VERSION_STATUSES:
        return False
    now = _now()
    sets = ["status = ?"]
    args = [status]
    if status == "approved":
        sets += ["approved_by = ?", "approved_at = ?"]
        args += [actor_id, now]
    if status == "locked":
        sets.append("locked_at = ?")
        args.append(now)
    if note:
        sets.append("change_summary = ?")
        args.append(note)
    args += [version_id, project_id, _pk(partner_id)]
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_versions SET %s"
            " WHERE id = ? AND project_id = ? AND partner_key = ?"
            "   AND locked_at IS NULL" % ", ".join(sets), args)
    if cur.rowcount:
        record_event(partner_id, project_id, "", "version." + status,
                     actor_id=actor_id)
    return cur.rowcount > 0


# --- provenance --------------------------------------------------------------

def record_event(partner_id, project_id, asset_id, event_type,
                 actor_id="", service_actor="", payload="{}"):
    """Append-only. Never updated, never deleted by this module."""
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_provenance (id, project_id, asset_id, partner_key,"
            " event_type, actor_id, service_actor, payload, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (_uid(), project_id, asset_id, _pk(partner_id), event_type,
             actor_id, service_actor, payload, _now()))


def provenance(partner_id, project_id, limit=200):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM studio_provenance"
            " WHERE project_id = ? AND partner_key = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (project_id, _pk(partner_id), limit)).fetchall()]


# --- assets ------------------------------------------------------------------

def create_studio_asset(partner_id, user_id, project_id, storage_key,
                        file_name="", mime_type="", file_size=0, sha256="",
                        asset_role="original", parent_asset_id="",
                        version_label="", sample_rate=None, channels=None,
                        bit_depth=None, lossless=0, duration_ms=None):
    """One asset row, in the table the rest of the audio product already uses.

    asset_role is the Studio question - is this the source, a mix, a master,
    an instrumental - and it is what the whole Deliver checklist is built on.
    audio_assets.asset_type stays as it was for Audio Studio rows.
    """
    import audio_store as astore

    if asset_role not in ASSET_ROLES:
        asset_role = "other"
    asset_id = astore.create_asset(
        partner_id, user_id, storage_key, file_name=file_name,
        mime_type=mime_type, file_size=file_size, duration_ms=duration_ms,
        checksum=sha256, asset_type="source", project_type="studio",
        project_id=project_id)
    with get_db() as db:
        db.execute(
            "UPDATE audio_assets SET parent_asset_id = ?, asset_role = ?,"
            " version_label = ?, sha256 = ?, sample_rate = ?, channels = ?,"
            " bit_depth = ?, lossless = ? WHERE id = ?",
            (parent_asset_id, asset_role, version_label, sha256, sample_rate,
             channels, bit_depth, 1 if lossless else 0, asset_id))
    record_event(partner_id, project_id, asset_id, "asset.uploaded",
                 actor_id=user_id)
    return asset_id


def get_studio_asset(partner_id, user_id, asset_id):
    """Ownership re-checked here rather than trusted from the caller. A
    separated vocal is the artist's master taken apart; an asset id is not an
    authorisation to hear it."""
    with get_db() as db:
        return _row(db.execute(
            "SELECT * FROM audio_assets"
            " WHERE id = ? AND owner_user_id = ? AND deleted_at IS NULL"
            "   AND COALESCE(partner_id, '') = ?",
            (asset_id, user_id, _pk(partner_id))).fetchone())


def list_project_assets(partner_id, user_id, project_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM audio_assets"
            " WHERE project_id = ? AND owner_user_id = ?"
            "   AND COALESCE(partner_id, '') = ? AND deleted_at IS NULL"
            " ORDER BY created_at",
            (project_id, user_id, _pk(partner_id))).fetchall()]


def project_summary(partner_id, user_id, project_id):
    """Everything the Session page states as fact, computed rather than
    asserted. A page that hard-codes "no unresolved notes" is wrong the moment
    somebody leaves one."""
    versions = list_versions(partner_id, project_id)
    assets = list_project_assets(partner_id, user_id, project_id)
    with get_db() as db:
        open_notes = db.execute(
            "SELECT COUNT(*) AS n FROM studio_comments"
            " WHERE project_id = ? AND partner_key = ? AND status = 'open'",
            (project_id, _pk(partner_id))).fetchone()["n"]
    approved = [v for v in versions if v["status"] in ("approved", "locked")]
    return {
        "versions": versions,
        "assets": assets,
        "open_notes": open_notes,
        "approved_mix": next(
            (v for v in approved if v["asset_role"] in ("mix", "approved_mix")), None),
        "approved_master": next(
            (v for v in approved if v["asset_role"] in ("master", "approved_master")), None),
        "source": next((a for a in assets if a["asset_role"] == "original"), None),
    }


# --- analysis and findings ---------------------------------------------------

def save_analysis(partner_id, user_id, project_id, asset_id, measurements,
                  analyzer_name="rack/loudness.js+tempokey.js",
                  analyzer_version="BS.1770-4"):
    """Store one measurement run, and derive its findings.

    The numbers arrive from the browser because that is where the audio is
    decoded - the same BS.1770-4 engine the Rack uses, plus the tempo and key
    detectors. The RULINGS are derived here rather than in the page, so the
    thresholds live in one place and a finding cannot be softened by whoever
    is rendering it.
    """
    import audio_readiness
    import json as _json

    analysis_id = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_analysis (id, project_id, asset_id, partner_key,"
            " analyzer_name, analyzer_version, analysis_type, measurements,"
            " findings, confidence, warnings, created_at)"
            " VALUES (?,?,?,?,?,?,'technical',?,?,?,?,?)",
            (analysis_id, project_id, asset_id, _pk(partner_id), analyzer_name,
             analyzer_version, _json.dumps(measurements), "[]", "{}", "[]",
             _now()))

        # Findings are replaced, not appended: they describe THIS measurement
        # of THIS asset, and stale ones would read as current.
        db.execute("DELETE FROM studio_findings WHERE asset_id = ?"
                   "  AND partner_key = ?", (asset_id, _pk(partner_id)))
        verdict = audio_readiness.assess(measurements)
        # Where a ruling has a measured moment - the loudest 3-second window,
        # the hottest momentary block - it is pinned there, so the console can
        # seek to it. A ruling with no time stays a whole-file card: pinning
        # it at 0:00 would send somebody listening for a problem at a place
        # it is not.
        # true_peak is deliberately NOT pinned: peak_at is the centre of the
        # loudest momentary block, which is where the ENERGY peaks - the true
        # peak sample can sit anywhere, and a marker saying "true peak here"
        # at the wrong bar sends somebody hunting in the wrong place.
        ruling_times = {
            "loudness": measurements.get("loudest_at"),
            "peak_section": measurements.get("peak_at"),
        }
        for ruling in verdict["rulings"]:
            if ruling["level"] == "ok":
                continue
            at = ruling_times.get(ruling["key"])
            db.execute(
                "INSERT INTO studio_findings (id, project_id, asset_id,"
                " partner_key, category, start_seconds, severity,"
                " evidence_source, confidence,"
                " measured_evidence, explanation, recommendation, status,"
                " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'open',?)",
                (_uid(), project_id, asset_id, _pk(partner_id), ruling["key"],
                 at if isinstance(at, (int, float)) else None,
                 {"problem": "blocking", "watch": "review",
                  "unknown": "informational"}.get(ruling["level"], "informational"),
                 "measured" if ruling["level"] != "unknown" else "inferred",
                 "strong" if ruling["level"] != "unknown" else "limited",
                 _json.dumps({"evidence": ruling["evidence"]}),
                 ruling["headline"] + " " + (ruling["detail"] or ""),
                 ruling["action"] or "", _now()))
    record_event(partner_id, project_id, asset_id, "analysis.completed",
                 actor_id=user_id)
    return analysis_id


def latest_analysis(partner_id, asset_id):
    import json as _json

    with get_db() as db:
        row = _row(db.execute(
            "SELECT * FROM studio_analysis WHERE asset_id = ? AND partner_key = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (asset_id, _pk(partner_id))).fetchone())
    if row:
        try:
            row["measurements"] = _json.loads(row["measurements"] or "{}")
        except ValueError:
            row["measurements"] = {}
    return row


def list_findings(partner_id, asset_id):
    import json as _json

    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM studio_findings WHERE asset_id = ? AND partner_key = ?"
            " ORDER BY CASE severity WHEN 'blocking' THEN 0"
            "   WHEN 'review' THEN 1 ELSE 2 END, created_at",
            (asset_id, _pk(partner_id))).fetchall()]
    for row in rows:
        try:
            row["measured_evidence"] = _json.loads(row["measured_evidence"] or "{}")
        except ValueError:
            row["measured_evidence"] = {}
    return rows


def resolve_finding(partner_id, user_id, finding_id, status="resolved"):
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_findings SET status = ? WHERE id = ? AND partner_key = ?",
            (status, finding_id, _pk(partner_id)))
    return cur.rowcount > 0


# --- comments ----------------------------------------------------------------

def add_comment(partner_id, user_id, project_id, asset_id, author_name, body,
                start_seconds=0.0, category="note", duration_seconds=None,
                assigned_to=""):
    """A comment is pinned to an ASSET and a time.

    Refused if the timestamp is outside the recording: a note at 4:12 of a
    three-minute mix is a note nobody can act on, and letting it through means
    somebody goes looking for a problem that is not there.
    """
    start = max(0.0, float(start_seconds or 0))
    if duration_seconds and start > float(duration_seconds):
        return None
    if not (body or "").strip():
        return None
    comment_id = _uid()
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_comments (id, project_id, asset_id, partner_key,"
            " author_id, author_name, start_seconds, body, category, status,"
            " assigned_to, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,'open',?,?,?)",
            (comment_id, project_id, asset_id, _pk(partner_id), user_id,
             author_name[:120], start, body.strip()[:2000], category,
             assigned_to[:64], now, now))
    return comment_id


def list_comments(partner_id, asset_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM studio_comments WHERE asset_id = ? AND partner_key = ?"
            " ORDER BY start_seconds",
            (asset_id, _pk(partner_id))).fetchall()]


def resolve_comment(partner_id, user_id, comment_id, reopen=False):
    with get_db() as db:
        cur = db.execute(
            "UPDATE studio_comments SET status = ?, resolved_by = ?,"
            " resolved_at = ?, updated_at = ? WHERE id = ? AND partner_key = ?",
            ("open" if reopen else "resolved", "" if reopen else user_id,
             None if reopen else _now(), _now(), comment_id, _pk(partner_id)))
    return cur.rowcount > 0


# --- approvals and delivery --------------------------------------------------

def record_approval(partner_id, user_id, project_id, asset_id, version_id,
                    checksum="", approval_type="master", note=""):
    """An approval names the bytes it approved.

    Storing the checksum is the whole point: "approved on the 3rd" is a memory,
    "approved sha256 9f2c..." is a fact that survives somebody re-uploading a
    different file under the same name.
    """
    approval_id = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_approvals (id, project_id, asset_id, version_id,"
            " partner_key, approval_type, status, note, asset_checksum,"
            " requested_by, responded_at, created_at)"
            " VALUES (?,?,?,?,?,?,'approved',?,?,?,?,?)",
            (approval_id, project_id, asset_id, version_id, _pk(partner_id),
             approval_type, note, checksum, user_id, _now(), _now()))
    record_event(partner_id, project_id, asset_id, "version.approved",
                 actor_id=user_id)
    return approval_id


def list_approvals(partner_id, project_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM studio_approvals WHERE project_id = ?"
            "  AND partner_key = ? ORDER BY created_at",
            (project_id, _pk(partner_id))).fetchall()]


def delivery_checklist(partner_id, user_id, project_id):
    """Every line computed from what the project actually holds.

    A checklist that hard-codes a tick is worse than no checklist: it says a
    thing is done at the exact moment somebody stops being able to check.
    Each entry is {key, label, ok, required, detail}.
    """
    project = get_project(partner_id, user_id, project_id)
    if project is None:
        return []
    summary = project_summary(partner_id, user_id, project_id)
    versions = summary["versions"]
    locked = [v for v in versions if v["status"] == "locked"]
    approved = [v for v in versions if v["status"] in ("approved", "locked")]

    findings = []
    analysis = None
    if summary["source"]:
        findings = list_findings(partner_id, summary["source"]["id"])
        analysis = latest_analysis(partner_id, summary["source"]["id"])
    blocking = [f for f in findings
                if f["severity"] == "blocking" and f["status"] == "open"]
    open_notes = summary["open_notes"]

    def line(key, label, ok, required, detail):
        return {"key": key, "label": label, "ok": bool(ok),
                "required": required, "detail": detail}

    return [
        line("source", "A source is uploaded", summary["source"], True,
             summary["source"]["file_name"] if summary["source"]
             else "Nothing has been uploaded to this project."),
        line("rights", "Rights are confirmed", project["rights_confirmed_at"],
             True,
             ("Confirmed by %s" % project["rights_confirmed_by"])
             if project["rights_confirmed_at"]
             else "Nobody has confirmed the rights to this recording."),
        line("measured", "The audio has been measured", analysis, True,
             "Measured to BS.1770-4 in the browser." if analysis
             else "Run the measurement on the Mix or Master page."),
        line("blocking", "No blocking problems are open", not blocking, True,
             "Nothing blocking." if not blocking
             else "%d blocking finding%s still open."
                  % (len(blocking), "" if len(blocking) == 1 else "s")),
        line("locked", "A version is locked", locked, True,
             ("%s is locked." % locked[0]["version_name"]) if locked
             else "Lock the version that ships, in the Version Vault."),
        line("title", "The project has a title", (project["title"] or "").strip(),
             True, project["title"] or "Untitled."),
        line("artist", "An artist is named",
             (project["artist_name"] or "").strip(), False,
             project["artist_name"] or "No artist set on this project."),
        line("approved_any", "Something is approved", approved, False,
             "%d approved." % len(approved) if approved
             else "Nothing has been approved yet."),
        line("notes", "Notes are resolved", open_notes == 0, False,
             "All resolved." if open_notes == 0
             else "%d note%s still open." % (open_notes,
                                             "" if open_notes == 1 else "s")),
        line("release", "Linked to a release",
             (project["release_id"] or "").strip(), False,
             project["release_id"] or "Not linked to a release yet."),
    ]


def build_package(partner_id, user_id, project_id, read_bytes):
    """A zip: the locked audio, a manifest, a checksum manifest, provenance.

    `read_bytes` is passed in rather than imported, so this function does not
    need to know where audio lives - the blueprint owns that, and this owns
    what belongs in the package.

    The checksum manifest is what makes the package checkable later. A
    distributor who receives it can prove the file they got is the file that
    was approved, which is the whole reason to record a checksum at approval
    time rather than at delivery time.
    """
    import io as _io
    import json as _json
    import zipfile

    project = get_project(partner_id, user_id, project_id)
    summary = project_summary(partner_id, user_id, project_id)
    versions = summary["versions"]
    locked = [v for v in versions if v["status"] == "locked"]
    approvals = list_approvals(partner_id, project_id)

    buffer = _io.BytesIO()
    included, checksums = [], []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for version in locked:
            asset = get_studio_asset(partner_id, user_id, version["asset_id"])
            if asset is None:
                continue
            data = read_bytes(asset)
            if not data:
                # Recorded as missing rather than skipped in silence. A package
                # that is quietly one file short is worse than one that says so.
                included.append({"version": version["version_name"],
                                 "file": asset["file_name"],
                                 "included": False,
                                 "reason": "the bytes could not be read"})
                continue
            name = "audio/%s" % (asset["file_name"] or "master.wav")
            archive.writestr(name, data)
            included.append({"version": version["version_name"],
                             "file": name, "included": True,
                             "asset_role": asset["asset_role"],
                             "bytes": len(data)})
            checksums.append("%s  %s" % (asset["sha256"] or "", name))

        manifest = {
            "project": {
                "id": project["id"],
                "title": project["title"],
                "artist": project["artist_name"],
                "type": project["project_type"],
                "release_id": project["release_id"],
                "track_id": project["track_id"],
            },
            "rights": {
                "confirmed_by": project["rights_confirmed_by"],
                "confirmed_at": project["rights_confirmed_at"],
            },
            "versions": [{
                "number": v["version_number"], "name": v["version_name"],
                "role": v["asset_role"], "status": v["status"],
                "approved_by": v["approved_by"], "approved_at": v["approved_at"],
                "locked_at": v["locked_at"], "change": v["change_summary"],
            } for v in versions],
            "approvals": [{
                "type": a["approval_type"], "status": a["status"],
                "checksum": a["asset_checksum"], "at": a["responded_at"],
            } for a in approvals],
            "files": included,
            "generated_at": _now(),
            "generated_by": "Street Banker Studio",
        }
        archive.writestr("manifest.json", _json.dumps(manifest, indent=2))
        archive.writestr("checksums.sha256", "\n".join(checksums) + "\n")
        archive.writestr("provenance.json", _json.dumps(
            provenance(partner_id, project_id, limit=500), indent=2))

    record_event(partner_id, project_id, "", "delivery.package_built",
                 actor_id=user_id)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-"
                   for ch in (project["title"] or "project"))[:60] or "project"
    return buffer.getvalue(), "%s-delivery.zip" % safe


# --- the team ----------------------------------------------------------------

MEMBER_ROLES = ("artist", "producer", "mix_engineer", "mastering_engineer",
                "manager", "a_and_r", "label_admin", "viewer", "collaborator")


def add_member(partner_id, owner_user_id, project_id, display_name, role,
               team_member_id="", added_by=""):
    """A member is a credit; a member bound to an accepted team row is also
    ACCESS. The distinction is real and the panel says which is which."""
    if role not in MEMBER_ROLES:
        role = "collaborator"
    member_id = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO studio_members (id, project_id, partner_key,"
            " owner_user_id, team_member_id, display_name, role, added_by,"
            " created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (member_id, project_id, _pk(partner_id), owner_user_id,
             team_member_id, display_name[:120], role,
             added_by or owner_user_id, _now()))
    record_event(partner_id, project_id, "", "team.member_added",
                 actor_id=added_by or owner_user_id)
    return member_id


def list_members(partner_id, project_id):
    """Members with their live access state, joined against team_members so a
    revoked team seat reads as credit-only THIS request, not eventually."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT sm.*, tm.email AS team_email, tm.status AS team_status,"
            "       tm.member_user_id AS team_user_id"
            " FROM studio_members sm"
            " LEFT JOIN team_members tm ON tm.id = sm.team_member_id"
            " WHERE sm.project_id = ? AND sm.partner_key = ?"
            " ORDER BY sm.created_at",
            (project_id, _pk(partner_id))).fetchall()]


def remove_member(partner_id, owner_user_id, project_id, member_id):
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM studio_members WHERE id = ? AND project_id = ?"
            "  AND partner_key = ? AND owner_user_id = ?",
            (member_id, project_id, _pk(partner_id), owner_user_id))
    if cur.rowcount:
        record_event(partner_id, project_id, "", "team.member_removed",
                     actor_id=owner_user_id)
    return cur.rowcount > 0


def get_project_shared(partner_id, user_id, project_id):
    """The project, for its owner OR a live collaborator.

    Returns (project, role) where role is "owner" or the member's role, or
    (None, None). Collaborator access requires the WHOLE chain to be alive
    right now - the studio_members row, the team_members row it binds to,
    that row ACTIVE (the team system's word for accepted), and its member_user_id equal to the caller - so
    removing any link ends access on the very next request.
    """
    project = get_project(partner_id, user_id, project_id)
    if project is not None:
        return project, "owner"
    with get_db() as db:
        row = db.execute(
            "SELECT sm.role, sp.* FROM studio_members sm"
            " JOIN team_members tm ON tm.id = sm.team_member_id"
            "   AND tm.status = 'active' AND tm.member_user_id = ?"
            " JOIN studio_projects sp ON sp.id = sm.project_id"
            "   AND sp.archived_at IS NULL"
            " WHERE sm.project_id = ? AND sm.partner_key = ?",
            (user_id, project_id, _pk(partner_id))).fetchone()
    if row is None:
        return None, None
    data = dict(row)
    role = data.pop("role")
    return data, role


def list_shared_projects(partner_id, user_id):
    """Projects shared WITH this account through a live team binding."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT sp.*, sm.role AS my_role FROM studio_members sm"
            " JOIN team_members tm ON tm.id = sm.team_member_id"
            "   AND tm.status = 'active' AND tm.member_user_id = ?"
            " JOIN studio_projects sp ON sp.id = sm.project_id"
            "   AND sp.archived_at IS NULL"
            " WHERE sm.partner_key = ?"
            " ORDER BY sp.updated_at DESC",
            (user_id, _pk(partner_id))).fetchall()]
