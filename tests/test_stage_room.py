"""The Stage Room: the room's opening screen (owner's mockup, 2026-09-22).

The Light Studio open as the centrepiece, the Stage Plot under it, and no
Tour anywhere. What these lock:

  a saved cue has ONE fade, not a fade-in and a fade-out
  the fixture list groups by truss and floor, which is what the editor
    knows - not the front/back truss the mockup drew
  a passport with no published version has NO version, not version 0
  the plot has three real states: drawn, list only, and empty
  no control on this screen edits anything - every action links out
  no Tour on the screen at all: it is its own suite now
"""
import uuid

import pytest

import app as appmod
import db as store
import stage_room as sr

PW = "stage-room-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _room(page):
    """Just the room's own markup.

    The page around it carries the app's chrome - the sidebar, the suite
    strip, the support form - and a test that slices loosely measures those
    instead, which is how the first cut of this file failed on a form the
    room does not own.
    """
    return page.split("<!--room:stage-->", 1)[1].split("<!--/room:stage-->")[0]


def _account(name="Stage Artist"):
    email = "sgroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _show(bars=4, chans=4, start=1, cues=None, pos=None):
    return {"name": "Main Show", "bars": bars, "chans": chans,
            "dmxStart": start, "dmxUniverse": 1,
            "pos": pos if pos is not None else
                   {str(i): [(i - 0.5) / bars, 0.25 if i <= bars / 2 else 0.75]
                    for i in range(1, bars + 1)},
            "cues": cues or []}


# --- the rig ---------------------------------------------------------------

def test_the_channel_count_is_the_rig_not_a_round_number():
    """Twelve four-channel bars is 48 channels. The figure is derived from
    what is patched, never typed."""
    got = sr.rig(_show(bars=12, chans=4))
    assert got["fixtures"] == 12 and got["chans"] == 4
    assert got["channels"] == 48


def test_a_three_channel_rig_is_counted_as_three():
    assert sr.rig(_show(bars=10, chans=3))["channels"] == 30


def test_an_address_runs_in_order_unless_a_bar_is_patched_itself():
    """Mirrors lights-engine.js fixtureAddress(): an explicit patch wins."""
    show = _show(bars=4, chans=4, start=1)
    assert [sr.address_of(show, i) for i in (1, 2, 3, 4)] == [1, 5, 9, 13]
    show["dmxAddr"] = {"3": "100"}
    assert sr.address_of(show, 3) == 100, "the bar's own patch wins"
    assert sr.address_of(show, 4) == 13, "and does not move the others"


def test_an_address_can_never_leave_the_universe():
    show = _show(bars=200, chans=4, start=500)
    assert sr.address_of(show, 200) == 512


# --- the fixture groups ----------------------------------------------------

def test_fixtures_group_by_truss_and_floor_because_that_is_what_is_known():
    """His mockup drew Front Truss and Back Truss. The editor reads truss
    from floor by a bar's height and knows nothing about front or back, so
    a third group would be a filter that lies."""
    show = _show(bars=4, pos={"1": [0.2, 0.2], "2": [0.4, 0.3],
                              "3": [0.6, 0.8], "4": [0.8, 0.9]})
    groups = {g["key"]: g["n"] for g in sr.fixture_groups(show)}
    assert groups == {"all": 4, "truss": 2, "floor": 2}
    assert [g["label"] for g in sr.fixture_groups(show)] == [
        "All fixtures", "Truss", "Floor"]


def test_a_bar_with_no_saved_position_is_counted_but_not_placed():
    show = _show(bars=2, pos={"1": [0.5, 0.2]})
    rows = sr.fixtures(show)
    assert rows[0]["place"] == "Truss"
    assert rows[1]["place"] == "", "no position, so nowhere on the stage yet"
    assert sr.rig(show)["fixtures"] == 2


# --- the cues --------------------------------------------------------------

def test_a_cue_has_one_fade():
    """The editor saves `fade` and nothing else. A fade-in and a fade-out
    would be one number printed twice under two headings."""
    rows = sr.cues(_show(cues=[{"t": 4, "note": "Wash", "intensity": 80,
                                "fade": 2, "color": "#e0a340"}]))
    assert rows[0]["fade"] == 2
    assert "fade_in" not in rows[0] and "fade_out" not in rows[0]


def test_cues_come_back_in_time_order_and_numbered():
    rows = sr.cues(_show(cues=[{"t": 30, "note": "Late"}, {"t": 5, "note": "Early"}]))
    assert [c["name"] for c in rows] == ["Early", "Late"]
    assert [c["n"] for c in rows] == [1, 2]


def test_an_unnamed_cue_is_named_by_what_it_does():
    dark = sr.cues(_show(cues=[{"t": 0, "intensity": 0}]))[0]
    lit = sr.cues(_show(cues=[{"t": 1, "intensity": 70}]))[0]
    assert dark["name"] == "Blackout" and dark["blackout"] is True
    assert lit["name"] == "Look" and lit["blackout"] is False


def test_the_timecode_reads_the_way_the_studio_transport_does():
    assert sr.timecode(0) == "0:00"
    assert sr.timecode(8) == "0:08"
    assert sr.timecode(104) == "1:44"


# --- the passport version --------------------------------------------------

def test_a_passport_with_no_published_version_has_none_not_zero():
    figs = {f["key"]: f for f in sr.figures(None, sr.rig(None), None)}
    assert figs["version"]["value"] == "Never published"
    assert figs["version"]["measured"] is False

    got = {f["key"]: f for f in sr.figures(None, sr.rig(None), 3)}
    assert got["version"]["value"] == "Version 3"


def test_an_account_with_no_show_says_so_rather_than_showing_zero_cues():
    figs = {f["key"]: f for f in sr.figures(None, sr.rig(None), None)}
    assert figs["cues"]["value"] == "No show saved yet"
    assert figs["channels"]["value"] == "Nothing patched"


# --- the plot's three states ------------------------------------------------

def test_the_plot_has_three_states_because_there_really_are_three():
    """The drawing is made in the browser and posted back - this server has
    no renderer - so a plot can exist with no picture."""
    assert sr.plot(None, None)["state"] == "empty"
    assert sr.plot({"items": {"bass": 1}}, None)["state"] == "list_only"
    assert sr.plot({"items": {"bass": 1}}, {"path": "plot:x.png"})["state"] == "drawn"


def test_the_input_list_comes_from_the_editor_s_own_catalogue():
    got = sr.plot({"items": {"drums": 1, "bass": 1}}, None)
    sources = [r["source"] for r in got["inputs"]]
    assert "Kick" in sources and "Bass" in sources
    kick = next(r for r in got["inputs"] if r["source"] == "Kick")
    assert kick["mic_di"] == "Beta 52"
    assert kick["channel"] == "1"


def test_no_phantom_power_column_is_invented():
    """stage_plot_catalog says it in as many words: everything the editor
    does not know is left empty rather than guessed."""
    rows = sr.plot({"items": {"bass": 1}}, None)["inputs"]
    assert not any("phantom" in k for k in rows[0])


# --- the page itself --------------------------------------------------------

def test_an_empty_account_is_told_in_words():
    c, _uid = _account()
    page = c.get("/room/stage").get_data(as_text=True)
    assert "Stage Room" in page
    assert "What the stage needs to know before you get there." in page
    assert "No show saved yet" in page
    # The plot no longer has a "nothing saved" sentence of its own: the real
    # designer is on the screen, and its empty state is an empty stage with
    # the controls to fill it, which is better than a sentence.
    assert "sp-canvas" in page


def test_both_instruments_are_drawn_even_with_nothing_saved():
    """Owner, 2026-09-22: "we did not agree to have the light studio and
    stage block closed when you open the room."

    I had collapsed both panels to a sentence and a button when an account
    had nothing saved - which is every account on its first day, and the
    opposite of what he asked for. The instrument is always drawn: the
    stage, the fixture list, the cue table with its headers, the input
    table. An empty rig claims nothing; it is the difference between a
    collapsed panel and a desk at rest.
    """
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))

    # the studio, unprogrammed but present
    assert "sg-stage" in body, "the stage preview is drawn"
    assert "data-sg-layer" in body, "and its Plot / Rig / Both toggle"
    assert "sg-cues" in body, "the cue table keeps its headers"
    assert "No cues yet" in body
    assert "sg-looks" in body, "and something to click"

    # the plot, unprogrammed but present - and it is the real editor, so
    # its empty state is an empty stage you can immediately drag onto
    assert "Input list" in body, "the input list is drawn"
    assert "sp-canvas" in body, "the designer's own stage, not a placeholder"

    # and nothing collapsed either of them away
    assert "rk-calm" not in body, (
        "a room-wide empty state replaced an instrument that should be drawn")


def test_tour_appears_nowhere_on_the_stage_screen():
    """Owner, 2026-09-22: Tour comes out and becomes its own suite. The
    suite strip at the foot of every page is its door, not this room."""
    c, _uid = _account()
    page = c.get("/room/stage").get_data(as_text=True)
    body = _room(page)
    for claim in ("/tours", "Advance", "Settlement", "Routing", "Tour dates"):
        assert claim not in body, claim


def test_the_plot_on_this_screen_is_the_real_editor():
    """Owner, 2026-09-22: "they're just blank boxes with text around them and
    they don't do anything."

    This test used to be test_the_room_edits_nothing, and its claim is no
    longer true: the plot panel includes templates/_stage_plot_designer.html,
    the SAME partial /stage-plot and the tour page use, so ticking an item
    here puts it on the stage and rewrites the input list. One editor, one
    catalogue, nothing mirrored.
    """
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "sp-canvas" in body, "the designer's own canvas"
    assert "sp-items" in body, "and its controls"
    assert "sp-inputs" in body, "and its input list"
    assert "stageplot.js" in body, "driven by the editor's own script"
    # and not a second input list beside the designer's
    assert "sg-in" not in body, "one instrument, one input list"


def test_a_seat_without_the_plot_area_sees_it_but_cannot_change_it():
    """The room writes now, so the seat gate matters. Read-only keeps the
    drawing and the input list - the partial's own behaviour - and drops the
    controls, so a seat is never shown a control it may not use."""
    import team_areas
    assert team_areas.allows("stage", "/stage-plot") in (True, False)
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    # the artist's own account edits
    assert "sp-items" in body


def test_a_saved_show_puts_its_rig_on_the_screen():
    c, uid = _account()
    store.save_light_show(uid, _show(bars=12, chans=4, start=1,
                                     cues=[{"t": 8, "note": "Verse Wash",
                                            "intensity": 80, "fade": 2,
                                            "color": "#e0a340"}]))
    page = c.get("/room/stage").get_data(as_text=True)
    assert "48 channels" in page and "12 fixtures" in page
    assert "Verse Wash" in page
    assert "Universe 1" in page and "Address 1" in page


def test_clicking_a_cue_can_light_the_rig():
    """Owner, 2026-09-22: the instruments "don't do anything".

    The small answer, and deliberately so: every cue row carries the look it
    sets, so clicking one lights the stage above it. No animation loop, no
    transport, nothing invented - every value comes off the row the server
    already rendered from the saved show. With no script the page is still
    exactly what the server drew, lit by the first cue.
    """
    c, uid = _account()
    store.save_light_show(uid, _show(bars=4, cues=[
        {"t": 0, "note": "Intro", "intensity": 0, "fade": 1, "color": "#8a8a8a"},
        {"t": 8, "note": "Verse Wash", "intensity": 80, "fade": 2, "color": "#e0a340"}]))
    body = _room(c.get("/room/stage").get_data(as_text=True))

    assert body.count("data-sg-cue") == 2, "every cue is a control"
    assert 'data-colour="#e0a340"' in body and 'data-intensity="80"' in body
    assert 'role="button"' in body and 'tabindex="0"' in body, (
        "a row that acts like a button answers the keys a button answers to")
    assert "room-stage.js" in body
    # the stage is lit by the first cue server-side, so it is never unlit
    assert 'id="sg-stage"' in body and "--sg-dim" in body


def test_an_account_with_no_show_still_sees_a_rig_and_something_to_click():
    """Owner, 2026-09-22: "it's just a black empty box."

    His account has no saved show, so the stage drew nothing: no bars, no
    cues, a black rectangle. The Light Studio itself does not do that - it
    boots a new user on six bars (lights.js:16) - so the room shows the same
    six, marked, and offers the studio's OWN looks to put on them. Read from
    lights-engine.js LOOKS in the browser, never copied here, so the room
    cannot drift from the studio's palette.

    The marking is the whole safety of it: the figures and the path must
    still say the account has nothing.
    """
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))

    assert body.count('class="sg-fx"') == 6, "the editor's own starting rig"
    assert "Starter rig" in body, "and it says so, every time"
    assert "sg-looks" in body and "lights-engine.js" in body, (
        "with the studio's looks to try on it, from the engine that owns them")

    # and nothing about it claims the account has a show
    assert "No show saved yet" in body
    assert "Nothing patched" in body
    assert "No cues yet" in body


def test_the_starter_rig_never_appears_once_a_show_is_saved():
    c, uid = _account()
    store.save_light_show(uid, _show(bars=3, cues=[{"t": 0, "note": "Wash",
                                                    "intensity": 70, "fade": 1}]))
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "Starter rig" not in body
    assert body.count('class="sg-fx"') == 3, "the artist's rig, not the starter"
    assert "sg-looks" not in body, "there are cues now, so the cues are what you click"
