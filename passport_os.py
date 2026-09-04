"""Show Passport - the routes.

Every handler here goes through `_owned()`, which resolves the passport and
the signed-in account together. Ownership is asked of the database, never
inferred from an id having arrived in a URL the caller was allowed to load -
the same rule `partner_os.owned_user_or_404` follows, and the rule this repo
has twice shipped a bug for want of.

The module is mounted, not standalone: it takes `current_user` and
`build_dashboard_context` from the app factory so a passport page wears the
same shell, sidebar and plate band as every other internal page.
"""
from functools import wraps

from flask import Blueprint, abort, redirect, render_template, request, url_for

import advance_store
import passport_store as ps
import stage_store

bp = Blueprint("passport", __name__, url_prefix="/passports")

_current_user = None
_dashboard_context = None

# The sections a form can post rows to. Kept as its own tuple rather than
# reading _SECTION_TABLES so a store-side rename cannot silently widen what
# the web is allowed to write.
EDITABLE_SECTIONS = ("contacts", "personnel", "inputs", "outputs",
                     "equipment", "cues")

SECTION_LABELS = {
    "contacts": "Production contacts",
    "personnel": "Personnel",
    "inputs": "Input list",
    "outputs": "Monitor mixes",
    "equipment": "Backline and equipment",
    "cues": "Show cues",
}


def _signed_in():
    return _current_user() if _current_user else None


def require_passport(fn):
    """Resolve the passport for this account, or refuse.

    404 rather than 403 for a passport somebody else owns: a stranger should
    not learn that an id exists by the shape of the refusal.
    """
    @wraps(fn)
    def guarded(passport_id, *args, **kwargs):
        user = _signed_in()
        if user is None:
            return redirect(url_for("login", next=request.path))
        head = ps.get_passport(passport_id, user["id"])
        if head is None:
            abort(404)
        return fn(head, user, *args, **kwargs)
    return guarded


def _ctx(**extra):
    base = dict(_dashboard_context() if _dashboard_context else {})
    base.update(extra)
    return base


@bp.route("/")
def index():
    user = _signed_in()
    if user is None:
        return redirect(url_for("login", next=request.path))
    return render_template("passport/index.html",
                           active_page="passports",
                           passports=ps.list_passports(user["id"]),
                           **_ctx())


@bp.route("/new", methods=["POST"])
def create():
    user = _signed_in()
    if user is None:
        return redirect(url_for("login", next=request.path))
    pid = ps.create_passport(
        user["id"],
        artist_name=(request.form.get("artist_name") or "").strip(),
        production_name=(request.form.get("production_name") or "").strip(),
        variant=(request.form.get("variant") or "").strip())
    return redirect(url_for("passport.detail", passport_id=pid))


@bp.route("/<passport_id>")
@require_passport
def detail(head, user):
    return render_template(
        "passport/detail.html",
        active_page="passports",
        passport=head,
        sections={s: ps.rows(s, head["id"]) for s in EDITABLE_SECTIONS},
        section_labels=SECTION_LABELS,
        playback=ps.get_playback(head["id"]),
        stage_plot=ps.get_stage_plot(head["id"]),
        documents=ps.documents(head["id"]),
        gaps=ps.gaps(head["id"], user["id"]),
        versions=ps.versions(head["id"]),
        current=ps.current_version(head["id"], user["id"]),
        unpublished=ps.draft_differs_from_current(head["id"], user["id"]),
        vocab={"visibility": ps.VISIBILITY, "output_kinds": ps.OUTPUT_KINDS,
               "provided_by": ps.PROVIDED_BY, "personnel_kinds": ps.PERSONNEL_KINDS,
               "document_kinds": ps.DOCUMENT_KINDS},
        **_ctx())


@bp.route("/<passport_id>/identity", methods=["POST"])
@require_passport
def save_identity(head, user):
    ps.update_passport(head["id"], user["id"],
                       **{k: request.form.get(k) for k in ps.IDENTITY_FIELDS
                          if k in request.form})
    return redirect(url_for("passport.detail", passport_id=head["id"]))


@bp.route("/<passport_id>/<section>/add", methods=["POST"])
@require_passport
def add_section_row(head, user, section):
    if section not in EDITABLE_SECTIONS:
        abort(404)
    ps.add_row(section, head["id"], **request.form.to_dict())
    return redirect(url_for("passport.detail", passport_id=head["id"]) + "#" + section)


@bp.route("/<passport_id>/<section>/<row_id>/save", methods=["POST"])
@require_passport
def save_section_row(head, user, section, row_id):
    if section not in EDITABLE_SECTIONS:
        abort(404)
    ps.update_row(section, head["id"], row_id, **request.form.to_dict())
    return redirect(url_for("passport.detail", passport_id=head["id"]) + "#" + section)


@bp.route("/<passport_id>/<section>/<row_id>/delete", methods=["POST"])
@require_passport
def delete_section_row(head, user, section, row_id):
    if section not in EDITABLE_SECTIONS:
        abort(404)
    ps.delete_row(section, head["id"], row_id)
    return redirect(url_for("passport.detail", passport_id=head["id"]) + "#" + section)


@bp.route("/<passport_id>/playback", methods=["POST"])
@require_passport
def save_playback(head, user):
    ps.save_playback(head["id"], **request.form.to_dict())
    return redirect(url_for("passport.detail", passport_id=head["id"]) + "#playback")


@bp.route("/<passport_id>/stage-plot", methods=["POST"])
@require_passport
def save_stage_plot(head, user):
    ps.save_stage_plot(head["id"],
                       width_m=request.form.get("width_m"),
                       depth_m=request.form.get("depth_m"),
                       power_notes=request.form.get("power_notes"),
                       access_notes=request.form.get("access_notes"),
                       elements=ps.get_stage_plot(head["id"])["elements"])
    return redirect(url_for("passport.detail", passport_id=head["id"]) + "#stage_plot")


@bp.route("/<passport_id>/publish", methods=["POST"])
@require_passport
def publish(head, user):
    """Publishing is the one irreversible act here: it mints a document other
    people will be held to. It is deliberately a POST with a note field and no
    'are you sure' - the note IS the confirmation, and it is what the change
    log shows."""
    ps.publish(head["id"], user["id"],
               published_by=user.get("name") or user.get("email") or "",
               change_note=request.form.get("change_note") or "")
    return redirect(url_for("passport.versions", passport_id=head["id"]))


@bp.route("/<passport_id>/versions")
@require_passport
def versions(head, user):
    history = ps.versions(head["id"])
    # Default the comparison to "what changed in the newest publish", because
    # that is the question somebody opening a change log is nearly always
    # asking, and making them pick two ids first is a worse first screen.
    older = request.args.get("from") or (history[1]["id"] if len(history) > 1 else None)
    newer = request.args.get("to") or (history[0]["id"] if history else None)
    diff = (ps.compare_versions(older, newer, user["id"])
            if older and newer and older != newer else None)
    return render_template("passport/versions.html",
                           active_page="passports",
                           passport=head, versions=history,
                           section_labels=dict(SECTION_LABELS,
                                               identity="Identity",
                                               stage_plot="Stage plot",
                                               playback="Playback and timecode",
                                               documents="Documents"),
                           older=older, newer=newer, diff=diff,
                           **_ctx())


@bp.route("/<passport_id>/version/<version_id>")
@require_passport
def version_detail(head, user, version_id):
    version = ps.get_version(version_id, user["id"])
    if version is None or version["passport_id"] != head["id"]:
        abort(404)
    return render_template("passport/version.html",
                           active_page="passports",
                           passport=head, version=version,
                           snapshot=version["snapshot"],
                           section_labels=SECTION_LABELS,
                           **_ctx())


def init(app, current_user=None, dashboard_context=None):
    global _current_user, _dashboard_context
    _current_user = current_user
    _dashboard_context = dashboard_context
    ps.init_passports()
    # Advancement's tables are created here rather than from their own init so
    # there is one place that owns Stage Control's schema. The routes that use
    # them land in phase 3; the tables existing first costs nothing and means a
    # deploy is never half-migrated when they do.
    advance_store.init_advance()
    stage_store.init_stage()
    app.register_blueprint(bp)
