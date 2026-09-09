"""Where the room is: coordinates, its time zone, and the drive.

Three Google APIs on the one GOOGLE_MAPS_API_KEY the venue photos
already use — Geocoding, Time Zone, and (only if the project has it
switched on) Routes v2. Every outbound call is canned here, and the
tests are about the honesty of the answers rather than the arithmetic:

  * an address Google does not know is "not found", not an error;
  * a key Google refuses says so, in Google's words, and writes nothing;
  * a date's time zone is filled from the room only into a blank, and
    the page says that is where it came from;
  * a leg with no measured drive shows the straight line and calls it
    one — no duration is ever invented from a distance;
  * in sandbox, and without a key, nothing leaves at all.
"""
import io
import json
import urllib.error
import urllib.parse

import pytest

import sandbox
import tour_os
import tour_store as ts
import venue_geo
import venue_photos
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401

# Two rooms, two points far enough apart that the straight line is a real
# number: The Basement East in Nashville and Terminal West in Atlanta.
NASHVILLE = (36.1745, -86.7496)
ATLANTA = (33.7776, -84.4128)
POINTS = {
    "917 Woodland St, Nashville, TN": (NASHVILLE, "America/Chicago",
                                       "917 Woodland St, Nashville, TN 37206, USA"),
    "887 W Marietta St NW, Atlanta, GA": (ATLANTA, "America/New_York",
                                          "887 W Marietta St NW, Atlanta, GA 30318, USA"),
}


def _quiet_photos(monkeypatch):
    """The photo lookup is not what these tests are about, but a key
    configures it too. Make every photo call fail quietly so the venue
    records are still linked and nothing goes out."""
    def no_photos(url, payload=None, headers=None):
        raise OSError("no photo lookup in this test")
    monkeypatch.setattr(venue_photos, "_http", no_photos)


def _google(monkeypatch, known=None, routes=None, tz_status="OK"):
    """Key on, HTTP canned. `known` decides which addresses Google has;
    `routes` is a (meters, seconds) pair when the Routes API answers, or
    an HTTPError-raising refusal when it is not enabled on the project.
    Returns the list of calls so a test can count them."""
    calls = []
    known = known if known is not None else (lambda a: a in POINTS)

    def fake_http(url, payload=None, headers=None):
        calls.append((url, payload))
        if url.startswith(venue_geo.GEOCODE_URL):
            q = urllib.parse.parse_qs(url.split("?", 1)[1])
            assert q["key"] == ["test-key"]
            asked = (q.get("address") or q.get("place_id") or [""])[0]
            if not known(asked):
                return json.dumps({"results": [], "status": "ZERO_RESULTS"}).encode("utf-8"), "application/json"
            (lat, lng), _tz, formatted = POINTS[_match(asked)]
            return json.dumps({"status": "OK", "results": [{
                "formatted_address": formatted, "place_id": "ChIJ%d" % (abs(hash(asked)) % 9999),
                "geometry": {"location": {"lat": lat, "lng": lng}}}]}).encode("utf-8"), "application/json"
        if url.startswith(venue_geo.TIMEZONE_URL):
            q = urllib.parse.parse_qs(url.split("?", 1)[1])
            assert q["key"] == ["test-key"] and q["timestamp"] and q["location"]
            lat = float(q["location"][0].split(",")[0])
            tz = "America/Chicago" if lat > 35 else "America/New_York"
            if tz_status != "OK":
                return json.dumps({"status": tz_status}).encode("utf-8"), "application/json"
            return json.dumps({"status": "OK", "timeZoneId": tz, "rawOffset": -21600,
                               "dstOffset": 3600}).encode("utf-8"), "application/json"
        if url == venue_geo.ROUTES_URL:
            assert headers["X-Goog-Api-Key"] == "test-key"
            assert headers["X-Goog-FieldMask"] == venue_geo.ROUTES_FIELD_MASK
            assert payload["travelMode"] == "DRIVE"
            assert payload["origin"]["location"]["latLng"]["latitude"]
            if routes is None:
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(json.dumps(
                    {"error": {"code": 403, "status": "PERMISSION_DENIED",
                               "message": "Routes API has not been used in project 42 before or it is disabled."}}
                ).encode("utf-8")))
            meters, seconds = routes
            return json.dumps({"routes": [{"distanceMeters": meters,
                                           "duration": "%ds" % seconds}]}).encode("utf-8"), "application/json"
        raise AssertionError("unexpected call to %s" % url)

    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(venue_geo, "_http", fake_http)
    venue_geo.clear_refusal()
    venue_geo.reset_routes()
    _quiet_photos(monkeypatch)
    return calls


def _match(asked):
    for key in POINTS:
        if asked.startswith(key):
            return key
    raise AssertionError("no canned point for %r" % asked)


def _no_google(monkeypatch):
    calls = []

    def fake_http(url, payload=None, headers=None):
        calls.append(url)
        raise AssertionError("no call may leave without a key")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(venue_geo, "_http", fake_http)
    monkeypatch.setattr(venue_photos, "_http", fake_http)
    return calls


def _address(owner, vid, address, city):
    ts.update_venue(owner["id"], vid, {"address": address, "city": city})


def _linked_venue(client, owner, tid, sid):
    """The venue record the show was linked to when it was made."""
    return ts.get_show(tid, sid)["venue_id"]


def _imported(client, tid):
    """Two shows through the CSV importer, which is the path that leaves a
    show's own time zone blank — the calendar form stamps the tour's."""
    csv_text = ("date,city,venue,type\n"
                "2030-05-02,Nashville,The Basement East,show\n"
                "2030-05-03,Atlanta,Terminal West,show\n")
    r = client.post("/tours/%s/import" % tid, data={"source": "csv", "text": csv_text,
                                                    "action": "confirm", "pick": ["0", "1"]})
    assert r.status_code == 302
    return ts.list_shows(tid)


def _with_addresses(client, owner, tid):
    shows = _imported(client, tid)
    assert [s["venue"] for s in shows] == ["The Basement East", "Terminal West"]
    assert all(not (s["tz"] or "") for s in shows), "an imported date carries no zone of its own"
    _address(owner, shows[0]["venue_id"], "917 Woodland St", "Nashville, TN")
    _address(owner, shows[1]["venue_id"], "887 W Marietta St NW", "Atlanta, GA")
    return ts.list_shows(tid)


def _home(client, tid):
    r = client.get("/tours/%s" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _map(client, tid):
    r = client.get("/tours/%s/map" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


# --- the provider on its own -------------------------------------------------

def test_a_known_address_answers_a_point_and_a_zone(monkeypatch):
    calls = _google(monkeypatch)
    found = venue_geo.geocode("917 Woodland St, Nashville, TN")
    assert found["lat"] == "36.1745" and found["lng"] == "-86.7496"
    assert found["formatted_address"].startswith("917 Woodland St, Nashville, TN 37206")
    assert found["place_id"]
    assert venue_geo.timezone_at(found["lat"], found["lng"], "2030-05-02") == "America/Chicago"
    # The timestamp the Time Zone API insists on is the show's own date.
    q = urllib.parse.parse_qs(calls[-1][0].split("?", 1)[1])
    assert int(q["timestamp"][0]) > 1893456000, "2030, not 1970"
    assert len(calls) == 2


def test_a_place_id_is_asked_instead_of_the_text_when_there_is_one(monkeypatch):
    calls = _google(monkeypatch, known=lambda a: True)
    venue_geo.geocode("917 Woodland St, Nashville, TN", place_id="ChIJ123")
    q = urllib.parse.parse_qs(calls[0][0].split("?", 1)[1])
    assert q["place_id"] == ["ChIJ123"] and "address" not in q, \
        "one exact Places record, not the best match for a string"


def test_zero_results_is_not_found_and_is_not_a_refusal(monkeypatch):
    _google(monkeypatch, known=lambda a: False)
    assert venue_geo.geocode("Nowhere At All") is None
    assert venue_geo.last_refusal() is None, "Google answered; it just does not know the address"


def test_a_refused_key_is_kept_with_googles_own_words(monkeypatch):
    _google(monkeypatch)

    def refused(url, payload=None, headers=None):
        return json.dumps({"results": [], "status": "REQUEST_DENIED",
                           "error_message": "This API project is not authorized to use this API."
                           }).encode("utf-8"), "application/json"
    monkeypatch.setattr(venue_geo, "_http", refused)
    venue_geo.clear_refusal()
    assert venue_geo.geocode("917 Woodland St, Nashville, TN") is None
    assert venue_geo.last_refusal() == {
        "status": "REQUEST_DENIED", "http": 200,
        "message": "This API project is not authorized to use this API."}


def test_a_bad_answer_never_raises(monkeypatch):
    _google(monkeypatch)
    monkeypatch.setattr(venue_geo, "_http", lambda *a, **k: (_ for _ in ()).throw(OSError("no route to host")))
    assert venue_geo.geocode("917 Woodland St, Nashville, TN") is None
    assert venue_geo.timezone_at(36.0, -86.0) is None
    assert venue_geo.drive(NASHVILLE, ATLANTA) is None
    monkeypatch.setattr(venue_geo, "_http", lambda *a, **k: (b"<html>not json", "text/html"))
    assert venue_geo.geocode("917 Woodland St, Nashville, TN") is None
    assert venue_geo.timezone_at(36.0, -86.0) is None


def test_routes_switches_itself_off_after_one_refusal(monkeypatch):
    calls = _google(monkeypatch, routes=None)
    assert venue_geo.routes_available()
    assert venue_geo.drive(NASHVILLE, ATLANTA) is None
    assert not venue_geo.routes_available(), "asked once, not once per leg"
    assert venue_geo.last_refusal()["status"] == "PERMISSION_DENIED"
    before = len(calls)
    assert venue_geo.drive(NASHVILLE, ATLANTA) is None
    assert len(calls) == before, "no second call to an API that is off"
    venue_geo.reset_routes()


def test_routes_answers_metres_and_protobuf_seconds(monkeypatch):
    _google(monkeypatch, routes=(399000, 14400))
    got = venue_geo.drive(NASHVILLE, ATLANTA)
    assert got == {"meters": 399000, "seconds": 14400}


def test_without_a_key_and_in_sandbox_nothing_leaves(monkeypatch, flask_app):
    calls = _no_google(monkeypatch)
    assert not venue_geo.configured()
    assert venue_geo.geocode("917 Woodland St, Nashville, TN") is None
    assert venue_geo.timezone_at(36.0, -86.0) is None
    assert venue_geo.drive(NASHVILLE, ATLANTA) is None
    assert calls == []
    calls = _google(monkeypatch)
    monkeypatch.setattr(sandbox, "active", lambda: True)
    assert not venue_geo.configured()
    assert venue_geo.geocode("917 Woodland St, Nashville, TN") is None
    assert venue_geo.timezone_at(36.0, -86.0) is None
    assert venue_geo.drive(NASHVILLE, ATLANTA) is None
    assert calls == [], "a key in a sandbox is still no provider"


# --- the button, the records, and the pages ----------------------------------

def test_a_venue_with_an_address_gets_a_point_a_zone_and_the_matched_address(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    home = _home(client, tid)
    assert "Fetch coordinates" in home and "no Google Maps key" not in home
    assert 'action="/tours/%s/venues/fetch-coordinates"' % tid in home
    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s" % tid)
    v = ts.get_venue(owner["id"], shows[0]["venue_id"])
    assert v["lat"] == "36.1745" and v["lng"] == "-86.7496"
    assert v["tz"] == "America/Chicago" and v["geocoded_at"]
    assert v["geo_address"].startswith("917 Woodland St, Nashville, TN 37206")
    asked = [urllib.parse.parse_qs(u.split("?", 1)[1]).get("address", [""])[0]
             for u, _p in calls if u.startswith(venue_geo.GEOCODE_URL)]
    assert asked == ["917 Woodland St, Nashville, TN", "887 W Marietta St NW, Atlanta, GA"], \
        "once per venue, the street address with its city"
    home = _home(client, tid)
    assert "Coordinates for 2 venues; 0 not found" in home
    assert "Fetch coordinates" not in home, "nothing left to fetch"
    # The date page names the source; a pair of numbers with no source
    # would read as a survey somebody did.
    page = client.get("/tours/%s/shows/%s?tab=venue" % (tid, shows[0]["id"])).get_data(as_text=True)
    assert "Coordinates from Google: 36.1745, -86.7496" in page
    assert "matched 917 Woodland St, Nashville, TN 37206" in page
    # Said once, for the run that happened.
    assert "Coordinates for 2 venues" not in _home(client, tid)


def test_a_room_with_no_address_is_skipped_not_counted_as_missing(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid, "2030-05-02", "TBA")
    sid = _show(client, tid, "2030-05-04", "The Basement East")
    vid = _linked_venue(client, owner, tid, sid)
    assert vid, "the room is named, so it has a record"
    assert not ts.get_venue(owner["id"], vid)["address"], "and no address yet"
    home = _home(client, tid)
    assert "Fetch coordinates" not in home, "nothing a press could do"
    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302
    assert [u for u, _p in calls if u.startswith(venue_geo.GEOCODE_URL)] == [], \
        "a name with no address is not geocoded: the best match for a bare name is anywhere"
    home = _home(client, tid)
    assert "Coordinates for 0 venues; 0 not found" in home
    assert not ts.get_venue(owner["id"], vid)["lat"]


def test_an_address_google_does_not_know_is_not_found_not_an_error(flask_app, monkeypatch):
    _google(monkeypatch, known=lambda a: a.startswith("917 Woodland"))
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302
    home = _home(client, tid)
    assert "Coordinates for 1 venues; 1 not found" in home
    assert "refused" not in home, "a room Google does not know is not a refusal"
    assert ts.get_venue(owner["id"], shows[0]["venue_id"])["lat"] == "36.1745"
    assert not ts.get_venue(owner["id"], shows[1]["venue_id"])["lat"]
    assert "Fetch coordinates" in home, "one venue still has no point"


def test_a_refused_key_says_so_and_writes_nothing(flask_app, monkeypatch):
    _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)

    def refused(url, payload=None, headers=None):
        return json.dumps({"results": [], "status": "REQUEST_DENIED",
                           "error_message": "You must enable Billing on the Google Cloud Project."
                           }).encode("utf-8"), "application/json"
    monkeypatch.setattr(venue_geo, "_http", refused)
    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302
    home = _home(client, tid)
    assert "Google refused the key (REQUEST_DENIED): You must enable Billing on the Google Cloud Project." in home
    assert "enable the Geocoding API and the Time Zone API" in home
    assert "not found" not in home, "a refusal is not a fact about the addresses"
    for s in shows:
        v = ts.get_venue(owner["id"], s["venue_id"])
        assert not v["lat"] and not v["lng"] and not v["geocoded_at"]
        assert not (ts.get_show(tid, s["id"])["tz"] or ""), "and no date was given a zone"
    assert "Fetch coordinates" in home


def test_in_sandbox_the_button_is_not_offered_and_nothing_leaves(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    _with_addresses(client, owner, tid)
    monkeypatch.setattr(sandbox, "active", lambda: True)
    home = _home(client, tid)
    assert "Venue coordinates: no Google Maps key on this deployment" in home
    assert "Fetch coordinates" not in home
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert calls == []


# --- the date's time zone ----------------------------------------------------

def test_a_blank_date_takes_the_rooms_zone_and_a_typed_one_is_kept(flask_app, monkeypatch):
    _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    nash, atl = shows[0], shows[1]
    # The owner types a zone on the Atlanta date before the run.
    r = client.post("/tours/%s/shows/%s/ext" % (tid, atl["id"]), data={"tz": "America/Denver"})
    assert r.status_code == 302
    assert ts.get_show(tid, atl["id"])["tz"] == "America/Denver"
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    filled = ts.get_show(tid, nash["id"])
    assert filled["tz"] == "America/Chicago" and filled["tz_source"] == "venue"
    kept = ts.get_show(tid, atl["id"])
    assert kept["tz"] == "America/Denver", "an owner's own zone is never overwritten"
    assert (kept["tz_source"] or "") == ""
    assert "1 dates took their time zone from the room" in _home(client, tid)
    # The date page says where the filled one came from — quietly, and
    # only on the date that was filled.
    page = client.get("/tours/%s/shows/%s?tab=venue" % (tid, nash["id"])).get_data(as_text=True)
    assert '<p class="to-muted" style="font-size:12px;margin:-4px 0 8px">' \
           "Time zone from the venue's location.</p>" in page, "quiet text, not a lamp"
    other = client.get("/tours/%s/shows/%s?tab=venue" % (tid, atl["id"])).get_data(as_text=True)
    assert "Time zone from the venue's location." not in other
    # And a later hand edit takes the zone back: the note goes with it.
    client.post("/tours/%s/shows/%s/ext" % (tid, nash["id"]), data={"tz": "America/New_York"})
    after = ts.get_show(tid, nash["id"])
    assert after["tz"] == "America/New_York" and (after["tz_source"] or "") == ""
    assert "Time zone from the venue's location." not in \
        client.get("/tours/%s/shows/%s?tab=venue" % (tid, nash["id"])).get_data(as_text=True)


def test_the_filled_zone_reaches_the_day_sheet(flask_app, monkeypatch):
    """The day sheet's header prints the show's zone, so a date that was
    blank printed nothing and a driver read the times as local. Filling
    the zone from the room changes exactly that line."""
    _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    sid = shows[0]["id"]
    before = client.get("/tours/%s/shows/%s/day-sheet" % (tid, sid))
    assert before.status_code == 200
    assert "All times" not in before.get_data(as_text=True)
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    after = client.get("/tours/%s/shows/%s/day-sheet" % (tid, sid)).get_data(as_text=True)
    assert "All times America/Chicago." in after


# --- the route page ----------------------------------------------------------

def test_the_route_says_straight_line_when_routes_is_not_enabled(flask_app, monkeypatch):
    _google(monkeypatch, routes=None)
    client, owner = _user(flask_app)
    tid = _tour(client)
    _with_addresses(client, owner, tid)
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    page = _map(client, tid)
    assert "mi straight line" in page
    assert "driving, Google Routes" not in page.split("<ol")[1].split("</ol>")[0]
    assert "no drive time because none was measured" in page
    home = _home(client, tid)
    assert "Drive times: Google refused the key (PERMISSION_DENIED)" in home
    assert "Routes API has not been used in project 42" in home
    assert "Enable the Routes API" in home
    assert "Coordinates for 2 venues; 0 not found" in home, "the coordinates run still succeeded"


def test_the_route_shows_a_measured_drive_and_names_its_source(flask_app, monkeypatch):
    _google(monkeypatch, routes=(399000, 14400))
    client, owner = _user(flask_app)
    tid = _tour(client)
    _with_addresses(client, owner, tid)
    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302
    assert "1 drives measured" in _home(client, tid)
    page = _map(client, tid)
    assert "248 mi, 4 h driving, Google Routes" in page
    assert "mi straight line" not in page.split("<ol")[1].split("</ol>")[0], \
        "a measured drive replaces the straight line, and says which it is"
    # Read from the store on the next render: a page never calls Google.
    monkeypatch.setattr(venue_geo, "_http",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("a page render must not call out")))
    assert "248 mi, 4 h driving, Google Routes" in _map(client, tid)


def test_an_overnight_the_tour_cannot_make_is_flagged_from_measured_times_only(flask_app, monkeypatch):
    """Bus call at 23:00 in Nashville, four hours of driving, load-in at
    10:00 in Atlanta — and Atlanta is an hour ahead. The flag is only
    ever drawn from a duration Google measured and two times somebody
    entered; with no measured duration the page says nothing."""
    import db as store
    _google(monkeypatch, routes=(399000, 14400))
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    ts.add_schedule_item(tid, owner["id"], {"day_date": "2030-05-02", "show_id": shows[0]["id"],
                                            "category": "bus_call", "title": "Bus call", "start_time": "23:00"})
    ts.add_schedule_item(tid, owner["id"], {"day_date": "2030-05-03", "show_id": shows[1]["id"],
                                            "category": "load_in", "title": "Load-in", "start_time": "10:00"})
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    page = _map(client, tid)
    assert "248 mi, 4 h driving, Google Routes" in page
    assert "load-in is 10:00" not in page, "four hours from a 23:00 bus call makes a 10:00 load-in"
    # The same two times against a fifteen-hour drive do not make it, and
    # the arrival is printed in the room's own zone, not the one left.
    key = tour_os._leg_key(("36.1745", "-86.7496"), ("33.7776", "-84.4128"))
    store.set_kv(key, json.dumps({"meters": 399000, "seconds": 54000}))
    page = _map(client, tid)
    assert "leaves 23:00, arrives 15:00 — load-in is 10:00, 5 h late" in page
    # And with no measured duration there is no flag at all: a straight
    # line has no drive time, so nothing can be late.
    store.set_kv(key, "")
    page = _map(client, tid)
    assert "load-in is 10:00" not in page and "mi straight line" in page


def test_a_view_only_member_sees_the_numbers_but_no_button(flask_app, monkeypatch):
    _google(monkeypatch, routes=(399000, 14400))
    client, owner = _user(flask_app)
    tid = _tour(client)
    _with_addresses(client, owner, tid)
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    home = viewer.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Fetch coordinates" not in home and "Coordinates for" not in home
    assert "no Google Maps key" not in home
    page = viewer.get("/tours/%s/map" % tid).get_data(as_text=True)
    assert "248 mi, 4 h driving, Google Routes" in page, "the measured drive is for everyone"
    assert viewer.post("/tours/%s/venues/fetch-coordinates" % tid).status_code == 403


def test_a_slow_google_is_cut_off_at_the_budget(flask_app, monkeypatch):
    """Each venue can cost two 10s calls; a request stops asking past
    GEO_BUDGET_S and says what it did not reach rather than calling those
    rooms not found."""
    clock = [0.0]
    monkeypatch.setattr(tour_os, "_clock", lambda: clock[0])
    _google(monkeypatch)
    real = venue_geo._http

    def slow(url, payload=None, headers=None):
        clock[0] += 16.0
        return real(url, payload, headers)
    monkeypatch.setattr(venue_geo, "_http", slow)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    home = _home(client, tid)
    assert "Coordinates for 1 venues; 0 not found; 1 not reached in time — press Fetch again" in home
    assert bool(ts.get_venue(owner["id"], shows[0]["venue_id"])["lat"])
    assert not ts.get_venue(owner["id"], shows[1]["venue_id"])["lat"]
    clock[0] = 0.0
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert "Coordinates for 1 venues; 0 not found" in _home(client, tid)
    assert bool(ts.get_venue(owner["id"], shows[1]["venue_id"])["lat"])


def test_a_hand_typed_point_is_never_replaced(flask_app, monkeypatch):
    calls = _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    ts.update_venue(owner["id"], shows[0]["venue_id"], {"lat": "36.0", "lng": "-86.0"})
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    v = ts.get_venue(owner["id"], shows[0]["venue_id"])
    assert v["lat"] == "36.0" and v["lng"] == "-86.0" and not v["geocoded_at"]
    asked = [urllib.parse.parse_qs(u.split("?", 1)[1]).get("address", [""])[0]
             for u, _p in calls if u.startswith(venue_geo.GEOCODE_URL)]
    assert asked == ["887 W Marietta St NW, Atlanta, GA"], "the room that already had a point is not asked about"


def test_typing_over_the_point_takes_googles_name_off_it(flask_app, monkeypatch):
    """A coordinate the owner has edited by hand is not Google's any more,
    so the record stops crediting Google for it."""
    _google(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    shows = _with_addresses(client, owner, tid)
    client.post("/tours/%s/venues/fetch-coordinates" % tid)
    vid = shows[0]["venue_id"]
    assert ts.get_venue(owner["id"], vid)["geocoded_at"]
    sid = shows[0]["id"]
    assert "Coordinates from Google" in \
        client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
    r = client.post("/tours/%s/venues/save" % tid,
                    data={"venue_id": vid, "name": "The Basement East", "address": "917 Woodland St",
                          "city": "Nashville, TN", "lat": "36.2", "lng": "-86.7496"})
    assert r.status_code == 302
    v = ts.get_venue(owner["id"], vid)
    assert v["lat"] == "36.2" and not v["geocoded_at"] and not v["geo_address"]
    assert "Coordinates from Google" not in \
        client.get("/tours/%s/shows/%s?tab=venue" % (tid, sid)).get_data(as_text=True)
