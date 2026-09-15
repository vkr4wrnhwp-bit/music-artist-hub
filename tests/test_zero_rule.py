"""The zero rule, from the owner: "if a card shows 0 it needs to not show up".

A figure nobody measured reads "Not measured", never 0. A counted figure
that happens to be zero is left out rather than drawn as a zero tile, a
zero heading or a green zero. The staging audit of 2026-09-15 found the
rule broken across the money and press pages; these are the locks.

A fresh account is the whole test: it has no statements, no fans, no
tracks and no campaigns, so every page below is at its emptiest.
"""
import re
import uuid

import pytest

from app import create_app

PW = "zero-rule-12345"


@pytest.fixture(scope="module")
def app_obj():
    return create_app()


@pytest.fixture(scope="module")
def fresh(app_obj):
    c = app_obj.test_client()
    c.post("/signup", data={"name": "Zero", "email": "zero-%s@example.net" % uuid.uuid4().hex[:8],
                            "password": PW})
    c.post("/plan/switch", data={"plan": "pro"})
    return c


def _body(client, path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.get_data(as_text=True)


def test_revenue_os_says_not_measured_rather_than_zero_profit(fresh):
    body = _body(fresh, "/revenue-os")
    assert "Not measured" in body
    for banned in ("Profitable", "Recouped", "$0.00"):
        assert banned not in body, banned


def test_the_press_desk_counts_nothing_it_has_not_counted(fresh):
    desk = _body(fresh, "/press-desk")
    assert "Active contacts" not in desk and "Coverage logged" not in desk
    assert "No contacts yet." in desk
    for path, word in (("/press-desk/contacts", "Media list"),
                       ("/press-desk/coverage", "Coverage"),
                       ("/press-desk/announcements", "Announcements")):
        body = _body(fresh, path)
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S).group(1).strip()
        assert h1 == word, (path, h1)
        assert not re.match(r"^0\b", h1), path


def test_the_catalog_draws_no_counters_and_no_invented_pager(fresh):
    body = _body(fresh, "/catalog")
    for banned in ("Showing 1 to", "156", "Total Tracks", "this month"):
        assert banned not in body, banned
    assert "Not measured" in body, "the catalog value with no statements"


def test_certified_and_the_one_sheet_hold_no_zero_summaries(fresh):
    body = _body(fresh, "/certified")
    assert "0% avg passport" not in body
    assert "No tracks on record yet." in body
    sheet = _body(fresh, "/deal-room/onesheet")
    for banned in ("$0.00", "0 of 0", "0/100"):
        assert banned not in sheet, banned
    assert "Nothing measured yet." in sheet


def test_capital_readiness_shows_the_first_step_not_five_zero_meters(fresh):
    body = _body(fresh, "/capital-score")
    assert "0/20" not in body and "$0" not in body
    assert "Upload a statement" in body


def test_disputes_and_recovery_cases_draw_no_zero_tiles(fresh):
    body = _body(fresh, "/disputes")
    assert "Open Disputes" not in body and "$0.00" not in body
    cases = _body(fresh, "/royalty-recovery/cases")
    assert "In Pipeline" not in cases and "$0.00" not in cases


def test_the_spend_optimizer_says_what_it_has_instead_of_three_zeros(fresh):
    body = _body(fresh, "/spend-optimizer")
    assert "Signals in use" not in body
    assert "No signals yet." in body
    assert "your account's real signals" not in body


def test_the_executive_report_drops_zero_tiles_and_the_zero_fan_line(fresh):
    body = _body(fresh, "/reports/executive")
    assert "Fan Ownership" in body
    assert "No fans captured yet." in body
    assert "Link Visits" not in body and "Fans Owned" not in body
    assert "SB Qualification" in body, "the score itself always shows"
