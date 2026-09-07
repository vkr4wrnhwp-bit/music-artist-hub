"""TOUR merch, marketing and content, less to read.

The same brief as the rest of TOUR: merch is windows over a row per
product with low stock as a lamp and the product form behind a plus,
plus a row per counted show with unsettled as the lamp; marketing is a
row per market with tickets as a meter that stays honest until both
numbers are entered and a missing ticket link as the lamp; each night's
shot list is headed by an assigned meter and counts.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def test_merch_is_windows_over_rows_with_low_stock_and_unsettled_as_lamps(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/merch" % tid).get_data(as_text=True)
    assert '<details class="to-add" id="add-product" open>' in html and "No products yet" in html
    assert html.split('id="merch-run"')[1].split("</div>")[0].count('<span class="sb-lcd-v">—</span>') == 4, "nothing yet: every window is a dash"
    client.post("/tours/%s/merch/products/add" % tid, data={"name": "Tour tee", "sku": "TEE-1", "price": "30",
                                                             "tour_inventory": "10", "low_stock_at": "3"})
    html = client.get("/tours/%s/merch" % tid).get_data(as_text=True)
    rows = html.split('id="products"')[1].split('<details class="to-add"')[0]
    assert rows.count('class="to-date to-date--money"') == 1 and "<table" not in rows
    assert "Tour tee" in rows and "TEE-1 · 30" in rows
    assert '<span class="to-fig"><span>left</span><b>10</b></span>' in rows and "sb-lamp" not in rows
    assert '<details class="to-add" id="add-product">' in html, "a product exists: the form waits"
    import tour_store as ts
    pid = ts.list_products(tid)[0]["id"]
    client.post("/tours/%s/shows/%s/merch" % (tid, sid), data={"sold__" + pid: "8", "gross__" + pid: "240"})
    html = client.get("/tours/%s/merch" % tid).get_data(as_text=True)
    rows = html.split('id="products"')[1].split('<details class="to-add"')[0]
    assert '<span class="to-fig"><span>left</span><b>2</b></span>' in rows
    assert 'sb-lamp sb-lamp--warn">low stock</span>' in rows
    assert '<span class="sb-lcd-v">8</span>' in html and '<span class="sb-lcd-v">240</span>' in html
    shows = html.split('id="merch-shows"')[1]
    assert shows.count('class="to-date to-date--money"') == 1 and "Nashville, TN" in shows
    assert 'sb-lamp sb-lamp--warn">unsettled</span>' in shows
    client.post("/tours/%s/shows/%s/merch" % (tid, sid), data={"sold__" + pid: "8", "gross__" + pid: "240", "settled__" + pid: "1"})
    html = client.get("/tours/%s/merch" % tid).get_data(as_text=True)
    assert "unsettled" not in html.split('id="merch-shows"')[1], "settled carries nothing"


def test_marketing_is_a_row_per_market_with_an_honest_ticket_meter(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/marketing" % tid).get_data(as_text=True)
    rows = html.split('id="markets"')[1]
    assert rows.count('class="to-date to-date--market"') == 1 and "<table" not in rows
    assert 'sb-meter sb-meter--none" role="img" aria-label="tickets: not entered"' in rows
    assert 'sb-lamp sb-lamp--warn">no ticket link</span>' in rows
    assert '<span class="to-fig"><span>push</span><b>0 / 9</b></span>' in rows
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid), data={
        "ticket_url": "https://tickets.example/x", "tickets_sold": "150", "capacity": "300",
        "announce": "2030-03-01", "radio": "booked", "ticket_status": "on sale"})
    html = client.get("/tours/%s/marketing" % tid).get_data(as_text=True)
    rows = html.split('id="markets"')[1]
    assert 'aria-label="tickets: 150 / 300"' in rows and "--sb-meter-fill: 50%" in rows
    assert '<a class="to-chip" href="https://tickets.example/x"' in rows and "no ticket link" not in rows
    assert '<span class="to-fig"><span>announce</span><b>2030-03-01</b></span>' in rows
    assert '<span class="to-fig"><span>push</span><b>1 / 9</b></span>' in rows and "on sale" in rows


def test_each_night_of_content_is_headed_by_an_assigned_meter(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    html = client.get("/tours/%s/content" % tid).get_data(as_text=True)
    head = html.split('<summary class="to-night-head">')[1].split("</summary>")[0]
    assert "Nashville, TN" in head
    m = re.search(r'aria-label="assigned: 0 / (\d+)"', head)
    assert m and int(m.group(1)) > 0, "the default shot list exists and none of it is owned"
    assert 'sb-lamp sb-lamp--warn">%s unassigned</span>' % m.group(1) in head
    assert '<span class="to-fig"><span>captured</span><b>0</b></span>' in head


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--market" in css and ".to-night > summary" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 17
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 199
