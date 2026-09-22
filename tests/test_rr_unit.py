"""The Release-Ready unit: one photographed rack unit, lit by code.

The owner's brief was "buttons on it, upload on this, like an interface.
Not a separate face for all three or whatever" - so there is ONE unit for
an upload, carrying its three takes, not one faceplate per preview.

Every position in rr-unit.css was measured off the photograph with PIL and
written down as a fraction of it. None of that is self-evident from reading
the CSS, and a value nudged by a few tenths puts a lit segment on the metal
between two lenses instead of on a lens - which looks like a fault in the
photograph rather than in a stylesheet. So the measurements are asserted
here against the same numbers the crop was taken with.

The other things held here: the photograph is a skin and never the only way
to use the page, and the load slot does not upload by itself.
"""
import io
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The crop the fractions came from: the black plate, x 7..1664, y 193..701.
PLATE_W, PLATE_H = 1658, 509
LENSES = 13


def _read(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def css():
    return _read("static/css/rr-unit.css")


def _take(i, loudness, has_preview=True, status="preview_ready", chip="Preview ready"):
    return {
        "id": "job%d" % i,
        "settings": {"loudness_label": "Loudness setting: " + loudness},
        "preview": {"url": "/f/p%d.mp3" % i} if has_preview else None,
        "status": status,
        "chip": chip,
        "in_flight": status in ("queued", "processing"),
        "message": "",
        "master": None,
    }


def _render(previews=None, can_load=False, upload_url="", title="Cell 5"):
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")))
    source = {"id": "src9", "title": title}
    if previews is None:
        previews = [_take(1, "Medium"), _take(2, "Low"), _take(3, "High")]
    return env.get_template("_rr_unit.html").render(
        source=source, previews=previews, can_load=can_load, upload_url=upload_url)


def _rules(css):
    """(selector, body) for every rule, comments stripped."""
    clean = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean)]


def _prop(css, selector, prop):
    """The value of `prop` in the rule for exactly `selector`. A selector
    can appear in several rules (a base rule, then ::after, then a state),
    so the lookup is by the property being asked for, not by whichever
    rule happens to come first."""
    for sel, body in _rules(css):
        if selector in [x.strip() for x in sel.split(",")]:
            got = re.search(prop + r"\s*:\s*([\d.]+)%", body)
            if got:
                return float(got.group(1))
    return None


# --- the photograph and what is laid over it --------------------------------

def test_every_plate_the_css_asks_for_is_actually_there(css):
    wanted = set(re.findall(r'url\("(/static/[^"]+)"\)', css))
    assert wanted, "the faceplate is the whole point of this stylesheet"
    for rel in wanted:
        path = os.path.join(HERE, rel.lstrip("/").replace("/", os.sep))
        assert os.path.exists(path), rel
        assert os.path.getsize(path) > 2000, "%s looks empty" % rel
    assert os.path.exists(os.path.join(HERE, "static", "img", "rr2-knob.png"))


def test_the_unit_keeps_the_photographs_own_proportions(css):
    got = re.search(r"aspect-ratio:\s*(\d+)\s*/\s*(\d+)", css)
    assert got, "without this the plate stretches and every fraction lies"
    assert (int(got.group(1)), int(got.group(2))) == (PLATE_W, PLATE_H)


@pytest.mark.parametrize("what, selector, prop, measured", [
    # Each is <pixels in the 1658x509 crop> / <crop width or height>.
    ("load slot left",   ".rr-unit-slot",   "left",   0.0446),
    ("load slot top",    ".rr-unit-slot",   "top",    0.2043),
    ("load slot width",  ".rr-unit-slot",   "width",  0.3324),
    ("load slot height", ".rr-unit-slot",   "height", 0.1395),
    ("display left",     ".rr-unit-screen", "left",   0.4041),
    ("display top",      ".rr-unit-screen", "top",    0.1532),
    ("display width",    ".rr-unit-screen", "width",  0.5495),
    ("display height",   ".rr-unit-screen", "height", 0.2574),
    ("transport left",   ".rr-unit-go",     "left",   0.2786),
    ("transport top",    ".rr-unit-go",     "top",    0.5894),
    ("transport width",  ".rr-unit-go",     "width",  0.0875),
    ("transport height", ".rr-unit-go",     "height", 0.2770),
])
def test_each_part_sits_where_it_was_measured(css, what, selector, prop, measured):
    got = _prop(css, selector, prop)
    assert got is not None, "%s has no %s" % (what, prop)
    assert abs(got - measured * 100) < 0.06, (
        "%s is at %s%%, the photograph puts it at %.4f%%"
        % (what, got, measured * 100))


def test_the_three_take_buttons_sit_on_the_three_photographed_buttons(css):
    tops = {}
    for i, left in enumerate((4.83, 12.06, 19.30)):
        rule = re.search(r'\.rr-unit-take\[data-i="%d"\]\s*\{([^}]*)\}' % i, css)
        assert rule, "no rule for take %d" % i
        got = re.search(r"left:\s*([\d.]+)%", rule.group(1))
        assert got and abs(float(got.group(1)) - left) < 0.06, (
            "take %d is at %s%%, the photograph puts it at %.2f%%"
            % (i, got and got.group(1), left))
    base = re.search(r"\.rr-unit-take\s*\{([^}]*)\}", css)
    assert base
    tops["top"] = re.search(r"top:\s*([\d.]+)%", base.group(1))
    assert tops["top"] and abs(float(tops["top"].group(1)) - 64.05) < 0.06


def test_the_meter_lenses_land_on_lenses(css):
    """Thirteen lenses a strip on THIS plate, first left 41.86%, pitch
    1.9348%, width 1.5681%. The silver generation of the same design came
    back with fourteen - two generations are not the same photograph, so
    the count belongs to the plate that actually shipped."""
    cell = re.search(r"\.rr-unit-meter i\s*\{([^}]*)\}", css)
    assert cell
    width = re.search(r"width:\s*([\d.]+)%", cell.group(1))
    assert width and abs(float(width.group(1)) - 1.5681) < 0.02

    for strip, top, height in (("l", 61.10, 6.48), ("r", 77.41, 6.88)):
        rule = re.search(r"\.rr-unit-meter--%s i\s*\{([^}]*)\}" % strip, css)
        assert rule, strip
        t = re.search(r"top:\s*([\d.]+)%", rule.group(1))
        h = re.search(r"height:\s*([\d.]+)%", rule.group(1))
        assert t and abs(float(t.group(1)) - top) < 0.06, strip
        assert h and abs(float(h.group(1)) - height) < 0.06, strip

    out = _render()
    lefts = [float(v) for v in re.findall(r'<i style="left: ([\d.]+)%"', out)]
    assert len(lefts) == LENSES * 2, "thirteen lenses on each of two strips"
    one = lefts[:LENSES]
    assert abs(one[0] - 41.86) < 0.01
    for i in range(1, LENSES):
        assert abs((one[i] - one[i - 1]) - 1.9348) < 0.01


def test_a_height_in_cqh_would_silently_collapse(css):
    """The unit is an inline-size container, so cqw resolves against it and
    cqh does not. A lens height in cqh comes out as nothing at all, and the
    meters simply never appear - which is not an obvious failure to look at."""
    assert "cqh" not in re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks = re.findall(r"\n\.rr-unit\s*\{([^}]*)\}", css)
    assert any("container-type: inline-size" in b for b in blocks), (
        "without this, cqw means 1% of the column instead of the faceplate")


# --- one unit, not one per preview ------------------------------------------

def test_there_is_one_unit_for_the_upload_not_one_per_take():
    out = _render()
    assert len(re.findall(r'data-rr-unit(?![\w-])', out)) == 1
    assert out.count("rr-unit-take") >= 3, "the three takes are buttons ON it"
    assert out.count("<canvas") == 1
    assert out.count("<audio") == 1


def test_a_take_button_says_whether_that_take_exists():
    out = _render([_take(1, "Medium"), _take(2, "Low", has_preview=False,
                                             status="processing", chip="Making previews")])
    assert 'data-has="1"' in out
    assert 'data-has="0"' in out
    # The third was never asked for at all, and is still drawn, dark.
    assert out.count("rr-unit-take") >= 3
    assert "Take 3, not made" in out
    assert "Take 2, Loudness setting: Low - making previews" in out


def test_the_takes_carry_the_source_the_script_switches_between():
    out = _render()
    assert 'data-src="/f/p1.mp3"' in out
    assert 'data-src="/f/p2.mp3"' in out
    assert 'data-src="/f/p3.mp3"' in out
    assert 'aria-pressed="false"' in out, "the script decides which is lit"


# --- the slot does not upload by itself -------------------------------------

def test_the_load_slot_hands_the_file_to_the_form_and_does_not_upload():
    """Uploading needs the rights and licence boxes ticked. A slot that
    quietly skipped them would be the one dishonest thing on the faceplate,
    so the script hands the file to the page's own form instead."""
    js = _read("static/js/rr-unit.js")
    assert "formInput" in js and "scrollIntoView" in js
    assert 'input[type="checkbox"]' in js, "it takes you to the boxes"
    assert not re.search(r"fetch\([^)]*upload", js), "it never posts the file itself"
    assert "DataTransfer" in js, "the file lands on the real input"


def test_a_page_that_cannot_load_does_not_offer_the_slot():
    out = _render(can_load=False)
    assert "disabled" in out.split("rr-unit-slot")[1][:200]
    assert "Loading is closed" in out
    lit = _render(can_load=True)
    assert "drop a file here" in lit


# --- the skin is a skin -----------------------------------------------------

def test_the_plain_player_is_what_a_narrow_column_gets(css):
    assert re.search(r"\.rr-unit\s*\{\s*display:\s*none", css), (
        "the photograph has to be off by default and switched on by the "
        "container query, so a column that never matches still has a player")
    query = re.search(r"@container\s*\(min-width:\s*(\d+)px\)\s*\{([^}]*\}[^}]*)\}", css)
    assert query and int(query.group(1)) == 520
    assert ".rr-unit { display: block" in query.group(2)
    assert ".rr-unit-plain { display: none" in query.group(2)


def test_the_unit_can_actually_appear_where_it_lives():
    """The one that was missed, and shipped. The unit was tested on a page
    of its own, where it had all the room it wanted, and pushed with a 900px
    threshold. On the real page previews sat two across, so each card was
    about 560px even on a 1536px screen, and the faceplate could not appear
    at any window size. The threshold is not a free number."""
    rr = _read("static/css/release_ready.css")
    grid = re.search(r"\.rr-prevs\s*\{([^}]*)\}", rr)
    assert grid, "no previews grid"
    cols = re.search(r"grid-template-columns:\s*([^;]+)", grid.group(1))
    assert cols and "repeat(" not in cols.group(1), (
        "previews are back to more than one column; a card is then about "
        "560px and the faceplate cannot show at any window size")
    query = re.search(r"@container\s*\(min-width:\s*(\d+)px\)", _read("static/css/rr-unit.css"))
    assert query and int(query.group(1)) <= 760


def test_the_audio_element_is_the_player_and_keeps_its_name():
    out = _render()
    assert 'id="rr-audio-src9"' in out
    assert 'data-rr-audio="rr-audio-src9"' in out, "the script finds it by id"
    assert 'aria-label="Preview of Cell 5"' in out
    assert "<audio" in out and "controls" in out


def test_the_knob_is_a_real_control_underneath():
    out = _render()
    assert 'type="range"' in out and 'min="0"' in out and 'max="100"' in out
    assert 'aria-label="Output level"' in out
    assert 'alt=""' in out, "the knob photograph is decoration; the input is the control"


# --- the states -------------------------------------------------------------

def test_takes_still_being_made_leave_the_unit_unlit():
    """This is the loading state, and it is why the plate was photographed
    with every lamp off: there is no second graphic to keep in step."""
    out = _render([_take(1, "Medium", has_preview=False, status="processing",
                         chip="Making previews")])
    assert 'data-state="working"' in out
    assert "RoEx is making the previews" in out


def test_one_take_arriving_is_enough_to_read_as_ready():
    out = _render([_take(1, "Medium"),
                   _take(2, "Low", has_preview=False, status="processing",
                         chip="Making previews")])
    assert 'data-state="ready"' in out


def test_takes_that_all_failed_read_as_failed():
    out = _render([_take(1, "Medium", has_preview=False, status="failed",
                         chip="Needs a retry")])
    assert 'data-state="failed"' in out


def test_an_upload_with_no_takes_yet_is_idle_not_broken():
    out = _render([])
    assert 'data-state="idle"' in out
    assert "Nothing to play yet" in out
    assert out.count("rr-unit-take") >= 3, "the buttons are still there, dark"


def test_the_lamp_says_something_different_in_each_state(css):
    for state in ("working", "ready", "failed"):
        assert re.search(r'\.rr-unit\[data-state="%s"\]\s+\.rr-unit-lamp' % state,
                         css), state
    assert "@keyframes rr-unit-breathe" in css


def test_motion_can_be_turned_off(css):
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*)\}", css, re.S)
    assert block and "animation: none" in block.group(1)
    assert "prefers-reduced-motion" in _read("static/js/rr-unit.js")


def test_the_script_holds_no_brand_colour_of_its_own():
    """A copy of a token's value here is a second source of truth for it.
    tests/test_design_system.py refuses raw hex in this file; this says why,
    so the next person does not simply add it to the exemption list."""
    js = _read("static/js/rr-unit.js")
    assert not re.findall(r"#[0-9a-fA-F]{6}\b", js)
    assert "--wave" in js, "read from the stylesheet, where the tokens are"
    assert "--wave: var(--sb-gold-bright)" in _read("static/css/rr-unit.css")
