"""REACH web layer.

One blueprint under ``/reach``, mounted by ``app.py``. The prefix is kept even
though REACH is now its own application: every route, bookmark, test and doc
already refers to it, and ``/`` redirects here.
"""

import json

from flask import Blueprint, abort, jsonify, render_template, request, url_for

from . import REACH_VERSION
from . import (analytics, approvals, audit, campaigns, catalog, compliance, contacts,
               db, drafts, entities, evidence, firewall, firstparty, humanactions, jobs,
               onboarding, outcomes, pipeline, policy, profile, rbac, relationships,
               scoring, sender)
from .errors import ReachError
from .providers import email as email_provider
from .providers import search as search_provider
from .providers import spotify as spotify_provider

bp = Blueprint("reach", __name__, url_prefix="/reach")


@bp.app_context_processor
def _template_globals():
    # Cache-busts the stylesheet across releases without hashing on every request.
    return {"reach_version": REACH_VERSION}

NAV = [
    ("overview", "Overview"),
    ("discover", "Discover"),
    ("opportunities", "Opportunities"),
    ("review", "Review"),
    ("outreach", "Outreach"),
    ("responses", "Responses"),
    ("placements", "Placements"),
]

GLOBAL_NAV = [
    ("reach.catalog_view", "Catalog"),
    ("reach.relationships_view", "Relationships"),
    ("reach.providers_view", "Provider Health"),
    ("reach.needs_you", "Needs You"),
    ("reach.settings_view", "Settings"),
]


def bootstrap():
    """Idempotent start-up work: tenant, principal, policies, catalog."""
    rbac.ensure_default_tenant()
    policy.seed_policies()
    catalog.ensure_catalog()


def _shell(campaign_id=None, active=None):
    principal = rbac.current_principal()
    return {
        "nav": NAV,
        "global_nav": GLOBAL_NAV,
        "active": active,
        "campaign_id": campaign_id,
        "principal": principal,
        "needs_you_count": humanactions.open_count(),
        "search_state": search_provider.status(),
        "fixture_mode": not search_provider.connected(),
    }


def _json_error(exc, status=400):
    return jsonify({"ok": False, "error": str(exc),
                    "kind": getattr(exc, "kind", "ERROR")}), status


@bp.errorhandler(ReachError)
def _handle_reach_error(exc):
    return _json_error(exc)


# --------------------------------------------------------------------------
# campaign list + creation
# --------------------------------------------------------------------------

@bp.route("/", strict_slashes=False)
def index():
    bootstrap()
    rows = campaigns.list_campaigns()
    items = []
    for row in rows:
        metrics = analytics.campaign_metrics(row["id"])
        items.append({"campaign": row, "metrics": metrics,
                      "health": analytics.campaign_health(row["id"])["score"]})
    return render_template("reach/index.html", campaigns=items,
                           recordings=catalog.recordings(),
                           onboarding=onboarding.status(), **_shell(active="overview"))


@bp.route("/catalog")
def catalog_view():
    bootstrap()
    rows = catalog.recordings()
    items = []
    for row in rows:
        used = db.query("SELECT id FROM campaign WHERE recording_id = ?", (row["id"],))
        items.append({
            "recording": row,
            "track": catalog.track(row),
            "readiness": catalog.release_readiness(row["id"]),
            "campaign_count": len(used),
        })
    return render_template("reach/catalog.html", tracks=items, **_shell())


@bp.route("/catalog", methods=["POST"])
def add_track():
    bootstrap()
    data = request.get_json(silent=True) or request.form
    try:
        recording_id = catalog.add_track(dict(data))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "recording_id": recording_id})


@bp.route("/catalog/<recording_id>/delete", methods=["POST"])
def delete_track(recording_id):
    try:
        catalog.delete_track(recording_id)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True})


@bp.route("/new")
def new_campaign():
    bootstrap()
    recording_id = request.args.get("recording_id")
    recordings = catalog.recordings()
    if not recording_id and recordings:
        recording_id = recordings[0]["id"]
    recording = catalog.get_recording(recording_id) if recording_id else None
    if recording is None:
        abort(404)
    profile_id = profile.get_or_create(recording_id)
    return render_template(
        "reach/new.html",
        recordings=recordings,
        recording=recording,
        identifiers=catalog.identifiers(recording_id),
        readiness=catalog.release_readiness(recording_id),
        profile_id=profile_id,
        profile_fields=profile.fields(profile_id),
        completeness=profile.completeness(profile_id),
        attestation=catalog.active_attestation(recording_id),
        attestation_scope=catalog.RIGHTS_SCOPE,
        attestation_statement=catalog.ATTESTATION_STATEMENT,
        audio_state=firstparty.audio_analysis_state(),
        channels=campaigns.CHANNELS,
        modes=[campaigns.SCOUT, campaigns.COPILOT],
        **_shell(active="overview"),
    )


@bp.route("/profile/<profile_id>/field", methods=["POST"])
def set_profile_field(profile_id):
    data = request.get_json(silent=True) or request.form
    field = (data.get("field") or "").strip()
    value = data.get("value")
    try:
        profile.set_field(profile_id, field, value)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "completeness": profile.completeness(profile_id)})


@bp.route("/recordings/<recording_id>/attest", methods=["POST"])
def attest(recording_id):
    try:
        attestation_id = catalog.attest_rights(recording_id)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "attestation_id": attestation_id,
                    "readiness": catalog.release_readiness(recording_id)})


@bp.route("/campaigns", methods=["POST"])
def create_campaign():
    data = request.get_json(silent=True) or request.form
    try:
        campaign_id = campaigns.create(
            data.get("recording_id"),
            name=data.get("name") or None,
            mode=data.get("mode") or campaigns.SCOUT,
            territories=_list(data, "territories"),
            channels=_list(data, "channels") or None,
            search_budget=_int(data.get("search_budget")),
            domain_budget=_int(data.get("domain_budget")),
            daily_send_limit=_int(data.get("daily_send_limit")),
        )
    except ReachError as exc:
        return _json_error(exc)
    analytics.capture_baseline(campaign_id)
    humanactions.build_dsp_tasks(campaign_id)
    return jsonify({"ok": True, "campaign_id": campaign_id,
                    "url": url_for("reach.discover", campaign_id=campaign_id)})


def _list(data, key):
    if hasattr(data, "getlist"):
        values = data.getlist(key)
        if values:
            return [value for value in values if value]
    raw = data.get(key)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# campaign screens
# --------------------------------------------------------------------------

def _campaign_or_404(campaign_id):
    row = campaigns.get(campaign_id)
    if row is None:
        abort(404)
    return row


@bp.route("/campaigns/<campaign_id>")
def overview(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    return render_template(
        "reach/overview.html",
        campaign=campaign,
        recording=catalog.get_recording(campaign["recording_id"]),
        metrics=analytics.campaign_metrics(campaign_id),
        health=analytics.campaign_health(campaign_id),
        pipeline_counts=campaigns.pipeline_counts(campaign_id),
        settings=campaigns.settings(campaign_id),
        progress=jobs.progress_for_campaign(campaign_id),
        stop_reason=pipeline.should_stop(campaign_id),
        tasks=humanactions.queue(campaign_id)[:5],
        task_count=humanactions.open_count(campaign_id),
        attribution=analytics.attribution_report(campaign_id),
        **_shell(campaign_id, "overview"),
    )


@bp.route("/campaigns/<campaign_id>/discover")
def discover(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    return render_template(
        "reach/discover.html",
        campaign=campaign,
        queries=pipeline.plan_queries(campaign_id),
        progress=jobs.progress_for_campaign(campaign_id),
        job_rows=jobs.for_campaign(campaign_id, limit=40),
        budget=campaigns.budget(campaign_id),
        settings=campaigns.settings(campaign_id),
        stop_reason=pipeline.should_stop(campaign_id),
        dead_letters=jobs.dead_letters(),
        **_shell(campaign_id, "discover"),
    )


@bp.route("/campaigns/<campaign_id>/discover/start", methods=["POST"])
def start_discovery(campaign_id):
    """Start discovery, or resume it — and only ever drain in short chunks.

    Each call does at most ~20 seconds of work and reports what is left, so no
    request can hit the server's timeout mid-run; the page keeps calling until
    nothing is pending. When queued jobs already exist the call resumes them
    rather than planning a second run on a spent search budget.
    """
    _campaign_or_404(campaign_id)
    job_id = None
    try:
        if not jobs.pending_count(campaign_id):
            job_id = pipeline.start(campaign_id)
        processed = pipeline.run_to_completion(campaign_id, max_seconds=20)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "job_id": job_id, "jobs_processed": processed,
                    "pending": jobs.pending_count(campaign_id),
                    "progress": jobs.progress_for_campaign(campaign_id)})


@bp.route("/campaigns/<campaign_id>/discover/progress")
def discovery_progress(campaign_id):
    _campaign_or_404(campaign_id)
    return jsonify({
        "ok": True,
        "progress": jobs.progress_for_campaign(campaign_id),
        "metrics": analytics.campaign_metrics(campaign_id),
        "stop_reason": pipeline.should_stop(campaign_id),
    })


@bp.route("/campaigns/<campaign_id>/discover/cancel", methods=["POST"])
def cancel_discovery(campaign_id):
    _campaign_or_404(campaign_id)
    try:
        cancelled = jobs.cancel_campaign_jobs(campaign_id)
        campaigns.set_status(campaign_id, campaigns.PAUSED)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "cancelled": cancelled})


@bp.route("/campaigns/<campaign_id>/opportunities")
def opportunities(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    status = request.args.get("status") or None
    return render_template(
        "reach/opportunities.html",
        campaign=campaign,
        targets=campaigns.targets(campaign_id, status=status),
        status_counts=campaigns.status_counts(campaign_id),
        pipeline_counts=campaigns.pipeline_counts(campaign_id),
        statuses=campaigns.TARGET_STATUSES,
        selected_status=status,
        **_shell(campaign_id, "opportunities"),
    )


@bp.route("/campaigns/<campaign_id>/targets/<target_id>")
def target_detail(campaign_id, target_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    target = campaigns.get_target(target_id)
    if target is None or target["campaign_id"] != campaign_id:
        abort(404)

    outlet = entities.get_outlet(target["outlet_id"])
    method = approvals._method_for(target)
    score = scoring.latest_score(target_id)
    risk = scoring.latest_risk(target_id)
    decision_row = compliance.latest_decision(target_id)

    return render_template(
        "reach/target.html",
        campaign=campaign,
        target=target,
        outlet=outlet,
        route=entities.best_route(target["outlet_id"]),
        routes=entities.routes_for_outlet(target["outlet_id"]),
        score=score,
        score_reasons=json.loads(score["reasons_json"]) if score else [],
        score_components=json.loads(score["components_json"]) if score else {},
        component_labels=scoring.COMPONENT_LABELS,
        risk=risk,
        risk_signals=json.loads(risk["signals_json"]) if risk else [],
        compliance_record=compliance.decision_record(decision_row),
        compliance_decision=decision_row["decision"] if decision_row else None,
        contact_method=method,
        sendability=contacts.sendability(method["id"]) if method else None,
        contact_evidence=contacts.method_evidence(method["id"]) if method else [],
        outlet_evidence=evidence.summary("outlet", target["outlet_id"]),
        draft=drafts.for_target(target_id),
        relationship_history=relationships.history(target["outlet_id"]),
        related_outlets=[entities.get_outlet(oid) for oid in
                         json.loads(target["related_outlets_json"] or "[]")],
        rejection_reasons=campaigns.REJECTION_REASONS,
        **_shell(campaign_id, "opportunities"),
    )


@bp.route("/targets/<target_id>/status", methods=["POST"])
def set_target_status(target_id):
    data = request.get_json(silent=True) or request.form
    try:
        rbac.require("target.edit")
        status = campaigns.set_target_status(
            target_id, data.get("status"), reason=data.get("reason"),
            rejection_reason=data.get("rejection_reason") or None,
        )
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "status": status})


@bp.route("/targets/<target_id>/score-override", methods=["POST"])
def override_score(target_id):
    data = request.get_json(silent=True) or request.form
    try:
        scoring.override_score(target_id, _int(data.get("score")) or 0,
                               data.get("reason") or "")
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# review / approval
# --------------------------------------------------------------------------

@bp.route("/campaigns/<campaign_id>/review")
def review(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    queue = approvals.approval_queue(campaign_id)
    selected_id = request.args.get("target_id") or (queue[0]["target_id"] if queue else None)
    view = approvals.approval_view(selected_id) if selected_id else None
    return render_template(
        "reach/review.html",
        campaign=campaign,
        queue=queue,
        view=view,
        selected_id=selected_id,
        health=sender.health_summary(),
        throttle=sender.throttle_state(campaign_id),
        ready_targets=campaigns.targets(campaign_id, status=campaigns.READY),
        draftable_targets=campaigns.targets(campaign_id, status=campaigns.QUALIFIED),
        **_shell(campaign_id, "review"),
    )


@bp.route("/targets/<target_id>/draft", methods=["POST"])
def generate_draft(target_id):
    try:
        draft_id = drafts.generate(target_id)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "draft_id": draft_id})


@bp.route("/campaigns/<campaign_id>/draft-all", methods=["POST"])
def draft_all(campaign_id):
    _campaign_or_404(campaign_id)
    created, failed = [], []
    for target in campaigns.targets(campaign_id, status=campaigns.READY):
        try:
            created.append(drafts.generate(target["id"]))
        except ReachError as exc:
            failed.append({"target_id": target["id"], "error": str(exc)})
    return jsonify({"ok": True, "created": len(created), "failed": failed})


@bp.route("/drafts/<draft_id>/edit", methods=["POST"])
def edit_draft(draft_id):
    data = request.get_json(silent=True) or request.form
    try:
        digest = drafts.edit(draft_id, subject=data.get("subject"), body=data.get("body"))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "payload_hash": digest})


@bp.route("/targets/<target_id>/approve", methods=["POST"])
def approve(target_id):
    data = request.get_json(silent=True) or request.form
    try:
        approval_id = approvals.approve(target_id, cost=float(data.get("cost") or 0))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "approval_id": approval_id})


@bp.route("/targets/<target_id>/send", methods=["POST"])
def send(target_id):
    try:
        submission_id = approvals.send_approved(target_id)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "submission_id": submission_id})


# --------------------------------------------------------------------------
# outreach / responses / placements
# --------------------------------------------------------------------------

@bp.route("/campaigns/<campaign_id>/outreach")
def outreach(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    sent = db.query(
        "SELECT s.*, o.name AS outlet_name, d.subject FROM submission s "
        "JOIN campaign_target t ON t.id = s.target_id "
        "JOIN outlet o ON o.id = t.outlet_id "
        "LEFT JOIN outreach_draft d ON d.target_id = t.id "
        "WHERE t.campaign_id = ? ORDER BY s.created_at DESC LIMIT 200",
        (campaign_id,),
    )
    return render_template(
        "reach/outreach.html",
        campaign=campaign,
        submissions=sent,
        health=sender.health_summary(),
        throttle=sender.throttle_state(campaign_id),
        follow_ups=outcomes.follow_ups_due(),
        **_shell(campaign_id, "outreach"),
    )


@bp.route("/campaigns/<campaign_id>/responses")
def responses(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    return render_template(
        "reach/responses.html",
        campaign=campaign,
        responses=outcomes.responses(campaign_id),
        awaiting=campaigns.targets(campaign_id,
                                   statuses=[campaigns.SENT, campaigns.SUBMITTED,
                                             campaigns.DELIVERED]),
        kinds=outcomes.RESPONSE_KINDS,
        **_shell(campaign_id, "responses"),
    )


@bp.route("/targets/<target_id>/response", methods=["POST"])
def record_response(target_id):
    data = request.get_json(silent=True) or request.form
    try:
        response_id = outcomes.record_response(
            target_id, data.get("kind"), body_excerpt=data.get("body") or None,
        )
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "response_id": response_id})


@bp.route("/campaigns/<campaign_id>/placements")
def placements(campaign_id):
    bootstrap()
    campaign = _campaign_or_404(campaign_id)
    rows = outcomes.placements(campaign_id)
    return render_template(
        "reach/placements.html",
        campaign=campaign,
        placements=rows,
        values={row["id"]: analytics.placement_value(row["id"]) for row in rows},
        evidence_sources=outcomes.EVIDENCE_SOURCES,
        accepted=campaigns.targets(campaign_id, statuses=[campaigns.ACCEPTED,
                                                          campaigns.SENT,
                                                          campaigns.SUBMITTED]),
        attribution=analytics.attribution_report(campaign_id),
        **_shell(campaign_id, "placements"),
    )


@bp.route("/targets/<target_id>/placement", methods=["POST"])
def record_placement(target_id):
    data = request.get_json(silent=True) or request.form
    try:
        placement_id = outcomes.record_placement(
            target_id, data.get("evidence_source"), url=data.get("url") or None,
            program_name=data.get("program_name") or None,
            position=_int(data.get("position")),
            excerpt=data.get("excerpt") or None,
        )
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "placement_id": placement_id})


# --------------------------------------------------------------------------
# global screens
# --------------------------------------------------------------------------

@bp.route("/needs-you")
def needs_you():
    bootstrap()
    campaign_id = request.args.get("campaign_id") or None
    return render_template(
        "reach/needs_you.html",
        tasks=humanactions.queue(campaign_id, include_done=False),
        done=humanactions.queue(campaign_id, include_done=True)[:0],
        campaigns=campaigns.list_campaigns(),
        selected_campaign=campaign_id,
        **_shell(campaign_id, None),
    )


@bp.route("/tasks/<task_id>/status", methods=["POST"])
def task_status(task_id):
    data = request.get_json(silent=True) or request.form
    try:
        if data.get("status") == humanactions.SNOOZED:
            humanactions.snooze(task_id, days=_int(data.get("days")) or 7)
            return jsonify({"ok": True, "status": humanactions.SNOOZED})
        status = humanactions.set_status(task_id, data.get("status"),
                                         note=data.get("note"))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "status": status})


@bp.route("/relationships")
def relationships_view():
    bootstrap()
    return render_template(
        "reach/relationships.html",
        rows=relationships.listing(),
        **_shell(None, None),
    )


@bp.route("/providers")
def providers_view():
    bootstrap()
    return render_template(
        "reach/providers.html",
        states=policy.all_connection_states(),
        spotify=spotify_provider.status(),
        observability=analytics.observability(),
        global_stop=policy.global_stop_engaged(),
        send_stop=policy.send_stop_engaged(),
        encryption_state=_encryption_state(),
        **_shell(None, None),
    )


def _encryption_state():
    from . import crypto

    return crypto.key_state()


@bp.route("/providers/<provider_id>/kill-switch", methods=["POST"])
def kill_switch(provider_id):
    data = request.get_json(silent=True) or request.form
    enabled = str(data.get("enabled", "true")).lower() in ("1", "true", "yes", "on")
    try:
        policy.set_kill_switch(provider_id, enabled, reason=data.get("reason"))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "state": policy.connection_state(provider_id)})


@bp.route("/providers/<provider_id>/review", methods=["POST"])
def mark_reviewed(provider_id):
    try:
        policy.mark_reviewed(provider_id)
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "state": policy.connection_state(provider_id)})


@bp.route("/providers/<provider_id>/policy")
def provider_policy(provider_id):
    from dataclasses import asdict

    return jsonify({"ok": True, "policy": asdict(policy.get(provider_id)),
                    "usage": asdict(firewall.source_usage_policy(provider_id))})


@bp.route("/settings")
def settings_view():
    bootstrap()
    return render_template(
        "reach/settings.html",
        health=sender.health_summary(),
        suppression=contacts.suppression_list(),
        audit_events=audit.events(limit=40),
        chain_ok=audit.verify_chain()[0],
        global_stop=policy.global_stop_engaged(),
        send_stop=policy.send_stop_engaged(),
        flags=_flag_states(),
        roles=rbac.ROLES,
        permissions=sorted(rbac.PERMISSIONS),
        encryption_state=_encryption_state(),
        email_state=email_provider.status(),
        **_shell(None, None),
    )


def _flag_states():
    from . import config

    return [{"flag": flag, "enabled": config.feature_enabled(flag)}
            for flag in sorted(config.FEATURE_FLAGS)]


@bp.route("/settings/emergency-stop", methods=["POST"])
def emergency_stop():
    data = request.get_json(silent=True) or request.form
    enabled = str(data.get("enabled", "true")).lower() in ("1", "true", "yes", "on")
    scope = data.get("scope") or "send"
    try:
        if scope == "global":
            policy.set_global_stop(enabled, reason=data.get("reason"))
        else:
            sender.emergency_stop(enabled, reason=data.get("reason"))
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "global_stop": policy.global_stop_engaged(),
                    "send_stop": policy.send_stop_engaged()})


@bp.route("/settings/suppression", methods=["POST"])
def add_suppression():
    data = request.get_json(silent=True) or request.form
    try:
        rbac.require("suppression.edit")
        record_id = contacts.suppress(data.get("value"), data.get("reason") or "Manual",
                                      scope=contacts.GLOBAL, source="manual")
    except ReachError as exc:
        return _json_error(exc)
    return jsonify({"ok": True, "id": record_id})


@bp.route("/webhooks/email", methods=["POST"])
def email_webhook():
    """Provider webhook. Rejected unless the shared secret matches."""
    from . import config

    secret = config.env("REACH_EMAIL_WEBHOOK_SECRET")
    provided = request.headers.get("X-Reach-Signature")
    if not secret or provided != secret:
        return jsonify({"ok": False, "error": "Invalid webhook signature"}), 401
    payload = request.get_json(silent=True) or {}
    outcome = outcomes.process_provider_event(
        (payload.get("type") or "").lower(), payload.get("email"),
        target_id=payload.get("target_id"),
    )
    return jsonify({"ok": True, "outcome": outcome})


@bp.route("/evidence/<entity_type>/<entity_id>")
def evidence_panel(entity_type, entity_id):
    """Backs the "Why do we know this?" panel."""
    return jsonify({"ok": True, "evidence": evidence.summary(entity_type, entity_id)})
