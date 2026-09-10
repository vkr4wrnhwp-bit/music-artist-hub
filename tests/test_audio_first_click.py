"""The first click on an audio transport did nothing; the second worked.

Reported live, 2026-09-10, for the Studio and Rack pages specifically.

A browser starts an AudioContext suspended until a user gesture, and
`resume()` is asynchronous. Both transports did:

    ensureCtx().resume();      // a promise, not awaited
    startAt(position());       // schedules against a clock that is
                               // still stopped

A source scheduled against a suspended clock is queued at a time that
never arrives, so nothing is heard. By the second click the context has
resumed on its own and playback works — which is exactly the "hit every
button twice" the owner described.

Held here: anything that needs the clock running waits for it. Decoding
does not need a running clock, so those calls are deliberately left
alone rather than slowed down.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYERS = ["static/js/studioconsole.js", "static/js/rackdsp.js"]


def _read(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def test_both_transports_wait_for_the_clock_before_starting_a_source():
    for rel in PLAYERS:
        src = _read(rel)
        assert "function sbWhenRunning(" in src, "%s has no gate" % rel
        body = src[src.index("function sbWhenRunning("):]
        body = body[:body.index("\n}") + 2]
        assert 'state === "suspended"' in body, "%s: it must ask, not assume" % rel
        assert ".resume().then(" in body, "%s: and wait for the answer" % rel


def test_the_studio_play_button_no_longer_starts_against_a_stopped_clock():
    src = _read("static/js/studioconsole.js")
    play = src[src.index("play: function ()"):]
    play = play[:play.index("pause: function ()")]
    assert "ensure().resume();" not in play, "the un-awaited resume is the bug"
    assert "sbWhenRunning(ensure()" in play
    # The position is read at click time, not after the await, so a
    # resume that takes a moment cannot move where playback begins.
    assert play.index("var at = position();") < play.index("sbWhenRunning")


def test_the_rack_transport_goes_through_the_same_gate():
    src = _read("static/js/rackdsp.js")
    start = src[src.index("function startPlayback(offset)"):]
    start = start[:start.index("function startPlaybackNow(offset)")]
    assert "sbWhenRunning(ensureCtx()" in start
    assert ".resume();" not in start, "no un-awaited resume on the play path"


def test_the_gate_is_reachable_from_every_call_site():
    """It lives at file scope because the callers sit in different closures."""
    for rel in PLAYERS:
        lines = _read(rel).split("\n")
        definition = next(i for i, l in enumerate(lines)
                          if l.startswith("function sbWhenRunning("))
        uses = [i for i, l in enumerate(lines)
                if "sbWhenRunning(" in l and not l.startswith("function")]
        assert uses, "%s defines the gate and never uses it" % rel
        assert all(u > definition for u in uses)
        # File scope means no leading indentation on the declaration.
        assert not lines[definition].startswith(" "), (
            "%s: nested in a closure, so the other call sites cannot see it" % rel)


def test_decoding_was_not_slowed_down_for_no_reason():
    """decodeAudioData works on a suspended context — those stay direct."""
    src = _read("static/js/rackdsp.js")
    assert re.search(r'ensureCtx\(\)\.resume\(\);', src), (
        "the load paths should still resume eagerly without waiting")


def test_the_video_capture_waits_for_the_clock_too():
    """A MediaRecorder started against a suspended context records the
    opening of the hook as silence — and unlike a transport that appears
    to do nothing, this produces a file that looks right and is wrong,
    discovered after it has been posted."""
    src = _read("static/js/rackdsp.js")
    start = src[src.index("function renderHookVideo(h)"):]
    start = start[:start.index("function renderHookVideoNow(h)")]
    assert "sbWhenRunning(ensureCtx()" in start
    assert ".resume();" not in start, "no un-awaited resume before recording"
