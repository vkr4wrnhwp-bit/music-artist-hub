"""One run rate on every money page.

Found on 2026-09-14 while mapping the estimate engines: Statements and
Capital annualised EVERY dollar, undated rows included, over the count
of dated periods; Valuation averaged the dated months and left undated
money out; and the trend was sorted alphabetically, so "JUN-26" came
before "MAY-26". The same account could show two run rates. The rule
now lives in statements_engine.annualize and every page reads it:
dated money only, over the distinct periods it covers, times twelve,
months in calendar order, undated money reported beside it.
"""
import io
import os
import uuid

import pytest

import capital_engine
import db as store
import statements_engine as se
import valuation_engine
from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROWS = [
    {"title": "A", "source": "Spotify", "amount": 300.0, "period": "JUN-26"},
    {"title": "A", "source": "Spotify", "amount": 100.0, "period": "MAY-26"},
    {"title": "B", "source": "Deezer", "amount": 50.0, "period": "MAY-26"},
    {"title": "B", "source": "ASCAP", "amount": 999.0, "period": ""},      # undated: real, not annualised
]
CSV = ("Reporting Period,Track Title,Digital Service Provider,Royalty\n"
       "JUN-26,A,Spotify,300.00\nMAY-26,A,Spotify,100.00\nMAY-26,B,Deezer,50.00\n,B,ASCAP,999.00\n")


def test_the_rule_dated_money_over_its_periods_in_calendar_order():
    run = se.annualize(ROWS)
    assert run["months"] == 2 and run["dated_total"] == 450.0 and run["undated_total"] == 999.0
    assert run["annualized"] == 2700.0, "450 over two months, times twelve; the 999 stays out"
    assert run["monthly"] == [("MAY-26", 150.0), ("JUN-26", 300.0)], "calendar order, not alphabetical"
    assert se.annualize([]) == {"annualized": 0.0, "months": 0, "dated_total": 0.0,
                                "undated_total": 0.0, "monthly": []}


def test_the_summary_reads_the_rule_and_says_what_it_left_out():
    s = se.build_royalty_summary(ROWS)
    assert s["annualized"] == 2700.0 and s["annualized_months"] == 2
    assert s["undated_revenue"] == 999.0 and s["total"] == 1449.0
    assert s["monthly_trend"] == [("MAY-26", 150.0), ("JUN-26", 300.0)]


def test_every_money_page_agrees_on_one_account():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "run-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Run Rate", "email": email, "password": "run-rate-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    client.post("/statements", data={"statement": (io.BytesIO(CSV.encode()), "s.csv")},
                content_type="multipart/form-data")
    with app_obj.app_context():
        uid = store.get_user_by_email(email)["id"]
        rows = store.get_statement_rows(uid)
        run = se.annualize(rows)
        view = valuation_engine.build(uid)
        capital = capital_engine.capital_score(uid)
        eligibility = capital_engine.advance_eligibility(uid)
    assert run["annualized"] == 2700.0
    assert view["annualized"] == 2700.0 and view["months"] == 2 and view["monthly_avg"] == 225.0
    assert [m["period"] for m in view["monthly"]] == ["MAY-26", "JUN-26"]
    assert view["undated_rows"] == 1
    assert capital["advance_band"] == (round(2700.0 * 0.8), round(2700.0 * 1.5))
    assert eligibility["band"] == {"low": round(2700.0 * 0.8), "high": round(2700.0 * 1.5)}
    body = client.get("/valuation").get_data(as_text=True)
    assert "2,700" in body


def test_the_royalties_desk_orders_periods_by_the_same_key():
    import royalties_desk
    assert royalties_desk.period_key is se.period_key
    assert royalties_desk.order_periods(["JUN-26", "MAY-26", "2026-04"]) == ["2026-04", "MAY-26", "JUN-26"]


def test_no_page_describes_the_retired_gap_formula():
    for name in ("_real_royalty_band.html", "report_executive.html"):
        s = io.open(os.path.join(HERE, "templates", name), encoding="utf-8").read()
        assert "per-source average" not in s, name


def test_no_engine_annualises_on_its_own():
    """The run rate is multiplied by twelve in one place. (Valuation's
    forecast carries a single month forward for a year; that is a
    scenario drawn from the months, not a second run rate.)"""
    retired = ("monthly_avg * 12", "total_income * (12", 'total"] / months * 12')
    for name in ("valuation_engine.py", "capital_engine.py"):
        s = io.open(os.path.join(HERE, name), encoding="utf-8").read()
        assert "annualize(" in s, name
        for expr in retired:
            assert expr not in s, (name, expr)
    s = io.open(os.path.join(HERE, "statements_engine.py"), encoding="utf-8").read()
    assert s.count("* 12") == 1, "once, inside annualize"
    bench = io.open(os.path.join(HERE, "benchmark_config.py"), encoding="utf-8").read()
    assert "get_earnings_trend" not in bench and "estimate_catalog_value" not in bench
