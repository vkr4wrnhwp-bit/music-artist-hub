"""Show Passport - the store.

A passport is the technical record a production carries from room to room: who
is on stage, what plugs in where, which mix each performer hears, what plays
back, and what has to happen on a cue. It is the thing a monitor engineer in a
venue nobody has played before reads at 3pm so that 9pm works.

THE SHAPE, AND WHY

The working tables ARE the draft. There is exactly one draft per passport and
it is always editable. Publishing does not move rows anywhere: it serialises
the whole draft into one immutable JSON snapshot in `passport_versions`.

That is the answer to the brief's hardest requirement - "every published
passport must be immutable" and "later passport edits must not silently change
historical shows". If a show pointed at live rows, editing the input list in
March would rewrite what the crew agreed to in January, and nobody would know.
A show points at a VERSION id, and a version is a frozen document. Editing the
draft afterwards cannot reach it.

The cost is duplication - a published snapshot repeats data that is also in the
working tables - and that is the correct trade. Storage is cheap; a technical
rider that quietly changed after it was signed off is not.

Version states are only ever `published`, `superseded` or `archived`, because
those are the states a FROZEN document can be in. "Draft" and "in review" are
states of the passport's working copy, not of a version, so they live on
`passports.review_state`. Modelling a draft as a version would mean a row that
is immutable in name and mutable in fact.
"""
import json
import sqlite3
import uuid

import stage_plot_catalog as catalog

from db import get_db, _now

# --- vocabulary --------------------------------------------------------------

# What a frozen document can be. See the module docstring for why "draft" is
# not in this list.
VERSION_STATES = ("published", "superseded", "archived")

# The working copy's state. A passport in review is still editable - review is
# a request for eyes, not a lock - but the UI says so, and publishing from
# review is the normal path.
REVIEW_STATES = ("draft", "review")

PERSONNEL_KINDS = ("performer", "crew")

# Who may see a contact detail. The brief asks for contact visibility controls
# because a technical rider goes to strangers: a venue tech needs the stage
# manager's phone, and does not need the artist's.
VISIBILITY = ("production", "crew", "private")

OUTPUT_KINDS = ("wedge", "iem", "side", "sub", "other")

PROVIDED_BY = ("artist", "venue", "rental")

DOCUMENT_KINDS = ("rider", "stage_plot", "input_list", "patch_list",
                  "lighting", "playback", "set_list", "advance", "safety",
                  "reference")

# The sections a snapshot carries. Named once here so publish, compare and the
# exports cannot drift apart from each other.
SECTIONS = ("identity", "contacts", "personnel", "stage_plot", "inputs",
            "outputs", "playback", "equipment", "cues", "documents")


def _uid():
    return uuid.uuid4().hex


def _row(r):
    return dict(r) if r else None


# --- schema ------------------------------------------------------------------

def init_passports():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS passports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                artist_name TEXT NOT NULL DEFAULT '',
                production_name TEXT NOT NULL DEFAULT '',
                tour_name TEXT NOT NULL DEFAULT '',
                /* "Theatre", "Festival", "Acoustic" - one passport per format
                   the production actually plays, because a festival input list
                   is not a theatre input list. */
                variant TEXT NOT NULL DEFAULT '',
                territories TEXT NOT NULL DEFAULT '',
                emergency_contact TEXT NOT NULL DEFAULT '',
                review_state TEXT NOT NULL DEFAULT 'draft',
                /* The published version in force. NULL until first publish -
                   a passport that has never been published has no version a
                   show could be advanced against, and that is a real state. */
                current_version_id TEXT,
                last_verified TEXT NOT NULL DEFAULT '',
                archived INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_passports_user
                ON passports(user_id, archived);

            CREATE TABLE IF NOT EXISTS passport_contacts (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'production',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pcontacts ON passport_contacts(passport_id, sort);

            CREATE TABLE IF NOT EXISTS passport_personnel (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'performer',
                name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                instruments TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'crew',
                notes TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ppersonnel ON passport_personnel(passport_id, sort);

            /* NO passport_stage_plot table. The Stage Plot editor
               (/stage-plot, static/js/stageplot.js) already owns the drawing,
               already derives a channel list from it, and already exports the
               PNG the TOUR advance email attaches. A second plot here would be
               a worse copy of a shipped feature. The passport READS that plot
               and freezes it into each published version instead - which gives
               the drawn plot the versioning it never had. */

            CREATE TABLE IF NOT EXISTS passport_inputs (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                performer TEXT NOT NULL DEFAULT '',
                mic_di TEXT NOT NULL DEFAULT '',
                stand TEXT NOT NULL DEFAULT '',
                phantom INTEGER NOT NULL DEFAULT 0,
                patch TEXT NOT NULL DEFAULT '',
                stagebox TEXT NOT NULL DEFAULT '',
                mix_relevance TEXT NOT NULL DEFAULT '',
                required INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pinputs ON passport_inputs(passport_id, sort);

            CREATE TABLE IF NOT EXISTS passport_outputs (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                mix_name TEXT NOT NULL DEFAULT '',
                performer TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'wedge',
                tx_rx TEXT NOT NULL DEFAULT '',
                stereo INTEGER NOT NULL DEFAULT 0,
                output_patch TEXT NOT NULL DEFAULT '',
                talkback TEXT NOT NULL DEFAULT '',
                /* What this mix should be set to before anybody is on stage.
                   The brief calls it "safe starting state" and it is the one
                   field here with a safety meaning, not just a documentation
                   meaning. */
                safe_start TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_poutputs ON passport_outputs(passport_id, sort);

            CREATE TABLE IF NOT EXISTS passport_playback (
                passport_id TEXT PRIMARY KEY,
                system TEXT NOT NULL DEFAULT '',
                primary_device TEXT NOT NULL DEFAULT '',
                redundant_device TEXT NOT NULL DEFAULT '',
                out_format TEXT NOT NULL DEFAULT '',
                sample_rate TEXT NOT NULL DEFAULT '',
                bit_depth TEXT NOT NULL DEFAULT '',
                channel_map TEXT NOT NULL DEFAULT '',
                click TEXT NOT NULL DEFAULT '',
                cues TEXT NOT NULL DEFAULT '',
                tc_type TEXT NOT NULL DEFAULT '',
                tc_fps TEXT NOT NULL DEFAULT '',
                midi_osc TEXT NOT NULL DEFAULT '',
                redundancy TEXT NOT NULL DEFAULT '',
                failure TEXT NOT NULL DEFAULT '',
                updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS passport_equipment (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                item TEXT NOT NULL DEFAULT '',
                provided_by TEXT NOT NULL DEFAULT 'artist',
                substitutions TEXT NOT NULL DEFAULT '',
                power TEXT NOT NULL DEFAULT '',
                network TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pequip ON passport_equipment(passport_id, sort);

            CREATE TABLE IF NOT EXISTS passport_cues (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                song TEXT NOT NULL DEFAULT '',
                cue_no TEXT NOT NULL DEFAULT '',
                cue_type TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                trigger TEXT NOT NULL DEFAULT '',
                confirm_required INTEGER NOT NULL DEFAULT 0,
                fallback TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pcues ON passport_cues(passport_id, sort);

            CREATE TABLE IF NOT EXISTS passport_documents (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'reference',
                title TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                stored_name TEXT NOT NULL DEFAULT '',
                mime TEXT NOT NULL DEFAULT '',
                bytes INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pdocs ON passport_documents(passport_id, created);

            /* The frozen documents. `snapshot` is the whole passport as JSON at
               the moment of publication - never read the working tables to
               render a version. */
            CREATE TABLE IF NOT EXISTS passport_versions (
                id TEXT PRIMARY KEY,
                passport_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                number INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'published',
                snapshot TEXT NOT NULL,
                change_note TEXT NOT NULL DEFAULT '',
                published_by TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL,
                UNIQUE(passport_id, number)
            );
            CREATE INDEX IF NOT EXISTS idx_pversions
                ON passport_versions(passport_id, number DESC);
        """)


# --- passports ---------------------------------------------------------------

def create_passport(user_id, artist_name="", production_name="", **fields):
    pid = _uid()
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO passports (id, user_id, artist_name, production_name, "
            "tour_name, variant, territories, emergency_contact, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, user_id, artist_name.strip(), production_name.strip(),
             (fields.get("tour_name") or "").strip(),
             (fields.get("variant") or "").strip(),
             (fields.get("territories") or "").strip(),
             (fields.get("emergency_contact") or "").strip(), now, now))
    return pid


def get_passport(passport_id, user_id=None):
    """Scoped by user_id whenever a caller has one. Every route does."""
    sql = "SELECT * FROM passports WHERE id = ?"
    args = [passport_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    with get_db() as db:
        return _row(db.execute(sql, args).fetchone())


def list_passports(user_id, include_archived=False):
    sql = "SELECT * FROM passports WHERE user_id = ?"
    if not include_archived:
        sql += " AND archived = 0"
    sql += " ORDER BY updated DESC"
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, (user_id,)).fetchall()]


IDENTITY_FIELDS = ("artist_name", "production_name", "tour_name", "variant",
                   "territories", "emergency_contact", "last_verified")


def update_passport(passport_id, user_id, **fields):
    sets, args = [], []
    for key in IDENTITY_FIELDS:
        if key in fields:
            sets.append("%s = ?" % key)
            args.append((fields[key] or "").strip())
    if "review_state" in fields and fields["review_state"] in REVIEW_STATES:
        sets.append("review_state = ?")
        args.append(fields["review_state"])
    if not sets:
        return False
    sets.append("updated = ?")
    args.extend([_now(), passport_id, user_id])
    with get_db() as db:
        cur = db.execute("UPDATE passports SET %s WHERE id = ? AND user_id = ?"
                         % ", ".join(sets), args)
    return cur.rowcount > 0


def set_archived(passport_id, user_id, archived=True):
    with get_db() as db:
        cur = db.execute(
            "UPDATE passports SET archived = ?, updated = ? WHERE id = ? AND user_id = ?",
            (1 if archived else 0, _now(), passport_id, user_id))
    return cur.rowcount > 0


def _touch(passport_id):
    with get_db() as db:
        db.execute("UPDATE passports SET updated = ? WHERE id = ?", (_now(), passport_id))


# --- the row sections --------------------------------------------------------
# One generic pair rather than eight near-identical ones. The columns each
# section owns are declared here, so an unknown key from a form is dropped
# rather than reaching SQL.

_SECTION_TABLES = {
    "contacts": ("passport_contacts",
                 ("name", "role", "phone", "email", "visibility", "sort")),
    "personnel": ("passport_personnel",
                  ("kind", "name", "role", "instruments", "phone", "email",
                   "visibility", "notes", "sort")),
    "inputs": ("passport_inputs",
               ("channel", "source", "performer", "mic_di", "stand", "phantom",
                "patch", "stagebox", "mix_relevance", "required", "notes", "sort")),
    "outputs": ("passport_outputs",
                ("mix_name", "performer", "kind", "tx_rx", "stereo",
                 "output_patch", "talkback", "safe_start", "notes", "sort")),
    "equipment": ("passport_equipment",
                  ("item", "provided_by", "substitutions", "power", "network",
                   "notes", "sort")),
    "cues": ("passport_cues",
             ("song", "cue_no", "cue_type", "operator", "trigger",
              "confirm_required", "fallback", "notes", "sort")),
}

_INT_COLUMNS = {"phantom", "required", "stereo", "confirm_required", "sort"}


def _clean(section, fields):
    _table, columns = _SECTION_TABLES[section]
    out = {}
    for col in columns:
        if col not in fields:
            continue
        value = fields[col]
        if col in _INT_COLUMNS:
            out[col] = 1 if str(value) not in ("", "0", "False", "false", "None") else 0
        else:
            out[col] = (value or "").strip() if isinstance(value, str) else (value or "")
    return out


def add_row(section, passport_id, **fields):
    table, _cols = _SECTION_TABLES[section]
    data = _clean(section, fields)
    data["id"] = _uid()
    data["passport_id"] = passport_id
    keys = list(data)
    with get_db() as db:
        db.execute("INSERT INTO %s (%s) VALUES (%s)"
                   % (table, ", ".join(keys), ", ".join("?" * len(keys))),
                   [data[k] for k in keys])
    _touch(passport_id)
    return data["id"]


def update_row(section, passport_id, row_id, **fields):
    table, _cols = _SECTION_TABLES[section]
    data = _clean(section, fields)
    if not data:
        return False
    args = list(data.values()) + [row_id, passport_id]
    with get_db() as db:
        cur = db.execute(
            "UPDATE %s SET %s WHERE id = ? AND passport_id = ?"
            % (table, ", ".join("%s = ?" % k for k in data)), args)
    _touch(passport_id)
    return cur.rowcount > 0


def delete_row(section, passport_id, row_id):
    table, _cols = _SECTION_TABLES[section]
    with get_db() as db:
        cur = db.execute("DELETE FROM %s WHERE id = ? AND passport_id = ?"
                         % table, (row_id, passport_id))
    _touch(passport_id)
    return cur.rowcount > 0


def rows_for(section, passport_id):
    return rows(section, passport_id)


def rows(section, passport_id):
    table, _cols = _SECTION_TABLES[section]
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM %s WHERE passport_id = ? ORDER BY sort, rowid" % table,
            (passport_id,)).fetchall()]


# --- the single-row sections -------------------------------------------------

_PLAYBACK_FIELDS = ("system", "primary_device", "redundant_device", "out_format",
                    "sample_rate", "bit_depth", "channel_map", "click", "cues",
                    "tc_type", "tc_fps", "midi_osc", "redundancy", "failure")


def save_playback(passport_id, **fields):
    data = {k: (fields.get(k) or "").strip() for k in _PLAYBACK_FIELDS}
    keys = ["passport_id"] + list(_PLAYBACK_FIELDS) + ["updated"]
    values = [passport_id] + [data[k] for k in _PLAYBACK_FIELDS] + [_now()]
    with get_db() as db:
        db.execute(
            "INSERT INTO passport_playback (%s) VALUES (%s) "
            "ON CONFLICT(passport_id) DO UPDATE SET %s"
            % (", ".join(keys), ", ".join("?" * len(keys)),
               ", ".join("%s = excluded.%s" % (k, k)
                         for k in list(_PLAYBACK_FIELDS) + ["updated"])),
            values)
    _touch(passport_id)
    return True


def get_playback(passport_id):
    with get_db() as db:
        row = _row(db.execute("SELECT * FROM passport_playback WHERE passport_id = ?",
                              (passport_id,)).fetchone())
    return row or dict({k: "" for k in _PLAYBACK_FIELDS},
                       passport_id=passport_id, updated="")


def get_stage_plot(passport_id, user_id=None):
    """The artist's drawn stage plot, from the Stage Plot editor.

    Per USER, not per passport, because that is where the editor keeps it and
    duplicating it here would fork the drawing. `elements` is whatever the
    editor saved; this module never writes it.
    """
    head = get_passport(passport_id, user_id)
    if head is None:
        return {"state": None, "channels": [], "has_plot": False}
    import db as _store
    try:
        state = _store.get_stage_plot(head["user_id"])
    except sqlite3.OperationalError:
        # The Stage Plot editor's table belongs to another module. A passport
        # page must not 500 because that module has not initialised its schema
        # on this deployment - "no plot" is the honest answer, and it is the
        # same answer an artist who has not drawn one gets.
        state = None
    return {"state": state, "channels": catalog.channel_list(state),
            "has_plot": bool(state and (state.get("items") or {}))}


def import_inputs_from_plot(passport_id, user_id=None, replace=False):
    """Seed the input list from the drawn plot.

    The editor already knows a drum kit is seven inputs. Typing that in again
    is work the product can do, so this turns its channel list into structured
    rows - and leaves patch, stagebox and performer BLANK, because the drawing
    does not know them and an invented patch number on a rider is worse than an
    empty one.

    Appends by default. `replace` is offered because re-importing after adding
    a keyboard should be able to rebuild rather than duplicate, but it is never
    the default: it would silently discard mic choices somebody typed by hand.
    """
    plot = get_stage_plot(passport_id, user_id)
    rows = catalog.as_input_rows(plot["state"])
    if not rows:
        return 0
    if replace:
        with get_db() as db:
            db.execute("DELETE FROM passport_inputs WHERE passport_id = ?", (passport_id,))
    else:
        existing = {(r.get("source") or "").lower() for r in rows_for("inputs", passport_id)}
        rows = [r for r in rows if r["source"].lower() not in existing]
    for r in rows:
        add_row("inputs", passport_id, **r)
    return len(rows)


# --- documents ---------------------------------------------------------------

def add_document(passport_id, kind, title, filename, stored_name, mime, size):
    did = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO passport_documents (id, passport_id, kind, title, filename, "
            "stored_name, mime, bytes, created) VALUES (?,?,?,?,?,?,?,?,?)",
            (did, passport_id, kind if kind in DOCUMENT_KINDS else "reference",
             (title or "").strip(), (filename or "").strip(), stored_name,
             (mime or "").strip(), int(size or 0), _now()))
    _touch(passport_id)
    return did


def documents(passport_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM passport_documents WHERE passport_id = ? ORDER BY created DESC",
            (passport_id,)).fetchall()]


def delete_document(passport_id, doc_id):
    with get_db() as db:
        cur = db.execute("DELETE FROM passport_documents WHERE id = ? AND passport_id = ?",
                         (doc_id, passport_id))
    _touch(passport_id)
    return cur.rowcount > 0


# --- snapshots and versions --------------------------------------------------

def build_snapshot(passport_id, user_id=None):
    """The whole passport as a plain dict, ready to freeze or to render.

    Every section named in SECTIONS appears, even when empty, so a consumer
    never has to guess whether a missing key means "no inputs" or "this
    snapshot predates input lists".
    """
    head = get_passport(passport_id, user_id)
    if head is None:
        return None
    return {
        "identity": {k: head.get(k, "") for k in IDENTITY_FIELDS},
        "contacts": rows("contacts", passport_id),
        "personnel": rows("personnel", passport_id),
        "stage_plot": get_stage_plot(passport_id, user_id),
        "inputs": rows("inputs", passport_id),
        "outputs": rows("outputs", passport_id),
        "playback": get_playback(passport_id),
        "equipment": rows("equipment", passport_id),
        "cues": rows("cues", passport_id),
        "documents": documents(passport_id),
    }


def publish(passport_id, user_id, published_by="", change_note=""):
    """Freeze the draft as the next numbered version.

    The previous published version becomes `superseded` in the same
    transaction as the new one is written, so there is never a moment where
    two versions are both current or none is.
    """
    snapshot = build_snapshot(passport_id, user_id)
    if snapshot is None:
        return None
    now = _now()
    vid = _uid()
    # Stamp the verification date INTO the frozen document, not just onto the
    # passport afterwards. A version's "last verified" is the day it was
    # published - that is what the date means on a rider. Stamping only the
    # draft would also make every passport read as having unpublished changes
    # forever, because the next snapshot would differ from the last by this
    # one field.
    snapshot["identity"]["last_verified"] = now[:10]
    with get_db() as db:
        row = db.execute(
            "SELECT MAX(number) AS n FROM passport_versions WHERE passport_id = ?",
            (passport_id,)).fetchone()
        number = int((row["n"] or 0)) + 1
        db.execute(
            "UPDATE passport_versions SET state = 'superseded' "
            "WHERE passport_id = ? AND state = 'published'", (passport_id,))
        db.execute(
            "INSERT INTO passport_versions (id, passport_id, user_id, number, state, "
            "snapshot, change_note, published_by, published_at) "
            "VALUES (?,?,?,?,'published',?,?,?,?)",
            (vid, passport_id, user_id, number, json.dumps(snapshot),
             (change_note or "").strip(), (published_by or "").strip(), now))
        db.execute(
            "UPDATE passports SET current_version_id = ?, review_state = 'draft', "
            "last_verified = ?, updated = ? WHERE id = ? AND user_id = ?",
            (vid, now[:10], now, passport_id, user_id))
    return vid


def get_version(version_id, user_id=None):
    sql = "SELECT * FROM passport_versions WHERE id = ?"
    args = [version_id]
    if user_id:
        sql += " AND user_id = ?"
        args.append(user_id)
    with get_db() as db:
        row = _row(db.execute(sql, args).fetchone())
    if row:
        try:
            row["snapshot"] = json.loads(row["snapshot"])
        except (TypeError, ValueError):
            row["snapshot"] = None
    return row


def versions(passport_id):
    """Newest first. The snapshot is NOT parsed here - a version list renders
    numbers and dates, and parsing every document to draw a list would be
    wasted work on a page that shows none of it."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT id, passport_id, user_id, number, state, change_note, "
            "published_by, published_at FROM passport_versions "
            "WHERE passport_id = ? ORDER BY number DESC", (passport_id,)).fetchall()]


def current_version(passport_id, user_id=None):
    head = get_passport(passport_id, user_id)
    if not head or not head.get("current_version_id"):
        return None
    return get_version(head["current_version_id"], user_id)


def archive_version(version_id, user_id):
    """Archiving is for a version nobody should advance against again. The
    version in force cannot be archived - that would leave the passport
    pointing at a document it is not offering."""
    with get_db() as db:
        row = db.execute("SELECT passport_id, state FROM passport_versions "
                         "WHERE id = ? AND user_id = ?", (version_id, user_id)).fetchone()
        if row is None or row["state"] == "published":
            return False
        cur = db.execute("UPDATE passport_versions SET state = 'archived' "
                         "WHERE id = ? AND user_id = ?", (version_id, user_id))
    return cur.rowcount > 0


# --- comparison --------------------------------------------------------------

def _key_for(section, row):
    """What makes a row "the same row" across two versions. Ids are not usable:
    a row deleted and retyped is a new id but the same channel, and the crew
    reads it as an edit."""
    if section == "inputs":
        return str(row.get("channel") or "") + "|" + str(row.get("source") or "")
    if section == "outputs":
        return str(row.get("mix_name") or "")
    if section == "cues":
        return str(row.get("song") or "") + "|" + str(row.get("cue_no") or "")
    if section in ("personnel", "contacts"):
        return str(row.get("name") or "")
    if section == "equipment":
        return str(row.get("item") or "")
    return row.get("id") or ""


_IGNORED_IN_DIFF = {"id", "passport_id", "sort", "updated", "created"}


def compare(older, newer):
    """What changed between two snapshots, section by section.

    Returns {section: {"added": [...], "removed": [...], "changed": [...]}}.
    A "changed" entry carries the field names that differ, because "the input
    list changed" is not something a monitor engineer can act on and "channel
    12 moved from SM58 to a DI" is.
    """
    out = {}
    for section in SECTIONS:
        a, b = (older or {}).get(section), (newer or {}).get(section)
        if isinstance(a, list) or isinstance(b, list):
            a_map = {_key_for(section, r): r for r in (a or [])}
            b_map = {_key_for(section, r): r for r in (b or [])}
            added = [b_map[k] for k in b_map if k not in a_map]
            removed = [a_map[k] for k in a_map if k not in b_map]
            changed = []
            for k in b_map:
                if k not in a_map:
                    continue
                fields = [f for f in set(list(a_map[k]) + list(b_map[k]))
                          if f not in _IGNORED_IN_DIFF
                          and a_map[k].get(f) != b_map[k].get(f)]
                if fields:
                    changed.append({"key": k, "fields": sorted(fields),
                                    "before": a_map[k], "after": b_map[k]})
            if added or removed or changed:
                out[section] = {"added": added, "removed": removed, "changed": changed}
        else:
            fields = [f for f in set(list(a or {}) + list(b or {}))
                      if f not in _IGNORED_IN_DIFF
                      and (a or {}).get(f) != (b or {}).get(f)]
            if fields:
                out[section] = {"added": [], "removed": [],
                                "changed": [{"key": section, "fields": sorted(fields),
                                             "before": a or {}, "after": b or {}}]}
    return out


def compare_versions(older_id, newer_id, user_id=None):
    a = get_version(older_id, user_id)
    b = get_version(newer_id, user_id)
    if not a or not b:
        return None
    return compare(a.get("snapshot"), b.get("snapshot"))


def draft_differs_from_current(passport_id, user_id=None):
    """Whether there is anything to publish. A publish button that is always
    live teaches people to ignore it."""
    current = current_version(passport_id, user_id)
    if current is None:
        return True
    return bool(compare(current.get("snapshot"), build_snapshot(passport_id, user_id)))


# --- readiness ---------------------------------------------------------------

def gaps(passport_id, user_id=None):
    """What is missing before this is worth sending to a venue.

    Deliberately a list of facts, not a score. A passport that is 80% complete
    is not 80% useful - the missing 20% is what the engineer needed - and a
    percentage here would be exactly the kind of invented metric the honesty
    doctrine forbids.
    """
    snap = build_snapshot(passport_id, user_id)
    if snap is None:
        return []
    out = []
    if not (snap["identity"].get("artist_name") or "").strip():
        out.append("No artist name.")
    if not snap["inputs"]:
        out.append("No input list. A venue cannot patch this show.")
    if not snap["outputs"]:
        out.append("No monitor mixes. Nobody on stage has anything to hear.")
    if not snap["personnel"]:
        out.append("No personnel, so no mix belongs to anybody yet.")
    unnamed = [o for o in snap["outputs"] if not (o.get("performer") or "").strip()]
    if unnamed:
        out.append("%d monitor mix%s not assigned to a performer."
                   % (len(unnamed), "" if len(unnamed) == 1 else "es"))
    no_safe = [o for o in snap["outputs"] if not (o.get("safe_start") or "").strip()]
    if snap["outputs"] and no_safe:
        out.append("%d mix%s with no safe starting state."
                   % (len(no_safe), "" if len(no_safe) == 1 else "es"))
    if not (snap["identity"].get("emergency_contact") or "").strip():
        out.append("No emergency production contact.")
    return out
