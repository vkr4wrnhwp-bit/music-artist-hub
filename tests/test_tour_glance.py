"""TOUR, less to read.

The owner, 2026-09-06: "when you open the screen, it's a lot of text. We
need more meters and images and less verbiage, more options if they want
the options." Then, 2026-09-07: "the show page just needs everything that
was in the header as well as in the dropdown menu in the more section
added into the day of venue page, they need to be below the venue
information and populate only if the user clicks the plus sign next to
each additional feature you can add." And, the same day, by numbered
mockup: nothing is pre-added.

So below the event header there is one grid. A feature on the show is a
folded row whose head says what it holds (set or empty, never a score);
only the one the URL asked for opens. A feature not on the show is a +
row in the same place; click it and the row populates there. No bar, no
list, nothing twice, and no meter until something is on. The tour bar
carries only the run-wide pages, read as three questions: booking, close
out, tools.
"""
import re

import pytest

import tour_os
from tests.test_tour_date_page import (_fresh, _page, _sections, _chips, flask_app,  # noqa: F401
                                       CORE, OPTIONAL, FEATURES)


def _open_sections(html):
    return re.findall(r'<section class="to-sec[^"]*" id="([a-z]+)" data-section="[a-z]+">\s*<details class="to-sec-d" open>', html)


def _rows(html):
    """Every cell of the feature grid in order: a section key, or +key for a plus row."""
    lst = html.split('id="features"')[1].split("<script>")[0]
    return [(m.group(1) or ("+" + m.group(2))) for m in
            re.finditer(r'<section class="to-sec[^"]*" id="([a-z]+)"|<form method="post" action="[^"]+/sections" class="to-feature-add" data-chip="([a-z]+)"', lst)]


def _add(client, tid, sid, key):
    return client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": key, "action": "add"})


def test_a_fresh_show_is_one_grid_below_the_header_and_nothing_open(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid)
    rows = _rows(html)
    assert rows == ["+" + k for k in FEATURES], "a + row for every feature, in the fixed order, once, nothing pre-added"
    assert _sections(html) == [] and _open_sections(html) == []
    grid = html.split('id="features"')[1].split("<script>")[0]
    assert "sb-lamp" not in grid, "a + row is the disc, a + and the name - no lamp, no status"
    assert 'id="glance"' not in html and "to-secs" not in html and 'id="showbar"' not in html and 'id="add-to-date"' not in html
    assert html.count('class="to-ready') == 0 and 'id="readiness"' not in html, "nothing on, nothing measured"
    assert "Not on this date" not in html and "9 more you can add" not in html
    # The five core features, once added, are folded rows in their places whose heads say 'empty'.
    for key in CORE[:5]:
        assert _add(client, tid, sid, key).status_code == 302
    html = _page(client, tid, sid)
    rows = _rows(html)
    assert rows[:5] == CORE[:5] and rows[-1] == "+activity", "the core rows in place, Activity still a + row"
    assert [r[1:] for r in rows if r.startswith("+")] == OPTIONAL + ["activity"]
    assert _open_sections(html) == [], "nothing opens until the URL asks"
    heads = html.split('id="features"')[1].split("<script>")[0]
    assert len(re.findall(r'class="sb-lamp\s*">empty</span>', heads)) == 5 and "sb-lamp--on" not in heads
    assert html.count('class="to-ready') == 1, "readiness reads once, in the strip"


def test_a_plus_row_populates_the_section_and_leaves_the_grid(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    r = _add(client, tid, sid, "hotel")
    assert r.headers["Location"].endswith("?tab=hotel")
    html = _page(client, tid, sid, tab="hotel")
    assert "hotel" in _rows(html) and "+hotel" not in _rows(html) and _open_sections(html) == ["hotel"]
    assert 'name="property"' in html, "populated"
    html = _page(client, tid, sid)
    rows = _rows(html)
    assert rows.index("hotel") == FEATURES.index("hotel") and _open_sections(html) == [], \
        "next visit it is a folded row in the same place"


def test_a_filled_row_stays_folded_and_its_head_says_so(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/notes" % (tid, sid), data={"notes": "Load in through the alley."})
    html = _page(client, tid, sid)
    assert _open_sections(html) == []
    assert "notes" in _rows(html) and "+notes" not in _rows(html), "data puts a feature on the show"
    head = html.split('id="notes" data-section="notes"')[1].split("</summary>")[0]
    assert 'sb-lamp sb-lamp--on">set</span>' in head and "Load in through the alley." in head
    assert _open_sections(_page(client, tid, sid, tab="deal")) == ["deal"]
    assert re.search(r'<section class="to-sec is-target is-open" id="deal"', _page(client, tid, sid, tab="deal"))


def test_the_tour_more_menu_is_three_named_groups(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    import html as _html
    heads = [_html.unescape(h) for h in re.findall(r'<div class="to-more-head">([^<]+)</div>', html)]
    assert heads == ["Booking", "Close out", "Tools"]
    items = re.findall(r'<a class="to-more-item[^"]*" href="/tours/[0-9a-f]+/([a-z-]+)"', html)
    assert len(items) == len(tour_os.MORE_ORDER) and set(items) == set(tour_os.MORE_ORDER), "nothing lost, nothing doubled"
    assert items.index("calendar") < items.index("exports") < items.index("settings")
    for day_of in ("my-day", "schedule", "guests", "vip", "setlists", "merch", "content", "tasks"):
        assert day_of not in items, day_of
    bar = tour_os._tour_bar({"is_owner": True, "scopes": list(tour_os.ts.SCOPES)}, "home")
    assert [g["label"] for g in bar["more_groups"]] == ["Booking", "Close out", "Tools"]
    assert sum(len(g["items"]) for g in bar["more_groups"]) == len(bar["more"])


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-feature-grid" in css and ".to-feature-btn" in css and ".to-more-head" in css
    assert ".to-features {" not in css and ".to-secs" not in css and ".to-showbar" not in css and ".to-tile--add" not in css
    shell = open(os.path.join(here, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 25
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 211
