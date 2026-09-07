"""Screen A of the owner's numbered mockup (2026-09-07), unchanged by the
critique: /tours is a list of full tours and one-off shows, click one to
go in; then Start a tour, Add a one-off show, and a way to start from an
import file. A one-off show is a tour of one date whose single show is
made at the same time.
"""
import re

import tour_store as ts
from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def test_the_index_is_rows_and_three_pluses(flask_app):
    client, owner = _user(flask_app)
    html = client.get("/tours").get_data(as_text=True)
    assert '<details class="to-add" id="start-tour" open>' in html, "nothing to list: the first form is open"
    assert '<details class="to-add" id="one-off">' in html and 'name="first" value="import"' in html
    tid = _tour(client)
    _show(client, tid)
    _show(client, tid, "2030-05-03", "Room Two")
    html = client.get("/tours").get_data(as_text=True)
    rows = html.split('id="mine"')[1].split("</div>\n  </div>")[0]
    assert '<span class="to-tile-l">Full tour' in rows and "2 dates" in rows and "<table" not in html
    assert '<details class="to-add" id="start-tour">' in html, "a tour exists: the form waits"
    assert ts.ADOPTED_TOUR_NAME not in html


def test_a_one_off_show_is_a_tour_of_one_date_with_its_show_made(flask_app):
    client, owner = _user(flask_app)
    r = client.post("/tours/new", data={"one_off": "1", "venue": "Turf Club", "city": "St. Paul, MN",
                                        "date": "2030-10-13", "home_tz": "America/Chicago"})
    assert r.status_code == 302 and "/shows/" in r.headers["Location"]
    tid = r.headers["Location"].split("/tours/")[1].split("/")[0]
    tour = ts.get_tour(tid)
    assert tour["name"] == "Turf Club · 2030-10-13" and tour["start_date"] == tour["end_date"] == "2030-10-13"
    shows = ts.list_shows(tid)
    assert len(shows) == 1 and shows[0]["venue"] == "Turf Club" and shows[0]["city"] == "St. Paul, MN"
    html = client.get("/tours").get_data(as_text=True)
    assert '<span class="to-tile-l">One-off show' in html and "1 date</span>" in html
    r = client.post("/tours/new", data={"one_off": "1", "venue": "No Date"})
    assert r.headers["Location"] == "/tours?one_off=date"
    assert '<details class="to-add" id="one-off" open>' in client.get("/tours?one_off=date").get_data(as_text=True)


def test_starting_from_a_file_lands_on_import(flask_app):
    client, owner = _user(flask_app)
    r = client.post("/tours/new", data={"name": "File Run", "start_date": "2030-05-01", "end_date": "2030-05-10",
                                        "home_tz": "America/New_York", "first": "import"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/import")
    assert client.get(r.headers["Location"]).status_code == 200
