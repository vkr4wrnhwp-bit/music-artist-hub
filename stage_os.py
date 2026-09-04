"""Stage Control - the two rooms.

The Engineer Desk and the performer's phone. They are the same data seen from
opposite ends of a stage, and they look nothing alike on purpose:

  * the DESK is dark and dense, because it is read at front of house during a
    blackout, next to a console;
  * the PHONE is dark and enormous, because it is read mid-song by somebody
    holding an instrument.

Both poll `/stage/<show>/events?since=N`. Per the phase 1 audit there is no
websocket infrastructure here and the deployment cannot host one - eight
request slots total - so the cursor in stage_store carries the realtime and
the transport is a fetch on a timer.

WHAT THIS MODULE WILL NOT DO. It never says a change was applied unless the
state machine says so. The mode banner is always on screen. There is no
console here at all: Request Mode is the whole product on most nights and it
has to be complete without one.
"""
from functools import wraps

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, url_for)

import passport_store as ps
import advance_store as adv
import stage_store as st

bp = Blueprint("stage", __name__, url_prefix="/stage")

_current_user = None
_dashboard_context = None


def _signed_in():
    return _current_user() if _current_user else None


def require_show(fn):
    """Resolve the signed-in owner of this show's stage.

    Ownership is the account that owns the passport attachment, which is what
    scopes every stage_store query. A show nobody has advanced has no stage.
    """
    @wraps(fn)
    def guarded(show_id, *args, **kwargs):
        user = _signed_in()
        if user is None:
            return redirect(url_for("login", next=request.path))
        return fn(show_id, user, *args, **kwargs)
    return guarded


def _ctx(**extra):
    base = dict(_dashboard_context() if _dashboard_context else {})
    base.update(extra)
    return base


def _mixes_and_sources(show_id, user_id):
    """The monitor mixes and input sources this show actually has.

    Read from the ATTACHED PASSPORT VERSION, never from the passport's working
    tables: the crew agreed to a specific document and the desk has to be
    looking at the same one. No attachment means no mixes, which is a real
    state - you cannot take requests against a show nobody advanced.
    """
    snap = adv.snapshot_for(show_id, user_id)
    if not snap:
        return [], [], None
    mixes = [o.get("mix_name") for o in snap.get("outputs") or []
             if (o.get("mix_name") or "").strip()]
    sources = [i.get("source") for i in snap.get("inputs") or []
               if (i.get("source") or "").strip()]
    return mixes, sources, snap


def _performer_mixes(snap, performer):
    """Which mixes belong to this performer. The server's answer, not the
    form's - a phone that offers only your own mixes is a convenience, and
    this is the check."""
    if not snap:
        return []
    return [o.get("mix_name") for o in snap.get("outputs") or []
            if (o.get("performer") or "").strip().lower() == (performer or "").strip().lower()
            and (o.get("mix_name") or "").strip()]


# --- the desk ----------------------------------------------------------------

@bp.route("/<show_id>")
@require_show
def desk(show_id, user):
    mixes, sources, snap = _mixes_and_sources(show_id, user["id"])
    return render_template(
        "stage/desk.html", active_page="stage",
        show_id=show_id, snapshot=snap,
        requests=st.for_show(show_id, user["id"], open_only=True),
        history=st.for_show(show_id, user["id"])[:40],
        summary=st.summary(show_id, user["id"]),
        presence=st.presence(show_id),
        cursor=st.cursor(show_id),
        mixes=mixes, sources=sources,
        steps=st.STEPS_DB, step_labels=st.STEP_LABELS,
        wording=st.PERFORMER_WORDING, labels=st.KIND_LABELS,
        open_states=st.OPEN_STATES,
        **_ctx())


@bp.route("/<show_id>/events")
@require_show
def events(show_id, user):
    """The poll. Returns only what the client has not seen, plus the summary
    it needs to redraw its counters without a second request."""
    since = request.args.get("since", 0)
    try:
        since = int(since)
    except (TypeError, ValueError):
        since = 0
    return jsonify({
        "cursor": st.cursor(show_id),
        "events": st.events_since(show_id, since),
        "summary": st.summary(show_id, user["id"]),
    })


@bp.route("/<show_id>/request/<request_id>/<action>", methods=["POST"])
@require_show
def act(show_id, user, request_id, action):
    """The desk's buttons. One route, because they are one act - an engineer
    deciding - and splitting them would put the transition rules in five
    places instead of one."""
    actor = user.get("name") or user.get("email") or ""
    req = st.get(request_id, user["id"])
    if req is None or req["show_id"] != show_id:
        abort(404)

    if action == "acknowledge":
        st.acknowledge(request_id, user["id"], actor=actor)
    elif action == "modify":
        try:
            step = int(request.form.get("step_db") or 0)
        except (TypeError, ValueError):
            step = 0
        st.modify(request_id, user["id"], step, actor=actor,
                  note=request.form.get("note") or "")
    elif action == "approve":
        st.approve(request_id, user["id"], actor=actor)
    elif action == "applied":
        # applied_manually, NOT applied. An engineer moving a fader is not a
        # console confirming a command and the two must never read alike.
        st.apply_manually(request_id, user["id"], actor=actor,
                          note=request.form.get("note") or "")
    elif action == "reject":
        st.reject(request_id, user["id"], actor=actor,
                  reason=request.form.get("reason") or "")
    elif action == "revert":
        st.revert(request_id, user["id"], actor=actor)
    else:
        abort(404)
    return redirect(url_for("stage.desk", show_id=show_id))


@bp.route("/<show_id>/lock", methods=["POST"])
@require_show
def lock(show_id, user):
    scope = (request.form.get("scope") or "").strip()
    target = (request.form.get("target") or "").strip()
    actor = user.get("name") or user.get("email") or ""
    if request.form.get("release"):
        st.unlock(show_id, scope, target)
    elif not st.lock(show_id, scope, target,
                     reason=request.form.get("reason") or "", by_whom=actor):
        abort(400)
    return redirect(url_for("stage.desk", show_id=show_id))


# --- the phone ---------------------------------------------------------------

@bp.route("/<show_id>/me")
@require_show
def performer(show_id, user):
    """The performer's page.

    Signed-in only for now. The brief's QR and guest tokens belong with the
    share links TOUR already owns (tour_share_links: opaque, revocable,
    expiring, scoped to one show) and wiring them is its own piece of work -
    so this says who it is for rather than pretending anybody can open it.
    """
    mixes, sources, snap = _mixes_and_sources(show_id, user["id"])
    who = (request.args.get("as") or "").strip()
    people = sorted({(o.get("performer") or "").strip()
                     for o in (snap or {}).get("outputs") or []
                     if (o.get("performer") or "").strip()})
    mine = _performer_mixes(snap, who) if who else []
    mix = (request.args.get("mix") or (mine[0] if mine else "")).strip()
    return render_template(
        "stage/performer.html", active_page="stage",
        show_id=show_id, snapshot=snap, people=people, who=who,
        my_mixes=mine, mix=mix, sources=sources,
        steps=st.STEPS_DB, step_labels=st.STEP_LABELS,
        reports=st.REPORTS, labels=st.KIND_LABELS,
        wording=st.PERFORMER_WORDING,
        mine_open=st.for_performer(show_id, who)[:12] if who else [],
        locked=st.locked_reason(show_id, performer=who, mix=mix),
        cursor=st.cursor(show_id),
        **_ctx())


@bp.route("/<show_id>/ask", methods=["POST"])
@require_show
def ask(show_id, user):
    who = (request.form.get("performer") or "").strip()
    mix = (request.form.get("mix") or "").strip()
    _mixes, sources, snap = _mixes_and_sources(show_id, user["id"])
    try:
        st.submit(show_id, user["id"], who, mix,
                  (request.form.get("kind") or "").strip(),
                  source=(request.form.get("source") or "").strip(),
                  step_db=request.form.get("step_db") or 0,
                  note=request.form.get("note") or "",
                  # The server's own answer to "is this yours", from the
                  # frozen version - not from the form that was submitted.
                  allowed_mixes=_performer_mixes(snap, who),
                  allowed_sources=sources)
    except st.Refused as refused:
        return redirect(url_for("stage.performer", show_id=show_id, **{
            "as": who, "mix": mix, "refused": str(refused)}))
    return redirect(url_for("stage.performer", show_id=show_id,
                            **{"as": who, "mix": mix}))


@bp.route("/<show_id>/cancel/<request_id>", methods=["POST"])
@require_show
def cancel(show_id, user, request_id):
    req = st.get(request_id, user["id"])
    if req is None or req["show_id"] != show_id:
        abort(404)
    st.cancel(request_id, user["id"], actor=req["performer"])
    return redirect(url_for("stage.performer", show_id=show_id,
                            **{"as": req["performer"], "mix": req["mix"]}))


def init(app, current_user=None, dashboard_context=None):
    global _current_user, _dashboard_context
    _current_user = current_user
    _dashboard_context = dashboard_context
    st.init_stage()
    app.register_blueprint(bp)
