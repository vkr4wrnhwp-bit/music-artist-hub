"""The shared control set, and the rule that governs it.

An audit found 39 hardware-style components across eight stylesheets and none
in shared chrome: five progress-bar dialects, four lamp dialects, three
segmented controls, three faders. These macros are those components promoted
once.

The rule they exist to enforce: an instrument shows a REAL value. A meter fed
by a constant and a switch that switches nothing are the fabrication this
product refuses everywhere else, and putting them in shared chrome would only
make the lie reusable. So the refusal lives in the macro rather than in each
caller's good intentions.
"""
import io
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.path.join(HERE, "static", "css", "app-chrome.css")


@pytest.fixture(scope="module")
def sb():
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")))
    return env.get_template("_sb.html").module


def _flat(markup):
    return " ".join(str(markup).split())


# --- the honesty rule --------------------------------------------------------

def test_a_meter_with_no_value_says_so_instead_of_reading_zero(sb):
    """An empty ladder reads as zero, and "not measured" is not zero."""
    out = _flat(sb.meter("Stereo image", None))
    assert "sb-meter--none" in out
    assert "Not measured" in out
    assert "sb-meter-fill" not in out, "no fill element at all, not a 0% one"


def test_a_meter_with_a_value_draws_it(sb):
    out = _flat(sb.meter("Headroom", 8, 10, tone="good"))
    assert "--sb-meter-fill: 80%" in out
    assert "sb-meter--good" in out


def test_a_meter_never_overflows_its_ceiling(sb):
    """A value above the ceiling is a real thing (an over), but a bar past
    100% would draw outside the well."""
    assert "--sb-meter-fill: 100%" in _flat(sb.meter("Over", 30, 10))


def test_a_zero_ceiling_is_treated_as_unknown_not_a_division(sb):
    out = _flat(sb.meter("Lanes claimed", 0, 0))
    assert "sb-meter--none" in out


def test_the_absent_wording_can_say_why(sb):
    out = _flat(sb.meter("Loudness", None, absent="Needs stems"))
    assert "Needs stems" in out


def test_an_lcd_with_no_value_does_not_invent_one(sb):
    out = _flat(sb.lcd(None, "BPM"))
    assert "sb-lcd--none" in out and "—" in out


# --- accessibility of the set ------------------------------------------------

def test_a_lamp_always_carries_a_word(sb):
    """A coloured dot alone makes colour the only carrier of meaning."""
    out = _flat(sb.lamp("Connected", "on"))
    assert "Connected" in out
    assert "sb-lamp--on" in out


def test_a_meter_is_labelled_for_a_screen_reader(sb):
    out = _flat(sb.meter("Headroom", 8, 10, shown="-6.1 dBTP"))
    assert 'aria-label="Headroom: -6.1 dBTP"' in out
    known = _flat(sb.meter("Stereo image", None))
    assert 'aria-label="Stereo image: Not measured"' in known


def test_a_segmented_control_uses_real_radios(sb):
    """So keyboard and assistive tech work. The labels are only the caps."""
    out = _flat(sb.seg("mode", [("a", "Alpha"), ("b", "Beta")], current="b"))
    assert out.count('type="radio"') == 2
    assert 'role="radiogroup"' in out
    assert 'value="b" checked' in out


def test_a_switch_the_viewer_cannot_throw_looks_unavailable(sb):
    """A lane behind a server flag must not offer a control that silently
    ignores the click."""
    out = _flat(sb.switch("Voice vault", on=False, disabled=True,
                          title="Off on this deployment"))
    assert "disabled" in out
    assert "Off on this deployment" in out


def test_a_display_switch_reports_its_state(sb):
    assert 'aria-pressed="true"' in _flat(sb.switch("Armed", on=True))
    assert 'aria-pressed="false"' in _flat(sb.switch("Armed", on=False))


def test_a_fader_is_a_native_range(sb):
    out = _flat(sb.fader("L", "level", 62))
    assert 'type="range"' in out and 'aria-label="L"' in out


def test_the_stage_rail_marks_the_current_step(sb):
    out = _flat(sb.stages([("a", "Draft"), ("b", "Sent"), ("c", "Paid")],
                          current="b", done=["a"]))
    assert 'aria-current="step"' in out
    assert "sb-stages-i--now" in out and "sb-stages-i--done" in out


# --- the collision guard -----------------------------------------------------

def test_the_stage_rail_is_not_called_sb_rail():
    """tailwind.css already compiles .sb-rail for the vertical desk navigation,
    and app-chrome.css loads AFTER it - so naming the lifecycle rail .sb-rail
    silently took the desk nav's border-right off. It is .sb-stages."""
    css = io.open(CHROME, encoding="utf-8").read()
    assert not re.search(r"^\.sb-rail\s*\{", css, re.M), \
        "app-chrome.css must not redefine .sb-rail — the desk nav owns it"
    assert ".sb-stages {" in css


def test_every_instrument_is_in_the_sheet_that_loads_everywhere():
    """The whole point: these were 39 components in eight stylesheets. If they
    are not in the sheet base.html loads on every page, nothing changed."""
    css = io.open(CHROME, encoding="utf-8").read()
    for selector in (".sb-meter", ".sb-lcd", ".sb-lamp", ".sb-switch",
                     ".sb-seg", ".sb-fader", ".sb-stages"):
        assert selector + " {" in css or selector + "-" in css, selector

    base = io.open(os.path.join(HERE, "templates", "base.html"),
                   encoding="utf-8").read()
    assert "app-chrome.css" in base


def test_touch_targets_are_handled_for_coarse_pointers():
    """board.css, light-studio.css and rack.css all carry this; a shared set
    that skipped it would spread the omission everywhere at once."""
    css = io.open(CHROME, encoding="utf-8").read()
    coarse = css[css.index("pointer: coarse"):]
    assert "44px" in coarse[:300]
