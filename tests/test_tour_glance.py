"""TOUR, less to read.

The owner, 2026-09-06: "when you open the screen, it's a lot of text. We
need more meters and images and less verbiage, more options if they want
the options." And on 2026-09-07, looking at a real date: "turf club has
multiple of the same features visible again ... allowing them to hit the
plus sign and add the features they want looks the cleanest, we should
have minimal information showing upon first opening."

So a date is one grid. Each section is a folded tile whose head carries
its lamp (set or empty, never a score) and its own status line; an open
section takes the row. One + tile, 'Add to this date', unfolds the chips
for what is not on the date yet. Nothing appears twice, and nothing is
open on first look unless the URL asked for it. The More menu is the same
nineteen pages read as four questions.
"""
import re

import pytest

import tour_os
from tests.test_tour_date_page import (_fresh, _page, _sections, _chips, flask_app,  # noqa: F401
                                       CORE, OPTIONAL)


def _open_sections(html):
    return re.findall(r'<section class="to-sec[^"]*" id="([a-z]+)" data-section="[a-z]+">\s*<details class="to-sec-d" open>', html)


def _head(html, key):
    sec = html.split('id="%s" data-section="%s"' % (key, key))[1]
    return sec.split("</summary>")[0]


def test_a_fresh_date_is_one_grid_of_folded_tiles_and_one_plus(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid)
    grid = html.split('<div class="to-secs">')[1]
    assert _sections(html) == CORE, "one section per core key, page order, activity last"
    assert _open_sections(html) == [], "nothing unfolds on first look"
    # Five empty; Activity already holds the date's creation, so it reads set.
    assert len(re.findall(r'class="sb-lamp\s*">empty</span>', grid)) == 5
    assert 'sb-lamp sb-lamp--on">set</span>' in _head(html, "activity") and grid.count("sb-lamp--on") == 1
    # Everything not on the date sits behind the one plus, once.
    assert grid.count('id="add-to-date"') == 1 and "9 more you can add" not in grid
    assert "%d more you can add" % len(OPTIONAL) in grid
    assert _chips(html) == set(OPTIONAL)
    for _key, label, _icon, _owned in tour_os.OPTIONAL_SECTIONS:
        assert grid.count("</span> %s</button>" % label) == 1, label
        assert ('to-sec-title">%s</span>' % label) not in grid, "not on the date: no tile of its own"
    # The old second surfaces are gone.
    assert 'id="glance"' not in html and "Not on this date" not in html and "to-adds-label" not in html
    assert html.count('class="to-ready') == 1, "readiness reads once, in the strip"


def test_a_filled_section_stays_folded_and_its_head_says_so(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/notes" % (tid, sid), data={"notes": "Load in through the alley."})
    html = _page(client, tid, sid)
    assert _open_sections(html) == [], "holding something is not a reason to unfold"
    head = _head(html, "notes")
    assert 'sb-lamp sb-lamp--on">set</span>' in head
    assert "Load in through the alley." in head, "the head carries the section's own status line"
    assert len(re.findall(r'class="sb-lamp\s*">empty</span>', html.split('<div class="to-secs">')[1])) == 4


def test_a_deep_link_still_unfolds_its_section_across_the_row(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid, tab="deal")
    assert _open_sections(html) == ["deal"]
    assert re.search(r'<section class="to-sec is-target is-open" id="deal"', html), "open: it takes the row"
    assert "advance" in _open_sections(_page(client, tid, sid, tab="send"))


def test_an_added_section_becomes_a_tile_and_leaves_the_plus(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": "hotel", "action": "add"})
    html = _page(client, tid, sid, tab="hotel")          # where the add redirects
    assert "hotel" in _sections(html) and "hotel" not in _chips(html)
    assert "hotel" in _open_sections(html), "just added: it is the target, so it opens"
    assert "%d more you can add" % (len(OPTIONAL) - 1) in html
    html = _page(client, tid, sid)
    assert "hotel" in _sections(html) and "hotel" not in _open_sections(html), "next visit it is a folded tile"


def test_the_more_menu_is_four_named_groups(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = client.get("/tours/%s" % tid).get_data(as_text=True)
    import html as _html
    heads = [_html.unescape(h) for h in re.findall(r'<div class="to-more-head">([^<]+)</div>', html)]
    assert heads == ["Show day", "People", "Sell & tell", "Tools"]
    items = re.findall(r'<a class="to-more-item[^"]*" href="/tours/[0-9a-f]+/([a-z-]+)"', html)
    assert len(items) == len(tour_os.MORE_ORDER) and set(items) == set(tour_os.MORE_ORDER), "nothing lost, nothing doubled"
    assert items.index("my-day") < items.index("guests") < items.index("merch") < items.index("settings")
    bar = tour_os._tour_bar({"is_owner": True, "scopes": list(tour_os.ts.SCOPES)}, "home")
    assert [g["label"] for g in bar["more_groups"]] == ["Show day", "People", "Sell & tell", "Tools"]
    assert sum(len(g["items"]) for g in bar["more_groups"]) == len(bar["more"])


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-secs" in css and ".to-sec.is-open" in css and ".to-sec--add" in css and ".to-more-head" in css
    assert ".to-tile--add" not in css and ".to-tile-btn" not in css, "the second surface's styles went with it"
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 18
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 200
