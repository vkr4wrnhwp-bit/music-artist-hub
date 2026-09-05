"""TOUR's check marks and state chips are the shared lamp.

The readiness checklist drew a glyph per state - a tick, an ellipsis, a
dash, a cross - coloured by a class on the row, so the state was a symbol
whose meaning lived in its colour. The home board's alerts drew "!". The
advance list and the parsed-inbox table drew state words as chips. All of
those are the lamp now: a word, coloured by its state, readable without
the colour. Chips that are labels rather than states stay chips.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "lamp-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner_with_show(flask_app):
    email = "lamp-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Lamp Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Lamp Run", "artist_name": "Lamp Artist", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "The Basement East",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    return client, tid, sid


def test_the_checklist_states_are_words_not_glyphs(flask_app):
    client, tid, sid = _owner_with_show(flask_app)
    body = client.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    check = body.split('class="to-check"')[1].split("</ul>")[0]
    assert 'class="mark"' not in check
    assert re.search(r'sb-lamp sb-lamp--crit">missing<', check) or \
        re.search(r'sb-lamp sb-lamp--on">done<', check)
    # A state the row cannot have yet is a word too, not a dash.
    assert "–" not in check and "×" not in check


def test_the_home_board_flags_with_a_word(flask_app):
    client, tid, sid = _owner_with_show(flask_app)
    body = client.get("/tours/%s" % tid).get_data(as_text=True)
    if "Needs attention" in body and 'class="to-check"' in body:
        board = body.split("Needs attention")[1]
        assert 'sb-lamp--crit">attention<' in board
        assert '<span class="mark">!' not in board


def test_no_tour_template_draws_a_mark_or_a_state_chip():
    import glob
    marks, state_chips = [], []
    for p in glob.glob(os.path.join(HERE, "templates", "tour", "**", "*.html"), recursive=True):
        s = io.open(p, encoding="utf-8").read()
        if 'class="mark"' in s:
            marks.append(os.path.basename(p))
        for word in ("sent", "failed", "high", "review"):
            if re.search(r'to-chip[^"]*">%s' % word, s):
                state_chips.append("%s: %s" % (os.path.basename(p), word))
    assert marks == [] and state_chips == [], (marks, state_chips)


def test_label_chips_are_still_chips():
    """A schedule category or "headliner" is a label, not a state, and a
    lamp on it would claim a state it does not have."""
    lineup = io.open(os.path.join(HERE, "templates", "tour", "show", "_lineup.html"),
                     encoding="utf-8").read()
    assert 'to-chip to-chip--gold">headliner' in lineup
    css = io.open(os.path.join(HERE, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-chip {" in css and ".to-check .mark" not in css
