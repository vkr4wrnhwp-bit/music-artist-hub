"""The Studio Room: the room's opening screen (owner's mockup, 2026-09-22).

It opens on a photographed master bus analyser carrying the artist's last
measured master. What these lock:

  a null reading is WORDS, never 0 - -0.0 dBTP would read as a clipping master
  no bit depth is printed, because the Rack does not store one
  the figures live on the unit, not in a strip of stat cards above it
  Release-Ready and Mix Check are two tiles, because they are two pages
  the hardware is a photograph; only the moving parts are drawn
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

def test_an_empty_account_opens_on_the_unit_not_on_an_empty_state():
    """The room opens on the instrument whatever the account holds - the
    same mistake as Stage, made once and not again. The plate is always
    drawn; only its windows are empty."""
    c, _uid = _account()
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "studio-bus-plate" in body, "the photographed unit is always there"
    assert "No master measured yet" in body
    assert "No artwork yet" in body
    assert body.count("Not measured yet") == 2, "both readouts, in words"
    assert "rk-calm" not in body, "no collapsed empty state stood in for it"


def test_the_standard_is_named_because_a_loudness_figure_needs_one():
    c, _uid = _account()
    body = _room(c.get("/room/studio").get_data(as_text=True))
    assert "ITU-R BS.1770" in body and "EBU R128" in body
    assert "encoder has the last word" in body


def test_the_room_never_claims_a_track_is_released_or_approved():
    c, _uid = _account()
    body = _room(c.get("/room/studio").get_data(as_text=True))
    for claim in ("Approved", "Released", "Will pass", "Guaranteed",
                  "Ready for Spotify"):
        assert claim not in body, claim
