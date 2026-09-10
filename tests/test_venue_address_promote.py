"""Google's street address reaches the record, not just the provenance.

Live, 2026-09-09: all 35 rooms on the owner's tour had been geocoded —
Turf Club held 44.9559821, -93.1679952 matched to "1601 University Ave W,
St Paul, MN 55104, USA" — and every one of them still printed "no
address" in the venue book, because the matched address was stored as
`geo_address` (provenance, deliberately off the record form) and never
promoted onto the record's own `address`. That is the line the advance,
the day sheet and the rider print, so the tour had a full set of
addresses and showed none of them.

The house rule applies: fill an empty field from a provider, never
overwrite one somebody typed.
"""
import uuid

import pytest

import tour_os
import tour_store as ts
import venue_geo
from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _venue(owner, name="Turf Club", city="St. Paul, MN", **fields):
    vid = ts.add_venue(owner["id"], dict({"name": name, "city": city}, **fields))
    return vid, ts.get_venue(owner["id"], vid)


def test_a_matched_address_is_promoted_onto_the_record(flask_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    _client, owner = _user(flask_app)
    vid, _v = _venue(owner)
    ts.set_venue_geo(owner["id"], vid, "44.9559821", "-93.1679952",
                     tz="America/Chicago",
                     address="1601 University Ave W, St Paul, MN 55104, USA")
    v = ts.get_venue(owner["id"], vid)
    assert v["lat"] and not (v["address"] or "").strip(), "placed, and still blank"

    # No network: the answer is already on the row.
    monkeypatch.setattr(venue_geo, "_http", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a promotion must not call Google")))
    assert tour_os.ensure_venue_geo(v) == "filled"
    after = ts.get_venue(owner["id"], vid)
    assert after["address"] == "1601 University Ave W, St Paul, MN 55104, USA"
    # Provenance survives, so the page can still say where it came from.
    assert after["geo_address"] == after["address"]
    # And there is nothing left to promote.
    assert tour_os.ensure_venue_geo(after) == "present"


def test_an_address_somebody_typed_is_never_replaced(flask_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    _client, owner = _user(flask_app)
    vid, _v = _venue(owner, address="Load in at the back, 1601 University")
    ts.set_venue_geo(owner["id"], vid, "44.95", "-93.16",
                     address="1601 University Ave W, St Paul, MN 55104, USA")
    v = ts.get_venue(owner["id"], vid)
    assert tour_os.ensure_venue_geo(v) == "present", "nothing to do"
    after = ts.get_venue(owner["id"], vid)
    assert after["address"] == "Load in at the back, 1601 University"


def test_the_button_returns_while_there_are_addresses_to_promote(flask_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-04", "Turf Club")
    vid = ts.get_show(tid, sid)["venue_id"]
    assert vid
    ts.set_venue_geo(owner["id"], vid, "44.95", "-93.16",
                     address="1601 University Ave W, St Paul, MN 55104, USA")
    tour = ts.get_tour(tid)
    # Placed but unpromoted still counts as work, so the control is offered.
    assert tour_os._geo_missing(tour, tid) == 1
    home = client.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Fetch coordinates" in home

    r = client.post("/tours/%s/venues/fetch-coordinates" % tid)
    assert r.status_code == 302
    assert ts.get_venue(owner["id"], vid)["address"] == \
        "1601 University Ave W, St Paul, MN 55104, USA"
    # Done: no work, no button.
    assert tour_os._geo_missing(ts.get_tour(tid), tid) == 0
    home = client.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Fetch coordinates" not in home
    assert "took the street address Google had already matched" in home


def test_a_room_with_no_match_at_all_is_left_alone(flask_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    _client, owner = _user(flask_app)
    vid, _v = _venue(owner, name="Somebody's Basement")
    ts.set_venue_geo(owner["id"], vid, "44.95", "-93.16", address="")
    v = ts.get_venue(owner["id"], vid)
    assert tour_os._address_to_promote(v) == ""
    assert tour_os.ensure_venue_geo(v) == "present"
    assert not (ts.get_venue(owner["id"], vid)["address"] or "").strip()
