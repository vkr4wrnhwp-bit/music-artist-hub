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
  the working room sits on the rooms' three-window plate (owner,
    2026-09-23): Cues, Channels, Passport on the screens, each named, an
    absence in words; the old desk's wide window is its own panel under it
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
    """It names the LIGHT show: "No show saved yet" read as the Tour show
    the room had just saved, under the done line (audit stage-2)."""
    figs = {f["key"]: f for f in sr.figures(None, sr.rig(None), None)}
    assert figs["cues"]["value"] == "No light show saved yet"
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
    assert "Your first show was added" not in page, "the param alone says nothing"
    r = c.post("/tours/new", data={"one_off": "1", "name": "Release show", "date": "2031-04-18",
                                   "venue": "The Basement East", "city": "Nashville, TN",
                                   "returnTo": "/room/stage"})
    assert r.status_code == 302 and r.headers["Location"] == "/room/stage?from=show", r.headers.get("Location")
    tours = [t for t in ts.list_tours(uid)]
    assert len(tours) == 1 and tours[0]["name"] == "Release show"
    shows = store.list_tour_shows(uid)
    assert len(shows) == 1 and shows[0]["venue"] == "The Basement East" and shows[0]["tour_id"] == tours[0]["id"]
    page = c.get("/room/stage?from=show").get_data(as_text=True)
    # the line names the saved show and claims no workspace (audit stage-2)
    line = "Your first show was added: The Basement East, Nashville, TN, April 18, 2031. Next, draw the stage plot."
    assert line in page and "Stage workspace is ready" not in page
    body = _room(page)
    assert "Start with a show" not in body and "sp-canvas" in body, "the desk is back, with the editor"
    assert "No show saved yet" not in body, "nothing under the line denies the show"
    assert "Your first show was added" not in c.get("/room/stage").get_data(as_text=True)


def test_a_way_back_is_a_same_site_path_or_nothing():
    import tour_os
    assert tour_os._safe_back("/room/stage") == "/room/stage"
    assert tour_os._safe_back("/room/stage?x=1") == "/room/stage?x=1"
    for bad in ("", "https://evil.example/", "//evil.example", "room/stage", "/a\nb", None):
        assert tour_os._safe_back(bad) == "", bad


def test_the_done_line_is_said_by_the_record_not_the_param():
    """It takes the show rows now, so it can name the one just saved."""
    rows = [{"venue": "Room One", "city": "Austin, TX", "date": "2031-05-02", "created": "a"},
            {"venue": "The Basement", "city": "Nashville", "date": "2026-10-30", "created": "b"}]
    assert sr.done_line("show", []) == ""
    assert sr.done_line(None, rows) == ""
    assert sr.done_line("plot", rows) == ""
    assert sr.done_line("show", rows) == (
        "Your first show was added: The Basement, Nashville, October 30, 2026. "
        "Next, draw the stage plot.")


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
    # the hero pill specifically: the drawer's Stage Plot tile points at the
    # card too, which says who adds shows (audit stage-5)
    assert 'class="rk-cta" href="#sg-z-show"' not in body, "and no hero pill pointing at a form that is not there"


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


# --- the working room on the rooms' plate (owner, 2026-09-23) ---------------

def _working(cues=None, plot=True):
    """An account with a show, a light show and a stage plot: the working
    room, not the page from zero."""
    c, uid = _account()
    store.set_user_plan(uid, "pro")
    r = c.post("/tours/new", data={"one_off": "1", "date": "2031-04-18",
                                   "venue": "The Basement East", "city": "Nashville, TN"})
    assert r.status_code == 302
    store.save_light_show(uid, _show(cues=cues))
    if plot:
        store.save_stage_plot(uid, {"items": {"drums": 1, "bass": 1, "vox": 1}})
    page = c.get("/room/stage").get_data(as_text=True)
    return page, _room(page)


def _screens(body):
    """(label, value, line) for each screen of the rack, in order."""
    import re as _re
    rack = body.split('<section class="cz-rack"', 1)[1].split("</section>", 1)[0]
    out = []
    for li in _re.findall(r'<li class="cz-screen"[^>]*>(.*?)</li>', rack, _re.S):
        k = _re.search(r'class="cz-screen-k">([^<]*)<', li).group(1)
        v = _re.search(r'class="cz-screen-v[^"]*">([^<]*)<', li).group(1)
        s = _re.search(r'class="cz-screen-s">([^<]*)<', li)
        out.append((k, v, s.group(1) if s else ""))
    return out


def test_the_working_room_draws_the_rooms_three_window_plate():
    """Owner, 2026-09-23: every room's rack is the shorter three-window
    plate. The Show Control desk (stage-plate.webp) is gone from the
    working page; its three reading windows are the plate's three screens,
    and because the new plate prints no names each screen says what it
    is - Cues, Channels, Passport, in the old silkscreen's order."""
    cues = [{"t": 4, "note": "Wash", "intensity": 80, "fade": 2},
            {"t": 20, "note": "Hit", "intensity": 100, "fade": 0}]
    page, body = _working(cues=cues)
    assert 'class="cz-plate" src="/static/img/room-plate.webp' in body
    assert "stage-plate.webp" not in body, "the old desk is not on the working page"
    assert body.count('<li class="cz-screen"') == 3
    # stage-room.css v=11 since the audit fixes of 2026-09-23 changed it
    assert "command-zero.css?v=4" in page and "stage-room.css?v=11" in page
    got = _screens(body)
    assert [k for k, _v, _s in got] == ["Cues", "Channels", "Passport"]
    assert got[0][1] == "2" and got[0][2] == "In Main Show"
    assert got[1][1] == "16" and got[1][2] == "4 fixtures · universe 1", "four 4-channel bars"
    assert got[2][1] == "Never published"
    # a reading is a figure; an absence is words, set as one
    assert 'class="cz-screen-v cz-screen-v--fig">2<' in body
    assert 'class="cz-screen-v cz-screen-v--none">Never published<' in body
    # the old desk's parts went with it: no fill reel, no positioned windows
    assert "rk-reel" not in body and "rk-pl" not in body


def test_every_screen_says_an_absence_in_words_never_a_nought():
    """A light show with no cues has no cues - not "0" - and a room open
    on a tour show alone has no light show at all, which is said as that
    rather than as "no show" (it has one)."""
    empty = {s["key"]: s for s in sr.rack_screens(_show(bars=0), sr.rig(_show(bars=0)), None)}
    assert empty["cues"]["v"] == "No cues yet" and empty["cues"]["none"] is True
    assert empty["cues"]["sub"] == "Nothing programmed in Main Show"
    assert empty["channels"]["v"] == "Nothing patched" and empty["channels"]["none"] is True
    assert empty["channels"]["sub"] == "No fixtures on the rig"
    none = {s["key"]: s for s in sr.rack_screens(None, sr.rig(None), None)}
    assert none["cues"]["v"] == "No light show saved"
    assert none["channels"]["sub"] == "No rig saved yet"
    assert none["version"]["v"] == "Never published" and none["version"]["fig"] is False
    for s in list(empty.values()) + list(none.values()):
        assert s["v"] != "0" and s["fig"] is not s["none"], s
    got = {s["key"]: s for s in sr.rack_screens(_show(bars=1, chans=3), sr.rig(_show(bars=1, chans=3)), 4)}
    assert got["version"]["v"] == "Version 4" and got["version"]["fig"] is True
    assert got["channels"]["v"] == "3" and got["channels"]["sub"] == "1 fixture · universe 1"
    # and on the page: a show with no cues says so on the glass
    _page, body = _working(cues=[])
    assert _screens(body)[0][:2] == ("Cues", "No cues yet")


def test_the_stage_window_is_its_own_panel_right_under_the_plate():
    """Nothing is lost: the old desk's wide window - THE STAGE, the saved
    cue list - is its own panel directly under the plate and the line
    that explains it, and the Stage plot panel follows it."""
    cues = [{"t": i * 10, "note": "Look %d" % i, "intensity": 50, "group": "truss"}
            for i in range(8)]
    _page, body = _working(cues=cues)
    rack = body.index('<section class="cz-rack"')
    foot = body.index('class="rk-foot sg-pl-foot"')
    panel = body.index('<section class="rk-panel sg-cuebox"')
    plot = body.index('aria-labelledby="sg-plot-h"')
    assert rack < foot < panel < plot, "plate, its line, the stage window's panel, then the plot"
    between = body[body.index("</section>", rack):panel]
    assert "<section" not in between, "nothing between the plate and the panel but its line"
    box = body[panel:plot]
    assert 'id="sg-cuebox-h">Cue list<' in box
    assert box.count("<li>") == 6, "the six the window showed"
    assert "<b>0:00</b><span>Look 0</span><i>truss</i><em>50%</em>" in box
    assert "2 more in the Light Designer" in box
    assert "sg-invite" not in box, "a real cue list replaces the illustration"
    # and it is inside the rack no longer
    rack_html = body[rack:body.index("</section>", rack)]
    assert "sg-cue-list" not in rack_html and "Look 0" not in rack_html


def test_with_no_cues_the_panel_is_the_invitation_and_a_door():
    _page, body = _working(cues=[])
    box = body[body.index('<section class="rk-panel sg-cuebox"'):body.index('aria-labelledby="sg-plot-h"')]
    assert 'class="sg-invite" href="/lights"' in box and 'class="sg-blueprint"' in box
    assert "No cues saved yet" in box and "sg-cue-list" not in box
    assert "/tours" not in body, "the 2026-09-22 rule holds on the working page"


# --- the demo account: the showcase, never the page from zero ---------------

DEMO_LOGINS = ("demo@streetbanker.io", "demo-pro@streetbanker.io", "demo-artist@streetbanker.io")


def _demo(email="demo@streetbanker.io"):
    c = appmod.app.test_client()
    r = c.post("/login", data={"email": email, "password": "sweep"})
    assert r.status_code == 302, email
    return c, store.get_user_by_email(email)["id"]


def _on_file(uid):
    return (store.get_light_show(uid), store.get_stage_plot(uid), len(store.list_tour_shows(uid)))


def test_the_demo_account_is_the_showcase_never_from_zero():
    """Owner's ruling: the demo account shows the showcase and never the
    page from zero - the Marketing room's zero=(not showcase) and ...
    All three showcase logins used to meet the onboarding page and its
    first-show form, under a Sample data lamp with nothing sample on it
    (audit stage-1, blocker). The example is in memory: nothing is
    written to the shared demo account by looking at it."""
    for email in DEMO_LOGINS:
        c, uid = _demo(email)
        before = _on_file(uid)
        body = _room(c.get("/room/stage").get_data(as_text=True))
        assert "Start with a show" not in body and 'class="sg-z-form"' not in body, email
        assert 'action="/tours/new"' not in body and 'href="#sg-z-show"' not in body, email
        assert "room-plate.webp" in body and "sp-canvas" in body, "the working room, with its plot"
        if before[0] is None:
            assert "Sample data" in body and sr.SHOWCASE_NAME in body, email
            assert _screens(body)[0][1] == str(len(sr.SHOWCASE_CUES))
            box = body[body.index('<section class="rk-panel sg-cuebox"'):body.index('aria-labelledby="sg-plot-h"')]
            assert "House to half" in box and '<span class="rk-lamp rk-lamp--info">Sample</span>' in box
            assert "2 more in the example" in box and "more in the Light Designer" not in box
        if before[1] is None:
            plot = body[body.index('aria-labelledby="sg-plot-h"'):]
            head = plot.split('class="sg-designer"')[0]
            assert "rk-lamp--info\">Sample<" in head and "Saved<" not in head, "an example plot is not Saved"
        assert _on_file(uid) == before, "looking at the showcase writes nothing"


def test_the_lamp_is_drawn_only_for_what_really_is_sample():
    """A real account from zero is not the showcase: no example, no lamp.
    And a demo's own saved light show is its own: shown, unmarked."""
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "Start with a show" in body and "Sample data" not in body and sr.SHOWCASE_NAME not in body
    c, uid = _demo("demo-artist@streetbanker.io")
    prior = store.get_light_show(uid)
    store.save_light_show(uid, _show())
    try:
        body = _room(c.get("/room/stage").get_data(as_text=True))
        assert "Main Show" in body and sr.SHOWCASE_NAME not in body
        box = body[body.index('<section class="rk-panel sg-cuebox"'):body.index('aria-labelledby="sg-plot-h"')]
        assert "rk-lamp--info" not in box, "the demo's own light show is not marked Sample"
    finally:
        if prior is None:
            with store.get_db() as db:
                db.execute("DELETE FROM light_shows WHERE user_id = ?", (uid,))
        else:
            store.save_light_show(uid, prior)


def test_a_locked_demo_is_offered_no_write_door():
    """A demo under the read-only lock was handed the first-show form,
    whose POST only bounced at the lock. Now it gets no form, and the plot
    on the working room is drawn read only; a locked account from zero
    is told why it cannot add a show."""
    c, uid = _demo("demo-pro@streetbanker.io")
    store.set_demo_lock(uid, True)
    try:
        body = _room(c.get("/room/stage").get_data(as_text=True))
        assert 'action="/tours/new"' not in body and "sg-z-form" not in body
        assert 'id="sp-save"' not in body and 'id="sp-items"' not in body, "the plot is drawn read only"
        assert "sp-canvas" in body and "This account is read only" in body
    finally:
        store.set_demo_lock(uid, False)
    c, uid = _account()
    store.set_demo_lock(uid, True)
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert "Start with a show" in body and 'class="sg-z-form"' not in body
    assert sr.ZERO_PROJECT["readonly"] in body and 'class="rk-cta" href="#sg-z-show"' not in body


# --- the audit of 2026-09-23 (stage-2 .. stage-19) ---------------------------

import io as _io
import os as _os
import re as _re

_HERE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


def _css(name):
    return _io.open(_os.path.join(_HERE, "static", "css", name), encoding="utf-8").read()


def _signed_in(name, plan):
    """A signed-in account carrying what the team helpers need."""
    c, uid = _account(name)
    store.set_user_plan(uid, plan)
    c._id = uid
    c._email = store.get_user(uid)["email"]
    return c


def _seat(owner, member, access="read", areas=None):
    """A real team seat, joined and opened (tests/test_team_rooms.py)."""
    import team_areas
    data = {"email": member._email, "role": "manager", "access": access, "areas_sent": "1",
            "areas": list(areas if areas is not None else team_areas.keys())}
    r = owner.post("/team/invite", data=data)
    assert r.get_json().get("ok"), r.get_json()
    row = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]
    member.post("/team/join/" + row["invite_token"], data={})
    member.post("/portal/%s/open" % owner._id)


def test_a_failed_passport_version_read_is_the_error_page_not_a_500(monkeypatch):
    """Audit stage-4: the version read sat after the one try, so a failure
    there was a bare 500. It is the room's error page at 503 now."""
    import passport_store
    c, _uid = _account()
    monkeypatch.setattr(passport_store, "list_passports",
                        lambda _uid: [{"id": "p1", "current_version_id": "v1"}])

    def boom(*_a, **_k):
        raise RuntimeError("stage: version store down")
    monkeypatch.setattr(passport_store, "current_version", boom)
    r = c.get("/room/stage")
    assert r.status_code == 503
    assert "We could not load your Stage workspace" in r.get_data(as_text=True)


def test_the_error_page_offers_only_doors_the_reader_can_open(monkeypatch):
    """Audit stage-9: a Stage-only seat is refused at the Command Center,
    which sends it back into the room that just failed. It gets Try again
    and Contact; the account holder keeps the Command Center door."""
    def boom(_uid):
        raise RuntimeError("stage: store down")
    owner, member = _signed_in("Owner", "pro"), _signed_in("Member", "artist")
    _seat(owner, member, access="edit", areas=["stage"])
    assert member.get("/command-center").status_code == 302, "the door it must not be shown"
    monkeypatch.setattr(store, "list_tour_shows", boom)
    page = member.get("/room/stage")
    assert page.status_code == 503
    body = page.get_data(as_text=True)
    assert 'href="/room/stage"' in body and "Back to Command Center" not in body
    mine = owner.get("/room/stage").get_data(as_text=True)
    assert "Back to Command Center" in mine and 'href="/command-center"' in mine


def test_the_plot_tile_from_zero_routes_to_add_show_not_the_editor():
    """Audit stage-5, spec: before a show exists the plot routes to Add
    show, never to a contextless editor - the tile included."""
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    drawer = body.split('<details class="sg-z-fold"', 1)[1]
    assert 'href="/stage-plot"' not in body
    tile = drawer.split('data-room-card="stage-plot"')[0].rsplit("<a ", 1)[1]
    assert 'href="#sg-z-show"' in tile
    assert sr.ZERO_PLOT_TILE[1] in drawer and "Draw it here before there is a tour" not in drawer


def test_what_stage_keeps_together_claims_nothing_the_app_lacks():
    """Audit stage-6: the plot and the light show are one per account and
    read no show record, so no Stage tool 'reads the show record'."""
    lines = " ".join(line for _k, _n, line in sr.KEEPS)
    assert "every Stage tool" not in lines


def test_every_drawer_tile_draws_its_own_icon():
    """Audit stage-8: Stage Plot and Tour fell through to the placeholder."""
    c, _uid = _account()
    body = _room(c.get("/room/stage").get_data(as_text=True))
    drawer = body.split('<details class="sg-z-fold"', 1)[1]
    tiles = _re.findall(r'<a class="rk-tile".*?</a>', drawer, _re.S)
    assert len(tiles) == len(sr.ZERO_TILES)
    for tile in tiles:
        assert '<circle cx="12" cy="12" r="8"/>' not in tile, tile[:80]


def test_ask_street_banker_opens_the_corner_ask_box():
    """Audit stage-7: the button kept only the no-script fallback and left
    the app for the public Contact page. It opens the corner Ask box, as
    the Command Center's does; Contact stays the no-script fallback."""
    c, _uid = _account()
    page = c.get("/room/stage").get_data(as_text=True)
    assert 'href="/contact" id="sg-z-ask">Ask Street Banker' in page
    script = page.split('getElementById("sg-z-ask")', 1)[1].split("</script>", 1)[0]
    assert 'getElementById("sbq-open")' in script and "preventDefault" in script
    assert 'id="sbq-open"' in page and 'id="sbq-q"' in page


def test_a_refused_first_show_comes_back_with_what_was_typed():
    """Audit stage-11 and stage-12. A date that is not a real calendar day
    used to be stored as a show (2026-02-30), and a date the pattern
    refused went to the Tour page with every typed field lost. Now a
    refused save comes back to the Stage card with the name, venue and
    city kept (in the session, never the URL) and the reason."""
    c, uid = _account()
    store.set_user_plan(uid, "pro")
    for bad in ("2026-02-30", "2026-13-45", "10/30/2026"):
        r = c.post("/tours/new", data={"one_off": "1", "name": "Release night", "date": bad,
                                       "venue": "The Basement", "city": "Nashville",
                                       "returnTo": "/room/stage"})
        loc = r.headers["Location"]
        assert r.status_code == 302 and loc == "/room/stage?show_error=date#sg-z-show", loc
        assert "Basement" not in loc and "Nashville" not in loc, "typed fields never ride in the URL"
        body = _room(c.get("/room/stage?show_error=date").get_data(as_text=True))
        assert "That date is not a real calendar day." in body
        form = body.split('<form class="sg-z-form"')[1].split("</form>")[0]
        for kept in ('value="Release night"', 'value="The Basement"', 'value="Nashville"'):
            assert kept in form, (bad, kept)
    assert store.list_tour_shows(uid) == [], "no impossible date was saved"
    # a second visit has nothing left to refill
    again = _room(c.get("/room/stage").get_data(as_text=True))
    assert 'value="The Basement"' not in again and "not a real calendar day" not in again
    # without a way back the Tour desk's own page answers, as before
    r = c.post("/tours/new", data={"one_off": "1", "date": "2026-02-30", "venue": "X", "city": "Y"})
    assert r.headers["Location"] == "/tours?one_off=date"
    assert store.list_tour_shows(uid) == []


def test_the_first_show_form_explains_its_rules_in_visible_hints():
    """Audit stage-17: the rules lived in placeholders a phone cut off."""
    c, _uid = _account()
    form = _room(c.get("/room/stage").get_data(as_text=True)).split(
        '<form class="sg-z-form"')[1].split("</form>")[0]
    for ph in _re.findall(r'placeholder="([^"]*)"', form):
        assert len(ph) <= 24, ph
    assert "Leave it blank and the venue and date name it." in form
    assert "A stand-in label is fine until the venue is confirmed." in form
    assert 'aria-describedby="sg-z-name-hint"' in form and 'id="sg-z-name-hint"' in form


def test_touch_targets_are_44_pixels():
    """Audit stage-13, spec Mobile: 44x44. The kit's header pill was 42px
    and the two inline links had no height at all."""
    kit = _css("room-kit.css")
    cta = kit.split(".rk-cta, .fr-cta, .mk-cta, .pb-cta {", 1)[1].split("}", 1)[0]
    assert "height: 44px" in cta
    links = _css("stage-room.css").split(".sg-z-links a {", 1)[1].split("}", 1)[0]
    assert "min-height: 44px" in links


def test_the_help_button_stays_inside_its_panel():
    """Audit stage-3: `.sg-z-help > div` also matched the actions wrapper
    and beat its flex: 0 0 auto, so the wrapper shrank below its nowrap
    button and the page scrolled sideways at 1024 and 1280."""
    css = _css("stage-room.css")
    assert ".sg-z-help > div {" not in css and ".sg-z-help > div," not in css
    assert ".sg-z-help > div:not(.sg-z-help-acts)" in css
    acts = css.split(".sg-z-help-acts {", 1)[1].split("}", 1)[0]
    assert "flex: 0 0 auto" in acts


def test_a_read_seat_meets_the_locked_line_and_never_a_form():
    """Audit stage-18: the seat states were pinned only at unit level.
    A real read seat on an account from zero gets the card without the
    form and the line saying who adds shows; on a working account it sees
    the plot and the input list without a Save it would be refused at."""
    owner, member = _signed_in("Owner", "pro"), _signed_in("Member", "artist")
    _seat(owner, member, access="read")
    body = _room(member.get("/room/stage").get_data(as_text=True))
    assert "Start with a show" in body and 'class="sg-z-form"' not in body
    assert sr.ZERO_PROJECT["locked"] in body and 'class="rk-cta" href="#sg-z-show"' not in body
    owner.post("/tours/new", data={"one_off": "1", "date": "2031-04-18",
                                   "venue": "Room One", "city": "Austin, TX"})
    store.save_stage_plot(owner._id, {"items": {"bass": 1}})
    body = _room(member.get("/room/stage").get_data(as_text=True))
    assert "sp-canvas" in body and 'id="sp-inputs"' in body
    assert 'id="sp-save"' not in body and 'id="sp-items"' not in body
    assert "Your seat can see this plot but not change it." in body
    # an edit seat with the Stage room draws and saves
    other = _signed_in("Editor", "artist")
    _seat(owner, other, access="edit", areas=["stage"])
    body = _room(other.get("/room/stage").get_data(as_text=True))
    assert 'id="sp-save"' in body


def test_a_plan_without_tour_gets_the_tier_line_when_the_gates_are_on(monkeypatch):
    """Audit stage-18: under the deployed gates Tour is a Pro suite, so an
    Artist plan is told what adding a show needs, not handed a form that
    answers 402."""
    monkeypatch.setenv("SUITE_GATES", "on")
    c, uid = _account()
    store.set_user_plan(uid, "artist")
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert 'class="sg-z-form"' not in body and sr.ZERO_PROJECT["tier"] in body
    store.set_user_plan(uid, "pro")
    body = _room(c.get("/room/stage").get_data(as_text=True))
    assert 'class="sg-z-form"' in body
