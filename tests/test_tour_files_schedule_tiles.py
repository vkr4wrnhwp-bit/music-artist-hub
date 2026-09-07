"""TOUR files and schedule, less to read.

The same brief as the rest of TOUR: file categories are counted chips
that filter, each file is a row with its chips and its who-and-when as
instruments, and the upload form waits behind a plus; the schedule's
days are headed by counts, confirmed is a lamp, and the eleven-field
add form waits behind a plus once anything is scheduled.
"""
import io
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _upload(client, tid, name, category, entity_type="tour", entity_id=""):
    r = client.post("/tours/%s/files/upload" % tid, data={
        "entity_type": entity_type, "entity_id": entity_id, "category": category, "visibility": "all",
        "file": (io.BytesIO(b"%PDF-1.4 test"), name)}, content_type="multipart/form-data")
    assert r.status_code in (302, 303)


def test_files_are_rows_with_counted_chips_and_a_folded_upload(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    html = client.get("/tours/%s/files" % tid).get_data(as_text=True)
    assert '<details class="to-add" id="add-file" open>' in html and "No files yet" in html
    _upload(client, tid, "rider.pdf", "rider")
    _upload(client, tid, "plot.pdf", "stage_plot", "show", sid)
    html = client.get("/tours/%s/files" % tid).get_data(as_text=True)
    chips = re.findall(r'<a class="to-chip-btn( is-on)?" href="[^"]+">([^<]+)</a>', html.split('id="cats"')[1].split("</div>")[0])
    assert [t for _on, t in chips] == ["All · 2", "rider · 1", "stage plot · 1"]
    rows = html.split('id="files"')[1].split("<details")[0]
    assert rows.count('class="to-date to-date--file"') == 2 and "<table" not in rows
    assert "rider.pdf" in rows and "whole tour" in rows and "Nashville, TN" in rows
    assert '<span class="to-chip">stage plot</span>' in rows
    assert re.search(r'<span class="to-fig"><span>on</span><b>\d{4}-\d{2}-\d{2}</b></span>', rows)
    assert '<details class="to-add" id="add-file">' in html, "files exist: the upload form waits"
    only = client.get("/tours/%s/files?category=rider" % tid).get_data(as_text=True)
    assert only.count('class="to-date to-date--file"') == 1 and "All · 2" in only


def test_schedule_days_carry_counts_and_confirmed_is_a_lamp(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    html = client.get("/tours/%s/schedule" % tid).get_data(as_text=True)
    assert '<details class="to-add" id="add-item" open>' in html and "Nothing scheduled yet" in html
    client.post("/tours/%s/schedule/add" % tid, data={"day_date": "2030-05-02", "title": "Load in",
                                                        "category": "load_in", "start_time": "14:00", "visibility": "all"})
    client.post("/tours/%s/schedule/add" % tid, data={"day_date": "2030-05-02", "title": "Doors",
                                                        "category": "doors", "start_time": "19:00", "visibility": "all"})
    html = client.get("/tours/%s/schedule" % tid).get_data(as_text=True)
    assert '<span class="to-fig"><span>items</span><b>2</b></span>' in html
    assert '<span class="to-fig"><span>confirmed</span><b>0</b></span>' in html
    assert html.count('sb-lamp sb-lamp--warn">unconfirmed</span>') == 2
    assert '<span class="warn">unconfirmed</span>' not in html
    assert '<details class="to-add" id="add-item">' in html, "items exist: the form waits"


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--file" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 15
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 197
