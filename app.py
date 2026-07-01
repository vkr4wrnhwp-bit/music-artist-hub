from flask import Flask, render_template

from royalty_data import (
    get_earnings_trend,
    get_kpis,
    get_platform_balances,
    get_recent_payouts,
    total_royalties,
)


def create_app():
    app = Flask(__name__)

    @app.route("/dashboard")
    def dashboard():
        balances = get_platform_balances()
        return render_template(
            "dashboard.html",
            balances=balances,
            total=total_royalties(balances),
            kpis=get_kpis(),
            earnings_trend=get_earnings_trend(),
            payouts=get_recent_payouts(),
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
