"""Text contrast.

REACH is a dark interface that states a great deal in small secondary text —
why a source is trusted, why a score is what it is, why something is not
automated. That copy is worth nothing if it cannot be read, and for most of this
project's life it could not be: the two tones carrying it measured 2.2-4.1
against the surfaces they sat on, below the WCAG AA floor of 4.5 for normal
text, on all fifteen screens.

These tests compute the requirement rather than blocklisting the old values, so
a new tone that happens to fail is caught the same way the old ones were.

The authority on the rendered result is ``tools/audit-contrast.py``, which walks
the running app in a browser and composites every real background. This is its
CI-runnable proxy: it measures each text colour used in a template against the
three flat surfaces REACH paints text on, which is the conservative case.
"""

import pathlib
import re

import pytest

# The surfaces REACH paints text on. #1a1a1c is a white/5 panel over #111113 —
# the lightest of the three and therefore the binding constraint for light text.
SURFACES = {"page": "#0a0a0a", "panel": "#111113", "raised": "#1a1a1c"}

AA_NORMAL = 4.5

ROOT = pathlib.Path(__file__).resolve().parent.parent
STYLESHEET = ROOT / "static" / "tailwind.css"
TEMPLATES = sorted((ROOT / "templates").rglob("*.html"))


def _luminance(rgb):
    def channel(value):
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(rgb, hex_ground):
    ground = tuple(int(hex_ground[i:i + 2], 16) for i in (1, 3, 5))
    a, b = _luminance(rgb), _luminance(ground)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def stylesheet_colours():
    """{class name: (r, g, b)} for every .text-* rule that sets a colour.

    Read from the build rather than a hardcoded table, so the test measures the
    colours the browser is actually given.
    """
    css = STYLESHEET.read_text()
    found = {}
    for name, body in re.findall(r"\.text-([a-z0-9-]+)(?:\\/\d+)?\s*\{([^}]*)\}", css):
        match = re.search(r"color:\s*rgba?\((\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)", body)
        if match:
            found.setdefault(name, tuple(int(g) for g in match.groups()))
    return found


def stylesheet_text_utilities():
    """Every .text-* class in the build, colour or not (text-sm, text-center…)."""
    return set(re.findall(r"\.text-([a-z0-9-]+)(?:\\/\d+)?\s*[,{]", STYLESHEET.read_text()))


def used_text_classes():
    """Every text-* class a template applies, with any /opacity suffix dropped."""
    used = set()
    for path in TEMPLATES:
        for match in re.findall(r"(?:^|[\s\"'])(?:[a-z-]+:)*text-([a-z0-9-]+)",
                                path.read_text()):
            used.add(match)
    return used


def test_the_stylesheet_was_built_and_carries_text_colours():
    assert STYLESHEET.exists(), "run tools/build-css.sh"
    assert stylesheet_colours(), "no .text-* colour rules in the build"


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_every_text_colour_used_clears_wcag_aa(surface):
    palette = stylesheet_colours()
    ground = SURFACES[surface]
    utilities = stylesheet_text_utilities()
    failures, unbuilt = [], []
    for name in sorted(used_text_classes()):
        rgb = palette.get(name)
        if rgb is None:
            # A size or alignment utility is fine. A class the build has never
            # heard of means a stale stylesheet or a typo — either way the
            # colour is unmeasured, and unmeasured must not read as passing.
            if name not in utilities:
                unbuilt.append(f"text-{name}")
            continue
        ratio = contrast(rgb, ground)
        if ratio < AA_NORMAL:
            failures.append(f"text-{name} = rgb{rgb} is {ratio:.2f}:1 on {ground}")
    assert not unbuilt, (
        "These text classes are used in a template but are not in the built "
        f"stylesheet, so their contrast is unmeasured: {', '.join(unbuilt)}. "
        "Run tools/build-css.sh.")
    assert not failures, (
        f"Text colours below WCAG AA ({AA_NORMAL}:1) on the {surface} surface:\n  "
        + "\n  ".join(failures))


def test_the_tertiary_tone_stays_dimmer_than_the_secondary_one():
    """The scale has to survive the fix.

    Raising everything until it passes would flatten three tiers into one, so
    `faint` is defined as the dimmest tone that still clears AA with margin —
    dimmer than gray-400, and readable.
    """
    palette = stylesheet_colours()
    faint, secondary = palette["faint"], palette["gray-400"]
    worst = SURFACES["raised"]
    assert contrast(faint, worst) >= AA_NORMAL
    assert contrast(faint, worst) < contrast(secondary, worst), \
        "faint must read as a dimmer tier than gray-400, not match it"


def test_the_tones_that_failed_before_are_not_reintroduced():
    """A named guard, so the regression has an obvious tripwire as well as a
    computed one."""
    offenders = {"gray-500", "gray-600", "gray-700"}
    used = used_text_classes() & offenders
    assert not used, (
        f"text-{', text-'.join(sorted(used))} measured below WCAG AA on REACH's "
        "surfaces. Use gray-400 for secondary text and faint for tertiary.")
