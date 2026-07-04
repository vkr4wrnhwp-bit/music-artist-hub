from dataclasses import asdict
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request

from royalty_data import (
    add_split,
    advance_claim,
    assess_advance_eligibility,
    catalog_completeness_score,
    complete_registration_step,
    COLLABORATOR_ROLES,
    estimate_catalog_value,
    get_action_center,
    get_collaborators,
    get_overview_health,
    recent_payout_rows,
    get_recovery_summary,
    invite_collaborator,
    generate_report,
    get_available_reports,
    get_catalog_value_tracker,
    get_claims,
    get_dashboard_story,
    get_documents_vault,
    get_earnings_trend,
    get_fixes_queue,
    get_health_factors,
    get_health_recommendations,
    get_kpis,
    get_missing_royalty_findings,
    get_platform_balances,
    get_platform_catalog,
    get_recent_payouts,
    get_registration_wizard,
    get_rights_conflicts,
    get_royalty_forecast,
    get_royalty_goal,
    get_royalty_leak_alerts,
    get_since_last_login_summary,
    get_smart_recommendations,
    get_song,
    get_songs,
    get_top_royalty_leaks,
    get_payout_calendar,
    get_upcoming_releases,
    WIZARD_TARGETS,
    WIZARD_TARGET_LABELS,
    live_song,
    meter_lit_segments,
    metadata_completion_score,
    money_left_on_table,
    registration_checklist_score,
    reject_claim,
    remove_collaborator,
    remove_split,
    royalty_health_score,
    royalty_progress,
    set_connection_status,
    set_fix_status,
    update_collaborator_role,
    song_check_status,
    song_missing_issues,
    split_total_percentage,
    splits_fully_confirmed,
    toggle_split_confirmed,
    total_royalties,
    upcoming_payout_total,
)


def build_dashboard_context():
    balances = get_platform_balances()
    payouts = get_recent_payouts()
    kpis = get_kpis()
    total = total_royalties(balances)
    goal = get_royalty_goal()
    max_balance = max((balance.amount for balance in balances), default=0)
    balance_meters = [
        {"balance": b, "segments": meter_lit_segments(b.amount, max_balance)}
        for b in balances
    ]
    catalog = get_platform_catalog()
    health_factors = get_health_factors(catalog)

    songs = [live_song(s) for s in get_songs()]
    songs_summary = [
        {
            "song": s,
            "missing_count": len(song_missing_issues(s)),
            "connected_platform_count": len(s.platform_earnings),
            "splits_confirmed": splits_fully_confirmed(s),
            "split_total": split_total_percentage(s),
        }
        for s in songs
    ]
    metadata_scores = [metadata_completion_score(s) for s in songs]
    avg_metadata_score = round(sum(metadata_scores) / len(metadata_scores) * 100) if songs else 0
    worst_metadata_songs = sorted(songs, key=metadata_completion_score)[:3]

    payout_calendar = get_payout_calendar()
    claims = get_claims(catalog)
    alerts = get_royalty_leak_alerts(balances, payouts, kpis, catalog)
    smart_recommendations = get_smart_recommendations(alerts, songs)
    missing_findings = get_missing_royalty_findings(catalog)

    earnings_trend = get_earnings_trend()
    catalog_value = estimate_catalog_value(earnings_trend)
    advance_eligibility = assess_advance_eligibility(
        earnings_trend, payout_calendar, catalog_value["mid"], total
    )

    documents_vault = get_documents_vault(songs)
    value_tracker = get_catalog_value_tracker(earnings_trend)

    return {
        "story": get_dashboard_story(total, missing_findings, catalog_value, smart_recommendations),
        "money_left": money_left_on_table(missing_findings),
        "fixes_queue": get_fixes_queue(catalog, songs, missing_findings),
        "top_leaks": get_top_royalty_leaks(missing_findings),
        "documents_vault": documents_vault,
        "completeness_score": catalog_completeness_score(songs, catalog, documents_vault),
        "releases": get_upcoming_releases(),
        "forecast": get_royalty_forecast(earnings_trend),
        "value_tracker": value_tracker,
        "available_reports": get_available_reports(),
        "since_last_login": get_since_last_login_summary(catalog, songs, value_tracker["pct_change"], catalog_value["mid"]),
        "overview_health": get_overview_health(catalog, songs),
        "action_center": get_action_center(alerts, payouts),
        "recent_payout_rows": recent_payout_rows(),
        "conflicts": get_rights_conflicts(songs),
        "registration_wizards": [get_registration_wizard(s) for s in songs],
        "wizard_targets": WIZARD_TARGETS,
        "wizard_target_labels": WIZARD_TARGET_LABELS,
        "collaborators": get_collaborators(),
        "collaborator_roles": COLLABORATOR_ROLES,
        "alerts": alerts,
        "smart_recommendations": smart_recommendations,
        "platform_catalog": catalog,
        "health_score": royalty_health_score(health_factors),
        "health_factors": health_factors,
        "health_recommendations": get_health_recommendations(health_factors),
        "balance_meters": balance_meters,
        "total": total,
        "goal": goal,
        "progress": royalty_progress(total, goal),
        "kpis": kpis,
        "earnings_trend": earnings_trend,
        "payouts": payouts,
        "songs_summary": songs_summary,
        "avg_metadata_score": avg_metadata_score,
        "worst_metadata_songs": [
            {"song": s, "score": round(metadata_completion_score(s) * 100)}
            for s in worst_metadata_songs
        ],
        "payout_calendar": payout_calendar,
        "upcoming_payout_total": round(upcoming_payout_total(payout_calendar), 2),
        "claims": claims,
        "catalog_value": catalog_value,
        "advance_eligibility": advance_eligibility,
    }


def build_song_detail(song_id):
    song = get_song(song_id)
    if song is None:
        return None
    song = live_song(song)
    payouts = [p for p in get_recent_payouts() if p.song == song.title]
    status = song_check_status(song)
    return {
        "id": song.id,
        "title": song.title,
        "isrc": song.isrc,
        "iswc": song.iswc,
        "upc": song.upc,
        "master_owner": song.master_owner,
        "writers": song.writers,
        "producers": song.producers,
        "publisher": song.publisher,
        "lyrics_on_file": song.lyrics_on_file,
        "alternate_titles": song.alternate_titles,
        "total_earned": round(song.total_earned, 2),
        "streams": song.streams,
        "platform_earnings": song.platform_earnings,
        "splits": [
            {"collaborator": sp.collaborator, "role": sp.role, "percentage": sp.percentage, "confirmed": sp.confirmed}
            for sp in song.splits
        ],
        "split_total": split_total_percentage(song),
        "splits_confirmed": splits_fully_confirmed(song),
        "monthly_trend": song.monthly_trend,
        "check_status": status,
        "missing_issues": song_missing_issues(song),
        "metadata_score": round(metadata_completion_score(song) * 100),
        "registration_score": round(registration_checklist_score(song) * 100),
        "recent_payouts": [
            {"platform": p.platform, "status": p.status, "amount": p.amount} for p in payouts
        ],
    }


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        songs = [live_song(s) for s in get_songs()]
        catalog = get_platform_catalog()
        earnings_trend = get_earnings_trend()
        summary = get_recovery_summary(catalog, songs, earnings_trend)
        return render_template(
            "landing.html", summary=summary,
            last_audit=datetime.now().strftime("%I:%M %p").lstrip("0"),
        )

    @app.route("/scan/recovery-summary", methods=["POST"])
    def scan_recovery_summary():
        songs = [live_song(s) for s in get_songs()]
        catalog = get_platform_catalog()
        earnings_trend = get_earnings_trend()
        summary = get_recovery_summary(catalog, songs, earnings_trend)
        return jsonify({
            "ok": True, "summary": summary,
            "scanned_at": datetime.now().strftime("%I:%M %p").lstrip("0"),
        })

    @app.route("/overview")
    def overview():
        return render_template("overview.html", active_page="overview", **build_dashboard_context())

    @app.route("/dashboard")
    def dashboard():
        return redirect("/overview")

    @app.route("/royalties")
    def royalties():
        return render_template("royalties.html", active_page="royalties", **build_dashboard_context())

    @app.route("/catalog")
    def catalog_page():
        return render_template("catalog.html", active_page="catalog", **build_dashboard_context())

    @app.route("/connections")
    def connections():
        return render_template("connections.html", active_page="connections", **build_dashboard_context())

    @app.route("/recovery")
    def recovery():
        return render_template("recovery.html", active_page="recovery", **build_dashboard_context())

    @app.route("/valuation")
    def valuation():
        return render_template("valuation.html", active_page="valuation", **build_dashboard_context())

    @app.route("/reports")
    def reports():
        return render_template("reports.html", active_page="reports", **build_dashboard_context())

    @app.route("/settings")
    def settings():
        return render_template("settings.html", active_page="settings", **build_dashboard_context())

    @app.route("/scan/missing-royalties", methods=["POST"])
    def scan_missing_royalties():
        findings = get_missing_royalty_findings(get_platform_catalog())
        return jsonify({
            "ok": True,
            "count": len(findings),
            "total_estimated": round(sum(f.estimated_value for f in findings), 2),
            "findings": [asdict(f) for f in findings],
        })

    @app.route("/connections/<platform_id>/connect", methods=["POST"])
    def connect_platform(platform_id):
        entry = set_connection_status(platform_id, "connected")
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": entry.status})

    @app.route("/connections/<platform_id>/disconnect", methods=["POST"])
    def disconnect_platform(platform_id):
        entry = set_connection_status(platform_id, "not_connected")
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": entry.status})

    @app.route("/songs/<song_id>")
    def song_detail(song_id):
        detail = build_song_detail(song_id)
        if detail is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "song": detail})

    @app.route("/songs/<song_id>/splits", methods=["POST"])
    def add_split_route(song_id):
        data = request.get_json(silent=True) or {}
        collaborator = (data.get("collaborator") or "").strip()
        role = (data.get("role") or "").strip()
        try:
            percentage = float(data.get("percentage"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid percentage"}), 400
        if not collaborator or not role or percentage <= 0:
            return jsonify({"ok": False, "error": "Missing required fields"}), 400
        splits = add_split(song_id, collaborator, role, percentage)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
        })

    @app.route("/songs/<song_id>/splits/<int:index>/remove", methods=["POST"])
    def remove_split_route(song_id, index):
        splits = remove_split(song_id, index)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
        })

    @app.route("/songs/<song_id>/splits/<int:index>/toggle", methods=["POST"])
    def toggle_split_route(song_id, index):
        splits = toggle_split_confirmed(song_id, index)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
            "splits_confirmed": splits_fully_confirmed(song),
        })

    @app.route("/claims/<claim_id>/advance", methods=["POST"])
    def advance_claim_route(claim_id):
        new_status = advance_claim(claim_id, get_platform_catalog())
        if new_status is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": new_status})

    @app.route("/claims/<claim_id>/reject", methods=["POST"])
    def reject_claim_route(claim_id):
        new_status = reject_claim(claim_id, get_platform_catalog())
        if new_status is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": new_status})

    @app.route("/fixes/<item_id>/status", methods=["POST"])
    def update_fix_status(item_id):
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        result = set_fix_status(item_id, status)
        if result is None:
            return jsonify({"ok": False}), 400
        return jsonify({"ok": True, "status": result})

    @app.route("/songs/<song_id>/registration-wizard")
    def registration_wizard(song_id):
        song = get_song(song_id)
        if song is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "wizard": get_registration_wizard(song)})

    @app.route("/songs/<song_id>/registration-wizard/<target>/complete", methods=["POST"])
    def complete_registration_wizard_step(song_id, target):
        wizard = complete_registration_step(song_id, target)
        if wizard is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "wizard": wizard})

    @app.route("/reports/<report_id>/generate", methods=["POST"])
    def generate_report_route(report_id):
        report = generate_report(report_id)
        if report is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "report": report})

    @app.route("/collaborators/invite", methods=["POST"])
    def invite_collaborator_route():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        role = data.get("role")
        songs = data.get("songs") or []
        collaborator = invite_collaborator(name, email, role, songs)
        if collaborator is None:
            return jsonify({"ok": False, "error": "Invalid name, email, or role"}), 400
        return jsonify({"ok": True, "collaborator": asdict(collaborator)})

    @app.route("/collaborators/<collaborator_id>/role", methods=["POST"])
    def update_collaborator_role_route(collaborator_id):
        data = request.get_json(silent=True) or {}
        collaborator = update_collaborator_role(collaborator_id, data.get("role"))
        if collaborator is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "collaborator": asdict(collaborator)})

    @app.route("/collaborators/<collaborator_id>/remove", methods=["POST"])
    def remove_collaborator_route(collaborator_id):
        removed = remove_collaborator(collaborator_id)
        if not removed:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/alerts/<alert_id>/resolve", methods=["POST"])
    def resolve_alert(alert_id):
        balances = get_platform_balances()
        payouts = get_recent_payouts()
        kpis = get_kpis()
        catalog = get_platform_catalog()
        alerts = get_royalty_leak_alerts(balances, payouts, kpis, catalog)
        alert = next((a for a in alerts if a.id == alert_id), None)
        if alert is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "message": alert.resolution_message})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
