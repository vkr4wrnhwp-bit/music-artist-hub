from flask import Flask, redirect, render_template

from royalty_data import (
    get_earnings_trend,
    get_kpis,
    get_platform_balances,
    get_recent_payouts,
    get_royalty_goal,
    meter_lit_segments,
    royalty_progress,
    total_royalties,
)


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/dashboard")
    def dashboard():
        balances = get_platform_balances()
        total = total_royalties(balances)
        goal = get_royalty_goal()
        max_balance = max(balance.amount for balance in balances)
        balance_meters = [
            {"balance": b, "segments": meter_lit_segments(b.amount, max_balance)}
            for b in balances
        ]
        return render_template(
            "dashboard.html",
            balance_meters=balance_meters,
            total=total,
            goal=goal,
            progress=royalty_progress(total, goal),
            kpis=get_kpis(),
            earnings_trend=get_earnings_trend(),
            payouts=get_recent_payouts(),
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
