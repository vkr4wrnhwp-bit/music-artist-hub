"""The Studio Room: the room's opening screen (owner's mockup, 2026-09-22).

It opens on a photographed master bus analyser carrying the artist's last
measured master. What these lock:

  a null reading is WORDS, never 0 - -0.0 dBTP would read as a clipping master
  no bit depth is printed, because the Rack does not store one
  the figures live on the unit, not in a strip of stat cards above it
  Release-Ready and Mix Check are two tiles, because they are two pages
  the hardware is a photograph; only the moving parts are drawn
  an empty account meets the page from zero; the unit waits for a record
"""
import uuid

import pytest

import app as appmod
import db as store
import studio_room as sd

PW = "studio-room-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _room(page):
    return page.split("<!--room:studio-->", 1)[1].split("<!--/room:studio-->")[0]


def _account(name="Studio Artist"):
    email = "sdroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _track(uid, title="Cell 5"):
    store.add_os_track(uid, title)


# --- a null is never a zero, and here it matters more than usual ----------

def test_an_unmeasured_reading_is_words_not_zero():
    """-0.0 dBTP would read as a master clipping the ceiling and 0.0 LUFS as
    an extraordinarily loud one. Either would be alarming and wrong."""
    got = sd.decibels(None, "LUFS")
    assert got["value"] == "Not measured yet"
    assert got["measured"] is False
    assert "0" not in got["value"]


def test_a_real_reading_keeps_its_sign_and_one_decimal():
    assert sd.decibels(-9.8, "LUFS") == {"value": "-9.8", "unit": "LUFS", "measured": True}
    assert sd.decibels(-1.2, "dBTP")["value"] == "-1.2"


def test_a_genuine_zero_is_still_printed():
    """0.0 dBTP is a measurement somebody took: a master right on the
    ceiling. It must not be mistaken for the absence."""
    got = sd.decibels(0.0, "dBTP")
    assert got["value"] == "0.0" and got["measured"] is True


# --- the unit prints only what was read ----------------------------------

def test_no_bit_depth_is_printed_because_none_is_stored():
    """track_analysis stores sample_rate and channels and has NO bit-depth
    column, so a "24-bit" on the unit would be a number nobody read off the
    file."""
    line = sd.source_line({"duration": 168, "sample_rate": 44100, "channels": 2})
    assert "44.1 kHz" in line and "Stereo" in line and "2:48" in line
    assert "bit" not in line.lower()


def test_the_title_is_the_file_s_own_name_without_its_extension():
    assert sd.title_of({"filename": "Higher Places.wav"}) == "Higher Places"
    assert sd.title_of({"filename": ""}) == "Untitled measurement"
    assert sd.title_of(None) == ""


def test_a_track_with_no_duration_says_nothing_rather_than_zero():
    assert sd.clock(None) == "" and sd.clock(0) == ""
    assert sd.clock(168) == "2:48"


# --- the needles are a picture of the figure, never a substitute ---------

def test_a_needle_rests_at_the_bottom_when_nothing_was_measured():
    assert sd.needle(None) == 0.0


def test_a_needle_maps_loudness_onto_the_dial_and_cannot_leave_it():
    assert sd.needle(-30) == 0.0
    assert sd.needle(-15) == 0.5
    assert sd.needle(0) == 1.0
    assert sd.needle(-60) == 0.0, "quieter than the dial still parks at rest"
    assert sd.needle(12) == 1.0, "and louder than the dial cannot overshoot it"


# --- the five circles ----------------------------------------------------

def test_the_path_says_what_each_step_counted():
    steps = {s["key"]: s for s in sd.path(3, "Last measured today", 0, 2, None)}
    assert steps["tracked"]["line"] == "3 tracks"
    assert steps["measured"]["line"] == "Last measured today"
    assert steps["mastered"]["line"] == "No master yet"
    assert steps["art"]["line"] == "2 covers"
    assert steps["ready"]["line"] == "Never checked"
    assert steps["mastered"]["reached"] is False
    assert steps["ready"]["reached"] is False


def test_an_empty_account_reaches_nothing_and_says_so():
    steps = sd.path(0, None, 0, 0, None)
    assert not any(s["reached"] for s in steps)
    assert [s["line"] for s in steps] == [
        "No tracks yet", "Never measured", "No master yet",
        "No art yet", "Never checked"]


# --- the tiles -----------------------------------------------------------

def test_release_ready_and_mix_check_are_two_tiles_because_they_are_two_pages():
    """Owner, 2026-09-22: "if it's going to be two doors, then leave it two
    tiles." His mockup drew one Master Check tile; that needs the two pages
    merged first, and until then one tile would be a door that lies."""
    cards = {k: ("/" + k, "M1", k.title(), "desc") for k in
             ("rack", "release-ready", "studio", "remix-lab", "audio-studio",
              "artwork")}
    keys = [t["key"] for t in sd.build(None, "", [], 0, 0, None, cards)["tiles"]]
    assert keys == ["rack", "release-ready", "studio", "remix-lab",
                    "audio-studio", "artwork"]


def test_a_seat_that_cannot_open_a_page_is_not_shown_its_tile():
    cards = {"rack": ("/rack", "M1", "The Rack", "x"),
             "artwork": ("/artwork", "M1", "Cover Art", "y")}
    out = sd.build(None, "", [], 0, 0, None, cards,
                   can_open=lambda href: href != "/artwork")
    assert [t["key"] for t in out["tiles"]] == ["rack"]


# --- the page itself ------------------------------------------------------

def test_an_empty_account_meets_the_page_from_zero_not_an_empty_unit():
    """The page from zero (owner's Studio spec, 2026-09-22). The analyser
    waits for a record; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it. No nought, no progress, no reading that nobody took,
    and none of the populated room's parts."""
    import re as _re
    c, _uid = _account()
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "command-plate.webp" in body, "the photographed three-screen plate"
    assert "studio-bus-plate" not in body, "the analyser waits for a record"
    assert "rk-cine" not in body and "rk-reel-win" not in body, "nothing rotates"
    assert "Not measured yet" not in body and "No master measured yet" not in body
    assert "rk-calm" not in body, "no collapsed empty state stood in for it"
    # the three screens, the spec's words exactly, none of them a door
    for k, v in sd.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3
    assert 'class="cz-screen-v" href' not in body
    # the header: the spec's subtitle and its one door, carrying the way back
    assert "Turn a song into a release-ready package." in body
    assert 'class="rk-cta" href="/tracks?returnTo=/room/studio&amp;from=song"' in body
    assert "Open The Rack" not in body
    # the card, the parts, the five stages as education
    assert "Create your first Studio project" in body
    assert "What Studio keeps together" in body
    for _k, name, _l in sd.WORKFLOW:
        assert name in body, name
    rail = body.split("How the Studio workflow works")[1].split("Your tracks will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body
    # the two empties in words, help, and the tools folded
    assert "Your tracks will appear here" in body and "Nothing to review yet" in body
    assert "Not sure where to begin?" in body
    assert '<details class="sz-fold" open>' in body and "More Studio tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert "0 tracks" not in text and not _re.search(r"(?<![\d.])0%", text), "an absence is words, not a nought"
    # the populated room's parts are not on this page
    assert "sd-needle" not in body and "Explore more tools" not in body
    assert "From the take to the master." not in body


def test_the_song_door_carries_the_way_back_and_the_record_says_the_line():
    """?from=song alone says nothing; the saved track says the sentence."""
    c, uid = _account()
    page = c.get("/room/studio?from=song").get_data(as_text=True)
    assert sd.DONE_LINE not in page, "the param alone says nothing"
    _track(uid)
    assert sd.DONE_LINE in c.get("/room/studio?from=song").get_data(as_text=True)
    assert sd.DONE_LINE not in c.get("/room/studio").get_data(as_text=True)


def test_the_done_line_is_said_by_the_record_not_the_param():
    assert sd.done_line("song", 0) == ""
    assert sd.done_line(None, 3) == ""
    assert sd.done_line("asset", 3) == ""
    assert sd.done_line("song", 1) == sd.DONE_LINE


def test_a_seat_without_the_publishing_room_gets_no_song_door():
    """/tracks is the Publishing room's (team_areas). A Studio-only seat
    is not offered a button that bounces: the card stays and says who
    adds songs, the hero has no pill, and the links skip /tracks."""
    z = sd.zero_page(can_open=lambda href: not href.startswith("/tracks"))
    assert z["cta"] is None and z["project"]["can"] is False
    assert z["links"] and all(not href.startswith("/tracks") for _l, href in z["links"])
    z = sd.zero_page()
    assert z["cta"]["href"] == sd.SONG_DOOR and z["project"]["can"] is True
    assert len(z["links"]) == 2


def test_one_track_brings_the_unit_back_untouched():
    """One record and the room is the room: the photographed analyser with
    its own empty words, the needles at rest, the tiles in the open - and
    none of the onboarding page."""
    c, uid = _account()
    _track(uid)
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "studio-bus-plate.webp?v=" in body
    assert "No master measured yet" in body
    # Counted on the element, not the substring: each needle carries
    # "sd-needle sd-needle--left", which is two hits for one needle.
    assert body.count('<span class="sd-needle ') == 2, "the needles are hardware and stay"
    assert "From the take to the master." in body and "Open The Rack" in body
    assert "Explore more tools" in body
    assert "cz-screen" not in body and "sz-fold" not in body
    assert "Create your first Studio project" not in body


def test_the_standard_is_named_because_a_loudness_figure_needs_one():
    c, uid = _account()
    _track(uid)
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "ITU-R BS.1770" in body and "EBU R128" in body
    assert "encoder has the last word" in body


def test_the_room_never_claims_a_track_is_released_or_approved():
    c, uid = _account()
    pages = [_room(c.get("/room/studio").get_data(as_text=True))]
    _track(uid)
    pages.append(_room(c.get("/room/studio").get_data(as_text=True)))
    for body in pages:
        for claim in ("Approved", "Released", "Will pass", "Guaranteed",
                      "Ready for Spotify"):
            assert claim not in body, claim


def test_the_plate_has_a_container_context_for_its_own_text():
    """The bug the owner saw: "studio looks terrible".

    Every text size on the plate is a clamp() in cqw, because the unit
    scales and its windows are fractions. cqw resolves against an
    inline-size container and there was none, so every one of those
    declarations was invalid and the plate's text fell back to page-sized
    type and burst out of its windows.

    cqh does NOT resolve against an inline-size container, which is why
    nothing here may be sized off the height.
    """
    import io as _io
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    css = _io.open(_os.path.join(here, "static", "css", "studio-room.css"),
                   encoding="utf-8").read()
    unit = css.split(".sd-unit {", 1)[1].split("}", 1)[0]
    assert "container-type: inline-size" in unit, (
        "cqw sizes on the plate need an inline-size container or they are "
        "all invalid")
    # Comments stripped first: this file EXPLAINS the cqh trap in prose, and
    # the first cut of this test failed on its own explanation.
    import re as _re
    code = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
    assert "cqh" not in code, "cqh does not resolve against an inline-size container"


def test_the_display_does_not_draw_a_waveform_nobody_measured():
    """The Rack stores numbers, not a shape. Bars across the display would
    be inventing the artist's audio - and the striped gradient that first
    stood in for one looked like a barcode."""
    import io as _io
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    css = _io.open(_os.path.join(here, "static", "css", "studio-room.css"),
                   encoding="utf-8").read()
    wave = css.split(".sd-wave {", 1)[1].split("}", 1)[0]
    assert "repeating-linear-gradient" not in wave


def test_the_plate_image_carries_a_cache_version():
    """The owner's "it's the same as it was" after the fix shipped.

    The server was right - staging served the cropped, transparent plate -
    but the <img> had no ?v on it and the file was REPLACED in place. So a
    browser took the new stylesheet, whose fractions are measured against
    the cropped plate, and kept the old uncropped one it already had. New
    positions, old picture, white ground still there.

    Every other asset on this page is versioned. This one has to be too,
    and the version has to move whenever the plate does.
    """
    c, uid = _account()
    _track(uid)
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "studio-bus-plate.webp?v=" in body, (
        "an image replaced in place needs a cache version or browsers keep "
        "the old one")


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {k: ("/" + k, "M1", k.title(), "desc", "hidden" if k == "remix-lab" else "live")
             for k in ("rack", "release-ready", "studio", "remix-lab", "audio-studio", "artwork")}
    tiles = {t["key"]: t for t in sd.build(None, "", [], 0, 0, None, cards)["tiles"]}
    assert tiles["remix-lab"]["state"] == "hidden" and tiles["rack"]["state"] != "hidden"
