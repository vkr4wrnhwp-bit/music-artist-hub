"""The Operator Desk and Signal are black and gold like the rest of the app.

Owner ruling 2026-09-19, on being shown the two internal tools in their
ivory "paper" look: "no, we want it black and gold just like the rest of
the website" (and earlier, 2026-09-14: every back-door site in the same
black, white and gold layout). Both tools keep their own dk-* / sg-*
variable names so no template had to change; each name is now defined in
terms of the app's dark tokens, and the paper tokens are not read at all.

This lock holds three things:

  1. Neither stylesheet reads a paper token, paints a light literal, or
     hard-codes a paper-era rgb() tint. Every colour comes through --sb-*.
  2. Neither shell wears the paper class, so the shared meter and lamp
     from app-chrome.css draw in their dark default.
  3. Every desk/signal template that once set a light colour inline is
     clean too, and the stylesheet versions moved so the browser does not
     keep serving the ivory sheet from cache.
"""
import glob
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHEETS = ("static/css/operator-desk.css", "static/css/signal.css")
SHELLS = ("templates/desk/layout.html", "templates/desk/denied.html",
          "templates/signal/_shell.html", "templates/signal/denied.html")

# The dark ramp every desk/signal ground and panel must resolve to.
DARK_GROUNDS = ("var(--sb-ground)", "var(--sb-surface-1)",
                "var(--sb-surface-2)", "var(--sb-surface-3)")


def _read(rel):
    return io.open(os.path.join(HERE, rel), encoding="utf-8").read()


def _luminance(hexish):
    h = hexish.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    ch = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def test_neither_sheet_reads_a_paper_token():
    for rel in SHEETS:
        css = _read(rel)
        assert "--sb-paper" not in css, "%s still reads a paper token" % rel
        assert "sb-on-paper" not in css, rel


def test_neither_sheet_paints_a_light_literal():
    """A light hex anywhere in these sheets is a paper ground sneaking back
    (the old input fields were background: #fff). The design-system lock
    already forbids hex outside the token set; this is stricter for these
    two files: no hex at all above 50% luminance, however it is spelled."""
    for rel in SHEETS:
        css = re.sub(r"/\*.*?\*/", "", _read(rel), flags=re.S)
        for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", css):
            if _luminance(h) > 0.5:
                raise AssertionError("%s paints a light literal %s" % (rel, h))
        # The paper era tinted hovers with a near-black rgb() over ivory
        # and gold-washed the active nav with a paper-only mix. On the dark
        # ground both read as nothing; they must come through tokens now.
        assert "rgb(20 18 16" not in css, rel
        assert "rgb(180 131 27" not in css, rel


def test_the_page_grounds_resolve_to_the_dark_ramp():
    dk = _read("static/css/operator-desk.css")
    sg = _read("static/css/signal.css")
    for css, ground, panel in ((dk, "--dk-paper", "--dk-panel"),
                               (sg, "--sg-paper", "--sg-panel")):
        m = re.search(r"%s:\s*([^;]+);" % re.escape(ground), css)
        assert m and m.group(1).strip() in DARK_GROUNDS, (ground, m and m.group(1))
        m = re.search(r"%s:\s*([^;]+);" % re.escape(panel), css)
        assert m and m.group(1).strip() in DARK_GROUNDS, (panel, m and m.group(1))
    # And the type on them is the app's ivory ink, not the paper ink.
    assert re.search(r"--dk-ink:\s*var\(--sb-ink\);", dk)
    assert re.search(r"--sg-ink:\s*var\(--sb-ink\);", sg)


def test_the_shells_do_not_wear_the_paper_class():
    for rel in SHELLS:
        html = _read(rel)
        assert "sb-on-paper" not in html, rel
        assert "sg-body sb-" not in html and "dk-body sb-" not in html, rel


def test_no_desk_or_signal_template_hard_codes_a_light_colour():
    hits = []
    for sub in ("desk", "signal"):
        for p in glob.glob(os.path.join(HERE, "templates", sub, "*.html")):
            s = _read(os.path.relpath(p, HERE))
            for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", s):
                if _luminance(h) > 0.5:
                    hits.append("%s/%s: %s" % (sub, os.path.basename(p), h))
            if "--sb-paper" in s or "sb-on-paper" in s:
                hits.append("%s/%s: paper" % (sub, os.path.basename(p)))
            if "background:#fff" in s.replace(" ", "") or "background:white" in s.replace(" ", ""):
                hits.append("%s/%s: white background" % (sub, os.path.basename(p)))
    assert hits == [], hits


def test_the_primary_action_is_the_gold_button():
    """On paper the primary button was ink-on-paper inverted. On the dark
    ground the same inversion is an ivory slab; the app's primary is gold
    with the on-gold ink, and both desks follow it."""
    dk = _read("static/css/operator-desk.css")
    sg = _read("static/css/signal.css")
    assert re.search(r"\.dk-btn \{[^}]*background: var\(--dk-gold\);[^}]*color: var\(--dk-on-gold\);", dk, re.S)
    assert re.search(r"\.sg-btn \{[^}]*background: var\(--sg-gold\);[^}]*color: var\(--sg-on-gold\);", sg, re.S)
    assert re.search(r"--dk-on-gold:\s*var\(--sb-on-gold\);", dk)
    assert re.search(r"--sg-on-gold:\s*var\(--sb-on-gold\);", sg)


def test_the_stylesheet_versions_moved_past_the_paper_era():
    """The service worker and the browser cache both key on ?v=; the ivory
    sheets were operator-desk.css?v=2 and signal.css?v=4."""
    for rel in SHELLS:
        html = _read(rel)
        for sheet, floor in (("operator-desk.css", 3), ("signal.css", 5)):
            m = re.search(r"/static/css/%s\?v=(\d+)" % re.escape(sheet), html)
            if m:
                assert int(m.group(1)) >= floor, (rel, sheet, m.group(1))
