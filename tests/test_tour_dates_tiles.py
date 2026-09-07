"""TOUR Dates, less to read.

The same brief as the date page and the home (2026-09-06: "more meters
and images and less verbiage"): one row per date with the venue as the
line that matters, the missing items behind a fold instead of a column
of words, the advance state as a lamp, and the 'Advance the run'
explainer folded. The pipeline line and the legend - the Tour Hub's own
words - stay where they were.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401
from tests.test_tour_fold import PIPELINE, LEGEND


def _dates(client, tid):
    r = client.get("/tours/%s/shows" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_each_date_is_a_row_with_its_missing_items_folded(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "The Basement East")
    s2 = _show(client, tid, "2030-05-04", "Exit/In")
    html = _dates(client, tid)
    rows = html.split('id="dates"')[1].split("</div>\n{#")[0] if "</div>\n{#" in html else html.split('id="dates"')[1]
    assert html.count('class="to-date"') == 2
    assert re.findall(r'<a class="to-date-when" href="/tours/%s/shows/([0-9a-f]+)"' % tid, html) == [s1, s2]
    assert "The Basement East" in rows and "Exit/In" in rows and "Nashville, TN" in rows
    assert "<table" not in html.split('id="dates"')[1].split(LEGEND)[0], "the dates table is gone"
    # Nothing on a fresh date, so nothing is measured: not started, never 0%, nothing to fold.
    assert "to-date-missing" not in html and ">0%<" not in html and "0% ready" not in html
    assert html.split('id="dates"')[1].split(LEGEND)[0].count("not started") == 2
    # Put the advance on both dates: the missing items are one fold per date, not a column of words.
    for sid in (s1, s2):
        client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": "advance", "action": "add"})
    html = _dates(client, tid)
    folds = re.findall(r'<details class="to-date-missing"><summary>(\d+) missing</summary><ul>(.*?)</ul></details>', html, re.S)
    assert len(folds) == 2 and all(int(n) >= 1 for n, _ in folds)
    assert "<li>Contract</li>" in folds[0][1]
    assert "contract, venue, promoter" not in html, "the old inline list of missing items is gone"
    # The Tour Hub's words stay, in the same order around the list.
    assert page_order(html) == ["pipeline", "dates", "legend"]


def page_order(html):
    marks = [("pipeline", html.index(PIPELINE)), ("dates", html.index('id="dates"')), ("legend", html.index(LEGEND))]
    return [name for name, _ in sorted(marks, key=lambda x: x[1])]


def test_the_status_form_and_the_advance_lamps_still_work(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "Room One")
    s2 = _show(client, tid, "2030-05-04", "Room Two")
    client.post("/tours/%s/shows/%s/advance-bulk" % (tid, s1), data={
        "status__venue_contact": "complete", "value__venue_contact": "Ana, one@venue.example"})
    html = _dates(client, tid)
    assert 'class="to-status-form"' in html and 'name="status"' in html
    assert "to-date-adv" not in html, "the advance state left the rows; the block below carries it"
    assert "Send 1 advance<" in html
    # The explainer is behind a fold; the pinned strings are intact.
    assert "<summary>What a venue gets</summary>" in html
    assert "composed from that show's own rows" not in html
    assert "shared test address" in html or 'value="%s"' % s1 in html
    # A view-only member reads chips, no forms, and the same rows.
    crew, _m = _member_join(flask_app, client, tid, "crew", ["view"])
    theirs = crew.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert theirs.count('class="to-date"') == 2 and "to-status-form" not in theirs


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date " in css or ".to-date {" in css
    assert ".to-date-missing" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 11
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 192


def test_the_no_address_list_is_a_count_with_the_dates_behind_it(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    _show(client, tid, "2030-05-03", "Room Two")
    html = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert '<details class="to-fold"><summary>2 dates without a venue address</summary>' in html
    assert "Room Two" in html.split("without a venue address</summary>")[1].split("</details>")[0]
