from flask import Flask, jsonify, redirect, render_template

from royalty_data import (
    get_action_items,
    get_earnings_trend,
    get_health_factors,
    get_health_recommendations,
    get_kpis,
    get_platform_balances,
    get_platform_catalog,
    get_recent_payouts,
    get_royalty_goal,
    meter_lit_segments,
    royalty_health_score,
    royalty_progress,
    set_connection_status,
    total_royalties,
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
    return {
        "actions": get_action_items(balances, payouts, kpis),
        "platform_catalog": catalog,
        "health_score": royalty_health_score(health_factors),
        "health_factors": health_factors,
        "health_recommendations": get_health_recommendations(health_factors),
        "balance_meters": balance_meters,
        "total": total,
        "goal": goal,
        "progress": royalty_progress(total, goal),
        "kpis": kpis,
        "earnings_trend": get_earnings_trend(),
        "payouts": payouts,
    }


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html", **build_dashboard_context())

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

    @app.route("/actions/<action_id>/complete", methods=["POST"])
    def complete_action(action_id):
        balances = get_platform_balances()
        payouts = get_recent_payouts()
        kpis = get_kpis()
        actions = get_action_items(balances, payouts, kpis)
        action = next((a for a in actions if a.id == action_id), None)
        if action is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "message": action.result_message})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
