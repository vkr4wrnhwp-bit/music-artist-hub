"""The homepage must not scroll sideways on a phone.

Two sections used to. The Three Lanes rack rendered at 175vw inside an
`overflow-x: auto` rail, and Six Departments was a horizontal snap
scroller. Both were deliberate — the engraving on the rack and the labels
on the photograph stay legible at full size — and both were the wrong
trade: a horizontal scrollbar on a marketing homepage reads as a bug, and
five of six departments sat behind a gesture nobody is told about.

These tests are static analysis of the stylesheets, not a rendered
measurement. Nothing in this environment can render a page, so what is
checked is the *cause* — viewport-exceeding widths and overflow-x on
homepage sections — rather than the symptom. That is weaker than
measuring `document.documentElement.scrollWidth`, and it is what is
available.
"""
import glob
import os
import re

import pytest

# Stylesheets belonging to homepage sections. Interior app pages are out
# of scope: they are behind a login and have their own constraints.
HOMEPAGE_CSS = [
    "artist-eq.css", "closing.css", "creative-studio.css", "departments.css",
    "disclosure.css", "distribution.css", "hero.css", "lanes.css",
    "passport.css", "public-header.css", "release-signal.css", "rollout.css",
    "sweep.css", "artist-twin.css",
]

CSS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "static", "css")


def _read(name):
    path = os.path.join(CSS_DIR, name)
    if not os.path.exists(path):
        pytest.skip("%s is not in this build" % name)
    return open(path, encoding="utf-8").read()


def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


@pytest.mark.parametrize("name", HOMEPAGE_CSS)
def test_no_section_declares_a_width_past_the_viewport(name):
    """A width above 100vw is a horizontal scrollbar with extra steps."""
    css = _strip_comments(_read(name))
    offenders = []
    for match in re.finditer(r"(?:^|[;{]|\s)(?:min-)?width:\s*(\d+(?:\.\d+)?)vw", css):
        if float(match.group(1)) > 100:
            offenders.append(match.group(0).strip())
    assert not offenders, "%s sets a width wider than the viewport: %s" % (
        name, offenders)


@pytest.mark.parametrize("name", HOMEPAGE_CSS)
def test_no_homepage_section_scrolls_sideways(name):
    """`overflow-x: auto` / `scroll` on a homepage section.

    `overflow-x: hidden` is not accepted either: hiding the overflow
    without fixing what causes it means the content is still off-screen,
    just unreachable.
    """
    css = _strip_comments(_read(name))
    scrollers = re.findall(r"overflow-x:\s*(auto|scroll)", css)
    assert not scrollers, "%s scrolls horizontally: %s" % (name, scrollers)

    hides = re.findall(r"overflow-x:\s*hidden", css)
    assert not hides, (
        "%s hides horizontal overflow rather than removing its cause" % name)


@pytest.mark.parametrize("name", HOMEPAGE_CSS)
def test_no_horizontal_snap_scrollers(name):
    css = _strip_comments(_read(name))
    assert "scroll-snap-type: x" not in css, (
        "%s carries a horizontal snap scroller; the two that existed hid "
        "most of their content behind an unadvertised gesture" % name)


def test_every_homepage_stylesheet_is_covered():
    """A new section stylesheet must be added to HOMEPAGE_CSS.

    Otherwise the next horizontal scroller ships unnoticed because its
    file was simply not in the list.
    """
    known = set(HOMEPAGE_CSS) | {
        # Not homepage sections.
        "tailwind.css", "product-tour.css", "release-check.css",
        "login-session-recall.css", "photo-credit.css",
    }
    on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(CSS_DIR, "*.css"))}
    unlisted = on_disk - known
    assert not unlisted, (
        "these stylesheets are not covered by the overflow tests — add them "
        "to HOMEPAGE_CSS, or to the exclusion set if they are not homepage "
        "sections: %s" % sorted(unlisted))
