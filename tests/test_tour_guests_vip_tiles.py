"""TOUR guests and VIP, less to read.

The same brief as the rest of TOUR: the run-wide guest page is a row per
show with its counts as instruments and 'over' as a lamp; the run-wide
VIP page is windows over a row per show; a date's guest list and VIP
list are rows with access as chips; the long add forms wait behind a
plus once the list has an entry. Allocation, redaction and the door link
are untouched - tests/test_tour_os.py keeps holding them.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def test_guest_page_is_a_row_per_show_with_over_as_a_lamp(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/guests" % tid).get_data(as_text=True)
    rows = html.split('id="guest-shows"')[1]
    assert rows.count('class="to-date to-date--money"') == 1 and "<table" not in rows
    assert 'sb-lamp sb-lamp--info">no allocation</span>' in html
    # Approved before any allocation exists, then the venue allows one: the row is over.
    client.post("/tours/%s/shows/%s/guests/add" % (tid, sid), data={"name": "A Guest", "count": "2", "status": "approved"})
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"guest_allocation": "1", "guest_cutoff": "4 PM"})
    html = client.get("/tours/%s/guests" % tid).get_data(as_text=True)
    assert '<span class="to-fig"><span>used</span><b>2 / 1</b></span>' in html
    assert 'sb-lamp sb-lamp--crit">over allocation</span>' in html
    assert "cutoff 4 PM" in html and 'href="/tours/%s/shows/%s?tab=guests"' % (tid, sid) in html
    client.post("/tours/%s/shows/%s/guests/add" % (tid, sid), data={"name": "B Guest", "count": "1"})
    html = client.get("/tours/%s/guests" % tid).get_data(as_text=True)
    assert 'sb-lamp sb-lamp--warn">1 waiting</span>' in html
    assert '<span class="to-fig"><span>pending</span><b>1</b></span>' in html


def test_a_dates_guest_list_is_rows_with_access_as_chips_and_a_folded_form(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/shows/%s?tab=guests" % (tid, sid)).get_data(as_text=True)
    assert '<details class="to-add" id="add-guest" open>' in html and "Guest list is empty" in html
    client.post("/tours/%s/shows/%s/guests/add" % (tid, sid), data={
        "name": "Sam Press", "count": "2", "category": "Media", "company": "The Paper",
        "requested_by": "Mgmt", "backstage": "1", "meet_greet": "1", "status": "approved"})
    html = client.get("/tours/%s/shows/%s?tab=guests" % (tid, sid)).get_data(as_text=True)
    rows = html.split('id="guest-rows"')[1].split('<details class="to-add"')[0]
    assert rows.count('class="to-date to-date--guest"') == 1 and "<table" not in rows
    assert "Sam Press" in rows and "+1" in rows and "Media · The Paper · asked by Mgmt" in rows
    assert '<span class="to-chip to-chip--gold">backstage</span>' in rows and '<span class="to-chip">M&amp;G</span>' in rows
    assert 'value="checked_in">Check in</button>' in rows
    assert '<details class="to-add" id="add-guest">' in html, "a guest exists: the form waits"


def test_vip_is_windows_over_a_row_per_show_and_a_dates_list_is_rows(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/vip" % tid).get_data(as_text=True)
    assert 'id="vip-totals"' in html and '<span class="sb-lcd-v">0</span>' in html
    assert re.search(r'<span class="sb-lcd-v">—</span>\s*<span class="sb-lcd-cap">VIP gross', html), "nothing sold: gross is not a number"
    assert '<details class="to-add" id="add-vip" open>' in client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    client.post("/tours/%s/shows/%s/vip/add" % (tid, sid), data={
        "package": "Soundcheck party", "price": "150", "quantity": "3", "purchaser": "Taylor",
        "guest": "Taylor Example", "merch": "1", "schedule_time": "16:30"})
    html = client.get("/tours/%s/vip" % tid).get_data(as_text=True)
    rows = html.split('id="vip-shows"')[1]
    assert rows.count('class="to-date to-date--money"') == 1 and "<table" not in rows
    assert '<span class="to-fig"><span>sold</span><b>3</b></span>' in rows
    assert 'sb-lamp sb-lamp--warn">1 merch owed</span>' in rows
    assert '<span class="sb-lcd-v">450.00</span>' in html
    show = client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    rows = show.split('id="vip-rows"')[1].split('<details class="to-add"')[0]
    assert rows.count('class="to-date to-date--guest"') == 1 and "<table" not in rows
    assert "Soundcheck party × 3" in rows and "Taylor Example · bought by Taylor" in rows
    assert '<span class="to-chip">merch</span>' in rows and ">Merch given</button>" in rows
    assert '<details class="to-add" id="add-vip">' in show, "a package exists: the form waits"


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--guest" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 16
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 198
