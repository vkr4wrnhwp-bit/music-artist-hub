"""Partner OS - the guard.

The main app authorises by hand: `user = current_user()` then
`if user is None: return login_required_redirect()`, copied into roughly a
hundred and twenty handlers, with row ownership left to whether the handler
remembered to pass `user["id"]` into the store call. That works until it
does not, and this repo has shipped that failure twice.

Partner routes do not get to repeat it. `@require("permission")` is the
boundary: it resolves the tenant, refuses a request with no seat, refuses a
seat without the permission, and hands the handler its partner and member
as the first two arguments so there is no way to write a partner route that
forgot to scope itself.

A template hiding a button is cosmetic. This is the check.
"""
import io
import os
import time
from functools import wraps

from flask import (Blueprint, abort, current_app, g, redirect, render_template,
                   request, session, url_for)

import db as store
import partner_store as pstore
import plans

bp = Blueprint("partner", __name__, url_prefix="/partner")

# The tiers a partner may grant. "fan" is included because taking a seat back
# down to the free tier is how a reseller stops paying for an artist who has
# gone quiet, and a grant screen that can only go up is a billing trap.
PARTNER_TIERS = ("fan", "artist", "pro", "label")


def _me():
    uid = session.get("user_id")
    return store.get_user(uid) if uid else None


def current_partner():
    """The tenant this request resolved to, or None for Street Banker."""
    return getattr(g, "partner", None)


def current_member():
    return getattr(g, "partner_member", None)


def require(permission="view"):
    """Server-side check before every partner handler.

    Order is deliberate. Not signed in is a redirect, because it is
    recoverable. Signed in with no seat is a 404, not a 403: a stranger
    should not be able to learn that a partner exists at this address by
    the shape of the refusal. A seat without the permission is a 403,
    because at that point they already know the tenant exists.
    """
    def wrap(fn):
        @wraps(fn)
        def guarded(*args, **kwargs):
            user = _me()
            if user is None:
                return redirect(url_for("login", next=request.path))
            partner = current_partner()
            if partner is None:
                abort(404)
            member = current_member()
            if member is None:
                member = pstore.get_member(partner["id"], user_id=user["id"],
                                           email=user.get("email"))
            if member is None:
                abort(404)
            if not pstore.can(member, permission):
                abort(403)
            pstore.touch_member(member["id"])
            return fn(partner, member, *args, **kwargs)
        return guarded
    return wrap


def owned_user_or_404(partner, user_id):
    """Every route that names an artist by id goes through here.

    Ownership is asked of the database, not inferred from the fact that the
    id arrived in a URL the partner was allowed to load.
    """
    if not pstore.owns_user(partner["id"], user_id):
        abort(404)
    user = store.get_user(user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/")
@require("view")
def home(partner, member):
    roster = pstore.roster(partner["id"])
    import partner_billing
    return render_template("partner/home.html",
                           partner=partner, member=member, roster=roster,
                           statement=partner_billing.statement(roster),
                           plan_names=plans.PLAN_NAMES,
                           can=lambda p: pstore.can(member, p),
                           role_label=pstore.ROLE_LABELS.get(member["role"], member["role"]))


# The surfaces an accent has to be legible on. Read from the token sheet
# rather than written here, so a change to the palette moves the bar with
# it instead of leaving this check measuring against a colour the product
# stopped using.
def _brand_surfaces():
    import re

    import os as _os
    here = _os.path.dirname(_os.path.abspath(__file__))
    try:
        with io.open(_os.path.join(here, "tools", "tailwind-input.css"),
                     encoding="utf-8") as fh:
            sheet = fh.read()
    except OSError:
        return {"sidebar": "#0B0A08"}
    out = {}
    for token, label in (("ground", "sidebar"), ("surface-1", "panel")):
        m = re.search(r"--sb-%s:\s*(#[0-9a-fA-F]{6})" % re.escape(token), sheet)
        if m:
            out[label] = m.group(1)
    return out or {"sidebar": "#0B0A08"}


def _uploads_dir():
    """Where this deployment keeps uploaded files.

    app.py derives it once - from the database's directory, with a
    fallback when DATABASE_PATH points at an unmounted disk - and
    publishes it. Re-deriving it here would get the fallback wrong on
    exactly the deployment where it matters.
    """
    path = current_app.config.get("UPLOADS_DIR")
    if not path:
        import db as _store
        path = os.path.join(os.path.dirname(_store.db_path()), "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def _save_logo(partner_id, file_storage):
    """Write a tenant's logo and return (path, problems).

    Held like every other upload this app takes: an extension whitelist,
    a byte cap, a name the uploader does not choose, and the public
    /uploads directory - a brand mark is public by definition, since it
    renders on the sign-in page before anybody has an account.

    SVG is refused even though a wordmark would rather be vector. An SVG
    is a document: served from /uploads it is same-origin with every
    artist's session, and opened directly its script runs. Rasterising or
    sanitising one is a real feature and a separate one.
    """
    import white_label

    name = (getattr(file_storage, "filename", "") or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "jpeg":
        ext = "jpg"
    if ext not in white_label.LOGO_EXTENSIONS:
        return None, ["Use a %s image. An SVG is a document, not a picture: "
                      "served from your artists' own address its script would "
                      "run there, so this only takes raster files."
                      % ", ".join(e.upper() for e in white_label.LOGO_EXTENSIONS)]

    raw = file_storage.read()
    if not raw:
        return None, ["That file was empty."]
    if len(raw) > white_label.LOGO_MAX_BYTES:
        return None, ["That logo is %.1f MB. The limit is %d MB - it is a "
                      "wordmark in a sidebar, not artwork."
                      % (len(raw) / 1048576.0,
                         white_label.LOGO_MAX_BYTES // 1048576)]
    try:
        from io import BytesIO

        from PIL import Image
        Image.open(BytesIO(raw)).verify()
    except ImportError:
        # Pillow is optional at runtime everywhere else in this app, and
        # it is optional here: the extension and the cap still hold.
        pass
    except Exception:
        return None, ["That file is not an image the browser could draw, "
                      "whatever it is named."]

    folder = _uploads_dir()
    fname = "partnerlogo_%s_%d.%s" % (partner_id, int(time.time()), ext)
    with io.open(os.path.join(folder, fname), "wb") as fh:
        fh.write(raw)
    return "/uploads/" + fname, []


def _forget_logo(path):
    """Take a replaced or removed logo off the disk.

    Best effort. A file that will not delete must not fail the save -
    the row is what the product reads, and an orphan is a tidiness
    problem, not a correctness one.
    """
    path = (path or "").strip()
    if not path.startswith("/uploads/partnerlogo_"):
        return
    try:
        os.remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))
    except OSError:
        pass


@bp.route("/branding", methods=["GET", "POST"])
@require("branding_edit")
def branding(partner, member):
    """What a reseller's artists see instead of Street Banker.

    branding_edit has existed as a permission since Partner OS shipped and
    guarded nothing, because there was nowhere to edit and nothing to
    store. This is the screen it was named for.

    The accent is checked for contrast at save. The design lock reads
    source files for colour literals and cannot see a colour that arrives
    from the database, so the only place this can be caught is here - the
    same answer the homepage editor reached for links.

    The logo arrived 2026-09-21. partners.logo_path had existed since
    Partner OS shipped and base.html and auth_base.html had always
    rendered brand.logo when it was set; nothing had ever written it, so
    every tenant showed a name where their mark should have been.
    """
    import brand_contrast
    import white_label

    problems, saved, notes = [], False, []
    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()[:120]
        tagline = (request.form.get("tagline") or "").strip()[:120]
        raw_accent = (request.form.get("accent") or "").strip()
        accent = ""
        if raw_accent:
            accent, accent_problems = brand_contrast.check_accent(
                raw_accent, _brand_surfaces())
            problems += accent_problems
            accent = accent or ""
        if not display_name:
            problems.append(
                "A name is needed - it is what your artists see where "
                "Street Banker's own would be.")

        # None means "leave whatever is stored alone"; "" means remove.
        logo_path, drop_old = None, ""
        upload = request.files.get("logo")
        if upload is not None and getattr(upload, "filename", ""):
            logo_path, logo_problems = _save_logo(partner["id"], upload)
            problems += logo_problems
            if logo_path:
                drop_old = partner.get("logo_path") or ""
        elif request.form.get("remove_logo"):
            logo_path = ""
            drop_old = partner.get("logo_path") or ""

        if problems:
            # Nothing is written, so a logo saved a moment ago must not be
            # left on disk pointing at nothing.
            if logo_path:
                _forget_logo(logo_path)
        else:
            pstore.set_branding(partner["id"], display_name=display_name,
                                accent=accent, tagline=tagline,
                                logo_path=logo_path)
            _forget_logo(drop_old)
            detail = "Brand set to %s" % display_name
            if logo_path:
                detail += "; logo uploaded"
            elif logo_path == "":
                detail += "; logo removed"
            pstore.audit(partner["id"], "branding.save", actor=member,
                         detail=detail)
            saved = True

    fresh = pstore.get_partner(partner["id"])
    brand = pstore.branding(fresh)
    # An accent can pass the save-time gate - readable AS INK on a dark
    # sidebar - and still leave nothing readable sitting ON it. Say so
    # rather than quietly painting buttons in the platform's gold and
    # letting the tenant wonder why.
    if brand and brand.get("accent") and not white_label.accent_fill_ok(brand["accent"]):
        notes.append(
            "Your colour is used for headings, labels, edges and the focus "
            "ring. Filled buttons keep the platform's gold: neither black nor "
            "white text is readable on this colour at body size.")
    return render_template("partner/branding.html",
                           partner=fresh, member=member,
                           brand=brand,
                           problems=problems, saved=saved, notes=notes,
                           logo_max_mb=white_label.LOGO_MAX_BYTES // 1048576,
                           logo_kinds=", ".join(
                               e.upper() for e in white_label.LOGO_EXTENSIONS),
                           can=lambda p: pstore.can(member, p),
                           role_label=pstore.ROLE_LABELS.get(member["role"],
                                                             member["role"]))


@bp.route("/roster")
@require("roster_view")
def roster(partner, member):
    return render_template("partner/roster.html",
                           partner=partner, member=member,
                           roster=pstore.roster_detail(partner["id"]),
                           seats_used=pstore.seats_used(partner["id"]),
                           seats_left=pstore.seats_left(partner["id"]),
                           seat_limit=pstore.seat_limit(partner["id"]),
                           tiers=PARTNER_TIERS,
                           plan_names=plans.PLAN_NAMES,
                           can=lambda p: pstore.can(member, p),
                           role_label=pstore.ROLE_LABELS.get(member["role"], member["role"]))


@bp.route("/roster/<user_id>/plan", methods=["POST"])
@require("entitlement_grant")
def set_artist_plan(partner, member, user_id):
    """The partner sets an artist's tier.

    A reseller's artist cannot buy their own plan - /plan/switch refuses them
    - so this is the only way their tier moves, and the partner carries the
    cost of what it unlocks. Written to the audit trail with the old and new
    tier, because "who upgraded this account" is exactly the question a
    disputed invoice asks.
    """
    artist = owned_user_or_404(partner, user_id)
    plan = (request.form.get("plan") or "").strip()
    if plan not in PARTNER_TIERS:
        abort(400)
    was = artist.get("plan") or "fan"
    if pstore.grant_plan(partner["id"], user_id, plan) is None:
        abort(400)
    if plan != was:
        pstore.audit(partner["id"], "entitlement.grant", actor=member,
                     subject_user_id=user_id,
                     detail="%s: %s to %s" % (
                         artist.get("name") or artist["email"],
                         plans.PLAN_NAMES.get(was, was),
                         plans.PLAN_NAMES.get(plan, plan)))
    return redirect(url_for("partner.roster"))


@bp.route("/audit")
@require("view")
def audit(partner, member):
    return render_template("partner/audit.html",
                           partner=partner, member=member,
                           trail=pstore.audit_trail(partner["id"]),
                           can=lambda p: pstore.can(member, p),
                           role_label=pstore.ROLE_LABELS.get(member["role"], member["role"]))


def acting_context(staff_user_id, subject_user_id):
    """The artist a partner seat may act as right now, or None.

    Every condition is re-checked, because each of them can be withdrawn
    between one request and the next:

      * the staff account still holds a seat at an ACTIVE partner
        (member_for_user joins partners, so a suspended one grants nothing)
      * that seat still holds act_as_artist
      * the partner still owns this artist

    Returning None is the safe answer for all of them, and the caller drops
    the impersonation rather than falling back to the staff account - a
    half-ended act-on-behalf is how somebody edits the wrong workspace.
    """
    if not staff_user_id or not subject_user_id:
        return None
    if staff_user_id == subject_user_id:
        return None

    member = pstore.member_for_user(staff_user_id)
    if member is None or not pstore.can(member, "act_as_artist"):
        return None
    if not pstore.owns_user(member["partner_id"], subject_user_id):
        return None
    return store.get_user(subject_user_id)


@bp.route("/act/<user_id>", methods=["POST"])
@require("act_as_artist")
def act_as(partner, member, user_id):
    """Open an artist's workspace as their partner.

    Written to the audit trail before the session changes, because an
    impersonation that fails halfway should still be on the record.
    """
    artist = owned_user_or_404(partner, user_id)
    # actor is the member ROW - audit reads id and email off it, and an
    # impersonation record that loses the impersonator is not a record.
    pstore.audit(partner["id"], "act_as.start", actor=member,
                 subject_user_id=user_id,
                 detail="Opened %s's workspace" % (artist.get("name") or artist["email"]))
    session["acting_as"] = user_id
    session["acting_as_name"] = artist.get("name") or artist.get("email") or ""
    return redirect("/overview")


@bp.route("/act/stop", methods=["POST"])
def act_stop():
    """Hand the workspace back. Deliberately NOT behind @require: a seat that
    has just lost its permission still has to be able to stop."""
    staff_id = session.get("user_id")
    subject = session.pop("acting_as", None)
    session.pop("acting_as_name", None)
    if staff_id and subject:
        member = pstore.member_for_user(staff_id)
        if member:
            pstore.audit(member["partner_id"], "act_as.stop", actor=member,
                         subject_user_id=subject, detail="Closed the workspace")
    return redirect("/partner/roster")


def init(app):
    app.register_blueprint(bp)
