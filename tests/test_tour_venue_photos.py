"""The room's photo, from Google, beside its date.

The owner, 2026-09-07: "have it import the image of the club on this
page as a thumbnail next to the show." With a GOOGLE_MAPS_API_KEY a new
show links its venue record and Places supplies the photo (credit shown,
as Google's terms ask). Without the key the page says so and draws the
monogram; in sandbox nothing goes out even with a key; an owner's own
upload is never replaced. Every outbound call is canned here.
"""
import io
import json

import sandbox
import tour_store as ts
import venue_photos
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"canned jpeg bytes, not pixels" * 6
PNG = b"\x89PNG\r\n\x1a\n" + b"an owner's own photo" * 4


def _google(monkeypatch, has_photo=lambda query: True, credit="Ana Photographer"):
    """Key on, HTTP canned: a search answer per query, one image. Returns
    the list of calls so a test can count them."""
    calls = []

    def fake_http(url, payload=None, headers=None):
        calls.append((url, payload))
        if url == venue_photos.SEARCH_URL:
            assert headers["X-Goog-Api-Key"] == "test-key"
            assert headers["X-Goog-FieldMask"] == venue_photos.FIELD_MASK
            assert payload["maxResultCount"] == 1 and payload["textQuery"]
            place = {"id": "ChIJ123", "displayName": {"text": payload["textQuery"]},
                     "formattedAddress": "917 Woodland St, Nashville, TN 37206"}
            if has_photo(payload["textQuery"]):
                place["photos"] = [{"name": "places/ChIJ123/photos/AB9",
                                    "authorAttributions": [{"displayName": credit}]}]
            return json.dumps({"places": [place]}).encode("utf-8"), "application/json"
        if url.startswith("https://places.googleapis.com/v1/places/ChIJ123/photos/AB9/media?"):
            assert "maxWidthPx=480" in url and "key=test-key" in url
            return JPEG, "image/jpeg"
        raise AssertionError("unexpected call to %s" % url)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(venue_photos, "_http", fake_http)
    return calls


def _no_google(monkeypatch):
    """No key; any outbound call is a test failure."""
    calls = []

    def fake_http(url, payload=None, headers=None):
        calls.append(url)
        raise AssertionError("no call may leave without a key")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(venue_photos, "_http", fake_http)
    return calls


def _home(client, tid, query=""):
    r = client.get("/tours/%s%s" % (tid, query))
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_a_new_show_gets_the_rooms_photo_and_a_second_date_reuses_it(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="The Basement East")
    assert [c[1]["textQuery"] for c in calls if c[1]] == ["The Basement East Nashville, TN"]
    assert len(calls) == 2, "one search, one image"
    show = ts.get_show(tid, sid)
    vid = show["venue_id"]
    assert vid, "the show is linked to a venue record"
    venue = ts.get_venue(owner["id"], vid)
    assert venue["name"] == "The Basement East" and venue["city"] == "Nashville, TN"
    assert venue["photo"] and venue["photo_source"] == "google"
    assert venue["photo_credit"] == "Ana Photographer" and venue["place_id"] == "ChIJ123"
    url = "/tours/%s/venues/%s/photo" % (tid, vid)
    img = '<img class="to-thumb-img" src="%s"' % url
    home = _home(client, tid)
    assert img in home, "the thumbnail beside the date"
    assert "to-thumb--mono" not in home
    assert "Fetch venue photos" not in home and "no Google Maps key" not in home, "nothing left to fetch"
    got = client.get(url)
    assert got.status_code == 200 and got.mimetype == "image/jpeg" and got.data == JPEG
    page = client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    assert "Photo: Ana Photographer via Google" in page, "the credit Google requires"
    assert 'value="remove">Remove</button>' in page and "Replace the photo" in page
    # A second date at the same room: the same record, no second lookup.
    sid2 = _show(client, tid, "2030-05-03", "the basement east")
    assert ts.get_show(tid, sid2)["venue_id"] == vid
    assert len(calls) == 2
    assert _home(client, tid).count(img) == 2
    assert len(ts.list_venues(owner["id"])) == 1


def test_a_one_off_show_gets_its_photo_too(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    r = client.post("/tours/new", data={"one_off": "1", "date": "2030-06-01", "venue": "Exit/In",
                                        "city": "Nashville, TN", "home_tz": "America/Chicago"})
    assert r.status_code == 302
    tid, sid = r.headers["Location"].split("/tours/")[1].split("/shows/")
    assert len(calls) == 2
    venue = ts.get_venue(owner["id"], ts.get_show(tid, sid)["venue_id"])
    assert venue["photo"] and venue["photo_source"] == "google"


def test_the_owners_own_photo_is_never_replaced(flask_app, monkeypatch):
    _no_google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="Turf Club")
    assert not ts.get_show(tid, sid)["venue_id"], "no key: the show is made exactly as before"
    client.post("/tours/%s/venues/save" % tid, data={"name": "Turf Club", "city": "St. Paul", "link_show_id": sid})
    vid = ts.get_show(tid, sid)["venue_id"]
    r = client.post("/tours/%s/venues/%s/photo" % (tid, vid), data={"photo": (io.BytesIO(PNG), "room.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 302
    venue = ts.get_venue(owner["id"], vid)
    assert venue["photo"].endswith(".png") and venue["photo_source"] == "upload" and venue["photo_credit"] == ""
    calls = _google(monkeypatch)
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s?photos=0&missing=0" % tid)
    assert calls == [], "a room with a photo is not looked up"
    after = ts.get_venue(owner["id"], vid)
    assert after["photo"] == venue["photo"] and after["photo_source"] == "upload"
    page = client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    assert "via Google" not in page
    # Replacing a Google photo with an upload drops the credit.
    sid2 = _show(client, tid, "2030-05-04", "The Basement East")
    vid2 = ts.get_show(tid, sid2)["venue_id"]
    assert ts.get_venue(owner["id"], vid2)["photo_credit"] == "Ana Photographer"
    client.post("/tours/%s/venues/%s/photo" % (tid, vid2), data={"photo": (io.BytesIO(PNG), "mine.png")},
                content_type="multipart/form-data")
    v2 = ts.get_venue(owner["id"], vid2)
    assert v2["photo_source"] == "upload" and v2["photo_credit"] == "" and v2["photo"].endswith(".png")
    assert "via Google" not in client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid2)).get_data(as_text=True)


def test_the_fetch_route_counts_found_and_missing_once_per_venue(flask_app, monkeypatch):
    _no_google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show(client, tid, "2030-05-02", "The Basement East")
    b = _show(client, tid, "2030-05-03", "No Photo Bar")
    c = _show(client, tid, "2030-05-04", "The Basement East")
    d = _show(client, tid, "2030-05-05", "No Photo Bar")
    assert not any(ts.get_show(tid, s)["venue_id"] for s in (a, b, c, d))
    home = _home(client, tid)
    assert "Venue photos: no Google Maps key on this deployment" in home and "Fetch venue photos" not in home
    calls = _google(monkeypatch, has_photo=lambda q: "Basement" in q)
    home = _home(client, tid)
    assert "Fetch venue photos" in home and "no Google Maps key" not in home
    assert 'action="/tours/%s/venues/fetch-photos"' % tid in home
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/tours/%s?photos=1&missing=1" % tid)
    queries = [c[1]["textQuery"] for c in calls if c[1]]
    assert queries == ["The Basement East Nashville, TN", "No Photo Bar Nashville, TN"], "once per venue"
    assert len(calls) == 3
    va, vb = ts.get_show(tid, a)["venue_id"], ts.get_show(tid, b)["venue_id"]
    assert va and vb and va != vb
    assert ts.get_show(tid, c)["venue_id"] == va and ts.get_show(tid, d)["venue_id"] == vb
    assert ts.get_venue(owner["id"], va)["photo"] and not ts.get_venue(owner["id"], vb)["photo"]
    home = _home(client, tid, "?photos=1&missing=1")
    assert "Photos found for 1 venues; 1 had none on Google" in home
    assert home.count('<img class="to-thumb-img" src="/tours/%s/venues/%s/photo"' % (tid, va)) == 2
    assert home.count('to-thumb--mono') == 2, "the rooms Google has no photo of keep their monogram"
    assert "Fetch venue photos" in home, "still two dates without a photo"
    assert client.get("/tours/%s/venues/%s/photo" % (tid, vb)).status_code == 404
    # A viewer sees neither the line nor the button, and cannot fetch.
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    vh = viewer.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Fetch venue photos" not in vh and "no Google Maps key" not in vh and "Photos found" not in vh
    assert 'title="Photo: Ana Photographer via Google"' in vh, "the credit travels with the photo, for every viewer"
    assert viewer.post("/tours/%s/venues/fetch-photos" % tid).status_code == 403
    assert len(calls) == 3


def test_no_photo_on_google_keeps_the_monogram_and_claims_nothing(flask_app, monkeypatch):
    calls = _google(monkeypatch, has_photo=lambda q: False)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="Quiet Room")
    assert len(calls) == 1, "the search, no image to fetch"
    vid = ts.get_show(tid, sid)["venue_id"]
    assert vid, "the record is still linked"
    venue = ts.get_venue(owner["id"], vid)
    assert not venue["photo"] and venue["photo_source"] == "" and venue["photo_credit"] == ""
    home = _home(client, tid)
    assert '<span class="to-thumb to-thumb--mono" aria-hidden="true">QR</span>' in home
    assert "to-thumb-img" not in home and "Fetch venue photos" in home
    page = client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    assert "via Google" not in page and "Add a photo of the room" in page
    assert client.get("/tours/%s/venues/%s/photo" % (tid, vid)).status_code == 404


def test_a_bad_answer_never_breaks_the_request(flask_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def broken(url, payload=None, headers=None):
        raise OSError("no route to host")
    monkeypatch.setattr(venue_photos, "_http", broken)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="Far Room")
    assert ts.get_show(tid, sid)["venue_id"]
    assert venue_photos.lookup("Far Room", "Nashville, TN") is None
    assert venue_photos.fetch_photo("places/x/photos/y") is None
    monkeypatch.setattr(venue_photos, "_http", lambda url, payload=None, headers=None: (b"<html>", "text/html"))
    assert venue_photos.lookup("Far Room", "Nashville, TN") is None
    assert venue_photos.fetch_photo("places/x/photos/y") is None, "not an image"
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.status_code == 302 and r.headers["Location"].endswith("?photos=0&missing=1")


def test_without_a_key_nothing_leaves_and_the_page_says_so(flask_app, monkeypatch):
    calls = _no_google(monkeypatch)
    assert not venue_photos.configured()
    assert venue_photos.lookup("The Basement East", "Nashville, TN") is None
    assert venue_photos.fetch_photo("places/ChIJ123/photos/AB9") is None
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    assert calls == []
    assert not ts.get_show(tid, sid)["venue_id"] and ts.list_venues(owner["id"]) == []
    home = _home(client, tid)
    assert "Venue photos: no Google Maps key on this deployment" in home
    assert "Fetch venue photos" not in home and "to-thumb-img" not in home
    assert client.post("/tours/%s/venues/fetch-photos" % tid).headers["Location"].endswith("?photos=0&missing=0")
    assert calls == []


def test_in_sandbox_nothing_leaves_even_with_a_key(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    monkeypatch.setattr(sandbox, "active", lambda: True)
    assert not venue_photos.configured()
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    assert calls == [] and not ts.get_show(tid, sid)["venue_id"]
    assert "no Google Maps key on this deployment" in _home(client, tid)
    client.post("/tours/%s/venues/fetch-photos" % tid)
    assert calls == []


def test_import_looks_each_created_show_up_once(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    csv_text = ("date,city,venue,type\n2030-05-02,Nashville,The Basement East,show\n"
                "2030-05-03,Atlanta,Terminal West,show\n2030-05-04,,Day off,off\n")
    r = client.post("/tours/%s/import" % tid, data={"source": "csv", "text": csv_text, "action": "confirm",
                                                  "pick": ["0", "1", "2"]})
    assert r.status_code == 302
    shows = ts.list_shows(tid)
    assert [s["venue"] for s in shows] == ["The Basement East", "Terminal West"]
    queries = [c[1]["textQuery"] for c in calls if c[1]]
    assert queries == ["The Basement East Nashville", "Terminal West Atlanta"]
    assert len(calls) == 4, "a search and an image per show, nothing for the day off"
    for s in shows:
        assert s["venue_id"] and ts.get_venue(owner["id"], s["venue_id"])["photo_source"] == "google"
    assert _home(client, tid).count("to-thumb-img") == 2


# --- the review round, 2026-09-07 --------------------------------------------

def _show_in(client, tid, date_, venue, city):
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": date_, "kind": "show", "venue": venue, "city": city, "tz": "America/Chicago"})
    assert r.status_code == 302
    return r.headers["Location"].split("/shows/")[1].split("?")[0]


def test_the_credit_sits_wherever_the_google_photo_is(flask_app, monkeypatch):
    """Google's terms want the attribution wherever the photo is shown: the
    show header (the default tab), the venue edit panel, the venue rows,
    and the date rows - not only the Venue tab."""
    _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="The Basement East")
    vid = ts.get_show(tid, sid)["venue_id"]
    credit = "Photo: Ana Photographer via Google"
    header = client.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    assert credit in header, "the Show Command header carries it"
    venue_tab = client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    assert credit in venue_tab
    assert "Matched on Google: The Basement East Nashville, TN, 917 Woodland St, Nashville, TN 37206" in venue_tab, \
        "the owner can see what Google matched, and take it off if it is not the room"
    v = ts.get_venue(owner["id"], vid)
    assert v["place_name"] == "The Basement East Nashville, TN" and v["place_address"].startswith("917 Woodland")
    edit = client.get("/tours/%s/venues?edit=%s" % (tid, vid)).get_data(as_text=True)
    assert credit in edit and "matched on Google: The Basement East Nashville, TN" in edit
    rows = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    assert credit in rows, "the venue list row"
    home = _home(client, tid)
    assert 'title="Photo: Ana Photographer via Google"' in home, "the date row's thumbnail names the photographer"
    # An owner's upload has no credit, and no 'matched' line, anywhere.
    client.post("/tours/%s/venues/%s/photo" % (tid, vid), data={"photo": (io.BytesIO(PNG), "mine.png")},
                content_type="multipart/form-data")
    for url in ("/tours/%s/shows/%s" % (tid, sid), "/tours/%s/venues?edit=%s" % (tid, vid), "/tours/%s" % tid):
        page = client.get(url).get_data(as_text=True)
        assert "via Google" not in page and "atched on Google" not in page, url


def test_a_same_named_room_in_another_city_is_its_own_record(flask_app, monkeypatch):
    """The Basement in Nashville and The Basement in Columbus are two
    rooms: two records, two lookups, never one room's photo on the
    other's date."""
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show_in(client, tid, "2030-05-02", "The Basement", "Nashville, TN")
    b = _show_in(client, tid, "2030-05-03", "The Basement", "Columbus, OH")
    va, vb = ts.get_show(tid, a)["venue_id"], ts.get_show(tid, b)["venue_id"]
    assert va and vb and va != vb
    assert ts.get_venue(owner["id"], va)["city"] == "Nashville, TN"
    assert ts.get_venue(owner["id"], vb)["city"] == "Columbus, OH"
    assert [c[1]["textQuery"] for c in calls if c[1]] == ["The Basement Nashville, TN", "The Basement Columbus, OH"]
    home = _home(client, tid)
    assert '<img class="to-thumb-img" src="/tours/%s/venues/%s/photo"' % (tid, va) in home
    assert '<img class="to-thumb-img" src="/tours/%s/venues/%s/photo"' % (tid, vb) in home
    assert len(ts.list_venues(owner["id"])) == 2
    # The same room in the same city is still one record (case-insensitive).
    c = _show_in(client, tid, "2030-05-04", "the basement", "Nashville, TN")
    assert ts.get_show(tid, c)["venue_id"] == va and len(calls) == 4
    # A hand-made record with no city matches on the name and takes the city.
    vh = ts.add_venue(owner["id"], {"name": "Hand Room", "city": ""})
    d = _show_in(client, tid, "2030-05-05", "Hand Room", "Austin, TX")
    assert ts.get_show(tid, d)["venue_id"] == vh
    assert ts.get_venue(owner["id"], vh)["city"] == "Austin, TX"


def test_a_hit_that_is_not_the_room_is_refused(flask_app, monkeypatch):
    """Text Search answers something for nearly any query. A top hit whose
    name shares no word with the venue's is not the room, so no photo,
    no credit, and the monogram stays."""
    assert venue_photos.same_room("Studio A", "Studio A Nashville")
    assert venue_photos.same_room("The Basement East", "Basement East (The)")
    assert venue_photos.same_room("Exit/In", "Exit In")
    assert not venue_photos.same_room("Studio A", "Nashville Hair Salon")
    assert not venue_photos.same_room("The Room", "The Bar"), "filler words alone are not a match"
    assert not venue_photos.same_room("", "Anything")
    calls = []

    def salon(url, payload=None, headers=None):
        calls.append(url)
        assert url == venue_photos.SEARCH_URL
        place = {"id": "ChIJsalon", "displayName": {"text": "Nashville Hair Salon"},
                 "formattedAddress": "1 Main St", "photos": [{"name": "places/ChIJsalon/photos/P1",
                                                              "authorAttributions": [{"displayName": "A Stylist"}]}]}
        return json.dumps({"places": [place]}).encode("utf-8"), "application/json"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(venue_photos, "_http", salon)
    assert venue_photos.lookup("Studio A", "Nashville, TN") is None
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="Studio A")
    assert calls == [venue_photos.SEARCH_URL] * 2, "the search only; the salon's photo is never fetched"
    venue = ts.get_venue(owner["id"], ts.get_show(tid, sid)["venue_id"])
    assert not venue["photo"] and venue["photo_credit"] == "" and venue["place_id"] == ""
    home = _home(client, tid)
    assert "to-thumb--mono" in home and "to-thumb-img" not in home and "via Google" not in home
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.headers["Location"].endswith("?photos=0&missing=1")


def test_the_report_line_comes_from_the_run_not_the_address_bar(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, venue="The Basement East")
    ts.set_venue_photo(owner["id"], ts.get_show(tid, sid)["venue_id"], "")
    typed = _home(client, tid, "?photos=40&missing=0")
    assert "Photos found" not in typed, "a typed query string reports nothing"
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.status_code == 302 and r.headers["Location"].endswith("?photos=1&missing=0")
    first = _home(client, tid, "?photos=1&missing=0")
    assert "Photos found for 1 venues; 0 had none on Google" in first
    again = _home(client, tid, "?photos=1&missing=0")
    assert "Photos found" not in again, "said once, for the run that happened"
    assert len(calls) == 4


def test_a_slow_google_is_cut_off_at_the_budget_and_the_button_says_so(flask_app, monkeypatch):
    """Each venue can cost two 10s calls and gunicorn kills the worker at
    180s: a request stops asking after PHOTO_BUDGET_S and leaves the rest
    to the Fetch button, which reports what it did not reach."""
    import tour_os
    clock = [0.0]
    monkeypatch.setattr(tour_os, "_clock", lambda: clock[0])
    calls = _google(monkeypatch)
    real_http = venue_photos._http

    def slow(url, payload=None, headers=None):
        clock[0] += 16.0
        return real_http(url, payload, headers)
    monkeypatch.setattr(venue_photos, "_http", slow)
    client, owner = _user(flask_app)
    tid = _tour(client)
    csv_text = ("date,city,venue,type\n2030-05-02,Nashville,The Basement East,show\n"
                "2030-05-03,Atlanta,Terminal West,show\n2030-05-04,Athens,40 Watt,show\n")
    r = client.post("/tours/%s/import" % tid, data={"source": "csv", "text": csv_text, "action": "confirm",
                                                  "pick": ["0", "1", "2"]})
    assert r.status_code == 302, "the import finishes"
    shows = ts.list_shows(tid)
    assert len(shows) == 3 and all(s["venue_id"] for s in shows), "every show is linked to its record"
    assert len(calls) == 2, "one venue asked within the budget, the rest left for the button"
    assert [bool(ts.get_venue(owner["id"], s["venue_id"])["photo"]) for s in shows] == [True, False, False]
    assert "Fetch venue photos" in _home(client, tid)
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.headers["Location"].endswith("?photos=1&missing=0&unreached=1")
    home = _home(client, tid)
    assert "Photos found for 1 venues; 0 had none on Google; 1 not reached in time — press Fetch again" in home
    assert "Fetch venue photos" in home
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.headers["Location"].endswith("?photos=1&missing=0")
    assert len(calls) == 6 and all(ts.get_venue(owner["id"], s["venue_id"])["photo"] for s in ts.list_shows(tid))
    assert "Fetch venue photos" not in _home(client, tid)


def test_a_tba_date_never_asks_for_the_button(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, venue="TBA")
    assert calls == [] and ts.list_venues(owner["id"]) == []
    home = _home(client, tid)
    assert "Fetch venue photos" not in home and "no Google Maps key" not in home, "nothing a press could do"
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.headers["Location"].endswith("?photos=0&missing=0") and calls == []
    assert "Fetch venue photos" not in _home(client, tid)
    _show(client, tid, "2030-05-03", "Quiet Room")
    assert "Fetch venue photos" not in _home(client, tid), "found: nothing left to fetch"


def test_a_key_google_refuses_is_reported_as_a_refusal_not_as_rooms_without_photos(flask_app, monkeypatch):
    """The owner's first Fetch with a key answered '0 photos; 3 had none
    on Google' when Google had in fact refused the key outright. A 4xx
    from Google is kept as the run's refusal, with Google's own status
    and message, and the report says that instead."""
    import urllib.error
    body = json.dumps({"error": {"code": 403, "status": "PERMISSION_DENIED",
                                 "message": "Places API (New) has not been used in project 42 before or it is disabled."}}).encode("utf-8")
    calls = []

    def refused(url, payload=None, headers=None):
        calls.append(url)
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(body))
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(venue_photos, "_http", refused)
    venue_photos.clear_refusal()
    assert venue_photos.lookup("The Basement East", "Nashville, TN") is None
    assert venue_photos.last_refusal() == {"status": "PERMISSION_DENIED", "http": 403,
                                           "message": "Places API (New) has not been used in project 42 before or it is disabled."}
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, "2030-05-03", "The Basement East")
    _show(client, tid, "2030-05-04", "Exit/In")
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s?photos=0&missing=2&refused=1" % tid)
    home = _home(client, tid, "?photos=0&missing=2&refused=1")
    assert "Google refused the key (PERMISSION_DENIED): Places API (New) has not been used in project 42" in home
    assert "2 venues were not answered" in home and "enable Places API (New)" in home
    assert "had none on Google" not in home, "a refusal is not a fact about the rooms"
    # A room Google has no photo of is still a plain miss, with no talk of refusal.
    _google(monkeypatch, has_photo=lambda q: False)
    r = client.post("/tours/%s/venues/fetch-photos" % tid)
    assert r.headers["Location"].endswith("?photos=0&missing=2")
    home = _home(client, tid, "?photos=0&missing=2")
    assert "2 had none on Google" in home and "refused" not in home
    # A photo that is gone (404 on the media endpoint) is not a refusal either.
    venue_photos.clear_refusal()

    def gone(url, payload=None, headers=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
    monkeypatch.setattr(venue_photos, "_http", gone)
    assert venue_photos.fetch_photo("places/ChIJ123/photos/AB9") is None
    assert venue_photos.last_refusal() is None


def test_a_long_google_photo_name_is_kept_whole(monkeypatch):
    """Live, 2026-09-09: the first fetch with the key enabled found every
    room and then Google refused each photo as 'invalid resource' - the
    photo name had been trimmed to 400 characters. Their names are longer."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    long_name = "places/ChIJ123/photos/" + ("A" * 700)
    seen = []

    def fake_http(url, payload=None, headers=None):
        if url == venue_photos.SEARCH_URL:
            return json.dumps({"places": [{"id": "ChIJ123", "displayName": {"text": "The Basement East"},
                                            "photos": [{"name": long_name, "authorAttributions": []}]}]}).encode("utf-8"), "application/json"
        seen.append(url)
        return JPEG, "image/jpeg"
    monkeypatch.setattr(venue_photos, "_http", fake_http)
    found = venue_photos.lookup("The Basement East", "Nashville, TN")
    assert found["photo_name"] == long_name
    assert venue_photos.fetch_photo(found["photo_name"]) is not None
    assert seen and seen[0].startswith(venue_photos.MEDIA_URL.split("%s")[0] + long_name + "/media?")
