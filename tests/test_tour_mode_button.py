"""Every tour page's Planning view / Live view button was a 404.

Found by checking every template form action against the URL map
(2026-09-12): tour/_shell.html has posted to /tours/<id>/mode since the
header was built, and no route answered. The override column and the
engine's reading of it already existed. This is the missing hop.
"""
import uuid

import pytest

import app as appmod
import db as store
import tour_store as ts

PASSWORD = "tour-mode-12345"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


@pytest.fixture
def owner(flask_app):
    email = "tmode-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Tour Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={"name": "Mode Run", "artist_name": "A",
                                        "start_date": "2030-05-01", "end_date": "2030-05-10",
                                        "home_tz": "America/New_York", "currency": "USD"})
    assert r.status_code == 302
    client._tour = r.headers["Location"].rstrip("/").split("/")[-1]
    return client


def test_the_header_button_posts_somewhere_that_answers(owner):
    body = owner.get("/tours/%s" % owner._tour).get_data(as_text=True)
    assert 'action="/tours/%s/mode"' % owner._tour in body
    assert "Live view" in body, "a 2030 tour reads as planning today"
    r = owner.post("/tours/%s/mode" % owner._tour, data={"mode": "live"})
    assert r.status_code == 302, "not a 404"
    assert ts.get_tour(owner._tour)["mode_override"] == "live"
    after = owner.get("/tours/%s" % owner._tour).get_data(as_text=True)
    assert "Planning view" in after, "the button now offers the way back"


def test_auto_hands_the_decision_back_to_the_dates(owner):
    owner.post("/tours/%s/mode" % owner._tour, data={"mode": "live"})
    owner.post("/tours/%s/mode" % owner._tour, data={"mode": "auto"})
    assert ts.get_tour(owner._tour)["mode_override"] == ""


def test_nonsense_changes_nothing(owner):
    owner.post("/tours/%s/mode" % owner._tour, data={"mode": "party"})
    assert ts.get_tour(owner._tour)["mode_override"] == ""


def test_a_stranger_cannot_flip_it(owner, flask_app):
    other = flask_app.test_client()
    other.post("/signup", data={"name": "S", "password": PASSWORD,
                                "email": "tmode-o-%s@example.net" % uuid.uuid4().hex[:8]})
    other.post("/login", data={"email": "nobody", "password": PASSWORD})
    r = other.post("/tours/%s/mode" % owner._tour, data={"mode": "live"})
    assert r.status_code in (302, 403, 404)
    assert ts.get_tour(owner._tour)["mode_override"] == ""
