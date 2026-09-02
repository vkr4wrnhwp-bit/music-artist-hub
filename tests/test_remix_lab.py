"""Remix Lab — rights-safe by construction, honest by construction.

What has to hold: the page is public, the upload is gated behind both
rights confirmations in markup before any script runs, the likeness
screen catches every imitation pattern the brief lists and passes every
allowed example, no real artist is named anywhere, the results are
labelled a worked example, and nothing promises streams or hits.
"""
import re

import pytest

import remix_lab_config as rl
from app import create_app


@pytest.fixture(scope="module")
def page():
    client = create_app().test_client()
    response = client.get("/remix-lab")
    assert response.status_code == 200, "Remix Lab must be public"
    return response.get_data(as_text=True)


# --- the rights gate --------------------------------------------------------

def _escaped(text):
    """Jinja auto-escapes apostrophes; compare what actually renders."""
    return text.replace("'", "&#39;")


def test_both_rights_confirmations_are_verbatim_and_required(page):
    assert _escaped(rl.RIGHTS_CHECKBOX) in page
    assert _escaped(rl.LIKENESS_CHECKBOX) in page
    assert re.search(r'id="sbrl-rights-own"[^>]*required', page)
    assert re.search(r'id="sbrl-rights-likeness"[^>]*required', page)


def test_the_upload_is_disabled_before_any_script_runs(page):
    """The gate must hold with JavaScript off, so the disabled attribute
    is rendered server-side rather than applied by the script."""
    assert re.search(r'id="sbrl-file"[^>]*\bdisabled\b', page)
    assert 'aria-disabled="true"' in page
    # And the note says why, beside the control.
    assert "confirm both rights statements above to enable" in page


def test_the_upload_constraints_are_stated(page):
    for fmt in ("WAV", "MP3", "AIFF", "FLAC"):
        assert fmt in page, fmt
    assert "250" in page                       # the size cap, visible


# --- the likeness screen ----------------------------------------------------

# Every pattern the brief bans, phrased the way a person would type it.
IMITATION_REQUESTS = [
    "make it sound like a famous rapper",
    "sounds like that one singer",
    "in the style of a chart producer",
    "make it like her last album",
    "use his voice on the hook",
    "clone the voice from the reference",
    "voice cloning please",
    "deepfake the vocals",
    "deep fake vocal",
    "an AI cover of this song",
    "impersonate the original singer",
    "copy the vocals exactly",
    "copy the vocal",
    "same flow as the reference track",
    "same voice as the demo",
    # The native idiom for this request in music. Leaving it out screened the
    # wording rather than the ask: naming somebody after "in the style of"
    # was refused while the same name before "type beat" - how this actually
    # gets typed in this industry - went through. Phrased without a real
    # person here, like every other case in this list.
    "a reference artist type beat",
    "that producer type beat with heavy 808s",
]


@pytest.mark.parametrize("request_text", IMITATION_REQUESTS)
def test_every_imitation_request_is_caught(request_text):
    assert rl.check_reference_text(request_text), request_text


@pytest.mark.parametrize("allowed", rl.ALLOWED_EXAMPLES)
def test_every_allowed_example_passes_the_screen(allowed):
    """The replacements the page suggests must not trip the screen that
    suggested them."""
    assert rl.check_reference_text(allowed) is None, allowed


def test_neutral_musical_descriptions_pass():
    for text in ("124 BPM four-on-the-floor with a hook-first intro",
                 "warm, intimate, sparse percussion, natural vocals",
                 "https://example.com/some-reference-track",
                 ""):
        assert rl.check_reference_text(text) is None, text


def test_the_warning_copy_is_verbatim_on_the_page(page):
    assert _escaped(rl.SAFETY_WARNING) in page
    for example in rl.ALLOWED_EXAMPLES:
        assert _escaped(example) in page, example


def test_the_pattern_list_reaches_the_browser_unchanged(page):
    """One source of truth: the JSON blob embeds the same list the server
    will enforce, so the two screens cannot drift apart."""
    blob = re.search(r'<script type="application/json" id="sbrl-config">(.*?)'
                     r'</script>', page, re.S).group(1)
    import json
    client_config = json.loads(blob)
    assert client_config["patterns"] == rl.BANNED_PATTERNS
    assert client_config["max_mb"] == rl.UPLOAD_MAX_MB


def test_no_real_artist_is_named_anywhere(page):
    """Not in the copy, not in the examples, not even as what to avoid."""
    for name in ("Drake", "Taylor Swift", "Metro Boomin", "Beyonc"):
        assert name not in page, name
    source = open("remix_lab_config.py", encoding="utf-8").read()
    for name in ("Drake", "Taylor Swift", "Metro Boomin"):
        assert name not in source, name


# --- the form ---------------------------------------------------------------

def test_all_ten_lanes_and_eight_uses_render(page):
    for lane in rl.REMIX_LANES:
        assert lane in page, lane
    for use in rl.TARGET_USES:
        assert use in page, use
    assert page.count('name="remixLane"') == 10
    assert page.count('name="targetUse"') == 8


def test_the_five_vibe_controls_render_with_their_options(page):
    for key, label, options in rl.VIBE_CONTROLS:
        assert 'name="%s"' % key in page, key
        assert label in page, label
        for option in options:
            assert option in page, (key, option)


# --- honesty ----------------------------------------------------------------

def test_the_results_are_labelled_a_worked_example(page):
    assert rl.EXAMPLE_TAG in page
    # Conditional for the same reason as the preview note below: the
    # unconditional string claimed generation was not connected on a
    # deployment where it was.
    assert rl.get_remix_lab_config()["example_note"] in page
    # The note is conditional now that the engine can actually be wired: it
    # says "generation is not yet connected" when it is not, and describes
    # what is measured when it is. Asserting the CURRENT note keeps the
    # original intent - the page states which of the two it is - without
    # pinning it to the state the deployment happens to be in.
    assert rl.get_remix_lab_config()["preview_note"] in page
    # The worth-making read is bands with the caveat beside it.
    assert rl.WORTH_NOTE in page


def test_nothing_promises_hits_streams_or_revenue(page):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text).lower()
    for banned in ("instant hit", "viral guaranteed", "guaranteed",
                   "hit score", "viral probability"):
        assert banned not in text, banned


def test_the_page_transmits_nothing(page):
    """The preview must not upload: no fetch, no XHR, no beacon carrying
    content. The submission object stays in the browser."""
    script = open("static/js/remix-lab.js", encoding="utf-8").read()
    assert "fetch(" not in script
    assert "XMLHttpRequest" not in script
    assert "sendBeacon" not in script
    assert "FormData" not in script
    # And the page says so where the visitor is looking.
    assert "Nothing is uploaded in this preview" in script


def test_the_capability_status_is_coming_soon():
    import capability_status
    resolved = capability_status.resolve("remix_lab")
    assert resolved["status"] == capability_status.COMING_SOON
    # The page carries the same admission in its own words.


def test_the_producer_handoff_goes_somewhere_real(page):
    client = create_app().test_client()
    href = re.search(r'class="sbrl-btn sbrl-btn--primary" '
                     r'href="(/[^"]+)">Request Producer Review', page).group(1)
    assert client.get(href).status_code == 200


def test_structure_and_access(page):
    assert len(re.findall(r"<h1[\s>]", page)) == 1
    assert 'lang="en"' in page
    assert "<main" in page
    # Both hero CTAs land on anchors that exist on this page.
    for anchor in ("brief", "rights"):
        assert 'href="#%s"' % anchor in page
        assert 'id="%s"' % anchor in page


# --- the studio redesign ------------------------------------------------------
#
# Photograph-and-light: a dark page with real photographs behind the hero, the
# outputs row and the rights band, lit indicators that mirror the real form
# state, and an honest "what the brief reads" rail that carries state text
# rather than numbers. These pin the structure the redesign added; everything
# above still has to hold.

import os as _os

_HERE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


def _outside_results(page):
    """The page with the worked-example block removed - the one place a
    number like '92 BPM' may legitimately appear, under its EXAMPLE tag."""
    text = re.sub(r'<section class="sbrl-results".*?</section>', " ", page, flags=re.S)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    return text


def test_the_photographs_are_real_files_and_decorative(page):
    for stem in ("sweep-wide-1400", "eq-room-", "distro-wide-"):
        assert stem in page, stem
    for src in re.findall(r'/static/img/(sweep-[a-z]+-\d+\.jpg|distro-[a-z]+-\d+\.jpg|eq-room-\d+\.jpg)', page):
        assert _os.path.exists(_os.path.join(_HERE, "static", "img", src)), src
    # Every image on the page is decorative and says so; the header logo
    # is the one image that carries meaning and lives in the shared partial.
    for tag in re.findall(r"<img[^>]*>", page):
        if "streetbanker-logo" in tag:
            continue
        assert 'alt=""' in tag, tag


def test_the_hero_light_is_a_streak_until_a_file_is_decoded(page):
    assert 'id="sbrl-hero-streak"' in page
    canvas = re.search(r"<canvas[^>]*>", page).group(0)
    assert 'id="sbrl-hero-canvas"' in canvas
    assert "hidden" in canvas
    assert 'id="sbrl-wave-note"' in page


def test_the_rail_is_honest_before_any_upload(page):
    """The mockup's Track Insights, readiness gauge, creative score and
    activity feed have no data source; none of it may be reproduced."""
    text = _outside_results(page)
    assert "Not detected — by design" in text
    for fake in ("BPM", "A minor", "A Minor", "% ready", "/100", "Creative score",
                 "Recent activity", "Outputs ready", "AI-Powered"):
        assert fake not in text, fake


def test_the_rail_says_which_state_it_is_in(page, monkeypatch):
    assert "Not measured in this preview" in page
    assert "Example sections" in page
    assert "Screened as you type. Nothing is sent." in page

    monkeypatch.setenv("AUDIO_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("REMIX_LAB_AUDIO_ENGINE_ENABLED", "1")
    live = create_app().test_client().get("/remix-lab").get_data(as_text=True)
    assert "Measured after upload" in live
    assert "After upload" in live
    assert "Not measured in this preview" not in live
    assert "again on the server" in live
    assert "Reads tempo, sections, energy" in live
    assert "AI-Powered" not in live


def test_the_lit_indicators_mirror_the_real_form(page):
    for attr in ('data-step="rights"', 'data-chip="rights"', 'data-safe="refs"'):
        assert attr in page, attr
    assert page.count('class="sbrl-step"') == 4
    assert page.count('class="sbrl-chip-state"') == 4
    assert page.count('class="sbrl-out ') == 4
    for letter in "abcd":
        assert 'href="#sbrl-ex-%s"' % letter in page
    for letter in "abcde":
        assert 'id="sbrl-ex-%s"' % letter in page


def test_the_segmented_switches_enhance_the_selects(page):
    assert page.count('role="radiogroup"') == 5
    assert page.count('role="radio"') == 16          # 3 + 3 + 4 + 3 + 3
    for key in re.findall(r'data-seg="([^"]+)"', page):
        assert 'name="%s"' % key in page, key


def test_the_submit_is_never_disabled(page):
    button = re.search(r'<button[^>]*id="sbrl-submit"[^>]*>', page).group(0)
    assert "disabled" not in button
    assert 'aria-describedby="sbrl-submit-note"' in button


def test_the_static_assets_were_bumped(page):
    assert "remix-lab.css?v=8" in page
    assert "remix-lab.js?v=4" in page
    sw = open(_os.path.join(_HERE, "static", "js", "sw.js"), encoding="utf-8").read()
    assert "sb-v167" in sw


def test_the_waveform_is_decoded_locally_and_references_are_named():
    script = open(_os.path.join(_HERE, "static", "js", "remix-lab.js"), encoding="utf-8").read()
    assert "OfflineAudioContext" in script
    assert "arrayBuffer" in script
    assert 'input.name = "reference"' in script
    for banned in ("fetch(", "XMLHttpRequest", "sendBeacon", "FormData"):
        assert banned not in script, banned


def test_the_icon_sprite_is_drawn_not_loaded():
    sprite = open(_os.path.join(_HERE, "templates", "partials", "remix_lab_icons.html"),
                  encoding="utf-8").read()
    ids = re.findall(r'<symbol id="([^"]+)"', sprite)
    assert ids and all(i.startswith("sbrl-i-") for i in ids)
    assert not re.search(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])", sprite)
    assert "http" not in sprite.replace("http://www.w3.org/2000/svg", "")


def test_the_brief_page_never_shows_mock_numbers_as_measured(monkeypatch):
    """The rail on the brief page draws a section map only from a real
    provider's plan; the offline mock's placeholder structure is labelled."""
    import io
    import uuid

    monkeypatch.setenv("AUDIO_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("REMIX_LAB_AUDIO_ENGINE_ENABLED", "1")
    client = create_app().test_client()
    email = "remix-ui-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Artist", "email": email, "password": "rl-pass-123"})
    client.post("/login", data={"email": email, "password": "rl-pass-123"})
    resp = client.post("/remix-lab/brief", data={
        "rights_own": "1", "rights_likeness": "1", "remixLane": "Club / DJ Edit",
        "targetUse": "DJ pack", "energy": "High", "tempoDirection": "Same",
        "vocalTreatment": "Hook-first", "instrumentation": "Balanced",
        "riskLevel": "Exploratory",
        "file": (io.BytesIO(b"RIFF" + b"\0" * 600), "master.wav")},
        content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "remix-lab.css?v=8" in body
    assert "Not detected — by design" in body
    assert "Placeholder — not a measurement" in body
    assert "sbrl-read-seg--measured" not in body
    # The body lines: a placeholder plan's tempo and structure are badged
    # placeholder, never green "measured", and the sentence says whose number it is.
    assert 'sbrl-badge--good">measured' not in body
    assert 'sbrl-badge--warn">placeholder' in body
    assert "Placeholder figure, not a reading of your track." in body
    assert "BPM measured" not in body
    assert re.search(r"<h1[\s>]", body)
