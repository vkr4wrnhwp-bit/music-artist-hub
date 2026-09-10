"""Each Audio Studio output was a grey bar and nothing else.

Asked for live, 2026-09-10: "i think we need a wav file view and fast
forward, rewind, etc buttons on each stem or track".

Every returned file was listed with the browser's own <audio> element:
it plays, and that is all. No picture of the file, no way to jump, no
way to nudge back and hear an edit again — so comparing four separated
stems meant scrubbing four identical grey bars.

The decisions worth holding:

  - the <audio> element stays the engine, because it streams and cannot
    get stuck behind a suspended AudioContext, which is the bug that
    made every other transport in the product need two clicks;
  - a context is opened once to decode for the drawing and closed
    again, because Chrome caps live contexts per tab and a page of
    eight stems would run out;
  - a file that will not decode keeps a working transport and says the
    picture is missing, rather than drawing a flat line, which reads as
    silence.
"""
import io
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def test_every_output_gets_a_transport_and_a_picture():
    markup = _read("templates/audio_studio_item.html")
    for hook in ("data-sd-src", "data-sd-play", "data-sd-back",
                 "data-sd-fwd", "data-sd-wave", "data-sd-time"):
        assert hook in markup, "the deck is missing %s" % hook
    assert "/static/js/stemdeck.js" in markup


def test_the_element_stays_the_engine():
    """Not an AudioContext source: that is what needed two clicks."""
    src = _read("static/js/stemdeck.js")
    assert "audio.play()" in src and "audio.pause()" in src
    assert "createBufferSource" not in src, (
        "playing through a context reintroduces the suspended-clock bug")


def test_the_decode_context_is_closed_again():
    src = _read("static/js/stemdeck.js")
    assert src.count("ctx.close()") >= 2, (
        "both the success and the failure path, or a page of stems runs "
        "out of contexts")


def test_a_file_that_will_not_decode_still_plays():
    src = _read("static/js/stemdeck.js")
    assert "No waveform for this format" in src
    # The transport is never torn down in the failure path.
    tail = src[src.index(".catch(function ()"):]
    assert "disabled" not in tail[:400]


def test_the_skip_buttons_cannot_run_off_either_end():
    src = _read("static/js/stemdeck.js")
    assert "Math.max(0, audio.currentTime - NUDGE)" in src
    assert "Math.min(dur, audio.currentTime + NUDGE)" in src


def test_the_picture_takes_its_colours_from_the_theme():
    """A canvas cannot inherit; it reads the tokens at draw time."""
    src = _read("static/js/stemdeck.js")
    assert "--sd-played" in src and "--sd-wave" in src
    css = _read("static/css/app-chrome.css")
    assert "--sd-wave: var(--sb-ink-3)" in css
    assert "--sd-played: var(--sb-gold)" in css


def test_there_is_still_something_without_javascript():
    markup = _read("templates/audio_studio_item.html")
    assert "<noscript>" in markup and "audio controls" in markup


def test_the_stylesheet_build_moved_so_the_deck_is_styled():
    """The deck's rules are new; a cached stylesheet has none of them."""
    base = _read("templates/base.html")
    assert "app-chrome.css?v=7" in base


def test_every_shell_asks_for_the_same_stylesheet_build():
    """Three shells were pinned two builds back and served the same file."""
    seen = set()
    for root, _dirs, files in os.walk(os.path.join(HERE, "templates")):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            src = _read(os.path.relpath(os.path.join(root, fn), HERE))
            for part in src.split("app-chrome.css?v=")[1:]:
                seen.add(part.split('"')[0])
    assert len(seen) <= 1, (
        "shells disagree about which build of app-chrome.css to load: %s" % seen)
