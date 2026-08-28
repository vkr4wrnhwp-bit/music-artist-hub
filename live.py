"""Street Banker Live - the stage rig.

WHERE THIS CAME FROM
--------------------
Live Lab was built inside the MASTERCLIP OS repository, on a branch that was
never merged. The engine - scene scheduling with launch quantisation, the stem
deck, MIDI parsing and Learn, the offline cache - is 2,688 lines of TypeScript
that depend on nothing but each other and the browser. It is bundled here as
`static/js/livelab.js` and mounted into these pages.

Nothing was rewritten. The valuable half is the half that carries over.

WHAT RUNS WHERE, AND WHY
------------------------
Everything audio happens in the browser, because it has to: exact-time scene
launching needs `AudioBufferSourceNode` scheduled against an AudioContext
clock, MIDI needs the browser's own device list, and Performance Mode reads
from IndexedDB with the network deliberately cut. A server cannot do any of
that, and serving these pages from Jinja rather than React changes none of it.

The Rack is the precedent this follows: 4,700 lines of Web Audio already run
in a Jinja-served Street Banker page.

The server's job is small and it is all this module does - store the set,
serve the stems, and hand the browser one manifest rather than making a stage
rig do six fetches before it can play.

UNLOCKING
---------
Live is an artist-tier section behind its own flag, so a deployment gets it
deliberately and a plan gates it the same way the Rack and the Vault are
gated. The flag is read per request; a module-level literal would freeze
whatever the environment said when the process booted.
"""
import os

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_file, url_for)

import blob_store
import db as store
import live_store as lstore

bp = Blueprint("live", __name__)

_FALSE = ("0", "false", "no", "off")
_current_user = None

# Audio the engine can decode. The browser does the decoding, so this is the
# set the Web Audio API handles rather than anything this server parses.
STEM_EXTS = (".wav", ".aiff", ".aif", ".flac", ".mp3", ".m4a", ".ogg")


def enabled():
    """ON unless a deployment turns it off.

    Live Lab works and is tested, so hiding it behind a variable nobody had
    been told about only meant the owner could not find his own stage rig.
    LIVE_LAB_ENABLED=0 still switches it off.
    """
    return (os.environ.get("LIVE_LAB_ENABLED") or "").strip().lower() not in _FALSE


def _live():
    """404 while the section is locked, rather than a redirect: a redirect
    tells a prober the route exists and merely bounces a bookmark somewhere
    confusing after a deployment turns the flag back off."""
    if not enabled():
        abort(404)


def _user():
    user = _current_user()
    if user is None:
        abort(401)
    return user


def _partner(user):
    return user.get("partner_id")


def _set_or_404(user, set_id):
    live_set = lstore.get_set(_partner(user), user["id"], set_id)
    if live_set is None:
        abort(404)
    return live_set


def readiness():
    """What this browser will and will not be able to do, stated before
    somebody relies on it at a venue.

    Reported rather than assumed: `AudioContext.setSinkId` - which is how each
    player gets their own in-ear feed - is Chromium-only, and finding that out
    during soundcheck is worse than reading it here.
    """
    return [
        ("audio", "Web Audio",
         "Scene launching is scheduled against the audio clock, not a timer."),
        ("midi", "Web MIDI",
         "Triggers and MIDI Learn. Chromium-based browsers; Safari does not "
         "implement it."),
        ("offline", "Offline performance",
         "Stems are cached in the browser so a show survives a reload with no "
         "network."),
        ("outputs", "Per-player outputs",
         "Sending stems to separate interface channels uses setSinkId, which "
         "is Chromium-only. Elsewhere everything folds to the default output."),
    ]


# --- sets --------------------------------------------------------------------

@bp.route("/live")
def live_home():
    _live()
    user = _user()
    return render_template("live/home.html", active_page="live",
                           sets=lstore.list_sets(_partner(user), user["id"]),
                           readiness=readiness())


@bp.route("/live/new", methods=["POST"])
def live_new():
    _live()
    user = _user()
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("live.live_home"))
    set_id = lstore.create_set(
        _partner(user), user["id"], name,
        venue=(request.form.get("venue") or "").strip(),
        show_date=(request.form.get("show_date") or "").strip(),
        tempo_bpm=_float(request.form.get("tempo_bpm"), 120.0))
    return redirect(url_for("live.live_set", set_id=set_id))


def _float(value, fallback):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


@bp.route("/live/<set_id>")
def live_set(set_id):
    _live()
    user = _user()
    live_set = _set_or_404(user, set_id)
    scenes = lstore.list_scenes(_partner(user), user["id"], set_id)
    for scene in scenes:
        scene["stems"] = lstore.list_stems(_partner(user), user["id"], scene["id"])
    vault = [f for f in store.list_vault_files(user["id"])
             if os.path.splitext(f.get("path") or "")[1].lower() in STEM_EXTS]
    return render_template("live/set.html", active_page="live",
                           live_set=live_set, scenes=scenes, vault=vault,
                           mappings=lstore.list_mappings(_partner(user),
                                                         user["id"], set_id),
                           targets=lstore.MIDI_TARGETS,
                           follow_actions=lstore.FOLLOW_ACTIONS,
                           quantizations=lstore.QUANTIZATIONS,
                           scene_types=lstore.SCENE_TYPES)


@bp.route("/live/<set_id>/settings", methods=["POST"])
def live_settings(set_id):
    _live()
    user = _user()
    _set_or_404(user, set_id)
    lstore.update_set(
        _partner(user), user["id"], set_id,
        name=(request.form.get("name") or "").strip()[:160],
        venue=(request.form.get("venue") or "").strip()[:160],
        tempo_bpm=_float(request.form.get("tempo_bpm"), 120.0),
        time_sig_num=_int(request.form.get("time_sig_num"), 4),
        time_sig_den=_int(request.form.get("time_sig_den"), 4),
        click_enabled=1 if request.form.get("click_enabled") else 0)
    return redirect(url_for("live.live_set", set_id=set_id))


# --- scenes ------------------------------------------------------------------

@bp.route("/live/<set_id>/scene", methods=["POST"])
def live_add_scene(set_id):
    _live()
    user = _user()
    _set_or_404(user, set_id)
    name = (request.form.get("name") or "").strip()
    if name:
        lstore.add_scene(_partner(user), user["id"], set_id, name,
                         bars=_int(request.form.get("bars"), 0),
                         follow_action=request.form.get("follow_action") or "stop",
                         quantization=request.form.get("quantization") or "1bar",
                         scene_type=request.form.get("scene_type") or "custom")
    return redirect(url_for("live.live_set", set_id=set_id))


@bp.route("/live/<set_id>/scene/<scene_id>/delete", methods=["POST"])
def live_delete_scene(set_id, scene_id):
    _live()
    user = _user()
    _set_or_404(user, set_id)
    lstore.delete_scene(_partner(user), user["id"], set_id, scene_id)
    return redirect(url_for("live.live_set", set_id=set_id))


# --- stems -------------------------------------------------------------------

@bp.route("/live/<set_id>/scene/<scene_id>/stem", methods=["POST"])
def live_add_stem(set_id, scene_id):
    """Stems come from the Asset Vault. A pointer, never a copy - one set of
    bytes listed in two places, the same rule the Audio Studio follows when it
    hands stems to the Rack."""
    _live()
    user = _user()
    _set_or_404(user, set_id)
    file_id = (request.form.get("vault_file_id") or "").strip()
    chosen = [f for f in store.list_vault_files(user["id"])
              if str(f.get("id")) == file_id]
    if not chosen:
        return redirect(url_for("live.live_set", set_id=set_id))
    vault_file = chosen[0]
    lstore.add_stem(_partner(user), user["id"], set_id, scene_id,
                    name=(request.form.get("name")
                          or vault_file.get("label") or "Stem")[:160],
                    vault_file_id=file_id,
                    storage_path=vault_file.get("path") or "",
                    output_bus=request.form.get("output_bus") or "master")
    return redirect(url_for("live.live_set", set_id=set_id))


@bp.route("/live/stem/<stem_id>")
def live_stem(stem_id):
    """Ownership re-checked on every request rather than handed out in a link.

    A performance stem is somebody's master taken apart; a URL that outlives
    the permission it was minted under is a copy of it loose on the internet.
    """
    _live()
    user = _user()
    with store.get_db() as db:
        row = db.execute(
            "SELECT * FROM live_stems WHERE id = ? AND user_id = ?"
            "  AND partner_key = ?",
            (stem_id, user["id"], _partner(user) or "")).fetchone()
    if row is None:
        abort(404)
    path = row["storage_path"] or ""
    if blob_store.is_remote(path):
        return redirect(blob_store.url_for(path))
    local = os.path.join(store.uploads_dir(), os.path.basename(path)) \
        if hasattr(store, "uploads_dir") else None
    if local and os.path.exists(local):
        return send_file(local, conditional=True)
    resolved = blob_store.url_for(path) if path else ""
    if resolved and resolved != path:
        return redirect(resolved)
    abort(404)


@bp.route("/live/stem/<stem_id>/set", methods=["POST"])
def live_set_stem(stem_id):
    _live()
    user = _user()
    fields = {}
    if request.form.get("gain") is not None:
        # Linear 0..2, which is what the engine's LiveStem schema accepts.
        fields["gain"] = max(0.0, min(2.0, _float(request.form.get("gain"), 1.0)))
    if request.form.get("pan") is not None:
        fields["pan"] = _float(request.form.get("pan"), 0.0)
    if request.form.get("output_bus"):
        fields["output_bus"] = request.form.get("output_bus")
    fields["muted"] = 1 if request.form.get("muted") else 0
    fields["soloed"] = 1 if request.form.get("soloed") else 0
    lstore.set_stem(_partner(user), user["id"], stem_id, **fields)
    return redirect(request.form.get("back") or url_for("live.live_home"))


@bp.route("/live/stem/<stem_id>/delete", methods=["POST"])
def live_delete_stem(stem_id):
    _live()
    user = _user()
    lstore.delete_stem(_partner(user), user["id"], stem_id)
    return redirect(request.form.get("back") or url_for("live.live_home"))


# --- MIDI --------------------------------------------------------------------

@bp.route("/live/<set_id>/midi", methods=["POST"])
def live_add_mapping(set_id):
    """Refuses an unknown target and refuses a duplicate control.

    Both are the server half of rules the engine's Learn already enforces: a
    mapping that resolves to nothing is a dead pad, and the same physical
    control mapped twice behaves according to iteration order.
    """
    _live()
    user = _user()
    _set_or_404(user, set_id)
    message_type = request.form.get("message_type") or "note_on"
    channel = _int(request.form.get("channel"), 0)
    data1 = _int(request.form.get("data1"), 0)
    existing = lstore.find_duplicate(_partner(user), user["id"], set_id,
                                     message_type, channel, data1)
    if existing is None:
        lstore.add_mapping(_partner(user), user["id"], set_id,
                           label=(request.form.get("label") or "").strip(),
                           message_type=message_type, channel=channel,
                           data1=data1,
                           target=request.form.get("target") or "",
                           target_id=request.form.get("target_id") or "")
    return redirect(url_for("live.live_set", set_id=set_id))


@bp.route("/live/midi/<mapping_id>/delete", methods=["POST"])
def live_delete_mapping(mapping_id):
    _live()
    user = _user()
    lstore.delete_mapping(_partner(user), user["id"], mapping_id)
    return redirect(request.form.get("back") or url_for("live.live_home"))


# --- the manifest and the stage ----------------------------------------------

@bp.route("/live/<set_id>/manifest.json")
def live_manifest(set_id):
    """One document, one request. A stage rig that has to make six network
    calls before it can play is a rig that fails in a venue with bad wifi."""
    _live()
    user = _user()
    _set_or_404(user, set_id)
    manifest = lstore.set_manifest(_partner(user), user["id"], set_id)
    if manifest is None:
        abort(404)
    return jsonify(manifest)


@bp.route("/live/<set_id>/perform")
def live_perform(set_id):
    """Performance Mode. Deliberately outside the app shell - no sidebar, no
    navigation - because everything on this screen is something somebody might
    hit by accident in the dark."""
    _live()
    user = _user()
    live_set = _set_or_404(user, set_id)
    return render_template("live/perform.html", live_set=live_set,
                           manifest_url=url_for("live.live_manifest",
                                                set_id=set_id))


def init(app, current_user):
    """Idempotent: blueprints are module-level singletons and app.py builds an
    app at import, so registering twice must not raise."""
    global _current_user
    _current_user = current_user
    if "live" not in app.blueprints:
        app.register_blueprint(bp)
