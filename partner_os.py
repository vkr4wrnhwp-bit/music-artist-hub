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
from functools import wraps

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for

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
    return render_template("partner/home.html",
                           partner=partner, member=member, roster=roster,
                           can=lambda p: pstore.can(member, p),
                           role_label=pstore.ROLE_LABELS.get(member["role"], member["role"]))


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
