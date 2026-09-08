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
                   request, session, url_for)

import passport_store as ps
import advance_store as adv
import stage_adapters as adapters
import stage_bridge as sb
import stage_rack as rack
import stage_safety as safety
import stage_store as st

# Fresh device credentials are handed to the page through the session, once,
# and never through the URL: a query string lands in server logs, proxies and
# browser history, and a device token is the only thing that authenticates a
# machine that can move a fader.
_CREDS_KEY = "stage.credentials.once"

bp = Blueprint("stage", __name__, url_prefix="/stage")

# The device's own door. Token-authenticated, never session-authenticated: a
# Stage Bridge is a machine on a venue network, not a person with a login.
dev_bp = Blueprint("bridge", __name__, url_prefix="/bridge")

_current_user = None
_dashboard_context = None


def _signed_in():
    return _current_user() if _current_user else None


def _resolve(show_id, me, permission):
    """Who is acting on this show, and as whom.

    The show's OWNER is the account that owns the passport attachment; every
    stage_store query is scoped to it. The owner holds every permission. A
    seat at the partner that owns the owner's account acts with the
    permission its role carries (partner_store.PERMS), and every such act is
    written to partner_audit. Anybody else is a 404, not a 403: a stranger
    must not learn a show exists from the shape of the refusal.

    Returns (user, member): `user` is the owner's record with the actor's
    name and email on it, so routes keep scoping on user["id"] and naming
    the person who pressed the button.
    """
    import db as store
    import partner_store as pstore
    link = adv.get_attachment(show_id)
    owner_id = link["user_id"] if link else me["id"]
    if owner_id == me["id"]:
        return dict(me, stage_perms=None), None
    member = pstore.member_for_user(me["id"])
    if member is None or not pstore.owns_user(member["partner_id"], owner_id):
        abort(404)
    if not pstore.can(member, permission):
        abort(403)
    owner = store.get_user(owner_id)
    if owner is None:
        abort(404)
    if request.method != "GET":
        pstore.audit(member["partner_id"], "stage." + permission, actor=me,
                     subject_user_id=owner_id, detail=request.path)
    acting = dict(owner)
    acting["name"] = me.get("name") or me.get("email") or ""
    acting["email"] = me.get("email") or ""
    acting["stage_perms"] = {perm for perm in pstore.PERMS if perm.startswith("stage_")
                             and pstore.can(member, perm)}
    return acting, member


def allowed(user, permission):
    """True for the owner; for a partner seat, only if its role carries it."""
    perms = user.get("stage_perms")
    return perms is None or permission in perms


def require_show(permission="stage_review"):
    """Resolve the actor for this show's stage, with a permission.

    A show nobody has advanced has no stage; the signed-in account is then
    treated as its owner, which is what the desk needs to say "attach a
    passport first".
    """
    def wrap(fn):
        @wraps(fn)
        def guarded(show_id, *args, **kwargs):
            me = _signed_in()
            if me is None:
                return redirect(url_for("login", next=request.path))
            user, _member = _resolve(show_id, me, permission)
            return fn(show_id, user, *args, **kwargs)
        return guarded
    return wrap


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
@require_show("stage_review")
def desk(show_id, user):
    mixes, sources, snap = _mixes_and_sources(show_id, user["id"])
    sb.expire_stale(show_id, user["id"])
    import tour_store as ts
    tour_id = ts.tour_id_for_show(show_id)
    return render_template(
        "stage/desk.html", active_page="stage",
        show_id=show_id, snapshot=snap,
        tour_id=tour_id,
        date_url=("/tours/%s/shows/%s?tab=advance#stage" % (tour_id, show_id)) if tour_id else "",
        mode=sb.mode(show_id, user["id"]),
        commands=sb.commands_for_show(show_id, user["id"], limit=12),
        may={"operate": allowed(user, "stage_operate"),
             "configure": allowed(user, "stage_configure"),
             "lockout": allowed(user, "stage_lockout")},
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
@require_show("stage_review")
def events(show_id, user):
    """The poll. Returns only what the client has not seen, plus the summary
    it needs to redraw its counters without a second request."""
    since = request.args.get("since", 0)
    try:
        since = int(since)
    except (TypeError, ValueError):
        since = 0
    # A dead command must not sit at "sent" forever; the poll is the clock.
    sb.expire_stale(show_id, user["id"])
    m = sb.mode(show_id, user["id"])
    return jsonify({
        "cursor": st.cursor(show_id),
        "events": st.events_since(show_id, since),
        "summary": st.summary(show_id, user["id"]),
        "mode": {"mode": m["mode"], "code": m["code"], "reason": m["reason"],
                 "simulated": m["simulated"]},
    })


@bp.route("/<show_id>/request/<request_id>/<action>", methods=["POST"])
@require_show("stage_review")
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
    elif action == "send":
        # Connected control. The safety engine decides; a refusal is written
        # to the log with its code and the desk shows it in words.
        if not allowed(user, "stage_operate"):
            abort(403)
        _cmd, decision = sb.issue(request_id, user["id"], actor=actor)
        if not decision:
            return redirect(url_for("stage.desk", show_id=show_id, refused=decision.reason))
        _drive_if_simulated(show_id, user["id"])
    elif action == "revert":
        if req["state"] == "applied":
            # Applied on the console: the revert is a console command too.
            if not allowed(user, "stage_operate"):
                abort(403)
            _cmd, decision = sb.issue(request_id, user["id"], actor=actor, is_revert=True)
            if not decision:
                return redirect(url_for("stage.desk", show_id=show_id, refused=decision.reason))
            _drive_if_simulated(show_id, user["id"])
        else:
            st.revert(request_id, user["id"], actor=actor)
    else:
        abort(404)
    return redirect(url_for("stage.desk", show_id=show_id))


def _drive_if_simulated(show_id, user_id):
    """The simulator has no bridge of its own, so the web process is it for
    one cycle. A real adapter is never driven from here - run_local refuses."""
    dev = sb.device_for_show(show_id, user_id)
    spec = adapters.spec(dev["adapter_key"]) if dev else None
    if spec and spec["simulated"]:
        sb.run_local(dev["id"], user_id)


# --- the bridge page -----------------------------------------------------------

@bp.route("/<show_id>/bridge")
@require_show("stage_configure")
def bridge(show_id, user):
    m = sb.mode(show_id, user["id"])
    dev = m["device"]
    inst = adapters.instance_for(dev["id"], dev["adapter_key"]) if dev and m["simulated"] else None
    mixes, sources, _snap = _mixes_and_sources(show_id, user["id"])
    # Shown once: popped from the session on this render and gone.
    creds = session.pop(_CREDS_KEY, None) or {}
    if creds.get("show_id") != show_id or (dev and creds.get("device_id") != dev["id"]):
        creds = {}
    return render_template(
        "stage/bridge.html", active_page="stage",
        show_id=show_id, mode=m, device=dev, spec=m["spec"],
        config=sb.config(dev) if dev else {},
        mixes=mixes, sources=sources,
        policy=safety.policy(show_id), bounds=safety.POLICY_BOUNDS,
        adapters=[adapters.spec(k) for k in adapters.available()],
        bench=adapters.bench_enabled(),
        commands=sb.commands_for_show(show_id, user["id"], limit=30),
        heartbeat_age=safety.age_seconds(dev["last_heartbeat"]) if dev else None,
        rack=rack.status(show_id, user["id"]), lamp_words=rack.LAMP_WORDS,
        sim=inst, never=adapters.NEVER,
        token=creds.get("token") or "", signing_key=creds.get("signing_key") or "",
        refused=request.args.get("refused") or "",
        **_ctx())


@bp.route("/<show_id>/bridge/diagnostics.json")
@require_show("stage_configure")
def bridge_diagnostics(show_id, user):
    """The Stage Rack diagnostic export: status, the last 50 events, the last
    20 commands - with every secret column stripped (stage_rack.redact)."""
    body = rack.diagnostics(show_id, user["id"])
    resp = jsonify(body)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Disposition"] = 'inline; filename="stage-%s-diagnostics.json"' % show_id
    return resp


def _hand_over_once(show_id, device, token):
    """Park fresh credentials for exactly one render of the bridge page."""
    session[_CREDS_KEY] = {"show_id": show_id, "device_id": device["id"],
                           "token": token, "signing_key": device["signing_key"]}


@bp.route("/<show_id>/bridge/<action>", methods=["POST"])
@require_show("stage_lockout")
def bridge_act(show_id, user, action):
    actor = user.get("name") or user.get("email") or ""
    # The emergency stop is the one thing every seat may press. Everything
    # else on the bridge is configuration.
    if action != "lockout" and not allowed(user, "stage_configure"):
        abort(403)
    dev = sb.device_for_show(show_id, user["id"])
    if action == "register":
        if dev is not None:
            return redirect(url_for("stage.bridge", show_id=show_id,
                                    refused="Revoke the current Stage Bridge before registering another."))
        try:
            new, token = sb.register(user["id"], show_id, request.form.get("name") or "",
                                     adapter_key=request.form.get("adapter") or "simulator")
        except ValueError as e:
            return redirect(url_for("stage.bridge", show_id=show_id, refused=str(e)))
        _hand_over_once(show_id, new, token)
        return redirect(url_for("stage.bridge", show_id=show_id, credentials="once"))
    if action == "policy":
        _pol, refused = safety.set_policy(show_id, user["id"], **{
            k: request.form.get(k) for k in safety.POLICY_BOUNDS if request.form.get(k)})
        if refused:
            return redirect(url_for("stage.bridge", show_id=show_id,
                                    refused="Out of bounds, not saved: " + ", ".join(refused)))
        return redirect(url_for("stage.bridge", show_id=show_id))
    if dev is None:
        abort(404)
    if action == "patch":
        mixes = {k[4:]: v for k, v in request.form.items() if k.startswith("mix_") and v.strip()}
        sources = {k[4:]: v for k, v in request.form.items() if k.startswith("src_") and v.strip()}
        _cfg, refused = sb.set_config(dev["id"], user["id"], host=request.form.get("host") or "",
                                      mixes=mixes, sources=sources)
        if refused:
            return redirect(url_for("stage.bridge", show_id=show_id,
                                    refused="Not patched (bus 1-16, channel 1-32): " + ", ".join(refused)))
        return redirect(url_for("stage.bridge", show_id=show_id))
    if action == "arm":
        if sb.arm(dev["id"], user["id"], actor=actor) is None:
            return redirect(url_for("stage.bridge", show_id=show_id,
                                    refused="Release the lockout before arming."))
    elif action == "disarm":
        sb.disarm(dev["id"], user["id"], actor=actor)
    elif action == "lockout":
        sb.lockout(dev["id"], user["id"], actor=actor, reason=request.form.get("reason") or "")
    elif action == "release":
        sb.release_lockout(dev["id"], user["id"], actor=actor)
    elif action == "rotate":
        new, token = sb.rotate(dev["id"], user["id"], actor=actor)
        if new is None:
            return redirect(url_for("stage.bridge", show_id=show_id,
                                    refused="A revoked device cannot be rotated."))
        _hand_over_once(show_id, new, token)
        return redirect(url_for("stage.bridge", show_id=show_id, credentials="once"))
    elif action == "revoke":
        sb.revoke(dev["id"], user["id"], actor=actor)
    elif action == "heartbeat":
        # The simulator's bridge lives in this process; this is its pulse.
        spec = adapters.spec(dev["adapter_key"])
        if not spec or not spec["simulated"]:
            abort(404)
        sb.run_local(dev["id"], user["id"])
    elif action == "simulate":
        # Rehearse failure on the desk: take the simulated console offline,
        # or make its next write fail. Only the simulator has these switches.
        spec = adapters.spec(dev["adapter_key"])
        if not spec or not spec["simulated"]:
            abort(404)
        inst = adapters.instance_for(dev["id"], dev["adapter_key"])
        what = request.form.get("what") or ""
        if what == "offline":
            inst.offline = True
        elif what == "online":
            inst.offline = False
        elif what == "fail_next":
            inst.fail_next = "Simulated: the console refused this write."
        elif what == "no_readback":
            inst.confirms = False
        elif what == "readback":
            inst.confirms = True
        sb.heartbeat(sb.get_device(dev["id"]), inst.health())
    else:
        abort(404)
    return redirect(url_for("stage.bridge", show_id=show_id))


# --- the device's door ---------------------------------------------------------

def _device_from_request():
    auth = request.headers.get("Authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    return sb.authenticate(token)


@dev_bp.route("/heartbeat", methods=["POST"])
def device_heartbeat():
    dev = _device_from_request()
    if dev is None:
        return jsonify({"ok": False, "error": "unauthorised"}), 401
    body = request.get_json(silent=True) or {}
    # The rack fields are optional and backward compatible: a phase-5 daemon
    # sends health and software_version only, and the rack reads "Not reported".
    extra = {k: body[k] for k in sb.REPORT_FIELDS if k in body}
    dev = sb.heartbeat(dev, body.get("health") or {"ok": True},
                       software_version=body.get("software_version") or "",
                       report=extra or None)
    return jsonify({"ok": True, "device_id": dev["id"], "armed": bool(dev["armed"]),
                    "lockout": bool(dev["lockout"]), "revoked": bool(dev["revoked_at"]),
                    "heartbeat_stale_s": safety.policy(dev["show_id"])["heartbeat_stale_s"]})


@dev_bp.route("/pull", methods=["POST"])
def device_pull():
    dev = _device_from_request()
    if dev is None:
        return jsonify({"ok": False, "error": "unauthorised"}), 401
    return jsonify({"ok": True, "commands": sb.pull(dev),
                    "armed": bool(dev["armed"]), "lockout": bool(dev["lockout"])})


@dev_bp.route("/ack", methods=["POST"])
def device_ack():
    dev = _device_from_request()
    if dev is None:
        return jsonify({"ok": False, "error": "unauthorised"}), 401
    body = request.get_json(silent=True) or {}
    _cmd, decision = sb.acknowledge(dev, body.get("command_id") or "", body.get("nonce") or "",
                                    body.get("result") or {})
    return jsonify({"ok": decision.allowed, "code": decision.code, "reason": decision.reason})


@dev_bp.route("/reconcile", methods=["POST"])
def device_reconcile():
    dev = _device_from_request()
    if dev is None:
        return jsonify({"ok": False, "error": "unauthorised"}), 401
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "outcomes": sb.reconcile(dev, body.get("entries") or [])})


@bp.route("/<show_id>/lock", methods=["POST"])
@require_show("stage_review")
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

def _performer_page(show_id, owner_id, page_url, act_base, guest=False):
    """The performer's page, for the owner's own session or for a guest who
    opened a TOUR share link. Both read the same frozen version and the same
    queue; only the URLs the page posts to differ."""
    mixes, sources, snap = _mixes_and_sources(show_id, owner_id)
    who = (request.args.get("as") or "").strip()
    people = sorted({(o.get("performer") or "").strip()
                     for o in (snap or {}).get("outputs") or []
                     if (o.get("performer") or "").strip()})
    mine = _performer_mixes(snap, who) if who else []
    mix = (request.args.get("mix") or (mine[0] if mine else "")).strip()
    # A guest has no account, so no dashboard context and no app chrome: the
    # page renders under its own small shell instead of base.html.
    extra = _ctx() if not guest else {}
    return render_template(
        "stage/performer.html", active_page="stage",
        layout="stage/_guest_shell.html" if guest else "base.html",
        show_id=show_id, snapshot=snap, people=people, who=who,
        my_mixes=mine, mix=mix, sources=sources,
        page_url=page_url, act_base=act_base, guest=guest,
        steps=st.STEPS_DB, step_labels=st.STEP_LABELS,
        reports=st.REPORTS, labels=st.KIND_LABELS,
        wording=st.PERFORMER_WORDING,
        mine_open=st.for_performer(show_id, who)[:12] if who else [],
        locked=st.locked_reason(show_id, performer=who, mix=mix),
        cursor=st.cursor(show_id),
        **extra)


def _ask(show_id, owner_id, page_url):
    who = (request.form.get("performer") or "").strip()
    mix = (request.form.get("mix") or "").strip()
    _mixes, sources, snap = _mixes_and_sources(show_id, owner_id)
    args = {"as": who, "mix": mix}
    try:
        st.submit(show_id, owner_id, who, mix,
                  (request.form.get("kind") or "").strip(),
                  source=(request.form.get("source") or "").strip(),
                  step_db=request.form.get("step_db") or 0,
                  note=request.form.get("note") or "",
                  # The server's own answer to "is this yours", from the
                  # frozen version - not from the form that was submitted.
                  allowed_mixes=_performer_mixes(snap, who),
                  allowed_sources=sources)
    except st.Refused as refused:
        args["refused"] = str(refused)
    from urllib.parse import urlencode
    return redirect(page_url + "?" + urlencode(args))


def _cancel(show_id, owner_id, request_id, page_url):
    req = st.get(request_id, owner_id)
    if req is None or req["show_id"] != show_id:
        abort(404)
    st.cancel(request_id, owner_id, actor=req["performer"])
    from urllib.parse import urlencode
    return redirect(page_url + "?" + urlencode({"as": req["performer"], "mix": req["mix"]}))


@bp.route("/<show_id>/me")
@require_show("stage_review")
def performer(show_id, user):
    """The performer's page, in the owner's own session. A performer without
    an account opens the same page through a TOUR share link - see
    guest_page - which is where the brief's QR access lives."""
    return _performer_page(show_id, user["id"], "/stage/%s/me" % show_id, "/stage/%s" % show_id)


@bp.route("/<show_id>/ask", methods=["POST"])
@require_show("stage_review")
def ask(show_id, user):
    return _ask(show_id, user["id"], "/stage/%s/me" % show_id)


@bp.route("/<show_id>/cancel/<request_id>", methods=["POST"])
@require_show("stage_review")
def cancel(show_id, user, request_id):
    return _cancel(show_id, user["id"], request_id, "/stage/%s/me" % show_id)


# --- guests: a performer's phone, through a TOUR share link -----------------

def _guest_link(token):
    """The link, checked the way TOUR checks it, plus the one thing that is
    ours: the scope must be "stage". A password-protected link sends the
    phone to TOUR's password form first; the session key it sets is the
    same one TOUR reads."""
    import tour_os
    import tour_store as ts
    link = ts.get_share_link(token)
    if link is None or link["revoked"] or link["scope"] != "stage" or not link.get("show_id"):
        abort(404)
    tour = ts.get_tour(link["tour_id"])
    if tour is None:
        abort(404)
    if link["expires"] and link["expires"] < tour_os.eng.today_in(tour["home_tz"]):
        abort(410)
    if link["password_hash"] and not session.get("tsl:" + token):
        return None, redirect("/tour-share/%s" % token)
    return link, None


def guest_page(token, link, tour):
    """Called by TOUR's /tour-share/<token> for scope "stage", after the
    password check and the access count."""
    base = "/stage/guest/%s" % token
    return _performer_page(link["show_id"], link["user_id"], base, base, guest=True)


@bp.route("/guest/<token>")
def guest(token):
    link, bounce = _guest_link(token)
    if bounce is not None:
        return bounce
    import tour_store as ts
    ts.touch_share_link(token)
    base = "/stage/guest/%s" % token
    return _performer_page(link["show_id"], link["user_id"], base, base, guest=True)


@bp.route("/guest/<token>/ask", methods=["POST"])
def guest_ask(token):
    link, bounce = _guest_link(token)
    if bounce is not None:
        return bounce
    return _ask(link["show_id"], link["user_id"], "/stage/guest/%s" % token)


@bp.route("/guest/<token>/cancel/<request_id>", methods=["POST"])
def guest_cancel(token, request_id):
    link, bounce = _guest_link(token)
    if bounce is not None:
        return bounce
    return _cancel(link["show_id"], link["user_id"], request_id, "/stage/guest/%s" % token)


@bp.route("/guest/<token>/events")
def guest_events(token):
    link, bounce = _guest_link(token)
    if bounce is not None:
        return jsonify({"ok": False, "error": "password"}), 401
    since = request.args.get("since", 0)
    try:
        since = int(since)
    except (TypeError, ValueError):
        since = 0
    show_id = link["show_id"]
    return jsonify({"cursor": st.cursor(show_id),
                    "events": st.events_since(show_id, since),
                    "summary": {"open": st.summary(show_id, link["user_id"])["open"]}})


def init(app, current_user=None, dashboard_context=None):
    global _current_user, _dashboard_context
    _current_user = current_user
    _dashboard_context = dashboard_context
    st.init_stage()
    sb.init_bridge()
    app.register_blueprint(bp)
    app.register_blueprint(dev_bp)
