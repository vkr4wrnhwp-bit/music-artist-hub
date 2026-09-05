"""Signal's state pills are the shared lamp, on paper.

A pill that carries a STATE - on the desk, watching, stale, fresh,
configured, removed, a severity, an anomaly reading, an evidence status -
is the lamp now. A pill that carries a LABEL - a distributor class, a
shape, a role, a watchlist name, a lane, a confidence percentage - stays a
pill, because a lamp on a label would claim a state it does not have.
"""
import glob
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
PASSWORD = "sig-lamp-123"


def test_no_signal_template_colours_a_pill_by_state():
    hits = []
    for p in glob.glob(os.path.join(HERE, "templates", "signal", "*.html")):
        s = io.open(p, encoding="utf-8").read()
        for dead in ("is-warn", "is-ok", "is-hot"):
            if re.search(r"sg-pill[^>]*%s" % dead, s):
                hits.append("%s: %s" % (os.path.basename(p), dead))
    assert hits == [], hits


def test_the_pill_sheet_keeps_only_the_label_emphasis():
    css = io.open(os.path.join(HERE, "static", "css", "signal.css"), encoding="utf-8").read()
    assert ".sg-pill {" in css and ".sg-pill.is-gold" in css
    for dead in (".sg-pill.is-warn", ".sg-pill.is-ok", ".sg-pill.is-hot"):
        assert dead not in css, dead


def test_labels_are_still_pills():
    macros = io.open(os.path.join(HERE, "templates", "signal", "_macros.html"), encoding="utf-8").read()
    assert '<span class="sg-pill">{{ r[\'shape\'] or \'—\' }}</span>' in macros
    artist = io.open(os.path.join(HERE, "templates", "signal", "artist.html"), encoding="utf-8").read()
    assert "<span class=\"sg-pill\">{{ (e['confidence'] * 100)|round|int }}%</span>" in artist


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def test_the_board_draws_states_as_lamps_on_paper(flask_app):
    providers.reset_registry(providers.ProviderRegistry(adapters=[]))
    ingest.refresh_universe(max_artists=6, force=True)
    email = "sig-lamp-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Scout", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    org = sstore.default_org()
    sstore.upsert_member(org["id"], email, "Scout", "owner", user_id=user["id"])
    body = client.get("/signal/admin/data-sources").get_data(as_text=True)
    if "configured" in body:
        assert re.search(r'sb-lamp[^"]*">(configured|not configured)<', body)
        assert "sg-pill is-ok" not in body
    board = client.get("/signal").get_data(as_text=True)
    assert 'class="sg-body sb-on-paper"' in board
    if "Low risk" in board:
        assert 'sb-lamp">Low risk<' in board
