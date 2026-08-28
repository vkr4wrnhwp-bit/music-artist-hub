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
import os

from flask import (Blueprint, abort, redirect, render_template, request,
                   send_file, url_for)

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
