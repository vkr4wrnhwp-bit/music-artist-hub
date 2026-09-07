"""TOUR home, less to read.

The same brief as the date page and the Fan Dashboard (2026-09-06, "more
meters and images and less verbiage"): readiness is a meter, the
upcoming dates are tiles that open the date, money sits in windows that
say '—' until a show actually has numbers - zero would be a claim - and
the change feed shows three rows with the rest behind a fold.
"""
import re

import tour_store as ts
from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _home(client, tid):
    r = client.get("/tours/%s" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_readiness_is_a_meter_and_the_dates_are_tiles(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "The Basement East")
    s2 = _show(client, tid, "2030-05-04", "Exit/In")
    html = _home(client, tid)
    assert re.search(r'aria-label="Tour readiness: \d+%"', html)
    assert 'id="tour-readiness"' in html and "shows scored" in html
    tiles = re.findall(r'<a class="to-tile" href="/tours/%s/shows/([0-9a-f]+)"' % tid, html)
    assert tiles == [s1, s2], "one tile per upcoming date, soonest first"
    up = html.split('id="upcoming"')[1].split("</div>\n\n")[0]
    assert "The Basement East" in up and "Exit/In" in up and "Nashville, TN" in up
    assert 'class="to-chip' in up and 'class="to-ready' in up
    assert '<table class="to-table' not in html, "the upcoming table is gone"
    # The count cards stay; the readiness card became the meter.
    assert ">Shows</span>" in html and "Tour readiness</span>" not in html


def test_money_windows_say_nothing_until_a_show_has_numbers(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    html = _home(client, tid)
    money = html.split(">Money</h2>")[1].split("</a>")[0]
    caps = re.findall(r'<span class="sb-lcd-cap">([^<]+)</span>', money)
    assert caps == ["projected net USD", "guarantees", "outstanding", "deposits due", "unsettled", "shows with numbers"]
    assert money.count('<span class="sb-lcd-v">—</span>') == 4, "no numbers entered: the money windows are blank, not zero"
    assert re.search(r'<span class="sb-lcd-v">0</span>\s*<span class="sb-lcd-cap">shows with numbers', money)
    assert "Projected net (USD)" not in html


def test_the_change_feed_folds_after_three(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    tour = ts.get_tour(tid)
    actor = {"id": owner["id"], "name": "Owner"}
    for i in range(5):
        ts.log_change(tid, tour["user_id"], actor, "show", sid, "The Basement East",
                      "venue", "Venue %d" % i, "Venue %d" % (i + 1), "important")
    html = _home(client, tid)
    aside = html.split(">What changed</h2>")[1].split(">Today for you</h2>")[0]
    assert aside.count('class="to-change"') == 5
    assert "<summary>2 more changes</summary>" in aside, "three shown, the rest behind a fold"
    assert aside.index("<summary>2 more changes") > aside.index('class="to-change"')
    assert "Time, place and hotel edits land here" not in html


def test_a_clean_board_is_a_lamp_not_a_sentence(flask_app):
    import tour_os
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    html = _home(client, tid)
    board = html.split("Needs attention</h2>")[1].split("<h2")[0]
    assert ('nothing flagged' in board) or ('class="to-check"' in board)
    assert "not that the work is done for you" not in html


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-tile-v" in css and ".to-lcds" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 10
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 191
