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
    data = {"name": "", "bars": 4, "chans": 3, "dmxStart": 10, "dmxAddr": {"3": 100},
            "dmxUniverse": 2, "output": "artnet", "rigName": "Club rig",
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
    assert "Club rig" in body and "5 programmed cues" in body
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
    got = lights_store.rider_lights({"name": "", "data": {"bars": 3, "chans": 3, "dmxStart": 511,
                                                          "output": "sacn", "name": "From data"}})
    assert got["name"] == "From data"
    assert got["patch"] == [(1, 511), (2, 512), (3, 512)], "clamped to the universe, never wrapped"
    assert got["output_words"].startswith("sACN")
