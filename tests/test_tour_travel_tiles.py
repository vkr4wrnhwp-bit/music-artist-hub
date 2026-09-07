"""TOUR travel and hotels, less to read.

The same brief as the rest of TOUR: a row per leg with its times as
instruments and the small print behind a fold; a hotel as a compact card
with its small print folded and the room forms behind a plus; the add
forms behind a plus until the page is empty. Redaction is untouched -
tests/test_tour_os.py keeps holding it - because the template only
folds what the viewer was already allowed to see.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def test_legs_are_rows_with_times_as_instruments_and_small_print_folded(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    html = client.get("/tours/%s/travel" % tid).get_data(as_text=True)
    assert '<details class="to-add" id="add-leg" open>' in html, "no legs yet: the form is open"
    client.post("/tours/%s/travel/add" % tid, data={
        "day_date": "2030-05-02", "mode": "ground", "vehicle": "Sprinter", "driver": "Dee",
        "phone": "555 0100", "confirmation": "VAN-CONF", "dep_loc": "Nashville", "arr_loc": "Atlanta",
        "dep_time": "09:00", "arr_time": "13:30", "travelers": ["all"]})
    html = client.get("/tours/%s/travel" % tid).get_data(as_text=True)
    legs = html.split('id="legs"')[1].split("<details class=\"to-add\"")[0]
    assert legs.count('class="to-date to-date--leg"') == 1 and "<table" not in legs
    assert "Ground" in legs and "Sprinter" in legs and "Nashville → Atlanta" in legs
    assert re.search(r'<span class="to-fig"><span>dep[^<]*</span><b>[^<]+</b></span>', legs)
    assert '<span class="to-fig"><span>who</span><b>everyone</b></span>' in legs
    assert '<details class="to-fold"><summary>details</summary>' in legs
    assert "Driver Dee" in legs and "VAN-CONF" in legs, "the owner may see the small print; it is folded, not gone"
    assert '<details class="to-add" id="add-leg">' in html, "a leg exists: the form waits behind the plus"


def test_hotels_are_compact_cards_with_room_forms_behind_a_plus(flask_app):
    import tour_store as ts
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/hotels" % tid).get_data(as_text=True)
    assert '<details class="to-add" id="add-hotel" open>' in html
    client.post("/tours/%s/hotels/add" % tid, data={"show_id": sid, "property": "Crew Hotel", "city": "Nashville",
                                                    "checkin": "2030-05-02", "checkout": "2030-05-03",
                                                    "confirmation": "HOTEL-CONF", "wifi": "crew2030"})
    html = client.get("/tours/%s/hotels" % tid).get_data(as_text=True)
    assert "Crew Hotel" in html
    assert '<span class="to-fig"><span>in</span><b>2030-05-02</b></span>' in html
    assert '<span class="to-fig"><span>rooms</span><b>0</b></span>' in html
    assert '<details class="to-fold"><summary>details</summary>' in html and "HOTEL-CONF" in html and "Wi-Fi crew2030" in html
    assert "Assign a room</summary>" in html
    assert html.count('<details class="to-add" open>') == 1, "nobody roomed: the assign form is open"
    assert '<details class="to-add" id="add-hotel">' in html, "a hotel exists: the add form waits"
    lodging = ts.list_lodging(tid)[0]
    client.post("/tours/%s/hotels/%s/rooms" % (tid, lodging["id"]), data={"guest_name": "Ava", "room_number": "1201"})
    html = client.get("/tours/%s/hotels" % tid).get_data(as_text=True)
    assert '<span class="to-fig"><span>rooms</span><b>1</b></span>' in html and "1201" in html
    assert '<details class="to-add" open>' not in html, "roomed: the assign form folds"


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--leg" in css and ".to-fold > summary" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 14
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 196
