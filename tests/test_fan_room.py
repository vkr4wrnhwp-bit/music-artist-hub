"""The Fan Room: the Fans room's opening screen (owner's mockup, 2026-09-19).

The layout is the mockup's; the figures are the account's own, and the
mockup's own figures, names and promises never reach a real page.
"""
import io
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import app as appmod
import db as store
import fan_room
import links_store as mls

PW = "fan-room-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account(name="Room Artist"):
    email = "fanroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


MOCKUP_ONLY = ("12,486", "1,204", "Maya Cole", "Send welcomes", "Send invites",
               "Founders Circle", "Find emails", "EST. REACH", "2,842", "London",
               "Real Fans", "journeys")


def test_an_empty_account_is_told_how_to_start_not_shown_a_crowd():
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert ">Fans</h1>" in body
    assert "Bring in the fans you already have" in body
    # The plate explains itself on an empty account now (owner,
    # 2026-09-22), so the map's own empty sentence is not reached: the
    # constellation branch only runs once there is something to draw.
    assert "Turn listeners into a list you own" in body
    assert "Launch a smart link" in body
    for gone in MOCKUP_ONLY:
        assert gone not in body, gone


def test_the_figures_are_the_accounts_own():
    c, uid = _account("Real Artist")
    for i in range(3):
        fid = mls.upsert_fan(uid, "fan%d-%s@example.net" % (i, uid[:6]), None)
        mls.set_fan_place(fid, "US", "Atlanta")
    body = c.get("/room/fans").get_data(as_text=True)
    assert '<p class="rk-pl-n">3</p>' in body
    assert "Welcome 3 new fans" in body and "Get their emails" in body
    assert "Real Artist" in body                       # the account, not a stand-in name
    assert "Atlanta" in body and "Read from your own records" in body   # the Live badge
    for gone in MOCKUP_ONLY:
        assert gone not in body, gone
    csv = c.get("/room/fans/new.csv?days=30").get_data(as_text=True)
    assert csv.count("@example.net") == 3


def test_the_window_is_one_of_three():
    c, _uid = _account()
    assert "Last 7 days" in c.get("/room/fans?days=7").get_data(as_text=True).split("fr-range-menu")[0]
    assert "Last 30 days" in c.get("/room/fans?days=5000").get_data(as_text=True).split("fr-range-menu")[0]


def test_the_demo_is_labelled_sample():
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = demo.get("/room/fans").get_data(as_text=True)
    assert "Sample data." in body and "fr-mark--sample" in body
    assert "Read from your own records" not in body, "the example is never called Live"


def test_the_other_rooms_keep_their_card_grid():
    c, _uid = _account()
    body = c.get("/room/studio").get_data(as_text=True)
    assert "data-room-card" in body and "fr-hero" not in body


def test_the_csv_needs_a_sign_in():
    r = appmod.app.test_client().get("/room/fans/new.csv")
    assert r.status_code in (302, 303)


# --- the builder -----------------------------------------------------------

TODAY = date(2026, 9, 19)


def _fan(email, days_ago, tags="[]", suppressed=""):
    return {"email": email, "tags": tags, "suppressed": suppressed,
            "created": (datetime(2026, 9, 19, tzinfo=timezone.utc) - timedelta(days=days_ago)).isoformat()}


def test_an_import_is_not_new_fans():
    rows = [_fan("a@x.net", 2), _fan("b@x.net", 2, tags='["imported"]'),
            _fan("c@x.net", 2, tags='["shopify"]'), _fan("d@x.net", 45)]
    assert [f["email"] for f in fan_room.new_fans(rows, 30, TODAY)] == ["a@x.net"]
    assert len(fan_room.new_fans(rows, 90, TODAY)) == 2


def test_the_welcome_move_counts_only_fans_it_can_email():
    rows = [_fan("a@x.net", 2), _fan("b@x.net", 2, suppressed="bounced")]
    audience = {"total": 2, "segments": [], "geo": {}}
    moves = fan_room.moves(rows, audience, 30, TODAY)
    welcome = [m for m in moves if m["title"].startswith("Welcome")][0]
    assert welcome["title"] == "Welcome 1 new fan"
    assert "you can email" in welcome["desc"]


def test_a_zero_is_stated_not_lit():
    audience = {"segments": []}
    assert fan_room.tile_status("fans", audience, 0, 30, {"on": False, "members": 0}, 0, "live")[0] == "off"
    assert fan_room.tile_status("marketplace", audience, 0, 30, {}, 0, "live") == ("off", "0 open briefs")
    assert fan_room.tile_status("marketplace", audience, 0, 30, {}, 4, "live") == ("good", "4 open briefs")
    assert fan_room.tile_status("fan-club", audience, 0, 30, {"on": False, "members": 0}, 0, "live") == ("off", "Not set up")
    assert fan_room.tile_status("discover", audience, 0, 30, {}, 0, "sample") == ("info", "Sample")


def test_no_cities_means_no_map():
    assert fan_room.pulse({"geo": {"dots": []}}) is None


def test_the_map_keeps_cities_inside_the_frame():
    dots = [{"x": 500.0, "y": 100.0, "core": 8, "city": "New York", "count": 9},
            {"x": 80.0, "y": 150.0, "core": 6, "city": "Los Angeles", "count": 4},
            {"x": 420.0, "y": 220.0, "core": 5, "city": "Atlanta", "count": 2}]
    p = fan_room.pulse({"geo": {"dots": dots, "cities": 3}})
    for d in p["dots"]:
        assert 0 <= d["x"] <= p["w"] and 0 <= d["y"] <= p["h"]
    assert [d["city"] for d in p["dots"] if d["label"]] == ["New York", "Los Angeles", "Atlanta"]


def test_the_fan_room_has_no_banner_photograph():
    """Owner, 2026-09-20: "most other pages don't have a banner image, let's
    remove this for now." The head keeps its title, line and controls; the
    stand-in crowd photograph, its mask and its files are gone."""
    import io as _io
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert 'class="fr-hero"' in body and 'id="fr-title"' in body
    assert "fr-hero-photo" not in body and "door-crowd" not in body
    for name in ("door-crowd-900.webp", "door-crowd-1600.webp"):
        assert not _os.path.exists(_os.path.join(here, "static", "img", name)), name
    css = _io.open(_os.path.join(here, "static", "css", "fan-room.css"), encoding="utf-8").read()
    assert "fr-hero-photo" not in css and "min-height: 318px" not in css
    # The sheet is versioned so a returning browser refetches it; pinning
    # the exact number only made this test fail every time it was bumped,
    # so it asserts the floor it was raised past instead.
    got = int(__import__("re").search(r"fan-room\.css\?v=(\d+)", body).group(1))
    assert got >= 6, got


# --- the plate (2026-09-22) ----------------------------------------------
# The owner's photographed Audience Monitor. The hardware is one image and
# only the readings are drawn on it.

def test_the_windows_sit_where_they_were_measured_on_the_plate():
    """Every window is a fraction of static/img/fans-plate.webp, measured
    off the file with PIL. If the plate is ever regenerated or re-cropped
    these move, and nothing else in the code would say so - the overlays
    simply land beside their glass."""
    assert fan_room.PLATE == {
        "room":      (6.67, 18.56, 59.30, 62.29),
        "on-file":   (71.02, 14.78, 22.20, 13.95),
        "reachable": (71.02, 41.02, 22.20, 13.83),
        "new":       (71.02, 67.14, 22.20, 13.95),
    }
    got = fan_room.box("on-file")
    for part in ("--x:71.02%", "--y:14.78%", "--w:22.2%", "--h:13.95%"):
        assert part in got, got


def test_the_three_small_windows_read_in_the_order_the_plate_prints_them():
    """ON FILE, REACHABLE, NEW, top to bottom. The silkscreen cannot be
    reordered, so neither can these."""
    keys = [w["key"] for w in fan_room.windows("240", 240, "37", 37, 62, 30)]
    assert keys == ["on-file", "reachable", "new"]


def test_reachable_says_words_when_nobody_is_on_file_and_a_figure_otherwise():
    none = fan_room.windows("0", 0, "0", 0, None, 30)[1]
    assert none["value"] == "None yet" and none["measured"] is False
    assert "0%" not in none["value"], "an absence is not a measurement of nought"
    real = fan_room.windows("10", 10, "0", 0, 0, 30)[1]
    assert real["value"] == "0%" and real["measured"] is True, (
        "0% IS a real reading - every fan suppressed or with no address")


def test_the_markup_never_prints_what_the_plate_silkscreens():
    """ON FILE, REACHABLE, NEW and THE ROOM are printed on the photograph.
    Owner, 2026-09-22: "check for duplicate buttons and text"."""
    import re
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    unit = body.split('class="rk-pl fr-pl"', 1)[1].split("</section>", 1)[0]
    for word in ("On file", "Reachable", "New", "The room"):
        for hit in re.finditer(re.escape(">" + word + "<"), unit):
            before = unit[:hit.start()].rsplit("<", 1)[-1]
            assert 'class="rk-pl-sr"' in before, (
                '"%s" is on the plate; the markup prints it again' % word)


def test_the_plate_image_carries_a_cache_version():
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert "fans-plate.webp?v=" in body, (
        "an image replaced in place is kept by every browser that has it")


def test_the_city_names_are_drawn_inside_the_viewbox_not_over_it():
    """The window is not the map's own aspect, so the drawing letterboxes
    inside its glass. A label positioned as a percentage of the WINDOW sits
    a few pixels off its dot, and a named dot that points at nothing is
    worse than no name at all."""
    page = io.open("templates/room_fans.html", encoding="utf-8").read()
    unit = page.split('class="rk-pl fr-pl"', 1)[1].split("</section>", 1)[0]
    assert "fr-map-name" in unit and "<text" in unit
    assert "fr-map-label" not in unit, "the absolutely-positioned labels are gone"


def test_the_readings_survive_a_phone_losing_the_photograph():
    """The figures ARE the screen. A phone that dropped them would be
    showing a picture of an instrument instead of this artist's audience."""
    import re
    css = io.open("static/css/room-kit.css", encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # The sheet carries more than one 560px block now (the plate's, and
    # the standby's), so this reads every one of them rather than
    # whichever happens to be last.
    blocks = code.split("@media (max-width: 560px)")[1:]
    assert blocks, "no narrow block at all"
    assert any(".rk-pl-img { display: none; }" in b for b in blocks), (
        "the photograph steps aside on a phone")
    for b in blocks:
        assert not re.search(r"\.rk-pl-win[^{:]*\{[^}]*display:\s*none", b), (
            "the readings must survive the plate")


def test_the_plate_has_a_container_context_and_is_never_sized_off_its_height():
    """cqw resolves against an inline-size container; with none, every
    clamp() on the plate is invalid and the type falls back to page-sized
    and bursts out of the windows. cqh does not resolve there at all."""
    import re
    css = io.open("static/css/room-kit.css", encoding="utf-8").read()
    unit = css.split(".rk-pl {", 1)[1].split("}", 1)[0]
    assert "container-type: inline-size" in unit
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert "cqh" not in code


def test_reachable_requires_an_address_not_just_an_unsuppressed_row():
    """The audit's finding: contactable() tested the suppression column
    alone, so a fan with no email counted toward the share the plate
    prints under REACHABLE. You cannot email somebody who has no address."""
    import fan_segments
    rows = [{"email": "a@example.net", "suppressed": ""},
            {"email": "", "suppressed": ""},
            {"email": "c@example.net", "suppressed": "bounced"}]
    assert len(fan_segments.contactable(rows)) == 1


def test_the_plate_keeps_the_live_or_sample_mark():
    """It used to sit in the head of the map panel, and that panel folded
    into the plate. The mark is what stops a demo account's generated
    audience being read as a real one, so it moved with the map rather
    than going out with it."""
    c, uid = _account()
    # It belongs to the READINGS, so it appears once there are some. In
    # standby there is no figure on the plate to mark as live or as an
    # example, and the foot that carries it is not drawn at all.
    empty = c.get("/room/fans").get_data(as_text=True)
    assert "fr-pl-foot" not in empty, "nothing to mark while the plate is in standby"
    mls.upsert_fan(uid, "one@example.net", "", name="One")
    body = c.get("/room/fans").get_data(as_text=True)
    foot = body.split('class="rk-foot fr-pl-foot"', 1)[1].split("</p>", 1)[0]
    assert "fr-mark" in foot and "Live" in foot


def test_the_map_says_so_when_fans_exist_but_none_could_be_placed():
    """The state between the two the plate shows: fans on file, so the room
    is NOT in standby, but no city the map can plot. It had no cover left
    after the standby took over the empty case, and it is the state a real
    account reaches first - a list import with no city column."""
    c, uid = _account()
    mls.upsert_fan(uid, "nowhere@example.net", "", name="No City")
    body = c.get("/room/fans").get_data(as_text=True)
    assert "is-standby" not in body, "a fan on file is not an empty room"
    assert "No fan cities yet" in body
    assert "Cities arrive with your smart links" in body
