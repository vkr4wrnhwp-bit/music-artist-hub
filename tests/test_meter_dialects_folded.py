"""TOUR's to-meter and Signal's sg-bar / sg-meter are the shared meter now.

Three private dialects of the same instrument - a track with a fill sized
by an inline width - lived in tour-os.css and signal.css beside the one in
app-chrome.css. They are gone; the pages draw the shared .sb-meter, and
Signal, which sits on ivory, gets the meter's paper variant rather than a
copy of its own.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import signal_ingest as ingest
import signal_providers as providers
import signal_store as sstore

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "dialect-pass-123"


def _read(rel):
    return io.open(os.path.join(HERE, rel), encoding="utf-8").read()


# --- the dialects are gone ---------------------------------------------------

def test_no_template_draws_a_private_meter_any_more():
    import glob
    hits = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"), recursive=True):
        s = _read(os.path.relpath(p, HERE))
        for dead in ('class="to-meter', 'class="sg-meter', 'class="sg-bar'):
            if dead in s:
                hits.append("%s: %s" % (os.path.basename(p), dead))
    assert hits == [], hits


def test_the_private_rules_are_out_of_the_sheets():
    for rel, dead in (("static/css/tour-os.css", r"^\.to-meter\b"),
                      ("static/css/signal.css", r"^\.sg-bar\b"),
                      ("static/css/signal.css", r"^\.sg-meter\b")):
        assert not re.search(dead, _read(rel), re.M), (rel, dead)


def test_the_shared_meter_can_sit_on_paper():
    css = _read("static/css/app-chrome.css")
    assert ".sb-on-paper .sb-meter {" in css
    assert ".sb-on-paper .sb-meter-fill { background: var(--sb-paper-gold); }" in css
    # And it is block-level, so a bare <span class="sb-meter"> outside a
    # grid or flex row still has a height.
    assert re.search(r"\.sb-meter \{\s*display: block;", css)


def test_the_fill_is_block_level_or_every_ladder_reads_empty():
    """Found on Signal: the fill is a <span>, and an inline span ignores
    its width, so a meter at 72 drew as a meter at zero. The well and
    the readout said one thing and the ladder said another."""
    css = _read("static/css/app-chrome.css")
    assert re.search(r"\.sb-meter-fill \{\s*display: block;", css)


def test_signal_loads_the_chrome_sheet_and_declares_paper():
    shell = _read("templates/signal/_shell.html")
    assert "/static/css/app-chrome.css?v=" in shell
    assert 'class="sg-body sb-on-paper"' in shell
    # signal.css must come after, so its cell sizing wins.
    assert shell.index("app-chrome.css") < shell.index("signal.css")


# --- and the pages still read --------------------------------------------------

@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def test_a_tour_date_draws_readiness_on_the_shared_meter(flask_app):
    email = "dialect-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Meter Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Meter Run", "artist_name": "Meter Artist", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "The Basement East",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    body = client.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    assert re.search(r'aria-label="Readiness: \d+%"', body)
    assert "sb-meter-fill" in body and "to-meter" not in body


def test_signal_scores_draw_on_the_shared_meter(flask_app):
    providers.reset_registry(providers.ProviderRegistry(adapters=[]))
    ingest.refresh_universe(max_artists=6, force=True)
    email = "dialect-sig-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Scout", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    org = sstore.default_org()
    sstore.upsert_member(org["id"], email, "Scout", "owner", user_id=user["id"])
    body = client.get("/signal").get_data(as_text=True)
    assert 'class="sg-body sb-on-paper"' in body
    if "sg-score" in body:                     # the board lists scored artists
        assert 'class="sb-meter' in body and "sg-bar" not in body
