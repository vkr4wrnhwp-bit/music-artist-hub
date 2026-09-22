"""The Release-Ready preview unit: a photographed faceplate, lit by code.

Every position in rr-unit.css was measured off the photograph with PIL and
written down as a fraction of it. Nothing about that is self-evident from
reading the CSS, and a value nudged by a few tenths puts a lit segment on
the metal between two lenses instead of on a lens - which looks like a bug
in the photograph rather than in a stylesheet. So the measurements are
asserted here, against the same numbers the crop was taken with.

The other thing held here is that the photograph is a skin and never the
only way to use the player: the <audio> element keeps its id and its ARIA
label, it is what actually plays, and in a column too narrow for it the
plain controls are what a reader gets.
"""
import io
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The crop these fractions came from: shot 8, faceplate x 6..1663, y 271..629.
PLATE_W, PLATE_H = 1658, 359


def _read(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def css():
    return _read("static/css/rr-unit.css")


def _render(**over):
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")))
    p = {
        "id": "job123",
        "preview": {"url": "/f/p.mp3", "starts_at": "1:12", "measured": "-9.4 LUFS"},
        "status": "preview_ready",
        "settings": {"loudness_label": "Loudness setting: Medium"},
        "master": None,
    }
    p.update(over)
    return env.get_template("_rr_unit.html").render(p=p, n=2)


# --- the photograph and what is laid over it --------------------------------

def test_every_plate_the_css_asks_for_is_actually_there(css):
    wanted = set(re.findall(r'url\("(/static/[^"]+)"\)', css))
    assert wanted, "the faceplate is the whole point of this stylesheet"
    for rel in wanted:
        path = os.path.join(HERE, rel.lstrip("/").replace("/", os.sep))
        assert os.path.exists(path), rel
        assert os.path.getsize(path) > 2000, "%s looks empty" % rel
    assert os.path.exists(os.path.join(HERE, "static", "img", "rr-knob.png"))


def test_the_unit_keeps_the_photographs_own_proportions(css):
    got = re.search(r"aspect-ratio:\s*(\d+)\s*/\s*(\d+)", css)
    assert got, "without this the plate stretches and every fraction lies"
    assert (int(got.group(1)), int(got.group(2))) == (PLATE_W, PLATE_H)


@pytest.mark.parametrize("what, rule, prop, measured", [
    # Each of these is <pixels in the crop> / <crop width or height>.
    ("display window left",  r"\.rr-unit-screen\b[^}]*", "left",   82 / PLATE_W),
    ("display window top",   r"\.rr-unit-screen\b[^}]*", "top",    94 / PLATE_H),
    ("display window width", r"\.rr-unit-screen\b[^}]*", "width",  (863 - 82) / PLATE_W),
    ("display window height", r"\.rr-unit-screen\b[^}]*", "height", (269 - 94) / PLATE_H),
    ("upper strip top",      r"\.rr-unit-meter--l\b[^}]*", "top",  100 / PLATE_H),
    ("lower strip top",      r"\.rr-unit-meter--r\b[^}]*", "top",  204 / PLATE_H),
])
def test_each_part_sits_where_it_was_measured(css, what, rule, prop, measured):
    block = re.search(rule + r"\{([^}]*)\}", css)
    assert block, what
    got = re.search(prop + r":\s*([\d.]+)%", block.group(1))
    assert got, "%s has no %s" % (what, prop)
    assert abs(float(got.group(1)) - measured * 100) < 0.06, (
        "%s is at %s%%, the photograph puts it at %.4f%%"
        % (what, got.group(1), measured * 100))


def test_the_meter_lenses_land_on_lenses(css):
    """Eleven lenses per strip, first left edge at 928.3px, pitch 28.67px,
    each 21px wide, all of the 1658px crop. Half a percent of drift puts a
    lit segment on the rib beside the lens."""
    strip = re.search(r"\.rr-unit-meter\s*\{([^}]*)\}", css)
    assert strip
    left = re.search(r"left:\s*([\d.]+)%", strip.group(1))
    assert abs(float(left.group(1)) - 928.3 / PLATE_W * 100) < 0.06

    cell = re.search(r"\.rr-unit-meter i\s*\{([^}]*)\}", css)
    width = re.search(r"width:\s*([\d.]+)cqw", cell.group(1))
    assert abs(float(width.group(1)) - 21 / PLATE_W * 100) < 0.02

    # The template places each lens; the pitch lives there.
    out = _render()
    lefts = [float(v) for v in re.findall(r'<i style="left: ([\d.]+)cqw"', out)]
    assert len(lefts) == 22, "eleven lenses on each of two strips"
    one = lefts[:11]
    assert one[0] == 0
    for i in range(1, 11):
        assert abs((one[i] - one[i - 1]) - 28.67 / PLATE_W * 100) < 0.01


def test_cqw_is_measured_against_the_faceplate_not_the_column(css):
    """The inner parts are in cqw, so the faceplate itself has to be the
    container. It was the wrapper once, and every segment came out about
    10% too wide and walked off the right-hand end of its strip."""
    blocks = re.findall(r"\n\.rr-unit\s*\{([^}]*)\}", css)
    assert blocks, "no .rr-unit rule at all"
    assert any("container-type: inline-size" in b for b in blocks), (
        "cqw resolves against the nearest container ancestor, so without "
        "this every inner measurement means 1% of the column instead")


# --- the skin is a skin -----------------------------------------------------

def test_the_plain_player_is_what_a_narrow_column_gets(css):
    assert re.search(r"\.rr-unit\s*\{\s*display:\s*none", css), (
        "the photograph has to be off by default and switched on by the "
        "container query, so a column that never matches still has a player")
    query = re.search(r"@container\s*\(min-width:\s*(\d+)px\)\s*\{([^}]*\}[^}]*)\}", css)
    # Measured against the column the unit sits in - a preview card - not
    # the window. At 900 it never appeared at all: two-across preview
    # cards are about 500px even on a wide screen.
    assert query and int(query.group(1)) == 700
    assert ".rr-unit { display: block" in query.group(2)
    assert ".rr-unit-plain { display: none" in query.group(2)


def test_the_unit_can_actually_appear_where_it_lives():
    """The one that was missed, and shipped.

    The unit was tested on its own, where it had a whole page to sit in, and
    pushed to staging with a 900px threshold. On the real page previews sat
    two across, so each card was about 500px even on a 1440px screen, and
    the faceplate could not appear anywhere at any window size: the page
    carried the photograph and showed the plain audio bar.

    So the threshold is not a free number. It has to be reachable inside a
    preview card, and that depends on how the previews are laid out - which
    is in a different stylesheet, which is exactly why nothing caught it."""
    rr = _read("static/css/release_ready.css")
    grid = re.search(r"\.rr-prevs\s*\{([^}]*)\}", rr)
    assert grid, "no previews grid"
    cols = re.search(r"grid-template-columns:\s*([^;]+)", grid.group(1))
    assert cols, "the previews grid sets no columns"
    assert "repeat(" not in cols.group(1), (
        "previews are back to more than one column; a card is then about "
        "500px and the faceplate cannot show at any window size")

    query = re.search(r"@container\s*\(min-width:\s*(\d+)px\)",
                      _read("static/css/rr-unit.css"))
    # A single-column card inside the previews section is roughly the page
    # column less its padding. 700 clears that on a normal desktop; 900 did
    # not clear it even at 1440.
    assert query and int(query.group(1)) <= 760, (
        "the threshold has to be reachable inside a preview card, not just "
        "in a test page of its own")


def test_the_audio_element_is_the_player_and_keeps_its_name():
    out = _render()
    assert 'id="rr-audio-job123"' in out
    assert 'data-rr-audio="rr-audio-job123"' in out, "the script finds it by id"
    assert 'aria-label="Preview 2, Loudness setting: Medium"' in out
    assert 'src="/f/p.mp3"' in out
    assert "<audio" in out and "controls" in out


def test_the_knob_is_a_real_control_underneath():
    out = _render()
    assert 'type="range"' in out and 'min="0"' in out and 'max="100"' in out
    assert 'aria-label="Output level for preview 2"' in out
    assert 'alt=""' in out, "the knob photograph is decoration; the input is the control"


def test_the_window_is_a_button_so_the_keyboard_reaches_it():
    out = _render()
    assert '<button type="button" class="rr-unit-screen"' in out
    assert 'aria-label="Play preview 2' in out
    assert '<canvas aria-hidden="true">' in out


# --- the states -------------------------------------------------------------

def test_a_preview_still_being_made_gets_the_same_unit_unlit():
    """This is the loading state, and it is why the plate was photographed
    with every lamp off: there is no second graphic to keep in step."""
    out = _render(preview=None, status="processing")
    assert 'data-state="working"' in out
    assert "rr-unit-lamp" in out
    assert 'aria-label="Preview 2 is being made"' in out
    assert "<audio" in out, "still present, just with nothing to play yet"
    assert "src=" not in out.split("<audio")[1].split(">")[0]


@pytest.mark.parametrize("status", ["failed", "credits_short", "needs_owner"])
def test_a_preview_that_did_not_arrive_reads_as_failed(status):
    out = _render(preview=None, status=status)
    assert 'data-state="failed"' in out
    assert "didn't finish" in out


def test_a_preview_that_arrived_reads_as_ready():
    assert 'data-state="ready"' in _render()


def test_the_lamp_says_something_different_in_each_state(css):
    for state in ("working", "ready", "failed"):
        assert re.search(r'\.rr-unit\[data-state="%s"\]\s+\.rr-unit-lamp' % state,
                         css), state
    assert "@keyframes rr-unit-breathe" in css


def test_motion_can_be_turned_off(css):
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*)\}",
                      css, re.S)
    assert block and "animation: none" in block.group(1)
    # The sweep in the display window is drawn, not animated by CSS, so the
    # script has to check for itself.
    js = _read("static/js/rr-unit.js")
    assert "prefers-reduced-motion" in js


def test_the_script_holds_no_brand_colour_of_its_own():
    """A copy of a token's value here is a second source of truth for it.
    tests/test_design_system.py refuses raw hex in this file; this says why
    so the next person does not simply add it to the exemption list."""
    js = _read("static/js/rr-unit.js")
    assert not re.findall(r"#[0-9a-fA-F]{6}\b", js)
    assert "--wave" in js, "read from the stylesheet, where the tokens are"
    assert "--wave: var(--sb-gold-bright)" in _read("static/css/rr-unit.css")
