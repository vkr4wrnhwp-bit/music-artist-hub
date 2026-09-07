"""The room beside its date.

The owner, 2026-09-07: "as shows are implemented into the tour section it
should pull a small thumbnail of the venue next to the date." There is no
honest automatic source for a picture of a room, so the photo lives on
the venue record - one upload, PNG/JPEG/WebP - and every date linked to
that venue carries it: the dates list, the home tiles, the date's own
header, the venue list. Until there is one, the slot is the venue's
monogram, a placeholder that does not pretend to be the room.
"""
import io
import re

import tour_store as ts
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"not really pixels, but a png by name" * 4


def _linked(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="Turf Club")
    r = client.post("/tours/%s/venues/save" % tid, data={"name": "Turf Club", "city": "St. Paul", "link_show_id": sid})
    assert r.status_code == 302
    vid = ts.list_venues(owner["id"])[0]["id"]
    assert ts.get_show(tid, sid)["venue_id"] == vid
    return client, owner, tid, sid, vid


def _upload(client, tid, vid, name, back=None):
    data = {"photo": (io.BytesIO(PNG), name)}
    if back:
        data["back"] = back
    return client.post("/tours/%s/venues/%s/photo" % (tid, vid), data=data, content_type="multipart/form-data")


def test_a_venue_photo_shows_beside_every_date_at_that_room(flask_app):
    client, owner, tid, sid, vid = _linked(flask_app)
    url = "/tours/%s/venues/%s/photo" % (tid, vid)
    dates = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert '<span class="to-thumb to-thumb--mono" aria-hidden="true">TC</span>' in dates, "no photo yet: the monogram"
    assert "to-thumb-img" not in dates
    assert client.get(url).status_code == 404
    r = _upload(client, tid, vid, "room.png", back="/tours/%s/shows/%s?tab=venue" % (tid, sid))
    assert r.status_code == 302 and r.headers["Location"].endswith("/shows/%s?tab=venue" % sid)
    assert ts.get_venue(owner["id"], vid)["photo"]
    img = '<img class="to-thumb-img" src="%s"' % url
    assert img in client.get("/tours/%s/shows" % tid).get_data(as_text=True), "the dates list"
    assert img in client.get("/tours/%s" % tid).get_data(as_text=True), "the tour's own list"
    page = client.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    assert '<span class="to-thumb to-thumb--lg">' + img in page, "the date's own header"
    assert 'to-thumb--mono to-thumb--lg' not in page
    assert img in client.get("/tours/%s/venues" % tid).get_data(as_text=True), "the venue list"
    got = client.get(url)
    assert got.status_code == 200 and got.mimetype == "image/png" and got.data == PNG
    # A second date at the same room carries it too, with nothing more to do.
    sid2 = _show(client, tid, "2030-05-03", "Turf Club")
    client.post("/tours/%s/shows/%s/ext" % (tid, sid2), data={"venue_id": vid})
    assert client.get("/tours/%s/shows" % tid).get_data(as_text=True).count(img) == 2


def test_only_images_and_only_editors_and_remove_takes_it_off(flask_app):
    client, owner, tid, sid, vid = _linked(flask_app)
    r = _upload(client, tid, vid, "room.pdf")
    assert r.status_code == 302 and "photo=type" in r.headers["Location"]
    assert not ts.get_venue(owner["id"], vid)["photo"]
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    assert _upload(viewer, tid, vid, "room.png").status_code == 403
    assert _upload(client, tid, vid, "room.png").status_code == 302
    assert viewer.get("/tours/%s/venues/%s/photo" % (tid, vid)).status_code == 200, "a viewer sees the room"
    assert 'value="remove">Remove</button>' in client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    assert 'value="remove"' not in viewer.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    client.post("/tours/%s/venues/%s/photo" % (tid, vid), data={"action": "remove"})
    assert not ts.get_venue(owner["id"], vid)["photo"]
    assert client.get("/tours/%s/venues/%s/photo" % (tid, vid)).status_code == 404
    assert "to-thumb--mono" in client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    # The record form never touches the photo.
    _upload(client, tid, vid, "room.webp")
    client.post("/tours/%s/venues/save" % tid, data={"venue_id": vid, "name": "Turf Club", "city": "Saint Paul"})
    assert ts.get_venue(owner["id"], vid)["photo"].endswith(".webp")


def test_the_venue_list_is_rows_and_the_sheet_moved_on(flask_app):
    client, owner, tid, sid, vid = _linked(flask_app)
    html = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    rows = html.split('id="venues"')[1]
    assert rows.count('class="to-date to-date--venue"') == 1 and "<table" not in rows
    assert '<span class="to-fig"><span>city</span><b>St. Paul</b></span>' in rows
    assert re.search(r'<a class="to-chip" href="/tours/%s/shows/%s">[^<]+</a>' % (tid, sid), rows)
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-thumb" in css and ".to-thumb--mono" in css and ".to-date--venue" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 19
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 201
