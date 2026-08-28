"""Street Banker Live - sets, scenes, stems and MIDI mappings.

WHAT THIS IS
------------
The server half of Live Lab. The audio half is `static/js/livelab.js`, the
engine bundled out of the TypeScript packages that were written in the wrong
repository: scene scheduling with launch quantisation, the stem deck with
solo/mute resolution, MIDI parsing and Learn, and the offline performance
cache. None of that runs here. It cannot: exact-time scene launching needs an
AudioContext, and MIDI needs the browser's own device list.

So this module stores decisions and serves bytes, which is all a stage rig
actually needs from a server. The audit of the original build put it plainly:
Live Lab does no server-side audio processing at all.

TENANCY
-------
Same rule as everywhere else: `partner_id` for the tenant (NULL means Street
Banker itself, stored as '' so SQLite's NULL-is-distinct behaviour cannot
defeat a uniqueness constraint) plus `user_id` for the owner, and every query
filters on both. `inbox` shipped once with no user_id and every account read
every row; that is why the tests here check it directly.

WHY STEMS POINT AT THE VAULT RATHER THAN COPYING
------------------------------------------------
A stem row records a vault path, not a second copy of the audio. One set of
bytes, listed in two places - the same rule the Audio Studio follows when it
hands stems to the Rack. Copying would double the storage on a disk that is
already shared with the database, and let the two drift apart.
"""
import json
import sqlite3
import uuid

from db import get_db, _now

# Capability keys, extending the Partner OS set rather than starting another.
CAPS = ["live.sets", "live.perform", "live.midi", "live.offline_package"]

# These four lists are the engine's own zod enums, copied exactly. It
# validates the project when it loads, so a value it does not recognise is a
# set that refuses to open - and a venue is the worst place to discover that.
# Source: packages/performance-project/src/types.ts in the extraction.
FOLLOW_ACTIONS = ("stop", "loop", "next_scene", "target")
QUANTIZATIONS = ("none", "1/4", "1/2", "1bar", "2bars", "4bars", "scene_end")
SCENE_TYPES = ("intro", "verse", "pre_chorus", "chorus", "break", "build",
               "drop", "bridge", "interlude", "outro", "custom")
STEM_TYPES = ("vocal", "drums", "bass", "music", "fx", "click", "custom")
OUTPUT_TYPES = ("master", "cue", "click", "stem", "custom")

# What a MIDI control can be pointed at. Kept in step with the engine's
# control targets; an unknown target is refused rather than stored, because a
# mapping that resolves to nothing is a dead pad somebody will hit on stage.
MIDI_TARGETS = (
    "scene_launch", "scene_stop", "transport_start", "transport_stop",
    "tap_tempo", "stem_volume", "stem_mute", "stem_solo", "master_volume",
    "click_toggle", "panic",
)


def _uid():
    return uuid.uuid4().hex


def _pk(partner_id):
    return partner_id or ""


def _row(r):
    return dict(r) if r is not None else None


def init_live():
    """Create the schema, then migrate. Returns the steps applied - empty on a
    database that is already current. Asserting on reported steps is the only
    honest idempotency check: SQLite reuses freed page numbers, so a test that
    watches rootpage passes while the schema is rebuilt on every boot."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS live_sets (
                id TEXT PRIMARY KEY,
                partner_key TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                venue TEXT NOT NULL DEFAULT '',
                show_date TEXT NOT NULL DEFAULT '',
                tempo_bpm REAL NOT NULL DEFAULT 120,
                time_sig_num INTEGER NOT NULL DEFAULT 4,
                time_sig_den INTEGER NOT NULL DEFAULT 4,
                click_enabled INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_live_sets_user
                ON live_sets(user_id, updated_at);

            CREATE TABLE IF NOT EXISTS live_scenes (
                id TEXT PRIMARY KEY,
                set_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL DEFAULT '',
                tempo_bpm REAL,
                bars INTEGER NOT NULL DEFAULT 0,
                follow_action TEXT NOT NULL DEFAULT 'stop',
                quantization TEXT NOT NULL DEFAULT '1bar',
                scene_type TEXT NOT NULL DEFAULT 'custom',
                loop_enabled INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_live_scenes_set
                ON live_scenes(set_id, position);

            -- A stem is a pointer at a vault file plus the deck settings for
            -- it. The audio itself is never copied here.
            CREATE TABLE IF NOT EXISTS live_stems (
                id TEXT PRIMARY KEY,
                scene_id TEXT NOT NULL,
                set_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                stem_type TEXT NOT NULL DEFAULT 'custom',
                vault_file_id TEXT NOT NULL DEFAULT '',
                storage_path TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0,
                gain REAL NOT NULL DEFAULT 1,
                pan REAL NOT NULL DEFAULT 0,
                muted INTEGER NOT NULL DEFAULT 0,
                soloed INTEGER NOT NULL DEFAULT 0,
                output_bus TEXT NOT NULL DEFAULT 'master',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_live_stems_scene
                ON live_stems(scene_id, position);

            CREATE TABLE IF NOT EXISTS live_midi_maps (
                id TEXT PRIMARY KEY,
                set_id TEXT NOT NULL,
                partner_key TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                message_type TEXT NOT NULL DEFAULT 'note_on',
                channel INTEGER NOT NULL DEFAULT 0,
                data1 INTEGER NOT NULL DEFAULT 0,
                target TEXT NOT NULL DEFAULT '',
                target_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_live_midi_set
                ON live_midi_maps(set_id, created_at);
        """)
        return _migrate(db)


def _migrate(db):
    """Additive only. ALTER TABLE ADD COLUMN with a default, never a drop or a
    retype, so rolling back means deploying the previous revision and nothing
    else. CREATE TABLE IF NOT EXISTS does nothing to a table that exists, which
    is why structural changes belong here rather than in the DDL above."""
    applied = []
    for table, column, decl, step in (
        ("live_sets", "click_enabled", "INTEGER NOT NULL DEFAULT 1", "sets_click"),
        ("live_stems", "output_bus", "TEXT NOT NULL DEFAULT 'master'", "stems_bus"),
    ):
        try:
            cols = {r[1] for r in db.execute("PRAGMA table_info(%s)" % table)}
        except sqlite3.OperationalError:
            continue
        if cols and column not in cols:
            db.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))
            applied.append(step)
    return applied


# --- sets --------------------------------------------------------------------

def create_set(partner_id, user_id, name, venue="", show_date="", tempo_bpm=120.0):
    sid = _uid()
    now = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO live_sets (id, partner_key, user_id, name, venue,"
            " show_date, tempo_bpm, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, _pk(partner_id), user_id, name[:160], venue[:160],
             show_date[:32], float(tempo_bpm or 120), now, now))
    return sid


def get_set(partner_id, user_id, set_id):
    """Both keys required. A set id is not an authorisation."""
    with get_db() as db:
        return _row(db.execute(
            "SELECT * FROM live_sets WHERE id = ? AND partner_key = ?"
            "  AND user_id = ? AND archived_at IS NULL",
            (set_id, _pk(partner_id), user_id)).fetchone())


def list_sets(partner_id, user_id, limit=100):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM live_sets WHERE partner_key = ? AND user_id = ?"
            "  AND archived_at IS NULL ORDER BY updated_at DESC LIMIT ?",
            (_pk(partner_id), user_id, limit)).fetchall()]


def update_set(partner_id, user_id, set_id, **fields):
    allowed = {"name", "venue", "show_date", "tempo_bpm", "time_sig_num",
               "time_sig_den", "click_enabled", "notes"}
    sets, args = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("%s = ?" % key)
            args.append(value)
    if not sets:
        return False
    sets.append("updated_at = ?")
    args += [_now(), set_id, _pk(partner_id), user_id]
    with get_db() as db:
        cur = db.execute(
            "UPDATE live_sets SET %s WHERE id = ? AND partner_key = ?"
            "  AND user_id = ?" % ", ".join(sets), args)
    return cur.rowcount > 0


def archive_set(partner_id, user_id, set_id):
    with get_db() as db:
        cur = db.execute(
            "UPDATE live_sets SET archived_at = ?, updated_at = ?"
            " WHERE id = ? AND partner_key = ? AND user_id = ?",
            (_now(), _now(), set_id, _pk(partner_id), user_id))
    return cur.rowcount > 0


# --- scenes ------------------------------------------------------------------

def add_scene(partner_id, user_id, set_id, name, bars=0, follow_action="stop",
              quantization="1bar", scene_type="custom", tempo_bpm=None,
              loop_enabled=0):
    """Values the engine does not recognise are corrected here, not stored.

    The engine validates the project with zod when it loads it, so an unknown
    follow action or quantization is not a cosmetic problem - it is a set that
    refuses to open.
    """
    if follow_action not in FOLLOW_ACTIONS:
        follow_action = "stop"
    if quantization not in QUANTIZATIONS:
        quantization = "1bar"
    if scene_type not in SCENE_TYPES:
        scene_type = "custom"
    with get_db() as db:
        row = db.execute(
            "SELECT COALESCE(MAX(position), -1) AS p FROM live_scenes"
            " WHERE set_id = ?", (set_id,)).fetchone()
        position = (row["p"] if row else -1) + 1
        scene_id = _uid()
        db.execute(
            "INSERT INTO live_scenes (id, set_id, partner_key, user_id, position,"
            " name, tempo_bpm, bars, follow_action, quantization, scene_type,"
            " loop_enabled, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (scene_id, set_id, _pk(partner_id), user_id, position, name[:160],
             tempo_bpm, int(bars or 0), follow_action, quantization, scene_type,
             1 if loop_enabled else 0, _now()))
    return scene_id


def list_scenes(partner_id, user_id, set_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM live_scenes WHERE set_id = ? AND partner_key = ?"
            "  AND user_id = ? ORDER BY position",
            (set_id, _pk(partner_id), user_id)).fetchall()]


def delete_scene(partner_id, user_id, set_id, scene_id):
    with get_db() as db:
        db.execute("DELETE FROM live_stems WHERE scene_id = ? AND user_id = ?"
                   "  AND partner_key = ?",
                   (scene_id, user_id, _pk(partner_id)))
        cur = db.execute(
            "DELETE FROM live_scenes WHERE id = ? AND set_id = ?"
            "  AND partner_key = ? AND user_id = ?",
            (scene_id, set_id, _pk(partner_id), user_id))
    return cur.rowcount > 0


# --- stems -------------------------------------------------------------------

def add_stem(partner_id, user_id, set_id, scene_id, name, vault_file_id="",
             storage_path="", output_bus="master", stem_type="custom"):
    with get_db() as db:
        row = db.execute(
            "SELECT COALESCE(MAX(position), -1) AS p FROM live_stems"
            " WHERE scene_id = ?", (scene_id,)).fetchone()
        position = (row["p"] if row else -1) + 1
        stem_id = _uid()
        db.execute(
            "INSERT INTO live_stems (id, scene_id, set_id, partner_key, user_id,"
            " name, stem_type, vault_file_id, storage_path, position,"
            " output_bus, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (stem_id, scene_id, set_id, _pk(partner_id), user_id, name[:160],
             stem_type if stem_type in STEM_TYPES else "custom",
             vault_file_id, storage_path, position, output_bus, _now()))
    return stem_id


def list_stems(partner_id, user_id, scene_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM live_stems WHERE scene_id = ? AND partner_key = ?"
            "  AND user_id = ? ORDER BY position",
            (scene_id, _pk(partner_id), user_id)).fetchall()]


def set_stem(partner_id, user_id, stem_id, **fields):
    allowed = {"gain", "pan", "muted", "soloed", "output_bus", "name"}
    sets, args = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append("%s = ?" % key)
            args.append(value)
    if not sets:
        return False
    args += [stem_id, _pk(partner_id), user_id]
    with get_db() as db:
        cur = db.execute(
            "UPDATE live_stems SET %s WHERE id = ? AND partner_key = ?"
            "  AND user_id = ?" % ", ".join(sets), args)
    return cur.rowcount > 0


def delete_stem(partner_id, user_id, stem_id):
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM live_stems WHERE id = ? AND partner_key = ? AND user_id = ?",
            (stem_id, _pk(partner_id), user_id))
    return cur.rowcount > 0


# --- MIDI --------------------------------------------------------------------

def add_mapping(partner_id, user_id, set_id, label, message_type, channel,
                data1, target, target_id=""):
    """Refuses a target it does not know.

    The engine's MIDI Learn refuses a target-less mapping rather than storing a
    dead one, and this is the server half of the same rule: a pad that resolves
    to nothing is a pad somebody hits on stage and nothing happens.
    """
    if target not in MIDI_TARGETS:
        return None
    mapping_id = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO live_midi_maps (id, set_id, partner_key, user_id, label,"
            " message_type, channel, data1, target, target_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (mapping_id, set_id, _pk(partner_id), user_id, label[:120],
             message_type[:32], int(channel or 0), int(data1 or 0), target,
             target_id, _now()))
    return mapping_id


def list_mappings(partner_id, user_id, set_id):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM live_midi_maps WHERE set_id = ? AND partner_key = ?"
            "  AND user_id = ? ORDER BY created_at",
            (set_id, _pk(partner_id), user_id)).fetchall()]


def find_duplicate(partner_id, user_id, set_id, message_type, channel, data1):
    """The same physical control mapped twice is a control whose behaviour
    depends on iteration order. The engine detects this in Learn; the server
    detects it too, because a mapping can also arrive by form post."""
    with get_db() as db:
        return _row(db.execute(
            "SELECT * FROM live_midi_maps WHERE set_id = ? AND partner_key = ?"
            "  AND user_id = ? AND message_type = ? AND channel = ? AND data1 = ?",
            (set_id, _pk(partner_id), user_id, message_type,
             int(channel or 0), int(data1 or 0))).fetchone())


def delete_mapping(partner_id, user_id, mapping_id):
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM live_midi_maps WHERE id = ? AND partner_key = ?"
            "  AND user_id = ?", (mapping_id, _pk(partner_id), user_id))
    return cur.rowcount > 0


# --- the shape the engine wants ----------------------------------------------

def set_manifest(partner_id, user_id, set_id):
    """The set, in the exact shape LiveAudioEngine.loadProject expects.

    Built here rather than transformed in the page for two reasons. The engine
    validates the project with zod, so the shape is a contract and a contract
    belongs in one place; and a stage rig that has to make six network calls
    and reshape the result before it can play is a rig that fails in a venue
    with bad wifi. One request, one document, already correct.

    The engine's model is SetItem -> Scene -> Clip, with stems hanging off the
    item. This module's model is flatter - a set has scenes, a scene has stems -
    so each scene here becomes one item AND one scene there, which is the
    honest mapping for a rig where a "scene" is a song.

    `assets` is not part of EngineProject. It is carried alongside because the
    engine takes audio by `loadAudio(assetId, arrayBuffer)` and has no opinion
    about where bytes come from - the page fetches them and hands them over.
    """
    live_set = get_set(partner_id, user_id, set_id)
    if live_set is None:
        return None

    org = _pk(partner_id) or "street-banker"
    items, scenes, clips, stems, assets = [], [], [], [], {}

    for scene in list_scenes(partner_id, user_id, set_id):
        item_id = "item-" + scene["id"]
        items.append({
            "id": item_id,
            "organizationId": org,
            "liveProjectId": set_id,
            "sortOrder": scene["position"],
            "type": "song",
            "title": scene["name"] or "Untitled",
            "sourceReleaseId": None,
            "sourceTrackId": None,
            "bpm": scene["tempo_bpm"] or live_set["tempo_bpm"],
            "key": None,
            "durationMs": None,
            "notes": scene["notes"] or "",
        })
        scenes.append({
            "id": scene["id"],
            "organizationId": org,
            "liveProjectId": set_id,
            "liveSetItemId": item_id,
            "name": scene["name"] or "Untitled",
            "sceneType": scene["scene_type"] or "custom",
            "sortOrder": scene["position"],
            "color": "",
            "bpm": scene["tempo_bpm"],
            "key": None,
            "bars": scene["bars"] or None,
            "quantization": scene["quantization"] or "1bar",
            "loopEnabled": bool(scene["loop_enabled"]),
            "followAction": scene["follow_action"] or "stop",
            "followTargetSceneId": None,
        })
        for stem in list_stems(partner_id, user_id, scene["id"]):
            stems.append({
                "id": stem["id"],
                "organizationId": org,
                "liveProjectId": set_id,
                "liveSetItemId": item_id,
                "stemType": stem["stem_type"] or "custom",
                "label": stem["name"] or "Stem",
                "sourceAssetId": stem["id"],
                "gain": float(stem["gain"]),
                "pan": float(stem["pan"]),
                "muted": bool(stem["muted"]),
                "solo": bool(stem["soloed"]),
                "outputId": stem["output_bus"] or "master",
            })
            clips.append({
                "id": "clip-" + stem["id"],
                "organizationId": org,
                "liveProjectId": set_id,
                "liveSceneId": scene["id"],
                "name": stem["name"] or "Stem",
                "sourceAssetId": stem["id"],
                "startMs": 0,
                "endMs": None,
                "loopStartMs": None,
                "loopEndMs": None,
            })
            assets[stem["id"]] = "/live/stem/%s" % stem["id"]

    return {
        "project": {
            "projectId": set_id,
            "masterTempo": float(live_set["tempo_bpm"]),
            "timeSignature": "%d/%d" % (live_set["time_sig_num"],
                                        live_set["time_sig_den"]),
            "items": items,
            "scenes": scenes,
            "clips": clips,
            "stems": stems,
            "padMap": _pad_map(scenes),
        },
        "assets": assets,
        "clickEnabled": bool(live_set["click_enabled"]),
        "name": live_set["name"],
        "venue": live_set["venue"],
        "midi": [{
            "id": m["id"],
            "label": m["label"],
            "messageType": m["message_type"],
            "channel": m["channel"],
            "data1": m["data1"],
            "target": m["target"],
            "targetId": m["target_id"],
        } for m in list_mappings(partner_id, user_id, set_id)],
    }


def _pad_map(scenes):
    """A 4x4 grid, scenes in order, STOP always on the last pad.

    Pad 15 is STOP in the engine's own default and it stays STOP here: on a
    dark stage the one control that must be in the same place every time is
    the one that makes everything stop.
    """
    pads = []
    for index in range(16):
        if index == 15:
            pads.append({"index": 15, "mode": "stop", "label": "STOP",
                         "targetId": None, "color": ""})
        elif index < len(scenes):
            scene = scenes[index]
            pads.append({"index": index, "mode": "scene",
                         "label": scene["name"][:12], "targetId": scene["id"],
                         "color": ""})
        else:
            pads.append({"index": index, "mode": "empty", "label": "",
                         "targetId": None, "color": ""})
    return pads


def manifest_json(partner_id, user_id, set_id):
    manifest = set_manifest(partner_id, user_id, set_id)
    return json.dumps(manifest) if manifest is not None else None
