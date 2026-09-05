"""The executive print report draws its qualification on the shared meter.

It was the last page with a hand-rolled bar, left alone at first because it
carries its own <head> without the chrome sheet. It loads the sheet itself
now, declares paper, and tells the printer to keep the meter's colours -
a printed meter with its fill dropped is a meter reading zero.
"""
import io
import os
import re

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tpl():
    return io.open(os.path.join(HERE, "templates", "report_executive.html"),
                   encoding="utf-8").read()


def test_the_report_has_no_hand_rolled_bar():
    s = _tpl()
    assert 'style="width:' not in s
    assert "sb.meter(" in s


def test_the_report_loads_the_chrome_sheet_and_declares_paper():
    s = _tpl()
    assert "/static/css/app-chrome.css?v=" in s
    assert 'class="sb-on-paper' in s
    assert "print-color-adjust: exact" in s


def test_the_meter_reads_the_real_points_out_of_ten():
    client = appmod.app.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = client.get("/reports/executive").get_data(as_text=True)
    assert re.search(r'aria-label="[^"]+: \d+/10"', body)
    assert "sb-meter-fill" in body
