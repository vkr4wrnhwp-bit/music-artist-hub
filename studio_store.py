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
