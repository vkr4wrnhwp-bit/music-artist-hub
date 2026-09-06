"""TOUR, less to read.

The owner, 2026-09-06: "when you open the screen, it's a lot of text. We
need more meters and images and less verbiage, more options if they want
the options." So a date opens as a row of tiles - one per section with
its state, a + tile for what is not on the date yet - and every section
stays folded until it holds something or is asked for. The More menu is
the same nineteen pages read as four questions.
"""
import re

import pytest

import tour_os
from tests.test_tour_date_page import (_fresh, _page, _sections, _chips, flask_app,  # noqa: F401
                                       CORE, OPTIONAL)


def _tiles(html):
    return re.findall(r'<a class="to-tile" href="#([a-z]+)"', html)


def _add_tiles(html):
    return re.findall(r'class="to-tile to-tile--add">\s*<input type="hidden" name="key" value="([a-z]+)"', html)


def _open_sections(html):
    return re.findall(r'<section class="to-sec[^"]*" id="([a-z]+)" data-section="[a-z]+">\s*<details class="to-sec-d" open>', html)


def test_a_fresh_date_opens_as_tiles_with_everything_folded(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid)
    assert _tiles(html) == ["times", "advance", "venue", "deal", "notes"], "one tile per core section, page order"
    assert set(_add_tiles(html)) == set(OPTIONAL), "a + tile for every section not on the date"
    assert _open_sections(html) == [], "nothing unfolds until it holds something"
    assert _sections(html) == CORE and _chips(html) == set(OPTIONAL), "the sections and chips are still there"
    # The tile says the state in a word, not a score.
    glance = html.split('id="glance"')[1].split('<section class="to-sec')[0]
    assert len(re.findall(r'class="sb-lamp\s*">empty</span>', glance)) == 5 and "sb-lamp--on" not in glance
    assert "Not on this date" in html
    # The sentence that explained the chips is gone; the tiles say it.
    assert "Only what this date needs" not in html


def test_a_section_unfolds_once_it_holds_something(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/notes" % (tid, sid), data={"notes": "Load in through the alley."})
    html = _page(client, tid, sid)
    assert _open_sections(html) == ["notes"]
    glance = html.split('id="glance"')[1].split('<section class="to-sec')[0]
    assert 'sb-lamp sb-lamp--on">set</span>' in glance and glance.count(">empty<") == 4
    assert "Load in through the alley." in glance, "the tile carries the section's own status line"


def test_a_deep_link_still_unfolds_its_section(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    assert _open_sections(_page(client, tid, sid, tab="deal")) == ["deal"]
    assert "advance" in _open_sections(_page(client, tid, sid, tab="send"))


def test_an_added_section_gets_a_tile_and_stays_one_line(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": "hotel", "action": "add"})
    html = _page(client, tid, sid, tab="hotel")          # where the add redirects
    assert "hotel" in _tiles(html) and "hotel" not in _add_tiles(html)
    assert "hotel" in _open_sections(html), "just added: it is the target, so it opens"
    html = _page(client, tid, sid)
    assert "hotel" not in _open_sections(html), "next visit it is folded, one line, until it holds a hotel"


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
    assert ".to-glance" in css and ".to-tile--add" in css and ".to-more-head" in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 9
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 190
