"""The tour bar: seven entries for the daily work, the rest under More.

Phase 2 of the audit. Every TOUR_TABS key, route and scope is unchanged;
only what the bar shows is. A page under a group (hotels, route) lights
Travel & hotels and gets the sub-row; a page in More lights the More button
with its own label; a viewer without a scope sees neither the entry nor the
menu item.
"""
import re
import uuid

import pytest

import app as appmod
import db as store
import tour_os

PASSWORD = "bar-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner(flask_app):
    email = "bar-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Bar Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Bar Run", "artist_name": "Bar Artist", "start_date": "2030-06-01",
        "end_date": "2030-06-08", "home_tz": "America/New_York", "currency": "USD"})
    assert r.status_code == 302
    return client, r.headers["Location"].rstrip("/").split("/")[-1]


def _bar(page):
    return page.split('class="to-tabs to-bar"')[1].split("</nav>")[0]


def test_the_bar_is_seven_entries_for_an_owner(flask_app):
    client, tid = _owner(flask_app)
    page = client.get("/tours/%s" % tid).get_data(as_text=True)
    bar = _bar(page)
    labels = re.findall(r'class="to-tab[^"]*"[^>]*>([^<]+)<', bar)
    assert labels[:6] == ["Home", "Dates", "Crew", "Travel &amp; hotels", "Money", "Files"]
    assert 'class="to-more"' in bar and ">More <" in bar
    # Home is lit; nothing in More is.
    assert 'aria-current="page">Home<' in bar
    items = re.findall(r'class="to-more-item[^"]*"[^>]*>([^<]+)<', bar)
    assert items == ["My Day", "Calendar", "Schedule", "Venues", "Set lists", "Stage plot", "Guests", "VIP", "Merch",
                     "Marketing", "Content", "Tasks", "What changed", "Ask Tour", "Import", "Exports",
                     "Share links", "Team", "Settings"]
    # The old 24-link bar is gone: no tab for Hotels or Route in the top row.
    assert "Hotels</a>" not in bar and "Route</a>" not in bar


def test_a_page_in_more_lights_the_more_button_with_its_own_label(flask_app):
    client, tid = _owner(flask_app)
    page = client.get("/tours/%s/settings" % tid).get_data(as_text=True)
    bar = _bar(page)
    assert re.search(r'<summary class="to-tab is-on"[^>]*>Settings <', bar)
    assert 'class="to-more-item is-on" href="/tours/%s/settings" aria-current="page">Settings<' % tid in bar
    assert 'aria-current="page">Home<' not in bar


def test_hotels_and_route_sit_under_travel_with_a_sub_row(flask_app):
    client, tid = _owner(flask_app)
    for path, label in (("hotels", "Hotels"), ("map", "Route"), ("travel", "Travel")):
        page = client.get("/tours/%s/%s" % (tid, path)).get_data(as_text=True)
        bar = _bar(page)
        assert 'class="to-tab is-on" href="/tours/%s/travel" aria-current="page">Travel &amp; hotels<' % tid in bar
        sub = page.split('class="to-subnav"')[1].split("</nav>")[0]
        assert 'aria-current="page">%s<' % label in sub
        assert sub.count("to-sub-tab") == 3
    # Elsewhere there is no sub-row.
    assert 'class="to-subnav"' not in client.get("/tours/%s" % tid).get_data(as_text=True)


def test_the_bar_is_scope_filtered():
    owner = {"is_owner": True, "scopes": ["admin"]}
    crew = {"is_owner": False, "scopes": ["view", "hotel", "travel"]}
    bar = tour_os._tour_bar(owner, "home")
    assert [t["key"] for t in bar["primary"]] == ["home", "shows", "people", "travel", "money", "files"]
    assert "settings" in [t["key"] for t in bar["more"]]
    bar = tour_os._tour_bar(crew, "home")
    assert [t["key"] for t in bar["primary"]] == ["home", "shows", "people", "travel"]
    keys = [t["key"] for t in bar["more"]]
    for gated in ("money", "files", "settings", "team", "share", "import", "guests", "merch",
                  "marketing", "content", "vip"):
        assert gated not in keys, gated
    assert "my-day" in keys and "calendar" in keys and "setlists" in keys


def test_every_tour_page_still_answers_with_the_new_bar(flask_app):
    client, tid = _owner(flask_app)
    for key, _label, path in tour_os.TOUR_TABS:
        url = "/tours/%s%s" % (tid, "/" + path if path else "")
        r = client.get(url)
        assert r.status_code == 200, (key, r.status_code)
        assert 'class="to-tabs to-bar"' in r.get_data(as_text=True), key
