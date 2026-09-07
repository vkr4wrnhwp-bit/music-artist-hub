"""TOUR calendar, less to read.

The same brief (2026-09-06: "more meters and images and less verbiage,
more options if they want the options"): the month is counted in
windows above the grid, the list view is rows like Dates, and the
seven-field 'Add a day' form waits behind a plus - open on its own only
when the calendar is empty, because then the first day is the page.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401


def _cal(client, tid, **args):
    q = "&".join("%s=%s" % kv for kv in args.items())
    r = client.get("/tours/%s/calendar%s" % (tid, ("?" + q) if q else ""))
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _lcds(html):
    return re.findall(r'<span class="sb-lcd-v">([^<]*)</span>\s*<span class="sb-lcd-cap">([^<]+)</span>', html)


def test_the_month_is_counted_in_windows(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, "2030-05-02", "The Basement East")
    _show(client, tid, "2030-05-04", "Exit/In")
    client.post("/tours/%s/days/add" % tid, data={"date": "2030-05-03", "kind": "off", "city": "Nashville, TN", "title": "Day off"})
    html = _cal(client, tid, month="2030-05")
    assert _lcds(html)[:3] == [("2", "show days"), ("1", "other day"), ("0", "fully ready")]
    assert 'class="to-cal"' in html, "the grid stays; it is the picture"
    # Readiness not scored: the ready window is blank, not zero.
    html = _cal(client, tid, month="2030-05", ready="0")
    assert ("—", "fully ready") in _lcds(html)
    # A month with nothing in it says so in numbers, not a sentence.
    assert _lcds(_cal(client, tid, month="2030-07"))[:3] == [("0", "show days"), ("0", "other days"), ("—", "fully ready")]


def test_the_list_view_is_rows_with_the_actions_kept(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-02", "The Basement East")
    client.post("/tours/%s/days/add" % tid, data={"date": "2030-05-03", "kind": "off", "city": "Nashville, TN", "title": "Day off"})
    html = _cal(client, tid, month="2030-05", view="list")
    assert 'id="days"' in html and html.count('class="to-date"') == 2
    assert "<table" not in html.split('id="days"')[1].split("<details")[0], "the table is gone"
    assert 'class="to-date-when" href="/tours/%s/shows/%s"' % (tid, sid) in html
    assert "Day off" in html and 'class="to-chip' in html
    assert "Post to Team-Up Board" in html and 'name="action" value="delete"' in html
    # A view-only member sees the rows and none of the actions.
    crew, _m = _member_join(flask_app, client, tid, ["view"], "Viewer")
    theirs = crew.get("/tours/%s/calendar?month=2030-05&view=list" % tid).get_data(as_text=True)
    assert theirs.count('class="to-date"') == 2 and "Post to Team-Up Board" not in theirs and "Remove" not in theirs


def test_add_a_day_waits_behind_a_plus_unless_the_calendar_is_empty(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = _cal(client, tid)
    assert '<details class="to-add" id="add-day" open>' in html, "an empty calendar opens the form: the first day is the page"
    assert 'name="date"' in html
    _show(client, tid, "2030-05-02", "The Basement East")
    html = _cal(client, tid, month="2030-05")
    assert '<details class="to-add" id="add-day">' in html and "Add a day</summary>" in html
    assert 'name="date"' in html, "folded, not gone"
    assert '<details class="to-add" id="add-day" open>' in _cal(client, tid, month="2030-05", add="1")
    crew, _m = _member_join(flask_app, client, tid, ["view"], "Viewer")
    assert 'id="add-day"' not in crew.get("/tours/%s/calendar" % tid).get_data(as_text=True)
