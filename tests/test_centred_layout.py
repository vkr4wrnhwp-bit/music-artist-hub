"""Centred, not pushed against the left margin.

Owner, 2026-09-19: "move the suites into the center and then the line
below it into the center. You always push stuff over to the left side
margin. We need to center a lot of text like that."

Two places this file holds: the Tool suites strip under every signed-in
page, and a room's screen of icons. The app home's bottom lines are held
in tests/test_split_home.py.
"""
import io
import os
import re
import uuid

import db as store
from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "centred-12345"


def _read(*parts):
    return io.open(os.path.join(HERE, *parts), encoding="utf-8").read()


def _rule(css, selector):
    return css.split(selector + " {")[1].split("}")[0]


def test_the_suites_strip_is_one_centred_block():
    css = _read("static", "css", "app-chrome.css")
    assert "text-align: center" in _rule(css, ".sb-suites")
    grid = _rule(css, ".sb-suites-grid")
    # Four columns that stop growing, sat in the middle as one group.
    assert "repeat(4, minmax(0, 240px))" in grid
    assert "justify-content: center" in grid and "margin-inline: auto" in grid
    # Inside a cell the mark, name and badge keep their shared lines.
    assert "text-align: left" in _rule(css, ".sb-suite")
    # A phone keeps two across.
    phone = css.split("@media (max-width: 767px) {")[-1]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in phone


def test_a_room_centres_its_header_its_icons_and_its_note():
    t = _read("templates", "room.html")
    assert "grid-cols-3" not in t and "lg:grid-cols-6" not in t
    section = t.split("<section")[1].split(">")[0]
    for cls in ("flex", "flex-wrap", "justify-center"):
        assert cls in section.split('class="')[1].split('"')[0].split(), cls
    assert '<div class="text-center">' in t
    assert "mx-auto" in t.split("{{ room.purpose }}")[0].rsplit("<p", 1)[1]
    note = t.split("Every icon opens")[0].rsplit("<p", 1)[1]
    assert "text-center" in note
    # Each icon keeps the width a grid cell had, so only a short last row
    # changes: three across, four from 640px, six from 1024px.
    css = _read("static", "css", "app-chrome.css")
    assert "width: calc((100% - 2 * 16px) / 3)" in css
    assert "width: calc((100% - 3 * 16px) / 4)" in css
    assert "width: calc((100% - 5 * 16px) / 6)" in css


def test_a_rendered_room_carries_the_centred_row(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = app_obj.test_client()
    email = "centred-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Centred", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": "pro"})
    page = c.get("/room/stage").get_data(as_text=True)
    cards = re.findall(r'<a class="sb-room-icon [^"]*"[^>]*data-room-card="([a-z-]+)"', page)
    assert cards and cards[0] == "tours"
    assert 'class="flex flex-wrap justify-center gap-4"' in page


def test_the_stylesheet_build_moved_with_the_change():
    """A cached app-chrome.css has none of these rules, and every shell
    must ask for the same build."""
    seen = set()
    for root, _dirs, files in os.walk(os.path.join(HERE, "templates")):
        for fn in files:
            if fn.endswith(".html"):
                src = io.open(os.path.join(root, fn), encoding="utf-8").read()
                seen.update(p.split('"')[0] for p in src.split("app-chrome.css?v=")[1:])
    assert seen and min(int(v) for v in seen) >= 11
