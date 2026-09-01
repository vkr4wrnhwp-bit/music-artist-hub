"""Street Banker Studio - the artist-facing surface.

PHASE 1: the shell, the project record, and the source upload.

WHAT WORKS HERE TODAY, EXACTLY
------------------------------
Create a project, upload a source, see it become version 1, watch the
waveform draw, and read the loudness the browser measured. That is a real
workflow end to end, and it needs no vendor: the measurement is the Rack's
own BS.1770-4 engine, running in the page.

What does NOT work is anything that needs a server to process audio. There
is no background worker on this deployment - one web service, 180-second
request timeout - and no mastering provider configured. Those actions are
rendered DISABLED with the reason attached, not hidden and not faked. An
artist should be able to see the shape of the product before an operator
switches on the parts that cost money.

WHY EVERY ROUTE RE-CHECKS THE FLAG
----------------------------------
`studio_config.enabled()` is consulted per request rather than at register
time. Blueprints are module-level singletons and app.py builds an app at
import, so a flag captured at registration would freeze whatever the
environment said when the process booted - and the sidebar, the palette and
the page would then disagree about whether the product exists.

THE RACK IS NOT MOVED
---------------------
/rack keeps working exactly as it did, with no project and no session. Opening
it from a Studio session adds a project binding through the query string; it
does not replace the route, because /rack is in the sidebar, in the command
palette, in command_center, and it is the target of the Audio Studio's
"Open the stems in the Rack" button.
"""
import hashlib
import io
import os

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_file, url_for)

import blob_store
import studio_config
import studio_store as sstore

bp = Blueprint("studio", __name__)

# Kept in step with studio_config.max_upload_bytes(), which is itself clamped
# below app.config["MAX_CONTENT_LENGTH"]. See docs/STUDIO.md.
AUDIO_EXTS = (".wav", ".aiff", ".aif", ".flac", ".mp3", ".m4a")
STUDIO_PREFIX = "/uploads/studio/"

_current_user = None


def _dir():
    import db as store
    path = os.path.join(os.path.dirname(store.db_path()), "studio")
    os.makedirs(path, exist_ok=True)
    return path


def _save(fname, data, content_type):
    """Never the public uploads tree. A master an artist uploaded is the most
    valuable file they own."""
    if blob_store.configured():
        try:
            if blob_store.put("studio/" + fname, data, content_type):
                return blob_store.PREFIX + "studio/" + fname
        except Exception:
            pass
    with open(os.path.join(_dir(), fname), "wb") as handle:
        handle.write(data)
    return STUDIO_PREFIX + fname


def _live():
    """404 rather than a redirect when Studio is off.

    A redirect would tell an unauthenticated prober that the route exists and
    is merely switched off. It also stops a bookmark from bouncing somewhere
    confusing after a deployment turns the flag back off.
    """
    if not studio_config.enabled():
        abort(404)


def _user():
    user = _current_user()
    if user is None:
        abort(401)
    return user


def _partner(user):
    return user.get("partner_id")


def _project_or_404(user, project_id):
    project = sstore.get_project(_partner(user), user["id"], project_id)
    if project is None:
        abort(404)
    return project


# --- home --------------------------------------------------------------------

@bp.route("/studio")
def studio_home():
    _live()
    user = _user()
    projects = sstore.list_projects(_partner(user), user["id"], limit=25)
    recent = []
    if projects:
        recent = sstore.provenance(_partner(user), projects[0]["id"], limit=8)
    return render_template("studio/home.html",
                           active_page="studio",
                           projects=projects,
                           continue_project=projects[0] if projects else None,
                           recent=recent,
                           readiness=studio_config.readiness(),
                           project_types=sstore.PROJECT_TYPES)


@bp.route("/studio/projects")
def studio_projects():
    _live()
    user = _user()
    return render_template("studio/projects.html",
                           active_page="studio",
                           projects=sstore.list_projects(_partner(user),
                                                         user["id"], limit=200))


# --- creating ----------------------------------------------------------------

_TYPE_LABELS = [
    ("stereo_mix_review", "Stereo Mix Review",
     "One stereo bounce. Measure it, mark what needs work, collect notes."),
    ("vocal_instrumental", "Vocal + Instrumental",
     "Two files. Check the vocal against the bed and how it translates."),
    ("stem_mix", "Stem Mix",
     "Consolidated stems, balanced and reviewed together."),
    ("master_single", "Master a Single",
     "One approved mix through premaster inspection and a master."),
    ("master_project", "Master an EP or Album",
     "A sequence, checked for cohesion across tracks."),
    ("remix", "Remix Project",
     "Work from an approved master or stems into a new version."),
    ("imported_rack", "Import Existing Rack Project",
     "Bring a saved Rack chain in as the starting point."),
]


@bp.route("/studio/new", methods=["GET", "POST"])
def studio_new():
    _live()
    user = _user()
    if request.method == "GET":
        return render_template("studio/new.html", active_page="studio",
                               types=_TYPE_LABELS)

    title = (request.form.get("title") or "").strip()
    if not title:
        return render_template("studio/new.html", active_page="studio",
                               types=_TYPE_LABELS,
                               error="Give the project a name so you can find "
                                     "it again."), 400
    project_id = sstore.create_project(
        _partner(user), user["id"], title[:200],
        project_type=request.form.get("project_type") or "stereo_mix_review",
        artist_name=(request.form.get("artist_name") or "").strip()[:120],
        created_by=user["id"])
    return redirect(url_for("studio.studio_session", project_id=project_id))


# --- the session console -----------------------------------------------------

@bp.route("/studio/session/<project_id>")
def studio_session(project_id):
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    summary = sstore.project_summary(_partner(user), user["id"], project_id)
    return render_template("studio/session.html",
                           active_page="studio", room="session",
                           project=project, summary=summary,
                           events=sstore.provenance(_partner(user), project_id, 12),
                           readiness=studio_config.readiness(),
                           max_mb=studio_config.max_upload_bytes() // (1024 * 1024))


@bp.route("/studio/session/<project_id>/versions")
def studio_versions(project_id):
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    return render_template("studio/versions.html",
                           active_page="studio", room="versions",
                           project=project,
                           summary=sstore.project_summary(_partner(user),
                                                          user["id"], project_id),
                           events=sstore.provenance(_partner(user), project_id, 50))


# --- Mix Station and Master Station ------------------------------------------
# Both work with no vendor and no worker, because everything they show is
# MEASURED rather than generated: the browser decodes the file with the same
# BS.1770-4 engine the Rack uses, plus the tempo and key detectors, and posts
# the numbers back. audio_readiness turns those into rulings. Nothing is sent
# anywhere, and nothing is claimed that was not measured.


@bp.route("/studio/session/<project_id>/measure", methods=["POST"])
def studio_measure(project_id):
    """Receive one measurement run from the browser.

    The numbers are recomputed into rulings server-side rather than trusted as
    conclusions: the page may send `integrated`, but whether -6.2 LUFS is a
    problem is a threshold decision, and thresholds belong in one place.
    """
    _live()
    user = _user()
    _project_or_404(user, project_id)
    payload = request.get_json(silent=True) or {}
    asset_id = (payload.get("asset_id") or "").strip()
    asset = sstore.get_studio_asset(_partner(user), user["id"], asset_id)
    if asset is None:
        abort(404)

    numeric = {}
    for key in ("integrated", "true_peak", "sample_peak", "lra", "bpm",
                "bpm_confidence", "key_fit", "short_term_max", "momentary_max",
                "first_beat", "grid_confidence", "duration_seconds"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            numeric[key] = float(value)
    if isinstance(payload.get("key"), str):
        numeric["key"] = payload["key"][:24]
    numeric["measured_at"] = payload.get("measured_at") or True

    sstore.save_analysis(_partner(user), user["id"], project_id, asset_id, numeric)
    return jsonify({"ok": True})


def _room(project_id, room, template):
    user = _user()
    project = _project_or_404(user, project_id)
    summary = sstore.project_summary(_partner(user), user["id"], project_id)
    source = summary["source"]
    analysis = findings = comments = None
    verdict = None
    if source:
        analysis = sstore.latest_analysis(_partner(user), source["id"])
        findings = sstore.list_findings(_partner(user), source["id"])
        comments = sstore.list_comments(_partner(user), source["id"])
        if analysis:
            import audio_readiness
            verdict = audio_readiness.assess(analysis["measurements"])
    return render_template(
        template, active_page="studio", room=room, project=project,
        summary=summary, source=source, analysis=analysis, verdict=verdict,
        findings=findings or [], comments=comments or [],
        targets=__import__("audio_readiness").PLATFORM_TARGETS,
        readiness=studio_config.readiness())


@bp.route("/studio/session/<project_id>/mix")
def studio_mix(project_id):
    _live()
    return _room(project_id, "mix", "studio/mix.html")


@bp.route("/studio/session/<project_id>/master")
def studio_master(project_id):
    _live()
    return _room(project_id, "master", "studio/master.html")


@bp.route("/studio/session/<project_id>/comment", methods=["POST"])
def studio_comment(project_id):
    _live()
    user = _user()
    _project_or_404(user, project_id)
    asset_id = (request.form.get("asset_id") or "").strip()
    asset = sstore.get_studio_asset(_partner(user), user["id"], asset_id)
    if asset is None:
        abort(404)
    analysis = sstore.latest_analysis(_partner(user), asset_id)
    duration = None
    if analysis:
        duration = analysis["measurements"].get("duration_seconds")
    sstore.add_comment(
        _partner(user), user["id"], project_id, asset_id,
        author_name=user.get("name") or "", body=request.form.get("body") or "",
        start_seconds=request.form.get("start_seconds") or 0,
        duration_seconds=duration)
    return redirect(url_for("studio.studio_mix", project_id=project_id))


@bp.route("/studio/session/<project_id>/comment/<comment_id>/resolve",
          methods=["POST"])
def studio_resolve_comment(project_id, comment_id):
    _live()
    user = _user()
    _project_or_404(user, project_id)
    sstore.resolve_comment(_partner(user), user["id"], comment_id,
                           reopen=bool(request.form.get("reopen")))
    return redirect(url_for("studio.studio_mix", project_id=project_id))


@bp.route("/studio/session/<project_id>/finding/<finding_id>/resolve",
          methods=["POST"])
def studio_resolve_finding(project_id, finding_id):
    _live()
    user = _user()
    _project_or_404(user, project_id)
    sstore.resolve_finding(_partner(user), user["id"], finding_id)
    return redirect(url_for("studio.studio_mix", project_id=project_id))


@bp.route("/studio/session/<project_id>/rack")
def studio_rack(project_id):
    """Into the Rack the artist already knows, carrying the project with it.

    A redirect rather than a second copy of the Rack: there is one DSP engine
    and one saved-chain library, and forking them so Studio could have its own
    would mean two places to fix the next bug in either.
    """
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    summary = sstore.project_summary(_partner(user), user["id"], project_id)
    source = summary["source"]
    target = "/rack?project=%s" % project["id"]
    if source:
        target += "&asset=%s" % source["id"]
    return redirect(target)


@bp.route("/studio/session/<project_id>/render", methods=["POST"])
def studio_render(project_id):
    """Accept a master the browser rendered, as a NEW asset.

    The source is never touched. The result carries parent_asset_id back to
    what it came from, so the chain from what the artist sent to what ships
    stays walkable in both directions - which is the whole point of keeping
    versions rather than files.

    The gain that was applied and the peak it landed on are recorded in the
    version's change summary. "Mastered" with no numbers is a claim; "-6.2
    to -14.0 LUFS, peak -1.0 dBTP" is a record.
    """
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    if not project["rights_confirmed_at"]:
        abort(403)

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "no audio was sent"}), 400
    data = upload.read()
    if not data or not data.startswith(b"RIFF"):
        return jsonify({"ok": False, "error": "that is not a WAV"}), 400
    cap = studio_config.max_upload_bytes()
    if len(data) > cap:
        return jsonify({"ok": False,
                        "error": "the render is over the %d MB limit"
                                 % (cap // (1024 * 1024))}), 413

    source_id = (request.form.get("source_asset_id") or "").strip()
    source = sstore.get_studio_asset(_partner(user), user["id"], source_id)
    if source is None:
        abort(404)

    digest = hashlib.sha256(data).hexdigest()
    label = (request.form.get("label") or "Master")[:80]
    note = (request.form.get("note") or "")[:400]
    name = "%s-%s.wav" % (project_id[:8], digest[:12])
    storage_key = _save(name, data, "audio/wav")
    asset_id = sstore.create_studio_asset(
        _partner(user), user["id"], project_id, storage_key,
        file_name="%s.wav" % label.replace(" ", "-").lower(),
        mime_type="audio/wav", file_size=len(data), sha256=digest,
        asset_role="master", parent_asset_id=source["id"],
        version_label=label, lossless=True)
    version_id = sstore.create_version(
        _partner(user), user["id"], project_id, asset_id,
        asset_role="master", version_name=label,
        change_summary=note or ("Rendered from %s"
                                % (source["file_name"] or "the source")),
        created_by=user["id"])
    sstore.update_project(_partner(user), user["id"], project_id,
                          active_asset_id=asset_id, active_version_id=version_id)
    return jsonify({"ok": True, "asset_id": asset_id, "version_id": version_id})


# --- approval, locking and delivery -------------------------------------------

@bp.route("/studio/session/<project_id>/version/<version_id>/status",
          methods=["POST"])
def studio_version_status(project_id, version_id):
    """Approve or lock a version.

    The lock is enforced in the store's WHERE clause rather than here, so a
    second route added later cannot forget it. Approving records the asset's
    checksum: an approval that does not say WHICH bytes were approved is not
    an approval, it is a memory.
    """
    _live()
    user = _user()
    _project_or_404(user, project_id)
    status = request.form.get("status") or ""
    version = sstore.get_version(_partner(user), project_id, version_id)
    if version is None:
        abort(404)

    if status == "approved":
        asset = sstore.get_studio_asset(_partner(user), user["id"],
                                        version["asset_id"])
        sstore.record_approval(_partner(user), user["id"], project_id,
                               version["asset_id"], version_id,
                               checksum=(asset or {}).get("sha256", ""))
    sstore.set_version_status(_partner(user), project_id, version_id, status,
                              actor_id=user["id"])
    return redirect(url_for("studio.studio_versions", project_id=project_id))


@bp.route("/studio/session/<project_id>/deliver")
def studio_deliver(project_id):
    """The checklist, computed rather than asserted.

    Every line is derived from what the project actually holds. A checklist
    that hard-codes a tick is worse than no checklist: it tells somebody a
    thing is done at the exact moment they stop being able to check.
    """
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    summary = sstore.project_summary(_partner(user), user["id"], project_id)
    checklist = sstore.delivery_checklist(_partner(user), user["id"], project_id)
    return render_template("studio/deliver.html", active_page="studio",
                           room="deliver", project=project, summary=summary,
                           checklist=checklist,
                           ready=all(c["ok"] for c in checklist
                                     if c["required"]),
                           readiness=studio_config.readiness())


@bp.route("/studio/session/<project_id>/deliver/package", methods=["POST"])
def studio_package(project_id):
    """Build the package, or refuse and say which line is not met.

    Refusing is the point. A package that can be produced before the master is
    locked is a package that can ship the wrong file, and the whole reason
    this product exists is that somebody has to be able to say which of the
    eleven files on the drive is the one that ships.
    """
    _live()
    user = _user()
    project = _project_or_404(user, project_id)
    checklist = sstore.delivery_checklist(_partner(user), user["id"], project_id)
    missing = [c for c in checklist if c["required"] and not c["ok"]]
    if missing:
        summary = sstore.project_summary(_partner(user), user["id"], project_id)
        return render_template(
            "studio/deliver.html", active_page="studio", room="deliver",
            project=project, summary=summary, checklist=checklist, ready=False,
            readiness=studio_config.readiness(),
            error="Not yet: " + missing[0]["label"].lower() + "."), 400

    archive, name = sstore.build_package(_partner(user), user["id"], project_id,
                                         _read_asset_bytes)
    return send_file(io.BytesIO(archive), mimetype="application/zip",
                     as_attachment=True, download_name=name)


def _read_asset_bytes(asset):
    """Bytes for one asset, wherever it actually lives."""
    key = asset.get("storage_key") or ""
    if blob_store.is_remote(key):
        try:
            return blob_store.fetch(key)
        except Exception:
            return None
    path = os.path.join(_dir(), os.path.basename(key))
    if os.path.exists(path):
        with open(path, "rb") as handle:
            return handle.read()
    return None


# --- the source upload -------------------------------------------------------

@bp.route("/studio/session/<project_id>/upload", methods=["POST"])
def studio_upload(project_id):
    """The source is written once and never rewritten.

    Every later render becomes a NEW asset carrying parent_asset_id back to
    this one, so the chain from "what the artist sent" to "what shipped" stays
    walkable in both directions and cannot be broken by a later job.
    """
    _live()
    user = _user()
    project = _project_or_404(user, project_id)

    def refuse(message, code=400):
        summary = sstore.project_summary(_partner(user), user["id"], project_id)
        return render_template(
            "studio/session.html", active_page="studio", room="session",
            project=project, summary=summary, error=message,
            events=sstore.provenance(_partner(user), project_id, 12),
            readiness=studio_config.readiness(),
            max_mb=studio_config.max_upload_bytes() // (1024 * 1024)), code

    if not project["rights_confirmed_at"]:
        return refuse("Confirm you have the rights to this recording before "
                      "uploading it.")

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return refuse("Choose an audio file to upload.")
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in AUDIO_EXTS:
        return refuse("That is not an audio file this can work with. WAV, "
                      "AIFF, FLAC, MP3 or M4A.")

    data = upload.read()
    if not data:
        return refuse("That file is empty.")
    cap = studio_config.max_upload_bytes()
    if len(data) > cap:
        return refuse("That file is %d MB; the limit is %d MB."
                      % (len(data) // (1024 * 1024), cap // (1024 * 1024)), 413)
    if not blob_store.configured() and len(data) > 25 * 1024 * 1024:
        # The disk fallback is 1 GB and shared with the SQLite database, so a
        # few masters there take the database down with them. Refusing is the
        # honest failure; filling the disk politely is not.
        return refuse("Object storage is not configured on this deployment, so "
                      "uploads fall back to a small shared disk. Files over "
                      "25 MB are refused until it is connected.", 413)

    digest = hashlib.sha256(data).hexdigest()
    existing = [a for a in sstore.list_project_assets(_partner(user), user["id"],
                                                      project_id)
                if a["sha256"] == digest]
    if existing:
        return refuse("That exact file is already on this project as %s."
                      % (existing[0]["file_name"] or "a source"))

    name = "%s-%s%s" % (project_id[:8], digest[:12], ext)
    storage_key = _save(name, data, upload.mimetype or "audio/wav")
    asset_id = sstore.create_studio_asset(
        _partner(user), user["id"], project_id, storage_key,
        file_name=os.path.basename(upload.filename)[:200],
        mime_type=upload.mimetype or "", file_size=len(data), sha256=digest,
        asset_role="original", lossless=ext in (".wav", ".aiff", ".aif", ".flac"))
    version_id = sstore.create_version(
        _partner(user), user["id"], project_id, asset_id,
        asset_role="original", version_name="Source",
        change_summary="Uploaded %s" % os.path.basename(upload.filename)[:120],
        created_by=user["id"])
    sstore.update_project(_partner(user), user["id"], project_id,
                          active_asset_id=asset_id, active_version_id=version_id,
                          status="in_progress")
    return redirect(url_for("studio.studio_session", project_id=project_id))


@bp.route("/studio/asset/<asset_id>")
def studio_asset(asset_id):
    """Ownership re-checked on every request rather than handed out in a link.

    The Audio Studio's stem handoff works the same way and for the same
    reason: a signed URL that outlives the permission it was minted under is
    a copy of somebody's master loose on the internet.
    """
    _live()
    user = _user()
    asset = sstore.get_studio_asset(_partner(user), user["id"], asset_id)
    if asset is None:
        abort(404)
    key = asset["storage_key"] or ""
    if blob_store.is_remote(key):
        return redirect(blob_store.url_for(key))
    path = os.path.join(_dir(), os.path.basename(key))
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype=asset["mime_type"] or "audio/wav",
                     conditional=True)


@bp.route("/studio/session/<project_id>/rights", methods=["POST"])
def studio_rights(project_id):
    _live()
    user = _user()
    _project_or_404(user, project_id)
    name = (request.form.get("confirmed_by") or "").strip()
    if name:
        sstore.confirm_rights(_partner(user), user["id"], project_id, name[:120])
    return redirect(url_for("studio.studio_session", project_id=project_id))


def init(app, current_user):
    """Idempotent: blueprints are module-level singletons and app.py builds an
    app at import, so registering twice must not raise."""
    global _current_user
    _current_user = current_user
    if "studio" not in app.blueprints:
        app.register_blueprint(bp)
