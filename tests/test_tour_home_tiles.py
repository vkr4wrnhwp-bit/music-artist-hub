"""TOUR home, less to read.

The owner, 2026-09-07: "tour home page should simply be a list ... then
you click into those. the workflow is to much", then by number on the
mockup: the dates list and the change banner come off the home too. So
the home is the month, with the booking bar above it and Import / Add a
day beside it; a day opens its show. Everything else is one click in.
"""
import re

import tour_store as ts
from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _home(client, tid):
    r = client.get("/tours/%s" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_the_home_is_the_month_and_a_day_opens_its_show(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "The Basement East")
    s2 = _show(client, tid, "2030-05-04", "Exit/In")
    html = _home(client, tid)
    assert '<div class="to-cal" role="grid" aria-label="May 2030">' in html, "the month the run starts in"
    grid = html.split('class="to-cal"')[1]
    assert ('href="/tours/%s/shows/%s"' % (tid, s1)) in grid and ('href="/tours/%s/shows/%s"' % (tid, s2)) in grid
    assert grid.count("Nashville, TN") == 2 and "% ready" in grid
    assert 'href="?month=2030-06">' in html and 'href="?month=2030-04">' in html
    assert ">Import dates</a>" in html and "Add a day</a>" in html and "All dates as a list</a>" in html
    body = html.split("</nav>")[-1]                 # below the bar: the More menu still names What changed
    for gone in ('id="dates"', 'id="upcoming"', 'id="tour-readiness"', "Needs attention", "What changed",
                 "Today for you", 'class="to-card"', 'id="unack"', 'class="to-date-when"'):
        assert gone not in body, gone
    assert "2 dates on the run" in html


def test_an_empty_run_says_where_to_start(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = _home(client, tid)
    assert "No dates yet" in html and "/import" in html


def test_the_bar_is_what_booking_needs(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = _home(client, tid)
    bar = html.split('class="to-tabs to-bar"')[1].split("</nav>")[0]
    labels = re.findall(r'class="to-tab[^"]*"[^>]*>([^<]+)<', bar)
    assert labels[:7] == ["Home", "Import", "Venues", "Crew", "Travel &amp; hotels", "Money", "Files"]
    items = re.findall(r'class="to-more-item[^"]*"[^>]*>([^<]+)<', bar)
    assert items == ["Dates", "Calendar", "Marketing", "Stage plot", "Exports", "What changed", "Ask Tour", "Share links", "Team", "Settings"]


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-tile-v" in css and ".to-lcds" in css and ".to-cal" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 22
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 206
