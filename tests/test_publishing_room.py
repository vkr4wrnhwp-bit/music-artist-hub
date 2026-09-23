"""The Publishing Room: the room's opening screen (owner's mockup, 2026-09-22).

The honesty rules these lock:

  a registry that has not answered is "Not measured", never 0 and never green
  something typed into a passport is never drawn as verified
  a song sits at the FURTHEST rung it reached, and the rungs sum to the works
  the Collecting count undercounts rather than over-claims, and says so
  no writer percentages are shown anywhere, because none are on file
  nothing claims a registration was accepted or a society paid
"""
import json
import re
import uuid

import pytest

import app as appmod
import db as store
import publishing_room as pb

PW = "publishing-room-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account(name="Publishing Artist"):
    email = "pbroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _song(uid, title="Cell 5"):
    """One song on file: the populated plate, not the page from zero."""
    store.add_os_track(uid, title)


def _body(page):
    return page.split('class="rk pb"', 1)[1]


def _track(title="A song", passport=None, lockbox=None):
    return {"id": uuid.uuid4().hex, "title": title, "release_title": "",
            "passport": passport or {}, "lockbox": lockbox or {}}


def _checked(track, result, works=None, asked="ISRC US-ABC-24-00001"):
    """A stored MLC answer, the shape artist_os.mlc_evidence reads."""
    track["mlc_check"] = {"result": result, "asked": asked, "works": works or []}
    return track


SIGNED_SHEET = {"split_sheet": {"file": "sheet.pdf",
                                "approvals": [{"state": "signed"}]}}


# --- the ladder -----------------------------------------------------------

def test_a_song_sits_at_the_furthest_rung_it_reached():
    none = set()
    assert pb.state_of(_track(), none) == "written"
    assert pb.state_of(_track(lockbox=SIGNED_SHEET), none) == "split_agreed"

    registered = _checked(_track(), "match",
                          [{"song_code": "T123", "share_total": 60}])
    assert pb.state_of(registered, none) == "registered"

    claimed = _checked(_track(), "match",
                       [{"song_code": "T123", "share_total": 100}])
    assert pb.state_of(claimed, none) == "claimed"

    assert pb.state_of(_track("Paid Song"), {"paidsong"}) == "collecting"


def test_collecting_outranks_a_missing_split_sheet_rather_than_hiding_it():
    """The rule the module states: furthest reached, not all-rungs-done. A
    song collecting money with no sheet on file is collecting; the missing
    sheet is a conflict, which is a different panel."""
    t = _track("Paid Song")           # no lockbox at all
    assert pb.state_of(t, {"paidsong"}) == "collecting"


def test_the_rungs_sum_to_the_works_on_file():
    tracks = [_track("One"), _track("Two", lockbox=SIGNED_SHEET),
              _checked(_track("Three"), "match",
                       [{"song_code": "T1", "share_total": 100}])]
    rungs = pb.states(tracks, set())
    assert sum(r["count"] for r in rungs) == len(tracks)
    assert [r["key"] for r in rungs] == ["written", "split_agreed",
                                         "registered", "claimed", "collecting"]


def test_only_publishing_money_counts_as_collecting():
    """A Spotify line is the master's money, not the work's. Counting it
    would tell an artist their publishing is collected when it is not."""
    rows = [{"title": "Master Money", "source": "Spotify"},
            {"title": "Work Money", "source": "The MLC"},
            {"title": "Perf Money", "source": "ASCAP"}]
    got = pb.collecting_titles(rows)
    assert got == {"workmoney", "perfmoney"}
    assert "mastermoney" not in got


def test_a_title_is_matched_on_its_letters_so_punctuation_does_not_break_it():
    assert pb.collecting_titles([{"title": "Don't Look (Remix)",
                                  "source": "MLC"}]) == {"dontlookremix"}


# --- the three figures ----------------------------------------------------

def test_nothing_asked_of_a_registry_is_not_measured_and_never_zero():
    tracks = [_track("One"), _track("Two")]
    head = pb.headline(tracks, pb.uncollected(tracks))
    by = {f["key"]: f for f in head}
    assert by["works"]["value"] == "2", "the catalogue IS counted; it is ours"
    assert by["share"]["value"] == "Not measured"
    assert by["share"]["sub"] == "No registry has answered yet"
    assert by["uncollected"]["value"] == "Not measured"
    assert by["uncollected"]["sub"] == "Nobody has asked a registry yet"


def test_an_empty_catalogue_says_so_rather_than_showing_zero_works():
    head = pb.headline([], [])
    assert [f["value"] for f in head] == ["Not measured"] * 3


def test_the_share_is_of_what_a_registry_answered_about_not_the_catalogue():
    """Two songs, one asked about and fully claimed. The share is 100% of
    the one answer we hold, not 50% of a catalogue nobody asked about."""
    tracks = [_checked(_track("Asked"), "match",
                       [{"song_code": "T1", "share_total": 100}]),
              _track("Never asked")]
    by = {f["key"]: f for f in pb.headline(tracks, pb.uncollected(tracks))}
    assert by["share"]["value"] == "100%"
    assert "1 recording" in by["share"]["sub"]


def test_uncollected_counts_only_what_a_registry_answered_about():
    tracks = [_checked(_track("No work"), "none"), _track("Never asked")]
    by = {f["key"]: f for f in pb.headline(tracks, pb.uncollected(tracks))}
    assert by["uncollected"]["value"] == "1"


# --- typed is never verified ----------------------------------------------

def test_a_typed_passport_value_never_reaches_green():
    """The whole point of the room. A claim is not evidence."""
    t = _track("Typed", passport={"mlc_status": "registered"})
    row = pb.uncollected([t])[0]
    assert row["state"] != "green"
    assert row["label"] == "typed, unverified"
    assert row["source"] == "typed"


def test_the_worst_rows_come_first():
    tracks = [_checked(_track("Good"), "match",
                       [{"song_code": "T1", "share_total": 100}]),
              _checked(_track("Bad"), "none"),
              _track("Unknown")]
    assert [r["title"] for r in pb.uncollected(tracks)] == ["Bad", "Unknown", "Good"]


# --- the splits panel, as the owner ruled ---------------------------------

def test_the_splits_panel_shows_what_is_on_file_and_no_percentages():
    t = _track("Mine", passport={"songwriters": "J. Hayes, N. Carter",
                                 "pro": "BMI"},
               lockbox=SIGNED_SHEET)
    out = pb.splits(t)
    by = {f["label"]: f for f in out["fields"]}
    assert by["Songwriters"]["value"] == "J. Hayes, N. Carter"
    assert by["Songwriters"]["on_file"] is True
    assert by["Publishers"]["on_file"] is False, "nothing typed there"
    assert out["sheet"] == "ready"
    # No share, percentage or total is produced anywhere by this function.
    assert not any("%" in str(v) for v in json.dumps(out))


def test_no_song_means_no_splits_panel_rather_than_an_empty_table():
    assert pb.splits(None) is None


# --- the tiles ------------------------------------------------------------

def test_the_tiles_carry_only_counts_that_were_counted():
    cards = {"catalog": ("/catalog", "M1", "Catalog", "every song"),
             "track-passports": ("/catalog?view=passports", "M1", "Track Passports", "one page"),
             "conflicts": ("/conflicts", "M1", "Rights Conflicts", "disagree"),
             "beats": ("/beats", "M1", "Beats", "registry and licences"),
             "fingerprints": ("/fingerprints/", "M1", "Fingerprints", "register"),
             "certified": ("/certified", "M1", "Certified", "six rungs")}
    out = pb.build([_track("One")], [], [{"title": "x", "description": "y"}],
                   None, cards)
    by = {t["key"]: t for t in out["tiles"]}
    # ONE DOOR MEANS ONE PAGE (owner, 2026-09-22): "if there's going to be
    # two pages behind it, then we don't need them to be one door ... if
    # it's going to be two doors, then leave it two tiles." Beats and
    # Fingerprints are still two pages, so they are still two tiles. They
    # become one tile when they become one page, not before.
    assert [t["key"] for t in out["tiles"]] == ["catalog", "track-passports",
                                                "conflicts", "beats",
                                                "fingerprints", "certified"]
    assert "Beat Fingerprints" not in [t["name"] for t in out["tiles"]], (
        "a single tile over two pages is a door that lies about what is "
        "behind it")
    assert by["track-passports"]["status"] == "1 record"
    assert by["conflicts"]["status"] == "1 open"
    assert by["catalog"]["status"] == "", "nothing counted it, so it says nothing"


def test_a_seat_that_cannot_open_a_page_is_not_shown_its_tile():
    cards = {"catalog": ("/catalog", "M1", "Catalog", "every song"),
             "conflicts": ("/conflicts", "M1", "Rights Conflicts", "disagree")}
    out = pb.build([], [], [], None, cards,
                   can_open=lambda href: href != "/conflicts")
    assert [t["key"] for t in out["tiles"]] == ["catalog"]


# --- the page itself ------------------------------------------------------

def test_an_empty_account_meets_the_page_from_zero_not_an_empty_plate():
    """The page from zero (owner's Publishing spec + mockup, 2026-09-23). The
    plate waits for a song; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it. No catalog total, registry count, collection number,
    chart or percentage; no five zero-count states; no blank conflict
    table - and none of the plate's parts."""
    import re as _re
    c, _uid = _account()
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert "room-plate.webp" in body, "the rooms' photographed three-window plate"
    assert "publishing-plate.webp" not in body, "the plate waits for a song"
    assert "rk-cine" not in body and "rk-reel-win" not in body and "rk-tick-win" not in body, "nothing rotates"
    assert "rk-pl-n" not in body and "pb-pl-split" not in body, "no reading, no claimed bar"
    assert "No recordings on file yet." not in body and "Nothing on file disagrees with itself." not in body, (
        "no zero-count ladder, no empty conflicts panel")
    for name in ("Written", "Split agreed", "Registered", "Claimed", "Collecting"):
        assert ">%s<" % name not in body, name + ": the five states wait for a song"
    # the three screens, the spec's words exactly, none of them a door
    for k, v in pb.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3 and 'class="cz-screen-v" href' not in body
    # the header: the spec's subtitle, the account chip kept, the one door
    assert pb.ZERO_SUBTITLE.replace("'", "&#39;") in body, "the subtitle, apostrophe escaped as the page prints it"
    assert "Publishing Artist" in body, "the account selector still says whose songs these are"
    door = pb.DOOR.replace("&", "&amp;")
    assert 'class="rk-cta" href="%s"' % door in body and "Add your first song" in body
    assert pb.DOOR == "/catalog/new?returnTo=/room/publishing&from=publishing-zero-state", "the spec's suggested route"
    # the card: one door, and the first-draft list in place
    assert "Start with one song" in body and "Create your first song record" in body
    assert 'class="pb-z-btn" href="%s"' % door in body and "Add a song</a>" in body
    assert "What information do I need?" in body
    for item in pb.FIRST_DRAFT:
        assert item.replace("\u201c", "&#8220;").replace("\u201d", "&#8221;") in body or item in body, item
    # the four categories, each a door by its own room card
    assert "What Publishing will organize" in body
    for _k, name, line, _card in pb.LENSES:
        assert name.replace("&", "&amp;") in body and line in body, name
    for href in ("/catalog?returnTo=/room/publishing", "/catalog?view=passports&amp;returnTo=/room/publishing",
                 "/conflicts?returnTo=/room/publishing"):
        assert 'class="pb-z-lens" href="%s"' % href in body, href
    # the five steps as education, numbered, Add song lit
    for _k, name, line in pb.WORKFLOW:
        assert name in body and line in body, name
    rail = body.split("How Publishing works")[1].split("Your publishing catalog will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body
    assert '<span class="rk-ring" aria-hidden="true">1</span>' in rail and ">5</span>" in rail
    # the two empties in words, help, the drawer open with Beats and Fingerprints inside
    assert "Your publishing catalog will appear here" in body and "Nothing has been verified yet" in body
    assert "never zero, registered, or collecting." in body
    assert 'href="#pb-z-flow-h">How song records work' in body
    # "Import catalog" was left out as "no catalog import exists"; one
    # does (POST /tracks/import), so the spec's second link is there, to
    # the shared form's import, carrying the way back (audit publishing-8)
    assert 'href="%s#pp-import">Import catalog' % door in body
    # the Ask link carries the id its script opens the corner Ask box by
    # (audit, 2026-09-23); /contact stays its no-script fallback
    assert "Not sure what belongs in Publishing?" in body and 'href="/contact" id="pb-ask">Ask Street Banker' in body
    assert '<details class="pb-z-fold" open>' in body and "More Publishing tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    drawer = body.split('<details class="pb-z-fold"')[1]
    drawn = _re.findall(r'data-room-card="([a-z-]+)"', drawer)
    for key in ("catalog", "track-passports", "conflicts", "beats", "fingerprints"):
        assert key in drawn, key
    assert "Writers &amp; splits" not in drawer, "a category with no page of its own is not a heading over nothing"
    # no total, no count, no nought, no chart, no percentage
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert not _re.search(r"\b0 (songs|works|records|conflicts)", text) and not _re.search(r"(?<![\d.])0%", text)
    assert "pb-bar" not in body and "The rest of this room" not in body


def test_the_shared_add_song_door_carries_the_way_back():
    """/catalog/new is the spec's suggested route, and it is the ONE
    shared add-song form (the catalog's passports view) rather than a
    second one - with the door's returnTo and from riding through."""
    c, _uid = _account()
    r = c.get(pb.DOOR)
    assert r.status_code == 302
    assert r.headers["Location"] == "/catalog?view=passports&returnTo=/room/publishing&from=publishing-zero-state"
    assert c.get("/catalog/new").headers["Location"] == "/catalog?view=passports"


def test_the_saved_song_says_the_line_never_the_param_alone():
    c, uid = _account()
    page = c.get("/room/publishing?from=publishing-zero-state").get_data(as_text=True)
    assert pb.DONE_LINE not in page, "the param alone says nothing"
    _song(uid)
    assert pb.DONE_LINE in c.get("/room/publishing?from=publishing-zero-state").get_data(as_text=True)
    assert pb.DONE_LINE not in c.get("/room/publishing").get_data(as_text=True)
    assert pb.done_line("publishing-zero-state", 0) == "" and pb.done_line(None, 2) == ""
    assert pb.done_line("publishing-zero-state", 1) == pb.DONE_LINE


def test_new_account_is_no_song_on_file():
    assert pb.new_account([]) is True and pb.new_account(None) is True
    assert pb.new_account([_track()]) is False


def test_one_song_brings_the_plate_back_untouched():
    c, uid = _account()
    _song(uid)
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    # the working room on the rooms' shared three-window plate (owner,
    # 2026-09-23): works on file, uncollected, share claimed, each named
    assert "room-plate.webp?v=" in body and "publishing-plate" not in body
    import re as _re
    assert _re.findall(r'<span class="cz-screen-k">([^<]+)</span>', body) == ["Works on file", "Uncollected", "Share claimed"]
    assert "The rest of this room" in body
    assert "Start with one song" not in body and "pb-z-fold" not in body
    for name in ("Written", "Split agreed", "Registered", "Claimed", "Collecting"):
        assert ">%s<" % name in body, name


def test_a_seat_that_may_not_write_gets_no_door_and_a_category_it_cannot_open_is_words():
    cards = {"catalog": ("/catalog", "M1", "Catalog", "x"),
             "track-passports": ("/catalog?view=passports", "M1", "Track Passports", "y"),
             "conflicts": ("/conflicts", "M1", "Rights Conflicts", "z"),
             "beats": ("/beats", "M1", "Beats", "b")}
    z = pb.zero_page(can_add="seat", can_open=lambda href: not href.startswith("/conflicts"), cards=cards)
    assert z["project"]["can"] == "seat"
    by = {l["key"]: l for l in z["lenses"]}
    assert by["conflicts"]["href"] == "" and by["catalog"]["href"] == "/catalog"
    assert by["registrations"]["href"] == "", "no Certified card for this account: words, not a door"
    assert [b["title"] for b in z["bands"]] == ["Catalog & passports", "Conflicts & clearances"]
    assert [t["key"] for t in z["bands"][1]["tiles"]] == ["beats"]
    assert pb.zero_page(cards=cards)["project"]["can"] is True


def test_a_failed_read_is_the_error_page_never_a_new_account(monkeypatch):
    """Owner's spec, Pass 1: loading and error detection. Before this the
    statement rows fell back to nothing on their own."""
    def boom(*_a, **_k):
        raise RuntimeError("publishing: store down")
    monkeypatch.setattr(store, "get_statement_rows", boom)
    c, _uid = _account()
    r = c.get("/room/publishing")
    assert r.status_code == 503
    page = r.get_data(as_text=True)
    assert "We could not load Publishing" in page
    assert 'href="/room/publishing"' in page and 'href="/catalog"' in page and "Open catalog" in page
    assert "Start with one song" not in page and "room-plate" not in page


def test_the_page_never_says_a_registration_was_accepted_or_a_society_paid():
    c, uid = _account()
    pages = [c.get("/room/publishing").get_data(as_text=True)]
    _song(uid)
    pages.append(c.get("/room/publishing").get_data(as_text=True))
    for page in pages:
        for claim in ("Registration accepted", "successfully registered",
                      "money recovered", "We collected", "Royalties recovered"):
            assert claim not in page, claim


def test_the_page_says_percentages_are_not_recorded():
    c, uid = _account()
    _song(uid)
    page = c.get("/room/publishing").get_data(as_text=True)
    assert "Writer percentages are not recorded anywhere yet." in page


def test_the_five_states_are_all_drawn_even_where_the_count_is_none():
    """A rung with nothing in it is still a rung. Hiding the empty ones
    would make a catalogue with one written song look finished."""
    c, uid = _account()
    _song(uid)
    page = c.get("/room/publishing").get_data(as_text=True)
    for name in ("Written", "Split agreed", "Registered", "Claimed", "Collecting"):
        assert ">%s<" % name in page, name


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {"catalog": ("/catalog", "M1", "Catalog", "x", "live"),
             "track-passports": ("/catalog?view=passports", "M1", "Track Passports", "y", "live"),
             "conflicts": ("/conflicts", "M1", "Rights Conflicts", "z", "live"),
             "beats": ("/beats", "M1", "Beats", "b", "hidden")}
    z = pb.zero_page(cards=cards)
    tiles = {t["key"]: t for b in z["bands"] for t in b["tiles"]}
    assert tiles["beats"]["state"] == "hidden" and tiles["catalog"]["state"] != "hidden"

# --- the demo account is the showcase, never the page from zero ------------
# Owner's ruling, the Marketing room's pattern: every non-fan demo login met
# "Start with one song" under a "Sample data" lamp that marked nothing
# (audit publishing-2, 2026-09-23). The room now hands a showcase session a
# labelled example, built in memory and read by the same engines.

def _demo(email):
    c = appmod.app.test_client()
    c.post("/login", data={"email": email, "password": "sweep"})
    return c


def test_the_demo_account_is_the_showcase_never_from_zero():
    import demo_accounts
    logins = [email for email, _name, plan in demo_accounts.ACCOUNTS if plan != "fan"]
    assert len(logins) == 3, logins
    for email in logins:
        r = _demo(email).get("/room/publishing")
        assert r.status_code == 200, email
        body = _body(r.get_data(as_text=True))
        assert "Start with one song" not in body and "Add your first song" not in body, email
        assert "pb-z-" not in body, email + ": none of the page from zero's parts"
        assert "Sample data" in body, email + ": the example is labelled as one"
        for t in pb.showcase():
            assert t["title"] in body, (email, t["title"])
        for name in ("Written", "Split agreed", "Registered", "Claimed", "Collecting"):
            assert ">%s<" % name in body, (email, name)
        # the example's songs have no passport page, so nothing links to one
        assert 'href="/tracks/showcase-' not in body, email
        assert "Nobody asked a registry about" in body, email
        assert pb.DONE_LINE not in _demo(email).get(
            "/room/publishing?from=publishing-zero-state").get_data(as_text=True), (
            email + ": the example's songs were not added by anybody")


def test_the_showcase_runs_on_the_rooms_own_engines_and_is_never_stored():
    import rights_conflicts
    tracks = pb.showcase()
    assert [pb.state_of(t, set()) for t in tracks] == [
        "claimed", "registered", "written", "split_agreed", "written"]
    assert [r["state"] for r in pb.uncollected(tracks)] == [
        "red", "yellow", "yellow", "yellow", "green"]
    found = rights_conflicts.for_account(tracks)
    assert [c["conflict_type"] for c in found] == ["Splits not agreed"], found
    assert pb.showcase() is not tracks and pb.showcase()[0] is not tracks[0], "a fresh copy each call"
    assert all(t["id"].startswith("showcase-") for t in tracks)


def test_a_real_account_never_wears_the_sample_lamp():
    c, uid = _account()
    assert "Sample data" not in c.get("/room/publishing").get_data(as_text=True)
    _song(uid)
    assert "Sample data" not in c.get("/room/publishing").get_data(as_text=True)


def test_a_locked_demo_is_offered_no_write_door():
    """A shared read-only demo's saves are refused by demo_lock_gate, so the
    room offers it no door to one - on either page."""
    c, uid = _account()
    store.set_demo_lock(uid, True)
    zero = _body(c.get("/room/publishing").get_data(as_text=True))
    assert 'class="rk-cta"' not in zero and 'class="pb-z-btn"' not in zero
    assert pb.DEMO_LOCKED in zero
    _song(uid)
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert "Works on file" in body
    assert 'class="rk-cta"' not in body, "the populated header's Add a song is a write door too"


# --- the Publishing audit of 2026-09-23 ----------------------------------------

def _landing(c):
    """Follow the room's door to the shared add-song form, as a person does."""
    r = c.get(pb.DOOR)
    assert r.status_code == 302
    loc = r.headers["Location"]
    page = c.get(loc)
    if page.status_code in (301, 302):
        loc = page.headers["Location"]
        page = c.get(loc)
    assert page.status_code == 200, loc
    return page.get_data(as_text=True)


def _hidden(page, form_action):
    form = page.split('action="%s"' % form_action, 1)[1].split("</form>", 1)[0]
    return dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form)), form


def test_the_real_add_song_form_brings_the_song_back_to_publishing():
    """publishing-1 and -15: the door carried returnTo and from to the
    shared form, the form posted neither, and the save landed on the
    catalogue - so the done line could only be reached by typing it. This
    drives the form the door opens: its own hidden fields, its own post."""
    c, uid = _account()
    page = _landing(c)
    fields, form = _hidden(page, "/tracks/add")
    assert fields == {"returnTo": "/room/publishing", "from": "publishing-zero-state"}, fields
    data = dict(fields, title="First Light", songwriters="A. Rivera, J. Cole")
    r = c.post("/tracks/add", data=data)
    loc = r.headers["Location"]
    assert loc.startswith("/room/publishing?from=publishing-zero-state&song="), loc
    tid = loc.split("song=", 1)[1]
    room = c.get(loc).get_data(as_text=True)
    assert pb.DONE_LINE in room, "the room says the line, decided by the saved song"
    assert '<option value="%s" selected>' % tid in room or "First Light" in room
    song = store.get_os_track(uid, tid)
    assert song["title"] == "First Light"
    assert song["passport"]["songwriters"] == "A. Rivera, J. Cole", "the writers went in with it"


def test_the_first_draft_takes_a_writer_or_writers_not_known_yet():
    """publishing-3: the card asks for "the title and writers now" and the
    form behind it had no writer field and no "Writers not known yet"."""
    c, uid = _account()
    page = _landing(c)
    _fields, form = _hidden(page, "/tracks/add")
    assert 'name="songwriters" required' in form
    assert 'name="writers_unknown"' in form and "Writers not known yet" in form
    # the tick lifts the writers field's requirement, in the form itself
    assert "document.getElementById('pp-writers').required = !this.checked" in form
    base = {"returnTo": "/room/publishing", "from": "publishing-zero-state"}
    # "Writers not known yet" is an answer: the song is saved with no
    # writers on file, and the passport says so rather than inventing one
    r = c.post("/tracks/add", data=dict(base, title="Unknown Writers", writers_unknown="1"))
    assert r.headers["Location"].startswith("/room/publishing?")
    assert [t["title"] for t in store.list_os_tracks(uid)] == ["Unknown Writers"]
    assert not (store.list_os_tracks(uid)[0]["passport"] or {}).get("songwriters")
    # and a plain save from the catalogue itself still lands on the catalogue
    r = c.post("/tracks/add", data={"title": "Plain", "songwriters": "Me"})
    assert "/room/" not in r.headers["Location"]


def test_the_import_carries_the_way_back_too():
    """publishing-8: the spec's "Import catalog" link opens the shared
    form's CSV import, which now carries the door's way back as well."""
    import io as _io
    c, uid = _account()
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert 'href="%s#pp-import">Import catalog' % pb.DOOR.replace("&", "&amp;") in body
    page = _landing(c)
    fields, _form = _hidden(page, "/tracks/import")
    assert 'id="pp-import"' in page
    assert fields == {"returnTo": "/room/publishing", "from": "publishing-zero-state"}
    csv = b"title,writers,isrc\nImported Song,A. Writer,USAAA2600001\n"
    r = c.post("/tracks/import", data=dict(fields, csv=(_io.BytesIO(csv), "cat.csv")),
               content_type="multipart/form-data")
    assert r.headers["Location"].startswith("/room/publishing?from=publishing-zero-state"), r.headers["Location"]
    assert pb.DONE_LINE in c.get(r.headers["Location"]).get_data(as_text=True)
    assert store.list_os_tracks(uid)[0]["passport"]["songwriters"] == "A. Writer"


def test_a_way_back_to_another_site_is_never_followed():
    c, _uid = _account()
    r = c.post("/tracks/add", data={"title": "Safe", "songwriters": "Me",
                                    "returnTo": "//evil.example/x", "from": "x"})
    assert "evil" not in r.headers["Location"]


def test_a_later_outage_never_wipes_the_registrys_answer():
    """publishing-7 and -17: after a stored 100% match, one failed lookup
    dropped the song from Claimed to Written and the room said "Nobody
    has asked". The vendor being down says nothing about the registration."""
    c, uid = _account()
    tid = store.add_os_track(uid, "Cell Five")
    works = [{"song_code": "T1", "share_total": 100}]
    store.add_track_mlc_check(uid, tid, "ISRC US-ABC-24-00001", "match", "", works)
    store.add_track_mlc_check(uid, tid, "ISRC US-ABC-24-00001", "error", "simulated outage", [])
    track = store.get_os_track(uid, tid)
    assert track["mlc_check"]["result"] == "match", "the answer, not the outage"
    assert pb.state_of(track, set()) == "claimed"
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert "Nobody has asked" not in body
    assert "song code T1" in body
    # both are still on the record, newest first
    assert [k["result"] for k in store.list_track_mlc_checks(uid, tid)] == ["error", "match"]


def test_a_failed_ask_with_no_answer_is_not_nobody_asked():
    c, uid = _account()
    tid = store.add_os_track(uid, "Never Reached")
    store.add_track_mlc_check(uid, tid, "ISRC US-ABC-24-00002", "error", "down", [])
    track = store.get_os_track(uid, tid)
    ev = __import__("artist_os").mlc_evidence(track)
    assert ev["source"] == "none" and "could not be reached" in ev["detail"]
    assert "Nobody has asked" not in ev["detail"]
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert "Nobody has asked" not in body and "No registry has answered yet" in body


def test_the_zero_chip_does_not_speak_of_figures():
    """publishing-11."""
    c, uid = _account()
    zero = c.get("/room/publishing").get_data(as_text=True)
    assert "The account these figures are for" not in zero
    assert "The account this room is for" in zero
    _song(uid)
    assert "The account these figures are for" in c.get("/room/publishing").get_data(as_text=True)


def test_the_drawer_is_named_once_and_ask_opens_the_box():
    """publishing-12: the summary and an sr-only h2 said the same words, so
    the drawer's name was read twice. And "Ask Street Banker" opens the
    corner Ask box on the page, as the Command Center's does."""
    c, _uid = _account()
    body = c.get("/room/publishing").get_data(as_text=True)
    assert body.count(">More Publishing tools<") == 1
    assert ('<summary class="pb-z-fold-sum"><h2 class="pb-z-fold-h" id="pb-z-tools-h">'
            'More Publishing tools</h2>') in body
    assert 'href="/contact" id="pb-ask"' in body
    script = body.split('getElementById("pb-ask")', 1)
    assert len(script) == 2 and 'getElementById("sbq-open")' in script[1]


def test_a_reader_who_may_not_add_songs_is_not_offered_the_import_either():
    z = pb.zero_page(can_add="seat")
    assert [l for l in z["links"] if l[2]] == [("Import catalog", pb.DOOR + "#pp-import", True)]
    c, uid = _account()
    store.set_demo_lock(uid, True)
    body = _body(c.get("/room/publishing").get_data(as_text=True))
    assert "Import catalog" not in body and "How song records work" in body
