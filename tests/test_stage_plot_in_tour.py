"""Stage Plot is in TOUR (owner, 2026-09-05).

The plot is the act's, not the tour's - one per account, drawn at
/stage-plot and attached to every advance TOUR sends. So it was not moved;
it was framed: a Stage plot page under every tour's More menu shows the
tour owner's plot, the owner edits it there, crew see the drawing and the
input list it derives, and the sidebar entry went because the plot is
reached from the tour, from Show Passport and from the TOUR home.
/stage-plot itself stays, for an act with no tour yet.
"""
import io
import os
import uuid

import pytest

import app as appmod
import hubs
import tour_os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "plot-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner(flask_app):
    email = "plot-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Plot Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Plot Run", "artist_name": "Plot Artist", "start_date": "2030-06-01",
        "end_date": "2030-06-08", "home_tz": "America/New_York", "currency": "USD"})
    assert r.status_code == 302
    return client, r.headers["Location"].rstrip("/").split("/")[-1]


def test_the_owner_draws_the_plot_inside_the_tour(flask_app):
    client, tid = _owner(flask_app)
    client.post("/stage-plot/save", json={"name": "Plot Artist", "items": {"drums": 1}, "pos": {}})
    body = client.get("/tours/%s/stage-plot" % tid).get_data(as_text=True)
    assert 'class="to-tabs to-bar"' in body            # the tour frame
    assert 'id="sp-canvas"' in body and 'id="sp-save"' in body
    assert '"drums": 1' in body or '"drums":1' in body  # the owner's own plot
    assert "var EDITABLE = true;" in body


def test_it_sits_under_more_for_the_owner_and_for_crew(flask_app):
    client, tid = _owner(flask_app)
    bar = client.get("/tours/%s" % tid).get_data(as_text=True).split(
        'class="to-tabs to-bar"')[1].split("</nav>")[0]
    assert ">Stage plot<" in bar
    crew = {"is_owner": False, "scopes": ["view"]}
    assert "stage-plot" in [t["key"] for t in tour_os._tour_bar(crew, "home")["more"]]


def test_crew_get_the_drawing_but_not_the_controls():
    """The read-only frame keeps the plot and the input list and drops
    every control, and the script is told so - a Save button that posts
    to the viewer's own plot would draw over the wrong act."""
    partial = io.open(os.path.join(HERE, "templates", "_stage_plot_designer.html"),
                      encoding="utf-8").read()
    assert partial.count("{% if editable %}") == 2
    assert 'var EDITABLE = {{ "true" if editable else "false" }};' in partial
    assert "if (!svg || !EDITABLE) return;" in partial
    assert "if (EDITABLE) {" in partial


def test_the_standalone_page_still_works_for_an_act_with_no_tour(flask_app):
    email = "plot-solo-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Solo", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    body = client.get("/stage-plot").get_data(as_text=True)
    assert "Stage Plot Designer" in body and 'id="sp-save"' in body
    assert "var EDITABLE = true;" in body


def test_the_sidebar_entry_is_gone_and_the_doors_remain():
    keys = {k for _hk, _n, _t, items in hubs.HUBS for k, *_ in items}
    assert "stage-plot" not in keys and "stage-plot" not in hubs.LIVE_KEYS
    home = io.open(os.path.join(HERE, "templates", "tour", "index.html"), encoding="utf-8").read()
    assert 'href="/stage-plot"' in home
    passport = io.open(os.path.join(HERE, "templates", "passport", "detail.html"), encoding="utf-8").read()
    assert 'href="/stage-plot"' in passport
