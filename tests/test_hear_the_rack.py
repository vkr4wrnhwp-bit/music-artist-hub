"""Hear the Rack: the homepage's one hands-on moment.

What has to hold: the loop is declared synthesized and nobody's record;
the chain is the Rack's stages (band table and tube curve verbatim);
nothing on the surface claims to analyse the visitor's music; the six
faders are not touched by the audio; and the pure parts pass the Node
check, which is the only place the tube curve and the groove are
actually executed.
"""
import os
import re
import shutil
import subprocess

import pytest

from app import create_app

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "static", "js", "hear-the-rack.js")
CHECK = os.path.join(HERE, "js", "check_hear_the_rack.js")
NODE = os.environ.get("SB_NODE_BIN") or shutil.which("node") or shutil.which("node.exe")
_REQUIRED = os.environ.get("SB_REQUIRE_JS_TESTS") == "1"
needs_node = pytest.mark.skipif(NODE is None and not _REQUIRED,
                                reason="node is not on PATH")


def _home():
    return create_app().test_client().get("/").get_data(as_text=True)


def _strip():
    body = _home()
    start = body.index('class="sbeq-trace"')
    return body[start:start + body[start:].index("</div>\n    </div>")]


def test_the_controls_and_the_script_are_on_the_homepage():
    body = _home()
    assert 'id="sbeq-htr-play"' in body and 'id="sbeq-htr-rack"' in body
    assert 'id="sbeq-lights"' in body
    assert "/static/js/hear-the-rack.js" in body
    client = create_app().test_client()
    assert client.get("/static/js/hear-the-rack.js").status_code == 200


def test_the_loop_is_declared_synthesized_and_nobodys_record():
    strip = _strip()
    assert "synthesized" in strip.lower()
    assert "Hear the Rack" in strip
    text = re.sub(r"<[^>]+>", " ", strip).lower()
    for claim in ("your track", "your song", "your music", "your mix",
                  "we analysed", "we analyzed", "detected"):
        assert claim not in text, claim


def test_the_chain_is_the_racks_stages():
    js = open(SCRIPT, encoding="utf-8").read()
    rack = open(os.path.join(ROOT, "static", "js", "rackdsp.js"), encoding="utf-8").read()
    # The tube transfer function, verbatim.
    assert "c[i] = Math.tanh(d * x) / norm;" in js and "c[i] = Math.tanh(d * x) / norm;" in rack
    assert "drive * (1 - bias * 0.6)" in js and "drive * (1 - bias * 0.6)" in rack
    # The band table, every frequency and type.
    for f, kind in ((40, "lowshelf"), (80, "peaking"), (120, "peaking"), (250, "peaking"),
                    (400, "peaking"), (630, "peaking"), (1000, "peaking"), (1600, "peaking"),
                    (2500, "peaking"), (4000, "peaking"), (8000, "peaking"), (14000, "highshelf")):
        assert '{f: %d, type: "%s"' % (f, kind) in js, f
        assert '{f: %d, type: "%s"' % (f, kind) in rack, f


def test_the_audio_never_touches_the_faders_and_never_fetches():
    js = open(SCRIPT, encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    for forbidden in ("sbeq-range", "state.values", "applyPreset", "fetch(",
                      "XMLHttpRequest", "localStorage", "createMediaElementSource",
                      "getUserMedia"):
        assert forbidden not in code, forbidden


def test_the_light_show_respects_reduced_motion():
    js = open(SCRIPT, encoding="utf-8").read()
    assert "prefers-reduced-motion" in js
    css = open(os.path.join(ROOT, "static", "css", "artist-eq.css"), encoding="utf-8").read()
    assert "sbeq-lights" in css and "prefers-reduced-motion" in css


@needs_node
def test_the_pure_parts_pass_the_node_check():
    if not NODE or not os.path.exists(NODE):
        pytest.fail("no usable node binary (%r)" % (NODE,))
    proc = subprocess.run([NODE, CHECK, SCRIPT], capture_output=True, text=True,
                          timeout=60, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "all checks passed" in proc.stdout
