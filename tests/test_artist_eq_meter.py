"""The Artist EQ's analyzer ladder reads like a real meter.

Owner, 2026-09-20: the lamps go "from green to yellow to red, like a real
meter". The ladder is drawn on a canvas, so the colours live in the
script; this pins them and the order they light in, and that the old
one-colour brass ladder is gone.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _script():
    return io.open(os.path.join(HERE, "static", "js", "artist-eq.js"),
                   encoding="utf-8").read()


def test_the_ladder_lights_green_then_amber_then_red():
    js = _script()
    body = js.split("function lamp(s, nSeg, top)")[1].split("}", 4)[0:4]
    body = "}".join(body)
    # bottom half green, the next quarter and a bit amber, the top fifth red
    assert re.search(r"f <= 0\.5\) \{ return top \? LAMP_G_TOP : LAMP_G; \}", body)
    assert re.search(r"f <= 0\.78\) \{ return top \? LAMP_A_TOP : LAMP_A; \}", body)
    assert "return top ? LAMP_R_TOP : LAMP_R;" in body
    assert body.index("LAMP_G") < body.index("LAMP_A") < body.index("LAMP_R")


def test_every_lit_lamp_and_the_peak_hold_take_their_rung_colour():
    js = _script()
    assert "ctx.fillStyle = lamp(s, nSeg, s === nLit - 1);" in js
    assert "ctx.fillStyle = lamp(s, nSeg, true);" in js
    # the brass single-colour ladder is gone
    assert "rgb(201,168,106)" not in js
    assert not re.search(r"var LAMP\s*=", js)


def test_green_amber_and_red_are_three_different_hues():
    js = _script()
    def rgb(name):
        m = re.search(name + r' = "rgb\((\d+),(\d+),(\d+)\)"', js)
        assert m, name
        return tuple(int(x) for x in m.groups())
    g, a, r = rgb("LAMP_G"), rgb("LAMP_A"), rgb("LAMP_R")
    assert g[1] > g[0] and g[1] > g[2]          # green leads
    assert a[0] > a[2] and a[1] > a[2]          # amber: red and green, little blue
    assert r[0] > r[1] and r[0] > r[2]          # red leads
    for base in ("LAMP_G", "LAMP_A", "LAMP_R"):
        top = rgb(base + "_TOP")
        assert sum(top) > sum(rgb(base)), base   # the top lamp is a step brighter
