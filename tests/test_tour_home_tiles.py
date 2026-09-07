"""A tour, opened, is the list of its shows.

The owner, 2026-09-07: "this is supposed to be just a list of the shows
like you had before and no header navigation or calendar. once you click
into the specific show day that is when the options for adding features
will be available." So /tours/<id> is the Dates rows and nothing else;
the bar lives on the other tour pages and inside a show.
"""
import re

from tests.test_tour_date_page import _user, _tour, _show, flask_app  # noqa: F401


def _home(client, tid):
    r = client.get("/tours/%s" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_the_tour_page_is_the_list_of_its_shows_and_nothing_else(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "The Basement East")
    s2 = _show(client, tid, "2030-05-04", "Exit/In")
    html = _home(client, tid)
    rows = html.split('id="dates"')[1]
    assert re.findall(r'<a class="to-date-when" href="/tours/%s/shows/([0-9a-f]+)"' % tid, html) == [s1, s2]
    assert "The Basement East" in rows and "Exit/In" in rows and "% ready" in rows or "ready" in rows
    assert 'class="to-tabs to-bar"' not in html, "no header navigation on the tour's page"
    assert 'class="to-cal"' not in html, "no calendar on the tour's page"
    for gone in ('id="upcoming"', "Needs attention", "What changed", "Today for you", "to-legend", "Advance the run"):
        assert gone not in html, gone
    assert "Import dates" not in html and "Add a day" not in html, "the list and nothing else"
    assert '<a href="/tours" style="text-decoration:none">‹ Home</a>' in html, "the way back to your tours and the calendar"
    assert "to-date-adv" not in html and "no address" not in html, "no advance lamp on a row"
    dates_page = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert 'class="to-tabs to-bar"' in dates_page and 'id="dates"' in dates_page, "the Dates page keeps its bar and the same rows"


def test_an_empty_run_says_where_to_start(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = _home(client, tid)
    assert "No dates yet" in html and 'class="to-tabs to-bar"' not in html


def test_the_bar_on_the_other_pages_is_what_booking_needs(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    html = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    bar = html.split('class="to-tabs to-bar"')[1].split("</nav>")[0]
    labels = re.findall(r'class="to-tab[^"]*"[^>]*>([^<]+)<', bar)
    assert labels[:7] == ["Home", "Import", "Venue book", "Crew directory", "All travel &amp; hotels", "Tour money", "All files"]
    assert '<a class="to-tab " href="/tours">Home</a>' in bar, "Home is your tours and the calendar"
    assert ('href="/tours/%s" style="color:inherit;text-decoration:none">Test Run</a>' % tid) in html, "the tour's name is the way back to its list"
    items = re.findall(r'class="to-more-item[^"]*"[^>]*>([^<]+)<', bar)
    assert items == ["Show list", "Calendar", "Marketing, all dates", "Stage plot", "Exports", "What changed", "Ask Tour", "Share links", "Team", "Settings"]


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-tile-v" in css and ".to-lcds" in css and ".to-cal" in css
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 209
