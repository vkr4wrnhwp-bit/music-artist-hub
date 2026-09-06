"""Stage Control's dark rooms, held to the same bar as the ivory sheet.

The sheet had its accessibility pass; the desk, the bridge page and the
performer's phone did not, and two paper-ink leaks were found by eye -
typing in the desk's "Why not" box was invisible, and muted text on the
desk was 3.2:1. These hold what a screenshot cannot: every ink the rooms
use clears 4.5:1 on every dark surface, no paper-only selector is used in
a dark room, and every control a phone presses clears 44px.
"""
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(HERE, "static", "css", "stage-control.css")
TOKENS = os.path.join(HERE, "static", "css", "tailwind.css")
ROOMS = ("stage/desk.html", "stage/bridge.html", "stage/performer.html", "stage/_guest_shell.html")


def _tokens():
    css = io.open(TOKENS, encoding="utf-8").read()
    return dict(re.findall(r"--(sb-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", css))


def _lum(h):
    r, g, b = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


DARK_SURFACES = ("sb-ground", "sb-surface-1", "sb-surface-2")
# Every ink the dark rooms set on text.
ROOM_INKS = ("sb-ink", "sb-ink-2", "sb-ink-3", "sb-gold", "sb-gold-bright",
             "sb-good", "sb-warn", "sb-crit")


@pytest.mark.parametrize("ink", ROOM_INKS)
def test_every_room_ink_clears_aa_on_every_dark_surface(ink):
    t = _tokens()
    for surface in DARK_SURFACES:
        ratio = _contrast(t[ink], t[surface])
        assert ratio >= 4.5, "%s on %s is %.2f:1" % (ink, surface, ratio)


def test_paper_ink_would_not_have_cleared_the_dark_ground():
    """The reason the rule below exists: the number that was on the desk."""
    t = _tokens()
    assert _contrast(t["sb-paper-ink-3"], t["sb-ground"]) < 4.5


def test_muted_text_is_room_ink_by_default_and_paper_ink_only_on_the_sheet():
    css = io.open(SHEET, encoding="utf-8").read()
    assert re.search(r"^\.sc-muted \{ color: var\(--sb-ink-3\); \}", css, re.M)
    assert ".sc-sheet .sc-muted, .sc-card .sc-muted { color: var(--sb-paper-ink-3); }" in css


def test_inputs_in_a_dark_panel_take_the_rooms_ink():
    css = io.open(SHEET, encoding="utf-8").read()
    assert ".sb-panel .sc-in { color: var(--sb-ink);" in css


def _paper_only_selectors(css):
    """Class selectors whose text colour is a paper ink and that have no
    dark-room override. Using one in a dark room is the leak."""
    out = set()
    for block in re.finditer(r"^((?:\.[a-z0-9_-]+(?:[^{]*?))+)\{([^}]*)\}", css, re.M):
        selectors, body = block.group(1), block.group(2)
        if "color: var(--sb-paper-ink" in body and "background" not in body:
            for sel in selectors.split(","):
                sel = sel.strip()
                if re.fullmatch(r"\.sc-[a-z0-9-]+", sel):
                    out.add(sel[1:])
    # Overridden for the dark rooms, by scope.
    for name in re.findall(r"\.sb-panel \.(sc-[a-z0-9-]+)", css):
        out.discard(name)
    if re.search(r"^\.sc-muted \{ color: var\(--sb-ink-3\)", css, re.M):
        out.discard("sc-muted")
    return out


def test_no_paper_only_selector_is_used_in_a_dark_room():
    css = io.open(SHEET, encoding="utf-8").read()
    paper_only = _paper_only_selectors(css)
    assert paper_only, "the detector should find the sheet's own selectors"
    leaks = []
    for rel in ROOMS:
        html = io.open(os.path.join(HERE, "templates", rel), encoding="utf-8").read()
        used = set(re.findall(r"\b(sc-[a-z0-9-]+)\b", html))
        for name in sorted(used & paper_only):
            leaks.append("%s uses .%s" % (rel, name))
    assert leaks == [], leaks


def test_every_control_a_phone_presses_clears_44px():
    css = io.open(SHEET, encoding="utf-8").read()
    coarse = css[css.index("@media (pointer: coarse)"):]
    coarse = coarse[:coarse.index("}\n\n") + 1] if "}\n\n" in coarse else coarse[:400]
    for sel in (".sc-act", ".sc-in", ".sc-btn"):
        assert sel in coarse, sel
    for sel, floor in ((".sc-step {", 64), (".sc-report {", 56)):
        block = css[css.index(sel):]
        block = block[:block.index("}")]
        assert "min-height: %dpx" % floor in block, sel


def test_focus_is_visible_on_every_room_control():
    css = io.open(SHEET, encoding="utf-8").read()
    for sel in (".sc-act:focus-visible", ".sc-step:focus-visible", ".sc-report:focus-visible"):
        i = css.index(sel)
        assert "box-shadow: var(--sb-focus)" in css[i:i + 120], sel


def test_the_guest_shell_is_a_page_on_its_own():
    s = io.open(os.path.join(HERE, "templates", "stage", "_guest_shell.html"), encoding="utf-8").read()
    assert '<html lang="en">' in s and 'name="viewport"' in s
    assert '<main id="main"' in s
    assert "_fonts.html" in s and "app-chrome.css" in s
    assert "noindex" in s
