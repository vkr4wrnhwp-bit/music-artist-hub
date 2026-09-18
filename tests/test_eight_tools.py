"""Section 4 — one system, eight tools.

Replaces the six-departments section on 2026-09-17 (owner: "yes swap it").
The six described the product before the suites existed; four of them are
things Street Banker itself does, so they stopped being departments rather
than going away. Everything else on the site says eight, and a visitor who
reads six and then counts eight has been handed a puzzle.

The rules that guarded the old section guard this one, because they were
never about departments:

  one photograph, one description   the rack is a single <img> with a single
                                    alt, not eight files and eight repeats
  three formats                     avif, webp and jpg, at the site's widths
  no stranger meets a login         and here, more strictly: nothing in the
                                    section is a link at all
  the decoration is hidden          lamps, windows and marks are
                                    aria-hidden; the names are not
  the homepage never changes        the power-on runs once and then stops
  around the reader

The departments partial, its stylesheet and its script stay in the
repository, so putting the old section back is one line in landing.html.
"""
import io
import os
import re

import pytest

import app as appmod
import eight_tools_config as cfg

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def body():
    return appmod.app.test_client().get("/").get_data(as_text=True)


@pytest.fixture(scope="module")
def section(body):
    return body.split('id="eight-tools"')[1].split("</section>")[0]


def test_it_sits_where_the_old_section_sat(body):
    assert body.index('id="artist-eq"') < body.index('id="eight-tools"')
    assert body.index('id="eight-tools"') < body.index('id="artist-twin-section"')
    assert 'id="departments"' not in body, "the old section is not rendered as well"


def test_the_copy_is_the_owners_words(section):
    assert "One system." in section and "Eight tools." in section
    assert "Everything behind the artist, working together." in section
    assert "Six departments" not in section


def test_all_eight_are_there_in_the_owners_order(section):
    names = re.findall(r'data-name="([^"]+)"', section)
    assert names == ["The Room", "Noise Lab", "REACH", "Royalty Sweep",
                     "Tour", "Company", "Artifacts", "Motion"]
    marks = re.findall(r'>([A-Z]{2})</text>', section)
    assert marks == ["TR", "NL", "RE", "RS", "TO", "CO", "AR", "MO"]


def test_each_one_says_what_it_is_and_what_opens_it(section):
    for tool in cfg.get_eight_tools_config()["tools"]:
        assert 'data-desc="%s"' % tool["desc"] in section, tool["name"]
        assert 'data-opens="%s"' % tool["opens"] in section, tool["name"]
    # Company and Artifacts are marked, not quietly sold.
    assert section.count('data-opens="Soon"') == 2


def test_it_is_one_photograph_and_one_description(section):
    """Two halves of four, so the photograph is drawn twice, but it is one
    file and it is described once. A screen reader must hear about the rack
    once, not once per half."""
    srcs = set(re.findall(r'<img src="([^"]+)"', section))
    assert len(srcs) == 1, ("eight faceplates, one file", srcs)
    alts = re.findall(r'alt="([^"]*)"', section)
    assert alts == ["", ""], "both copies are decorative"
    assert 'role="group" aria-label="%s"' % cfg.IMAGE["alt"] in section


def test_a_phone_never_scrolls_the_rack_sideways(section):
    """Owner, 2026-09-18: "we don't want to have to scroll left and right
    that's stupid". The rack is two halves that stack, and nothing in the
    stylesheet may give it a floor wider than a phone."""
    assert section.count('class="sbet-half ') == 2
    css = open(os.path.join(HERE, "static", "css", "eight-tools.css"), encoding="utf-8").read()
    assert "overflow-x" not in css, "a sideways scroller came back"
    assert not re.search(r"min-width:\s*\d{3,}px", css.split("@media")[0]), (
        "a fixed minimum width outside a media query forces a scroll")
    # Names under each half on phones, four each, in plate order.
    rows = re.findall(r'<ol class="sbet-names"[^>]*>(.*?)</ol>', section, re.S)
    got = [re.findall(r">([^<]+)</li>", r) for r in rows]
    assert got == [["The Room", "Noise Lab", "REACH", "Royalty Sweep"],
                   ["Tour", "Company", "Artifacts", "Motion"]]


def test_the_power_on_can_be_played_again(section):
    """In the owner's artifact and missing from the live page. Hidden until
    the script runs, since without it there is nothing to replay."""
    assert 'id="sbet-replay" hidden>Play the power-on again</button>' in section


def test_the_picture_ships_in_three_formats_at_the_sites_widths(section):
    for fmt in ("avif", "webp", "jpg"):
        for width in cfg.IMAGE["widths"]:
            assert "eight-tools-%d.%s" % (width, fmt) in section, (width, fmt)
    for fmt, width in [(f, w) for f in ("avif", "webp", "jpg") for w in cfg.IMAGE["widths"]]:
        path = os.path.join(HERE, "static", "img", "eight-tools-%d.%s" % (width, fmt))
        assert os.path.exists(path), path


def test_nothing_in_the_section_hands_a_stranger_a_login(section):
    """Stricter than the rule it inherits: there are no links on the plates
    at all. Seven of the eight suites have no public page, so pointing at a
    tool writes a sentence rather than opening a door."""
    hrefs = re.findall(r'<a [^>]*href="([^"]+)"', section)
    assert hrefs == [cfg.CTA["href"]], hrefs
    assert "/suites/go/" not in section
    r = appmod.app.test_client().get(cfg.CTA["href"])
    assert r.status_code == 200, cfg.CTA["href"]
    assert "/login" not in r.headers.get("Location", "")


def test_the_decoration_is_hidden_and_the_names_are_not(section):
    assert section.count('class="sbet-lamp" aria-hidden="true"') == 8
    assert section.count('class="sbet-win" aria-hidden="true"') == 8
    for tool in cfg.get_eight_tools_config()["tools"]:
        assert ">%s</span>" % tool["name"] in section, tool["name"]


def test_the_plates_land_on_the_photograph_and_the_last_one_fits():
    p = cfg.PLATE
    right = p["first_left"] + 7 * p["step"] + p["width"]
    assert 90 < right < 99, right
    assert p["top"] + p["height"] <= 100


def test_the_power_on_runs_once_and_then_the_page_is_still():
    js = io.open(os.path.join(HERE, "static", "js", "eight-tools.js"), encoding="utf-8").read()
    assert "watcher.disconnect()" in js, "the observer stops after the first run"
    assert "setInterval" not in js and "requestAnimationFrame" not in js
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in js


def test_a_reader_who_asked_for_less_motion_gets_it_lit_from_the_start():
    css = io.open(os.path.join(HERE, "static", "css", "eight-tools.css"), encoding="utf-8").read()
    block = css.split("@media (prefers-reduced-motion: reduce)")[1]
    assert "opacity: 1" in block, "lit, not dark and waiting"


def test_the_assets_are_linked_and_the_old_section_is_only_unlinked():
    landing = io.open(os.path.join(HERE, "templates", "landing.html"), encoding="utf-8").read()
    assert "eight-tools.css?v=" in landing and "eight-tools.js?v=" in landing
    assert 'partials/eight_tools.html' in landing
    assert 'partials/departments.html' not in landing
    # Kept, so the old section is one line away if the new one performs worse.
    for kept in ("templates/partials/departments.html", "static/css/departments.css",
                 "static/js/departments.js"):
        assert os.path.exists(os.path.join(HERE, kept)), kept
