"""Section 7 — Creative Studio.

The photograph carries the section, so the tests care most about what is
NOT in it: no generated Street Banker merchandise, no invented prices, no
malformed shirt lettering. The rest is the ordinary contract - the copy
is markup, the labels say a sentence each, and a stranger can read what
the tools do and do not do without an account.
"""

import os
import re

from PIL import Image

from app import create_app


def _anon():
    return create_app().test_client()


def _home():
    return _anon().get("/").get_data(as_text=True)


def _section(body=None):
    body = body or _home()
    start = body.index('id="creative-studio"')
    return body[start:start + body[start:].index("</section>")]


def _css():
    return open("static/css/creative-studio.css", encoding="utf-8").read()


# --- placement and copy ---------------------------------------------------

def test_the_section_sits_after_the_lanes_and_displaces_nothing():
    body = _home()
    assert body.index('id="lanes"') < body.index('id="creative-studio"')
    assert body.index('id="creative-studio"') < body.index('id="royalty-sweep-section"')
    for kept in ["Choose your lane.", "Find what&#39;s yours.",
                 "Built for artist control.", "Your catalog is the ",
                 "One system. Six departments.", "TUNE YOUR ARTIST SYSTEM."]:
        assert kept in body, kept


def test_the_copy_is_the_approved_copy():
    eq = _section()
    assert "Creative Studio" in eq
    assert ">07<" in eq
    assert "Build the" in eq and "visual world." in eq
    assert ("Cover art, merch, campaign pieces, and every format the release "
            "needs — without losing the artist in the process." in eq)
    assert "Open Creative Studio" in eq
    assert "See the workflow" in eq
    # One differentiator, not another feature block.
    assert "Built around your identity." in eq
    assert "remembers approved visual directions" in eq


def test_four_labels_each_with_one_line():
    from creative_config import FEATURES

    eq = _section()
    labels = re.findall(r'data-feature="[^"]+"[^>]*>([^<]+)<', eq)
    assert labels == ["Cover Art", "Merch", "Campaign Assets", "Platform Formats"]
    # Every line is in the document, not only in a hover handler.
    for f in FEATURES:
        assert f["line"] in eq, f["id"]
        assert len(f["line"]) < 90, f["id"]
    # They are labels, not cards: no icons, no boxes, no repeated headings.
    assert "<svg" in eq                     # only the CTA arrow
    assert eq.count("<svg") == 1


def test_the_workflow_is_five_steps_on_request():
    from creative_config import WORKFLOW

    eq = _section()
    assert [s for s, _ in WORKFLOW] == ["Brief", "Directions", "Refine",
                                        "Approve", "Adapt"]
    for step, detail in WORKFLOW:
        assert ">%s<" % step in eq, step
        assert detail[:40] in eq, step
    # Hidden, not absent - it reads with no script at all.
    assert 'id="sbcs-workflow" hidden' in eq
    assert 'aria-controls="sbcs-workflow"' in eq
    assert 'aria-expanded="false"' in eq


# --- the photograph -------------------------------------------------------

def test_two_crops_chosen_by_the_browser():
    """A phone gets the table and the working light; anything wider gets
    the room. Not one file centre-cropped for every device."""
    eq = _section()
    assert eq.count("<img") == 1
    assert eq.count('media="(max-width: 767px)"') == 3      # avif, webp, jpeg
    for width in (400, 600):
        assert "creative-close-%d" % width in eq, width
    for width in (520, 830):
        assert "creative-wide-%d" % width in eq, width
    assert 'width="830" height="980"' in eq                 # no layout shift
    assert 'loading="lazy"' in eq and 'decoding="async"' in eq


def test_both_crops_ship_in_three_formats():
    ratios = {}
    for name, widths in (("wide", (520, 830)), ("close", (400, 600))):
        seen = []
        for width in widths:
            for ext in ("avif", "webp", "jpg"):
                asset = "static/img/creative-%s-%d.%s" % (name, width, ext)
                assert os.path.exists(asset), asset
                with Image.open(asset) as im:
                    assert im.size[0] == width, (asset, im.size)
                    seen.append(round(im.size[0] / im.size[1], 3))
        assert max(seen) - min(seen) < 0.01, (name, seen)
        ratios[name] = seen[0]
    # The two crops are genuinely different compositions.
    assert ratios["wide"] < 1 < ratios["close"], ratios


def test_the_alt_text_describes_the_room_and_sells_nothing():
    eq = _section()
    alt = re.search(r'alt="([^"]+)"', eq).group(1)
    assert alt == ("Touring artist and crew setting up a merchandise table "
                   "backstage inside a small music venue.")
    words = set(re.findall(r"[a-z]+", alt.lower()))
    for marketing in ("street", "banker", "creative", "studio", "premium",
                      "campaign"):
        assert marketing not in words, marketing


def test_the_photograph_carries_no_functional_text():
    """The supplied frame had a price sheet reading STREET BANKER /
    SECTION 7, a shirt printed SECTIN 7, two more Street Banker prints, a
    reaper logo on the merch cloth and SB7 stickers. The tool that built
    these assets clears all of it - and every word that matters is in the
    markup either way."""
    tool = open("tools/clean_creative_photo.py", encoding="utf-8").read()
    assert "ZONES" in tool and tool.count("# ") > 8
    for cleared in ("price sheet", "hanging shirt", "reaper logo", "sticker"):
        assert cleared in tool, cleared
    eq = _section()
    # Nothing in the section depends on reading the picture.
    for word in ("Cover Art", "Merch", "Campaign Assets", "Platform Formats",
                 "Build the", "Open Creative Studio"):
        assert word in eq, word


# --- destinations ---------------------------------------------------------

def test_the_cta_explains_before_it_asks_for_an_account():
    eq = _section()
    href = re.search(r'class="sbcs-cta" href="([^"]+)"', eq).group(1)
    assert href == "/creative-studio"
    client = _anon()
    page = client.get("/creative-studio")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    # The explanation comes before the account ask.
    assert body.index("How it runs") < body.index("/signup")
    # The gated tool itself is still gated.
    assert client.get("/artwork").status_code == 302


def test_the_tour_says_what_is_not_built():
    from creative_config import CAPABILITIES

    body = _anon().get("/creative-studio").get_data(as_text=True)
    headings = [h for h, _ in CAPABILITIES]
    assert headings == ["In the app today", "Guided, not automatic",
                        "Not built yet"]
    for heading in headings:
        assert heading in body, heading
    for honest in ("Nothing here makes video", "not for handing to a printer",
                   "nothing is picked", "a file you own"):
        assert honest in body, honest
    # No claim that the whole thing runs itself.
    for banned in ("fully automated", "does it for you", "one click",
                   "instantly generates"):
        assert banned not in body.lower(), banned


# --- what the brief rules out --------------------------------------------

def test_no_cards_no_stats_no_second_rack():
    eq = _section()
    text = re.sub(r"<[^>]+>", " ", eq)
    for banned in ("$", "%", "artists trust", "testimonial", "as seen in"):
        assert banned not in text, banned
    # Section 6 owns the analog rack; this one must not repeat it.
    for banned in ("VU", "fader", "knob", "rack", VU_WORD := "mastering"):
        assert banned.lower() not in text.lower(), banned
    assert "sblane" not in eq                # no borrowed hardware markup
    css = _css()
    for banned in ("@keyframes", "animation:", "parallax", "scale(1."):
        assert banned not in css, banned
    for ms in re.findall(r"transition:[^;]*?(\d+)ms", css):
        assert 150 <= int(ms) <= 250, ms


def test_the_dark_system_holds():
    css = _css()
    for token in ("#090908", "#C9A86A", "#EDE7DA"):
        assert token in css, token
    assert "background: var(--cs-black)" in css
    for bright in ("background: #fff", "background: white"):
        assert bright not in css, bright
    # Gradients only where the type has to stay readable: the base veil,
    # the narrower one the desktop column needs, and the top-down one on
    # a phone. Nothing is dimmed for the sake of being dimmed.
    assert css.count("linear-gradient") == 3


# --- interaction, accessibility, analytics -------------------------------

def test_the_labels_work_by_pointer_keyboard_and_without_script():
    css = _css()
    assert ".sbcs-feature:hover" in css
    assert ".sbcs-feature:focus-visible" in css
    assert ".sbcs-feature.is-active" in css
    assert "min-height: 46px" in css              # tap target
    # A fixed line box, so a label lighting up never moves the row.
    assert "min-height: 2.8em" in css
    js = open("static/js/creative-studio.js", encoding="utf-8").read()
    assert "function release()" in js             # focus outlives hover
    assert "sbcs-feature-fallback" in js          # the lines come from the DOM
    eq = _section()
    assert 'class="sbcs-feature-fallback"' in eq  # readable with no script


def test_accessibility_scaffolding():
    eq = _section()
    assert 'aria-labelledby="sbcs-heading"' in eq
    assert '<h2 class="sbcs-title" id="sbcs-heading">' in eq
    assert 'aria-live="polite"' in eq
    assert 'aria-describedby="sbcs-feature-line"' in eq
    assert eq.count('aria-hidden="true"') >= 2
    css = _css()
    assert "outline: 2px solid var(--cs-brass)" in css
    assert "prefers-reduced-motion" in css


def test_the_analytics_report_features_and_nothing_else():
    js = open("static/js/creative-studio.js", encoding="utf-8").read()
    for event in ("creative_studio_section_viewed", "creative_studio_opened",
                  "creative_workflow_opened", "creative_feature_selected",
                  "creative_features_swiped"):
        assert '"%s"' % event in js, event
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    for sensitive in ("email", "user_id", "localStorage", "prompt"):
        assert sensitive not in code, sensitive


def test_the_assets_are_linked_and_the_cache_version_moved():
    body = _home()
    assert "/static/css/creative-studio.css" in body
    assert "/static/js/creative-studio.js" in body
    sw = open("static/js/sw.js", encoding="utf-8").read()
    version = re.search(r'VERSION = "sb-v(\d+)"', sw)
    assert version and int(version.group(1)) >= 90
