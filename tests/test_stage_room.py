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


def _light(uid):
    """One saved light show: the populated desk, not the page from zero."""
    store.save_light_show(uid, _show())


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

def test_an_empty_account_meets_the_page_from_zero_not_the_desk():
    """The page from zero (owner's Stage spec + mockup, 2026-09-23). The
    desk waits for a record; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it - with the first-show form IN the card and the plot
    editor nowhere. No nought, no progress, none of the desk's parts."""
    import re as _re
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "room-plate.webp" in body, "the rooms' photographed three-window plate"
    assert "stage-plate.webp" not in body, "the desk waits for a record"
    assert "rk-cine" not in body and "rk-reel-win" not in body, "nothing rotates"
    assert "No show saved yet" not in body and "Nothing patched" not in body
    assert "sp-canvas" not in body and "stageplot.js" not in body, "no plot editor before a show exists"
    # the three screens, the spec's words exactly
    for k, v in sr.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3
    # the header: the spec's subtitle and its one door, into the card
    assert "Turn show details into a plan everyone can use." in body
    assert 'class="rk-cta" href="#sg-z-show"' in body and "Add your first show" in body
    assert "Open the plot editor" not in body
    # the card holds the form: the Tour desk's own one-off route, the way
    # back, and only what the first save needs
    assert "Create your first Stage project" in body and "Start with a show" in body
    form = body.split('<form class="sg-z-form"')[1].split("</form>")[0]
    assert 'action="/tours/new"' in form
    assert 'name="one_off" value="1"' in form and 'name="returnTo" value="/room/stage"' in form
    for field in ('name="date" required', 'name="venue"', 'name="city"', 'name="name"'):
        assert field in form, field
    assert 'name="venue" maxlength="120" required' in form and 'name="city" maxlength="80" required' in form
    assert form.count("<input") == 6, "four fields and two hidden - nothing else"
    assert "You can complete technical details after the show is saved." in body
    # the parts, the five stages as education
    assert "What Stage keeps together" in body
    for _k, name, _l in sr.KEEPS:
        assert name in body, name
    for _k, name, line in sr.WORKFLOW:
        # "Team & tech" is escaped on the page
        assert name.replace("&", "&amp;") in body and line in body, name
    rail = body.split("How the Stage workflow works")[1].split("Your shows will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body
    # the two empties in words, help with its five questions, the drawer open
    assert "Your shows will appear here" in body and "Nothing to advance yet" in body
    assert "Need help planning your first show?" in body
    for q in sr.HELP_QUESTIONS:
        assert q in body, q
    assert '<details class="sg-z-fold" open>' in body and "More Stage tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    assert _re.findall(r'data-room-card="([a-z-]+)"', body) == list(sr.ZERO_TILES)
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert "0 shows" not in text and not _re.search(r"(?<![\d.])0%", text), "an absence is words, not a nought"
    assert "sd-needle" not in body and "Explore more tools" not in body


def test_the_first_show_is_the_tour_desk_s_record_and_comes_back_with_the_line():
    """One Show record for every Stage tool (spec): the card's form posts
    to the Tour desk's own one-off route, which names the tour after the
    event, comes back to /room/stage?from=show, and the room says what
    was made - once, from the saved show, never from the param alone."""
    import tour_store as ts
    c, uid = _account()
    store.set_user_plan(uid, "pro")
    page = c.get("/room/stage?from=show").get_data(as_text=True)
    assert sr.DONE_LINE not in page, "the param alone says nothing"
    r = c.post("/tours/new", data={"one_off": "1", "name": "Release show", "date": "2031-04-18",
                                   "venue": "The Basement East", "city": "Nashville, TN",
                                   "returnTo": "/room/stage"})
    assert r.status_code == 302 and r.headers["Location"] == "/room/stage?from=show", r.headers.get("Location")
    tours = [t for t in ts.list_tours(uid)]
    assert len(tours) == 1 and tours[0]["name"] == "Release show"
    shows = store.list_tour_shows(uid)
    assert len(shows) == 1 and shows[0]["venue"] == "The Basement East" and shows[0]["tour_id"] == tours[0]["id"]
    page = c.get("/room/stage?from=show").get_data(as_text=True)
    assert sr.DONE_LINE in page
    body = _room(page)
    assert "Start with a show" not in body and "sp-canvas" in body, "the desk is back, with the editor"
    assert sr.DONE_LINE not in c.get("/room/stage").get_data(as_text=True)


def test_a_way_back_is_a_same_site_path_or_nothing():
    import tour_os
    assert tour_os._safe_back("/room/stage") == "/room/stage"
    assert tour_os._safe_back("/room/stage?x=1") == "/room/stage?x=1"
    for bad in ("", "https://evil.example/", "//evil.example", "room/stage", "/a\nb", None):
        assert tour_os._safe_back(bad) == "", bad


def test_the_done_line_is_said_by_the_record_not_the_param():
    assert sr.done_line("show", 0) == ""
    assert sr.done_line(None, 2) == ""
    assert sr.done_line("plot", 2) == ""
    assert sr.done_line("show", 1) == sr.DONE_LINE


def test_new_account_is_empty_on_every_count_the_spec_names():
    assert sr.new_account([], [], None, None, []) is True
    assert sr.new_account([{"id": "s"}], [], None, None, []) is False
    assert sr.new_account([], [{"id": "t"}], None, None, []) is False
    assert sr.new_account([], [], {"name": "Main Show"}, None, []) is False
    assert sr.new_account([], [], None, {"items": []}, []) is False
    assert sr.new_account([], [], None, None, [{"id": "p"}]) is False


def test_the_mock_up_tour_does_not_end_the_page_from_zero(monkeypatch):
    """The Tour desk seeds an example tour with invented shows for a new
    account. Those are not the artist's records: with only a mock tour on
    file the Stage room is still from zero."""
    import tour_mockup
    c, uid = _account()
    store.set_user_plan(uid, "pro")
    c.post("/tours/new", data={"one_off": "1", "date": "2031-05-02", "venue": "Room One",
                               "city": "Austin, TX"})
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "Start with a show" not in body, "a real show: the desk"
    monkeypatch.setattr(tour_mockup, "is_mock", lambda tour_id: True)
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "Start with a show" in body, "the same tour marked as the example: from zero"


def test_who_may_add_a_show_is_told_on_the_card():
    """A seat that may not write here, or a plan without Tour, gets the
    card without the form and a line saying who adds shows - not a form
    that bounces at the Tour desk."""
    z = sr.zero_page(can_add="seat")
    assert z["project"]["can"] == "seat"
    z = sr.zero_page(can_add="tier")
    assert z["project"]["can"] == "tier"
    assert sr.zero_page()["project"]["can"] is True
    # a Fan plan has no Tour: the tier line, no form
    c, uid = _account()
    store.set_user_plan(uid, "fan")
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert 'class="sg-z-form"' not in body and "membership that includes Tour" in body
    assert 'href="#sg-z-show"' not in body, "and no hero pill pointing at a form that is not there"


def test_a_failed_read_is_the_error_page_never_a_new_account(monkeypatch):
    """Owner's spec: a failed request must never look like a new account."""
    def boom(_uid):
        raise RuntimeError("stage: store down")
    monkeypatch.setattr(store, "list_tour_shows", boom)
    c, _uid = _account()
    r = c.get("/room/stage")
    assert r.status_code == 503
    page = r.get_data(as_text=True)
    assert "We could not load your Stage workspace" in page
    assert "Your shows and plans are safe. Try loading the Room again." in page
    assert 'href="/room/stage"' in page and 'href="/command-center"' in page
    assert "Start with a show" not in page and "room-plate" not in page
    assert 'action="/tours/new"' not in page, "no form on the error page"


def test_tour_appears_nowhere_on_the_populated_stage_screen():
    """Owner, 2026-09-22: Tour comes out and becomes its own suite. The
    suite strip at the foot of every page is its door, not this room.
    The page from zero is the one exception (owner's spec, 2026-09-23):
    its first-show form posts to the Tour desk, because a show IS the
    Tour desk's record and Stage must not invent a second kind."""
    c, uid = _account()
    _light(uid)
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
    c, uid = _account()
    _light(uid)
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "sp-canvas" in body, "the designer's own canvas"
    assert "sp-items" in body, "and its controls"
    assert "sp-inputs" in body, "and its input list"
    assert "stageplot.js" in body, "driven by the editor's own script"
    # and not a second input list beside the designer's. Matched on what
    # the rule MEANS rather than on the prefix "sg-in", which also caught
    # sg-invite - the blueprint that fills THE STAGE window when nothing
    # is programmed, and not an input list at all.
    import re as _re
    mine = {c for group in _re.findall(r'class="([^"]*)"', body)
            for c in group.split() if c.startswith("sg-")}
    assert not [c for c in mine if "input" in c], (
        "one instrument, one input list: %s" % sorted(mine))


def test_a_seat_without_the_plot_area_sees_it_but_cannot_change_it():
    """The room writes now, so the seat gate matters. Read-only keeps the
    drawing and the input list - the partial's own behaviour - and drops the
    controls, so a seat is never shown a control it may not use."""
    import team_areas
    assert team_areas.allows("stage", "/stage-plot") in (True, False)
    c, uid = _account()
    _light(uid)
    body = _room(c.get("/room/stage").get_data(as_text=True))
    # the artist's own account edits
    assert "sp-items" in body


def test_the_room_is_the_plot_and_the_light_designer_is_a_card():
    """Owner, 2026-09-22: "this looks way too cheap ... hide the light
    designer, just call it light designer not light studio, and put it in one
    of the cards underneath. Leave the stage plot there."

    Why it was withdrawn is in stage_room.py's docstring, because the fix is
    known: the room drew its stage as flat SVG shapes while the Designer
    itself draws onto a photographed stage with a photographed LED bar. The
    working rig, cue and look code is in the history at 87fcbcc9.
    """
    c, uid = _account()
    _light(uid)
    body = _room(c.get("/room/stage").get_data(as_text=True))

    # the plot is the room
    assert "sp-canvas" in body and "Input list" in body

    # the designer is a card, under its new name
    assert "Light Designer" in body
    assert "Light Studio" not in body

    # and the stage view is gone, with the scripts that drove it
    assert "sg-stage" not in body
    assert "room-stage.js" not in body and "lights-engine.js" not in body


def test_the_stage_room_closes_with_four_cards():
    c, uid = _account()
    _light(uid)
    body = _room(c.get("/room/stage").get_data(as_text=True))
    import re as _re
    assert _re.findall(r'data-room-card="([a-z-]+)"', body) == [
        "lights", "passports", "tour-board", "live"]


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {k: ("/" + k, "M1", k.title(), "desc", "hidden" if k == "lights" else "live")
             for k in sr.ZERO_TILES}
    tiles = {t["key"]: t for t in sr.build(None, None, None, None, cards, zero=True)["zero_tiles"]}
    assert tiles["lights"]["state"] == "hidden" and tiles["stage-plot"]["state"] != "hidden"


def test_the_owners_hidden_mark_stays_on_a_populated_room_tile():
    """The populated room's tiles carry the owner's mark too: the same
    pill the drawer from zero shows, by the same state."""
    cards = {k: ("/" + k, "M1", k.title(), "desc", "hidden" if k == "passports" else "live")
             for k in ("lights", "passports", "tour-board", "live")}
    tiles = {t["key"]: t for t in sr.build(None, None, None, None, cards)["tiles"]}
    assert tiles["passports"]["state"] == "hidden" and tiles["lights"]["state"] != "hidden"
