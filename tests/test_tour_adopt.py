"""Nothing entered in the old Tour Hub is left behind.

Every show sitting on no tour is adopted onto one: the account's one tour,
the tour whose dates cover it, or a new tour made for them. Attaching is the
same path as the Add-to-tour button; nothing is deleted; it is idempotent;
it runs at boot, on the tours index and on the old /tour link.
"""
import uuid

import pytest

import app as appmod
import db as store
import tour_store as ts

PASSWORD = "adopt-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app):
    email = "adopt-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Adopt Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    return client, store.get_user_by_email(email)


def _hub_show(owner, date_, venue, city="Nashville, TN"):
    sid = store.add_tour_show(owner["id"], date_, venue, city, "")
    return sid


def test_hub_shows_with_no_tour_get_a_tour_made_for_them(flask_app):
    client, owner = _user(flask_app)
    a = _hub_show(owner, "2026-10-14", "The Basement")
    b = _hub_show(owner, "2026-10-16", "Terminal West", "Atlanta, GA")
    assert ts.list_tours(owner["id"]) == []
    tid, n = ts.adopt_orphan_shows(owner["id"])
    assert n == 2
    tours = ts.list_tours(owner["id"])
    assert len(tours) == 1 and tours[0]["id"] == tid
    assert tours[0]["name"] == ts.ADOPTED_TOUR_NAME
    assert (tours[0]["start_date"], tours[0]["end_date"]) == ("2026-10-14", "2026-10-16")
    # Attached exactly as Add-to-tour would: on the tour, with a day and an ext row.
    for sid in (a, b):
        assert store.get_tour_show(owner["id"], sid)["tour_id"] == tid
        assert ts.get_show(tid, sid) is not None
    assert len(ts.list_shows(tid)) == 2
    # Nothing was deleted, and adopting again does nothing.
    assert len(store.list_tour_shows(owner["id"])) == 2
    assert ts.adopt_orphan_shows(owner["id"]) == (None, 0)
    # The change log says where they came from.
    page = client.get("/tours/%s/changes?level=all" % tid).get_data(as_text=True)
    assert "from Tour Hub" in page and "The Basement" in page
    # The old link lands on the adopted tour's Dates page.
    r = client.get("/tour")
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s/shows" % tid)
    dates = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert "The Basement" in dates and "Terminal West" in dates


def test_hub_shows_join_the_tour_whose_dates_cover_them(flask_app):
    client, owner = _user(flask_app)
    r = client.post("/tours/new", data={
        "name": "Spring", "artist_name": "A", "start_date": "2026-03-01", "end_date": "2026-03-31",
        "home_tz": "America/New_York", "currency": "USD"})
    spring = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/new", data={
        "name": "Autumn", "artist_name": "A", "start_date": "2026-10-01", "end_date": "2026-10-31",
        "home_tz": "America/New_York", "currency": "USD"})
    autumn = r.headers["Location"].rstrip("/").split("/")[-1]
    in_autumn = _hub_show(owner, "2026-10-14", "The Basement")
    in_spring = _hub_show(owner, "2026-03-05", "Cat's Cradle", "Carrboro, NC")
    outside = _hub_show(owner, "2027-01-09", "9:30 Club", "Washington, DC")
    home, n = ts.adopt_orphan_shows(owner["id"])
    assert n == 3
    assert store.get_tour_show(owner["id"], in_autumn)["tour_id"] == autumn
    assert store.get_tour_show(owner["id"], in_spring)["tour_id"] == spring
    # A show no tour covers joins the most recent tour, never a new one.
    assert store.get_tour_show(owner["id"], outside)["tour_id"] == autumn
    assert len(ts.list_tours(owner["id"])) == 2 and home == autumn


def test_the_tours_index_and_boot_sweep_adopt_too(flask_app):
    client, owner = _user(flask_app)
    _hub_show(owner, "2026-11-02", "Bowery Ballroom", "New York, NY")
    page = client.get("/tours").get_data(as_text=True)
    assert ts.ADOPTED_TOUR_NAME in page and "Bowery Ballroom" not in page   # listed as a tour, not as a stray
    assert ts.orphan_shows(owner["id"]) == []
    # The boot sweep covers every account at once.
    client2, other = _user(flask_app)
    _hub_show(other, "2026-12-01", "Metro", "Chicago, IL")
    assert ts.adopt_all_orphans() >= 1
    assert ts.orphan_shows(other["id"]) == []
    assert ts.list_tours(other["id"])[0]["name"] == ts.ADOPTED_TOUR_NAME
