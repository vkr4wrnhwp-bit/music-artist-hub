"""The money pages' share bars are the shared meter now.

Eleven pages in the Royalty Sweep hub drew the same proportion bar by
hand - a rounded track with an inline width - each with its own colour
and its own thresholds. Every one of those values is real (statement
rows, a factor score out of twenty, an allocation of a budget), so the
only change is the instrument. /capital is deliberately NOT here: its own
config says every figure is a simulated demo, and a meter on an invented
number is the theatre the instruments exist to refuse.
"""
import io
import os
import re

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONEY = ("overview", "royalties", "royalty_type", "statements", "recovery",
         "valuation", "tax", "territories", "revenue_os", "capital_score",
         "spend_optimizer")


def _tpl(name):
    return io.open(os.path.join(HERE, "templates", name + ".html"),
                   encoding="utf-8").read()


def test_no_money_page_draws_its_own_bar_any_more():
    for name in MONEY:
        s = _tpl(name)
        assert 'style="width:' not in s, name
        assert "sb.meter(" in s or 'class="sb-meter' in s, name


def test_capital_keeps_its_hands_off_the_instruments():
    """Simulated figures do not get a meter. If someone wires one up, the
    config docstring is the first thing to read."""
    s = _tpl("capital")
    assert "sb.meter(" not in s and 'class="sb-meter' not in s


@pytest.fixture(scope="module")
def demo():
    client = appmod.app.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def test_the_overview_health_bars_are_meters_with_the_real_percentage(demo):
    body = demo.get("/overview").get_data(as_text=True)
    assert re.search(r'aria-label="[^"]+: \d+%"', body)
    assert "sb-meter-fill" in body


def test_the_capital_score_factors_read_out_of_twenty(demo):
    body = demo.get("/capital-score").get_data(as_text=True)
    if body.count("/20") == 0:            # a page state with no factors
        pytest.skip("no factors rendered for this account")
    assert re.search(r'aria-label="[^"]+: \d+/20"', body)
