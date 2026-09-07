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


def test_the_index_carries_a_month_across_every_tour(flask_app):
    client, owner = _user(flask_app)
    assert 'id="all-cal"' not in client.get("/tours").get_data(as_text=True), "no dates: no calendar"
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "Room One")
    r = client.post("/tours/new", data={"one_off": "1", "venue": "Turf Club", "city": "St. Paul, MN", "date": "2030-05-09"})
    tid2 = r.headers["Location"].split("/tours/")[1].split("/")[0]
    s2 = ts.list_shows(tid2)[0]["id"]
    html = client.get("/tours").get_data(as_text=True)
    assert 'aria-label="May 2030" id="all-cal"' in html, "the month of the first upcoming date"
    grid = html.split('id="all-cal"')[1]
    assert ('href="/tours/%s/shows/%s"' % (tid, s1)) in grid and ('href="/tours/%s/shows/%s"' % (tid2, s2)) in grid
    assert "2 dates across your tours" in html and "% ready" not in grid, "no readiness figure off the tour"
    assert 'href="?month=2030-06">' in html and 'href="?month=2030-04">' in html
    assert 'aria-label="June 2030"' in client.get("/tours?month=2030-06").get_data(as_text=True)


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
