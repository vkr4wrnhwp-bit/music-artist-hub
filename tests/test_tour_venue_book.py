"""The venue book says what it is missing.

The owner wants the page honest about gaps, not only a list of what
exists: a date that names a room with no record behind it, and a record
with no photo of the room. Each is a fold at the top of the list, gone
when there is nothing to say; a date with no record has one button that
links it (an existing record by name in its city, else a new one) so the
fold empties itself. TBA and blank venues are not gaps.
"""
import tour_store as ts
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401
from tests.test_tour_venue_thumbs import _upload


def _book(flask_app):
    """One date linked to a record with a photo, one naming a room with no
    record, one TBA."""
    client, owner = _user(flask_app)
    tid = _tour(client)
    linked = _show(client, tid, "2030-05-02", venue="Turf Club")
    client.post("/tours/%s/venues/save" % tid, data={"name": "Turf Club", "city": "St. Paul", "link_show_id": linked})
    vid = ts.list_venues(owner["id"])[0]["id"]
    assert _upload(client, tid, vid, "room.png").status_code == 302
    bare = _show(client, tid, "2030-05-03", venue="The Basement East")
    tba = _show(client, tid, "2030-05-04", venue="TBA")
    assert not ts.get_show(tid, bare)["venue_id"] and not ts.get_show(tid, tba)["venue_id"]
    return client, owner, tid, linked, bare, tba, vid


def test_the_book_names_the_one_date_with_no_record_and_not_the_tba(flask_app):
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Dates with no venue record · 1" in page
    fold = page.split('id="unlinked"')[1].split("</details>")[0]
    assert "The Basement East" in fold and "Nashville, TN" in fold
    assert "/shows/%s" % bare in fold and "/shows/%s" % linked not in fold and "/shows/%s" % tba not in fold
    assert "TBA" not in fold
    assert 'sb-lamp sb-lamp--warn">needs a record<' in fold, "a gap is something to act on"
    assert 'value="%s"' % bare in fold and ">Create record</button>" in fold
    assert "Venues without a photo" not in page, "the one record has its photo"


def test_create_record_links_the_date_and_the_fold_goes_away(flask_app):
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    r = client.post("/tours/%s/venues/link" % tid, data={"show_id": bare})
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s/venues" % tid)
    new_vid = ts.get_show(tid, bare)["venue_id"]
    assert new_vid and new_vid != vid
    rec = ts.get_venue(owner["id"], new_vid)
    assert rec["name"] == "The Basement East" and rec["city"] == "Nashville, TN"
    assert not rec["photo"], "never invented"
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Dates with no venue record" not in page
    # The new record has no photo, so it moves to the second fold, with its date count.
    assert "Venues without a photo · 1" in page
    fold = page.split('id="no-photo"')[1].split("</details>")[0]
    assert "The Basement East" in fold and "1 date on this run" in fold and "Turf Club" not in fold
    assert 'href="?edit=%s"' % new_vid in fold
    assert "sb-lamp" not in fold, "a missing photo is not an alarm"
    assert "to-thumb--mono" in page, "the monogram stays"
    # Pressing it again changes nothing, and a show that is not there is a 404.
    assert client.post("/tours/%s/venues/link" % tid, data={"show_id": bare}).status_code == 302
    assert ts.get_show(tid, bare)["venue_id"] == new_vid
    assert client.post("/tours/%s/venues/link" % tid, data={"show_id": "nope"}).status_code == 404


def test_a_second_date_at_a_known_room_links_to_the_existing_record(flask_app):
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    again = _show(client, tid, "2030-05-05", venue="Turf Club")
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Dates with no venue record · 2" in page
    client.post("/tours/%s/venues/link" % tid, data={"show_id": again})
    assert ts.get_show(tid, again)["venue_id"] != vid, "Turf Club, St. Paul is not Turf Club, Nashville"
    # But a record with no city at all takes the date's city and is reused.
    client.post("/tours/%s/venues/save" % tid, data={"name": "Exit/In", "city": ""})
    exit_in = ts.find_venue_by_name(owner["id"], "Exit/In")["id"]
    third = _show(client, tid, "2030-05-06", venue="Exit/In")
    client.post("/tours/%s/venues/link" % tid, data={"show_id": third})
    assert ts.get_show(tid, third)["venue_id"] == exit_in
    assert ts.get_venue(owner["id"], exit_in)["city"] == "Nashville, TN"


def test_a_stale_venue_id_counts_as_a_gap(flask_app):
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    ts.update_show_ext(tid, bare, {"venue_id": "gone-record"})
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Dates with no venue record · 1" in page and "/shows/%s" % bare in page.split('id="unlinked"')[1]


def test_a_viewer_sees_the_gaps_but_has_no_buttons(flask_app):
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    client.post("/tours/%s/venues/save" % tid, data={"name": "Exit/In", "city": "Nashville, TN"})
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    page = viewer.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Dates with no venue record · 1" in page and "Venues without a photo · 1" in page
    assert "Create record" not in page and "/venues/link" not in page
    assert "Add a photo" not in page and "?edit=" not in page
    assert viewer.post("/tours/%s/venues/link" % tid, data={"show_id": bare}).status_code == 403
    assert not ts.get_show(tid, bare)["venue_id"]


def test_the_photo_note_depends_on_whether_google_is_configured(flask_app, monkeypatch):
    import venue_photos
    client, owner, tid, linked, bare, tba, vid = _book(flask_app)
    client.post("/tours/%s/venues/save" % tid, data={"name": "Exit/In", "city": "Nashville, TN"})
    monkeypatch.setattr(venue_photos, "configured", lambda: False)
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Fetch venue photos" not in page and "monogram stands in" in page
    monkeypatch.setattr(venue_photos, "configured", lambda: True)
    page = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert "Fetch venue photos on the tour home will ask Google" in page
