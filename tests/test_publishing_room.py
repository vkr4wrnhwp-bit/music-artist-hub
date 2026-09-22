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
             "fingerprints": ("/fingerprints/", "M1", "Fingerprints", "register"),
             "certified": ("/certified", "M1", "Certified", "six rungs")}
    out = pb.build([_track("One")], [], [{"title": "x", "description": "y"}],
                   None, cards)
    by = {t["key"]: t for t in out["tiles"]}
    # One tile over beats AND fingerprints (owner, 2026-09-22), so the
    # fingerprints key keeps its card and its room but draws no door of its
    # own - "not be two different ones in publishing".
    assert [t["key"] for t in out["tiles"]] == ["catalog", "track-passports",
                                                "conflicts", "beats",
                                                "certified"]
    assert [t["name"] for t in out["tiles"]][3] == "Beat Fingerprints"
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

def test_an_empty_account_is_told_in_words_and_shown_no_zero_figures():
    c, _uid = _account()
    page = c.get("/room/publishing").get_data(as_text=True)
    assert "Publishing Room" in page
    assert "Your songs, who owns them, and who is collecting." in page
    # Counted on the figure's own class, not on the words: the note panel
    # explains the rule and says "Not measured" in passing, which is prose
    # rather than a fourth unmeasured figure.
    assert page.count("rk-fig-n--none") == 3
    assert "No recordings on file yet." in page
    assert "Nothing on file disagrees with itself." in page


def test_the_page_never_says_a_registration_was_accepted_or_a_society_paid():
    c, _uid = _account()
    page = c.get("/room/publishing").get_data(as_text=True)
    for claim in ("Registration accepted", "successfully registered",
                  "money recovered", "We collected", "Royalties recovered"):
        assert claim not in page, claim


def test_the_page_says_percentages_are_not_recorded():
    c, _uid = _account()
    page = c.get("/room/publishing").get_data(as_text=True)
    assert "Writer percentages are not recorded anywhere yet." in page


def test_the_five_states_are_all_drawn_even_where_the_count_is_none():
    """A rung with nothing in it is still a rung. Hiding the empty ones
    would make a catalogue with one written song look finished."""
    c, _uid = _account()
    page = c.get("/room/publishing").get_data(as_text=True)
    for name in ("Written", "Split agreed", "Registered", "Claimed", "Collecting"):
        assert ">%s<" % name in page, name
