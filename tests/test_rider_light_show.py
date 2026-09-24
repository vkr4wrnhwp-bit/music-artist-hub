"""The public tech rider describes the light show saved for THAT date.

Make-it-real audit, 2026-09-23 (not_real_today[12]; the 2026-09-11
overclaims list, item 9): /rider/<token>, which the advance sends to
venues, read the account's Light Studio working copy (db.get_light_show:
whatever the artist last had open) rather than the show saved against
the date, and always said "addressed outward-in in pairs", "over an
ENTTEC DMX USB Pro" and "a power drop stage left" whatever the patch.

Now it reads the library show linked to the date (the one "Save to
library" wrote; autosave never touches it) and says that show's bar
count, channel width, each bar's DMX address by the Light Studio's own
rule, the universe for a network output, the output it is set to and its
cue count. No linked show, no Lighting section.
"""
import uuid

import pytest

import app as appmod
import db as store
import lights_store
from tests.test_tour_date_page import _show, _tour, _user

STOCK = ("outward-in", "power drop", "House needs")


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _date_with_rider(flask_app):
    c, owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    token = uuid.uuid4().hex
    store.set_show_share_token(owner["id"], sid, token)
    return c, owner, tid, sid, token


def _rider(flask_app, token):
    r = flask_app.test_client().get("/rider/%s" % token)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _show_data(**over):
    # rigKey "dive4" is the Light Studio's "Dive bar 4-bar" preset: 4 bars
    # of RGB, the same shape as this show, so the rider may name it.
    data = {"name": "", "bars": 4, "chans": 3, "dmxStart": 10, "dmxAddr": {"3": 100},
            "dmxUniverse": 2, "output": "artnet", "rigKey": "dive4", "rigName": "Dive bar 4-bar",
            "cues": [{"t": i, "group": "all", "color": "#ffffff", "intensity": 80} for i in range(5)]}
    data.update(over)
    return data


def test_the_working_copy_alone_puts_no_lighting_on_the_rider(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    store.save_light_show(owner["id"], {"name": "Scratch Copy", "bars": 8, "chans": 4,
                                        "cues": [{"t": 1}, {"t": 2}]})
    body = _rider(flask_app, token)
    assert 'id="rider-lighting"' not in body and "Scratch Copy" not in body
    assert "8 wash bars" not in body


def test_the_rider_reads_the_show_saved_for_this_date(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    store.save_light_show(owner["id"], {"name": "Scratch Copy", "bars": 8, "chans": 4, "cues": []})
    lights_store.save_show(owner["id"], None, "Tour Night Looks", _show_data(), tour_show_id=sid)
    body = _rider(flask_app, token)
    assert 'id="rider-lighting"' in body
    assert "Tour Night Looks" in body and "Scratch Copy" not in body
    assert "4 wash bars" in body and "RGB, 3 DMX channels each" in body
    assert '"Dive bar 4-bar" rig' in body and "5 programmed cues" in body
    # Bars run on from address 10 in threes; bar 3 has its own patch.
    assert "bar 1 at 10, bar 2 at 13, bar 3 at 100, bar 4 at 19." in body
    assert "universe 2" in body and "Art-Net" in body
    assert "ENTTEC" not in body
    for words in STOCK:
        assert words not in body, words


def test_an_enttec_show_says_enttec_and_preview_names_no_device(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lib_id = lights_store.save_show(owner["id"], None, "USB Night",
                                    _show_data(output="enttec", dmxAddr={}, chans=4, dmxStart=1),
                                    tour_show_id=sid)
    body = _rider(flask_app, token)
    assert "an ENTTEC DMX USB Pro on the act" in body
    assert "bar 1 at 1, bar 2 at 5, bar 3 at 9, bar 4 at 13." in body
    assert "universe" not in body.split('id="rider-lighting"')[1].split("</section>")[0], \
        "an ENTTEC USB interface is one universe; no number is claimed"
    lights_store.save_show(owner["id"], lib_id, "USB Night", _show_data(output="preview"), tour_show_id=sid)
    body = _rider(flask_app, token)
    lighting = body.split('id="rider-lighting"')[1].split("</section>")[0]
    assert "Output:" not in lighting and "ENTTEC" not in lighting and "Art-Net" not in lighting


def test_a_show_saved_for_another_date_stays_off_this_rider(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    other = _show(c, tid, "2030-05-05", "Other Room")
    lights_store.save_show(owner["id"], None, "Other Night", _show_data(), tour_show_id=other)
    lights_store.save_show(owner["id"], None, "Unlinked Show", _show_data())
    body = _rider(flask_app, token)
    assert 'id="rider-lighting"' not in body
    assert "Other Night" not in body and "Unlinked Show" not in body


def test_rider_lights_reads_only_what_the_show_holds():
    assert lights_store.rider_lights(None) is None
    assert lights_store.rider_lights({"name": "x", "data": {"cues": [1]}}) is None, "no bars, no section"
    got = lights_store.rider_lights({"name": "Night", "data": {"bars": 2, "cues": []}})
    assert got["chans"] == 4, "the Light Studio's own default width"
    assert got["patch"] == [(1, 1), (2, 5)]
    assert got["output"] == "" and got["output_words"] == ""
    got = lights_store.rider_lights({"name": "", "data": {"bars": 3, "chans": 3, "dmxStart": 507,
                                                          "output": "sacn", "name": "From data"}})
    assert got["name"] == "From data"
    # Was [(1, 511), (2, 512), (3, 512)] from dmxStart 511: a bar at 511 in
    # 3-channel mode needs 511-513, and lights-engine.js dmxFrame/dmxData
    # skip any bar that runs past 512, so none of those bars got a signal.
    # A bar the Studio never sends is said so, never given an address.
    assert got["patch"] == [(1, 507), (2, 510), (3, None)], "past the end is not sent, never wrapped"
    assert got["output_words"].startswith("sACN")


# --- review of 2026-09-23: fixture mode, a stale rig name, bars never sent ---

def test_a_four_channel_show_is_dimmer_plus_rgb_never_rgba(flask_app):
    """The Light Studio's 4-channel fixture is "Dimmer + RGB (4ch)", sent
    as [intensity, R, G, B] (lights-engine.js dmxFrame/dmxData). The rider
    called it RGBA, so a venue patching from it would run the bars in the
    wrong mode."""
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lights_store.save_show(owner["id"], None, "Four Channel Night",
                           _show_data(chans=4, output="enttec", dmxAddr={}, dmxStart=1, rigKey=None),
                           tour_show_id=sid)
    lighting = _rider(flask_app, token).split('id="rider-lighting"')[1].split("</section>")[0]
    assert "dimmer + RGB, 4 DMX channels each (dimmer, red, green, blue)" in lighting
    assert "RGBA" not in lighting


def test_a_three_channel_show_stays_rgb(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lights_store.save_show(owner["id"], None, "Three Channel Night", _show_data(), tour_show_id=sid)
    lighting = _rider(flask_app, token).split('id="rider-lighting"')[1].split("</section>")[0]
    assert "RGB, 3 DMX channels each" in lighting
    assert "dimmer" not in lighting and "RGBA" not in lighting


def test_a_rig_name_that_no_longer_fits_the_show_is_not_printed(flask_app):
    """A show made from "Club 8-bar" and cut to 6 bars keeps rigName in the
    Studio (the bar and channel handlers never clear it). The rider said
    "6 wash bars ... on the Club 8-bar rig"."""
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lights_store.save_show(owner["id"], None, "Cut Down",
                           _show_data(bars=6, chans=4, dmxAddr={}, dmxStart=1,
                                      rigKey="club8", rigName="Club 8-bar"), tour_show_id=sid)
    body = _rider(flask_app, token)
    assert "6 wash bars" in body and "Club 8-bar" not in body


def test_a_rig_name_is_printed_while_the_rig_still_fits(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lights_store.save_show(owner["id"], None, "Full Club",
                           _show_data(bars=8, chans=4, dmxAddr={}, dmxStart=1,
                                      rigKey="club8", rigName="Club 8-bar"), tour_show_id=sid)
    assert '"Club 8-bar" rig' in _rider(flask_app, token)


def test_a_saved_rig_is_named_only_while_its_shape_matches(flask_app):
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    rig_id, err = lights_store.save_rig(owner["id"], None, "Basement Six", {"bars": 6, "chans": 3})
    assert err is None
    lib_id = lights_store.save_show(owner["id"], None, "On Basement",
                                    _show_data(bars=6, chans=3, dmxAddr={}, dmxStart=1,
                                               rigKey=rig_id, rigName="Basement Six"), tour_show_id=sid)
    assert '"Basement Six" rig' in _rider(flask_app, token)
    lights_store.save_show(owner["id"], lib_id, "On Basement",
                           _show_data(bars=6, chans=4, dmxAddr={}, dmxStart=1,
                                      rigKey=rig_id, rigName="Basement Six"), tour_show_id=sid)
    assert "Basement Six" not in _rider(flask_app, token), "channel width changed since the rig"
    # A name with no rig behind it (an imported show, rigKey null) proves nothing.
    lights_store.save_show(owner["id"], lib_id, "On Basement",
                           _show_data(bars=6, chans=3, dmxAddr={}, dmxStart=1,
                                      rigKey=None, rigName="Basement Six"), tour_show_id=sid)
    assert "Basement Six" not in _rider(flask_app, token)


def test_a_bar_patched_past_the_end_of_the_universe_is_said_to_get_no_signal(flask_app):
    """lights-engine.js skips a bar when addr + chans - 1 > 512. The rider
    listed it at 510 as though it were patched."""
    c, owner, tid, sid, token = _date_with_rider(flask_app)
    lights_store.save_show(owner["id"], None, "Edge Patch",
                           _show_data(bars=2, chans=4, dmxStart=1, dmxAddr={"2": 510}, rigKey=None),
                           tour_show_id=sid)
    lighting = _rider(flask_app, token).split('id="rider-lighting"')[1].split("</section>")[0]
    assert "bar 1 at 1" in lighting
    assert "bar 2 at 510" not in lighting
    assert "bar 2 not sent (patched past the end of the universe)" in lighting


def test_the_rider_knows_the_studios_rig_presets():
    """rider_lights checks a preset rig's shape against lights-engine.js
    RIG_PRESETS; the two lists must not drift apart."""
    import os
    import re
    js = open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "lights-engine.js"),
              encoding="utf-8").read()
    found = {m.group(1): (int(m.group(2)), int(m.group(3)))
             for m in re.finditer(r'\{key: "(\w+)", name: "[^"]*", bars: (\d+), chans: (\d+)', js)}
    assert found and found == lights_store.RIG_PRESET_SHAPES
