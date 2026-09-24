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
    """The page from zero (owner's Fans spec, 2026-09-22). The rack is a
    STABLE information centre - three modules on the photographed plate,
    no rotation, no reel, no ticker - and the page below it is the spec's
    order: two equal starting cards, the five-stage workflow as
    education, "Your fans will appear here" beside "You stay in control",
    contextual help, and the tools folded away. The animated standby is
    retired on this room only."""
    import re as _re
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert ">Fans</h1>" in body
    # the three modules, exact words, and nothing rotating
    assert "Own the listener relationship" in body
    assert "Choose how to add your first fans" in body
    assert "Nothing is added until you review and confirm" in body
    assert "rk-cine" not in body and "rk-reel-ico" not in body
    assert 'class="rk-tip"' not in body and "rk-tick-i" not in body
    # the rooms' three-window rack, like every other room (owner,
    # 2026-09-23: "one room has a different plate on it... swap it out to
    # this three-window one like the rest"); the Fans map plate is the
    # working room's
    assert "room-plate.webp" in body and "fans-plate.webp" not in body
    assert body.count('<li class="cz-screen"') == 3
    assert "fr-z-mod" not in body and "fr-z-win" not in body
    # the hero's own pill, its door on the Fan Hub, carrying the way back
    # like the two cards (audit, 2026-09-23: the bare href's builder
    # offered "Back to Marketing")
    assert 'class="fr-cta" href="/links/new?type=bio&amp;returnTo=/room/fans"' in body
    assert "Launch fan campaign" in body
    # two EQUAL starting cards, each with a way back
    assert "Choose your starting point" in body
    assert body.count('class="fr-start"') == 2
    assert 'href="/links/new?type=bio&amp;returnTo=/room/fans"' in body
    assert 'href="/fans?returnTo=/room/fans"' in body
    assert "Best if you are starting from zero." in body
    assert "CSV, spreadsheet, or pasted contacts." in body
    # the workflow, five named stages, no progress claimed
    assert "How the fan workflow works" in body
    for stage in ("Capture", "Confirm consent", "Organize", "Activate", "Measure"):
        assert stage in body, stage
    rail = body.split("How the fan workflow works")[1].split("Your fans will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    # the empty workspace and the reassurance, in words - never a table or a nought
    assert "Your fans will appear here" in body and "You stay in control" in body
    assert "Nothing is sent without your approval" in body
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    assert "0 fans" not in text and not _re.search(r"(?<![\d.])0%", text), "an absence is words, not a nought"
    # help, and the tools folded
    assert "Not sure where to begin?" in body
    assert '<details class="fr-fold" open>' in body and "More fan tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    # the populated room's parts are not on this page
    assert "Next best moves" not in body and "The fan lifecycle" not in body
    for gone in MOCKUP_ONLY:
        assert gone not in body, gone


def test_the_figures_are_the_accounts_own():
    c, uid = _account("Real Artist")
    for i in range(3):
        fid = mls.upsert_fan(uid, "fan%d-%s@example.net" % (i, uid[:6]), None)
        mls.set_fan_place(fid, "US", "Atlanta")
    body = c.get("/room/fans").get_data(as_text=True)
    # three on file and three new, each a figure on its screen
    assert body.count('<span class="cz-screen-v cz-screen-v--fig">3</span>') == 2
    assert "Welcome 3 new fans" in body and "Get their emails" in body
    assert "Real Artist" in body                       # the account, not a stand-in name
    assert "Atlanta" in body and "Read from your own records" in body   # the Live badge
    for gone in MOCKUP_ONLY:
        assert gone not in body, gone
    csv = c.get("/room/fans/new.csv?days=30").get_data(as_text=True)
    assert csv.count("@example.net") == 3


def test_the_window_is_one_of_three():
    """The chooser governs the readings, so it is tested where there are
    some: one fan on file. (This test used a fresh account until the Fans
    audit of 2026-09-23, which pinned the chooser onto the page from zero,
    where it governed nothing - see the test below.)"""
    c, uid = _account()
    mls.upsert_fan(uid, "window-%s@example.net" % uid[:6], None)
    assert "Last 7 days" in c.get("/room/fans?days=7").get_data(as_text=True).split("fr-range-menu")[0]
    assert "Last 30 days" in c.get("/room/fans?days=5000").get_data(as_text=True).split("fr-range-menu")[0]


def test_the_page_from_zero_has_no_date_chooser_over_nothing():
    """Audit, 2026-09-23 (fans-7): a fresh account got the "Last 30 days"
    chooser, and ?days=7 changed nothing but the chooser. The sibling
    zero pages dropped theirs by spec. The chip's title said "The account
    these figures are for" on a page with no figures."""
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert "fr-range" not in body and "Last 30 days" not in body
    assert "The account these figures are for" not in body
    assert "Last 7 days" not in c.get("/room/fans?days=7").get_data(as_text=True), (
        "?days= renders the same page: there is nothing for it to govern")


def test_the_range_choices_keep_their_link_role():
    """Audit, 2026-09-23 (fans-16): role="listitem" on each <a href>
    replaced its link role, so a screen reader heard list items."""
    c, uid = _account()
    mls.upsert_fan(uid, "role-%s@example.net" % uid[:6], None)
    body = c.get("/room/fans").get_data(as_text=True)
    menu = body.split('class="fr-range-menu"', 1)[1].split("</ul>", 1)[0]
    assert 'role="listitem"' not in body
    for n in (7, 30, 90):
        assert '<li><a href="/room/fans?days=%d"' % n in menu, n


def test_the_demo_is_labelled_sample():
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = demo.get("/room/fans").get_data(as_text=True)
    assert "Sample data." in body and "fr-mark--sample" in body
    assert "Read from your own records" not in body, "the example is never called Live"
    # the demo is the showcase, never the page from zero (owner's ruling)
    for part in ("Choose your starting point", "fr-start", "How the fan workflow works",
                 "Your fans will appear here"):
        assert part not in body, part


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


# --- the rack and the map (2026-09-23) --------------------------------------
# Every room's rack is the owner's shorter three-window plate
# (static/img/room-plate.webp, partials/cc_rack.html). The working Fans room
# puts its three readings on its three screens, and the old Audience Monitor
# plate's big window - the map - is a panel of its own directly under it.

def _working(cities=("Atlanta",)):
    """An account with a fan in each city, so the working room draws."""
    c, uid = _account()
    for i, city in enumerate(cities):
        fid = mls.upsert_fan(uid, "f%d-%s@example.net" % (i, uid[:6]), None)
        mls.set_fan_place(fid, "US", city)
    return c, c.get("/room/fans").get_data(as_text=True)


def _rack(body):
    return body.split('<section class="cz-rack"', 1)[1].split("</section>", 1)[0]


def test_the_working_room_draws_the_rooms_plate_with_three_named_screens():
    """Owner, 2026-09-23: every room's rack uses the shorter three-window
    plate, and each working room shows its three figures on the three
    screens. The Audience Monitor photograph is not drawn any more."""
    import re
    _c, body = _working()
    assert 'class="cz-plate" src="/static/img/room-plate.webp?v=' in body
    assert "command-zero.css?v=" in body, "the shared plate's rules load on the working room too"
    rack = _rack(body)
    assert rack.count('<li class="cz-screen"') == 3
    assert re.findall(r'<span class="cz-screen-k">([^<]*)</span>', rack) == ["On file", "Reachable", "New"]
    assert "fans-plate.webp" not in body, "the old plate is gone from the working room"
    assert "rk-pl-win" not in body and "rk-reel" not in body
    assert not hasattr(fan_room, "PLATE") and not hasattr(fan_room, "standby"), (
        "the old plate's measured windows and its standby have nothing left to place")


def test_the_three_screens_read_on_file_reachable_new():
    """Left to right, the order the old plate printed them top to bottom."""
    wins = fan_room.windows("240", 240, "37", 37, 62, 30)
    assert [w["key"] for w in wins] == ["on-file", "reachable", "new"]
    screens = fan_room.rack_screens(wins)
    assert [(s["k"], s["v"], s["sub"]) for s in screens] == [
        ("On file", "240", "fans"), ("Reachable", "62%", "can be emailed"),
        ("New", "37", "in 30 days")]
    assert all(s["fig"] and not s["none"] for s in screens)


def test_reachable_says_words_when_nobody_is_on_file_and_a_figure_otherwise():
    none = fan_room.windows("0", 0, "0", 0, None, 30)[1]
    assert none["value"] == "None yet" and none["measured"] is False
    assert "0%" not in none["value"], "an absence is not a measurement of nought"
    real = fan_room.windows("10", 10, "0", 0, 0, 30)[1]
    assert real["value"] == "0%" and real["measured"] is True, (
        "0% IS a real reading - every fan suppressed or with no address")
    # and on the screen: the absence is set as words, the 0% as a figure
    words = fan_room.rack_screens(fan_room.windows("0", 0, "0", 0, None, 30))[1]
    assert words["v"] == "None yet" and words["none"] and not words["fig"]
    nought = fan_room.rack_screens(fan_room.windows("10", 10, "0", 0, 0, 30))[1]
    assert nought["v"] == "0%" and nought["fig"] and not nought["none"]


def test_every_screen_says_what_it_is_once():
    """The new plate prints no names, so each screen carries its own - once,
    as its label, and never again inside the rack (owner, 2026-09-22:
    "check for duplicate buttons and text")."""
    import re
    _c, body = _working()
    rack = _rack(body)
    for word in ("On file", "Reachable", "New"):
        hits = list(re.finditer(re.escape(">" + word + "<"), rack))
        assert len(hits) == 1, (word, len(hits))
        before = rack[:hits[0].start()].rsplit("<", 1)[-1]
        assert 'class="cz-screen-k"' in before, word


def test_the_plate_image_carries_a_cache_version():
    _c, body = _working()
    assert "room-plate.webp?v=" in body, (
        "an image replaced in place is kept by every browser that has it")


def test_the_map_is_its_own_panel_directly_under_the_plate():
    """Nothing is lost: the constellation, its names, dots and lines, now in a
    panel of its own straight after the rack, and the Live mark and the
    glossary under them."""
    _c, body = _working(("Atlanta", "Chicago", "Denver"))
    after = body.split('<section class="cz-rack"', 1)[1].split("</section>", 1)[1]
    assert after.lstrip().startswith('<section class="fr-panel fr-map-panel"'), after[:200]
    panel = after.split("</section>", 1)[0]
    assert "<svg viewBox=" in panel and "fr-map-dot" in panel and "fr-map-line" in panel
    for city in ("Atlanta", "Chicago", "Denver"):
        assert ">%s</text>" % city in panel, city
    # a reader who cannot see the drawing is told what it names
    assert 'aria-label="Reachable fans by city: ' in panel
    foot = body.index('class="rk-foot fr-pl-foot"')
    assert body.index('class="fr-panel fr-map-panel"') < foot
    assert body.index("The fan lifecycle") > foot


def test_the_city_names_are_drawn_inside_the_viewbox_not_over_it():
    """The box is not always exactly the map's aspect, so the drawing can
    letterbox inside it. A label positioned as a percentage of the BOX sits
    a few pixels off its dot, and a named dot that points at nothing is
    worse than no name at all."""
    page = io.open("templates/room_fans.html", encoding="utf-8").read()
    unit = page.split('class="fr-panel fr-map-panel"', 1)[1].split("</section>", 1)[0]
    assert "fr-map-name" in unit and "<text" in unit
    assert "fr-map-label" not in unit, "the absolutely-positioned labels are gone"
    # the count hangs one line under its name in em, so a larger name on a
    # phone never runs into it
    assert 'dy="1.15em"' in unit


def _map_sizes():
    """(the map's padding, its base sizes, and each narrower step) read out
    of fan-room.css."""
    import re
    css = io.open("static/css/fan-room.css", encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    pad = re.search(r"\.fr-map \.rk-pl-art \{[^}]*padding: (\d+)px (\d+)px", code)
    name = re.search(r"\n\.fr-map-name \{[^}]*font-size: (\d+)px", code)
    count = re.search(r"\n\.fr-map-count \{[^}]*font-size: (\d+)px", code)
    steps = []
    for m in re.finditer(r"@container frmap \(max-width: (\d+)px\) \{(.*?)\n\}", code, re.S):
        body = m.group(2)
        steps.append((int(m.group(1)),
                      int(re.search(r"\.fr-map-name \{ font-size: (\d+)px", body).group(1)),
                      int(re.search(r"\.fr-map-count \{ font-size: (\d+)px", body).group(1))))
    return (int(pad.group(1)), int(pad.group(2))), (int(name.group(1)), int(count.group(1))), steps


def test_the_city_names_stay_legible_at_every_map_width():
    """The names were raised to 13 and 12 viewBox units for legibility, and
    a unit is a page pixel only at 604px. At 375 the map is about 300px
    wide, so 13 units would read at about six pixels. Each container step
    sets them larger; at the NARROWEST width of every step the name must
    still read at 13px and the count at 12px on the page. The last step is
    held to a 240px map, narrower than a 320px phone gives it."""
    import re
    (pad_y, pad_x), (name, count), steps = _map_sizes()
    assert (name, count) == (13, 12), "the sizes the owner's legibility pass set"
    assert steps, "no narrower step: the names shrink with the map on a phone"
    assert [(name, count)] + [(n, c) for _w, n, c in steps] == list(fan_room.LABEL_STEPS), (
        "fan_room places the names at the sizes the sheet draws them")
    css = io.open("static/css/fan-room.css", encoding="utf-8").read()
    assert "container: frmap / inline-size" in css and "aspect-ratio: 604 / 306" in css
    tiers = [(steps[0][0] + 1, name, count)]
    for i, (width, n, c) in enumerate(steps):
        low = steps[i + 1][0] + 1 if i + 1 < len(steps) else 240
        tiers.append((low, n, c))
    for low, n, c in tiers:
        # the container's content box is `low` wide; the box keeps the map's
        # aspect (border 1px), and the drawing sits inside the padding
        height = (low + 2) * 306.0 / 604 - 2
        scale = min((low - 2 * pad_x) / 604.0, (height - 2 * pad_y) / 306.0)
        assert n * scale >= 13, "a %dpx map sets the names at %.1fpx" % (low, n * scale)
        assert c * scale >= 12, "a %dpx map sets the counts at %.1fpx" % (low, c * scale)


def _drawn(p, step):
    """The label boxes drawn at a step, in viewBox units."""
    fn, fc = fan_room.LABEL_STEPS[step]
    return [(d["city"], fan_room._label_box(d, "end" if d["right"] else "start", fn, fc))
            for d in p["dots"] if d["label"] and (d["off"] is None or d["off"] > step)]


def test_no_two_city_names_are_drawn_over_each_other():
    """New York and Chicago, drawn at 1280 and at 375 on 2026-09-23, sat on
    top of each other and read as neither. Each name takes the side that
    keeps it clear, and at a narrower step - where every name is set larger
    - a smaller city's name that would still collide is left out there,
    never drawn over."""
    dots = [{"x": 520.0, "y": 110.0, "core": 9, "city": "New York", "count": 5},
            {"x": 470.0, "y": 118.0, "core": 7, "city": "Chicago", "count": 3},
            {"x": 480.0, "y": 180.0, "core": 10, "city": "Atlanta", "count": 6},
            {"x": 90.0, "y": 170.0, "core": 8, "city": "Los Angeles", "count": 4},
            {"x": 505.0, "y": 125.0, "core": 5, "city": "Philadelphia", "count": 2}]
    p = fan_room.pulse({"geo": {"dots": dots, "cities": 5}})
    for step in range(len(fan_room.LABEL_STEPS)):
        boxes = _drawn(p, step)
        assert boxes, "the biggest city is always named"
        for i, (a_city, a) in enumerate(boxes):
            assert a[0] >= 0 and a[2] <= p["w"] and a[1] >= 0 and a[3] <= p["h"], (step, a_city)
            for b_city, b in boxes[i + 1:]:
                assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]), (
                    "step %d draws %s over %s" % (step, a_city, b_city))
    # the biggest city keeps its name at every width
    assert p["dots"][0]["city"] == "Atlanta" and p["dots"][0]["off"] is None
    # and a name left out at one step stays out at every narrower one: the
    # sheet hides is-off-N from step N down
    css = io.open("static/css/fan-room.css", encoding="utf-8").read()
    assert ".fr-map-lab.is-off-0 { display: none; }" in css
    for n, width in ((1, 659), (2, 519), (3, 399), (4, 299)):
        block = css.split("@container frmap (max-width: %dpx) {" % width, 1)[1].split("@", 1)[0]
        assert ".fr-map-lab.is-off-%d { display: none; }" % n in block, n


def test_the_readings_and_the_map_survive_a_phone():
    """The figures ARE the screen, and the map is the room's picture of its
    audience. On a phone the shared rack steps its photograph aside for
    the three screens stacked (command-zero.css), and nothing hides them
    or the map."""
    import re
    zero = io.open("static/css/command-zero.css", encoding="utf-8").read()
    block = zero.split("@container czrack (max-width: 880px) {", 1)[1].split("\n}", 1)[0]
    assert ".cz-plate { display: none; }" in block
    assert not re.search(r"\.cz-screen[^{-]*\{[^}]*display:\s*none", block), (
        "the readings must survive the plate")
    fans = re.sub(r"/\*.*?\*/", "", io.open("static/css/fan-room.css", encoding="utf-8").read(), flags=re.S)
    # (a name that would collide at a step is left out there - the test
    # above - but the map itself, its dots and lines, never are)
    fans = re.sub(r"\.fr-map-lab\.is-off-\d \{ display: none; \}", "", fans)
    assert not re.search(r"\.fr-map[^{]*\{[^}]*display:\s*none", fans), "the map must survive a phone"


def test_the_map_is_sized_off_its_width_never_its_height():
    """cqw resolves against an inline-size container; cqh does not resolve
    there at all. The map box is the container its names step against."""
    import re
    for sheet in ("fan-room.css", "command-zero.css"):
        code = re.sub(r"/\*.*?\*/", "", io.open("static/css/" + sheet, encoding="utf-8").read(), flags=re.S)
        assert "cqh" not in code, sheet


# --- the kit's photographed plate ---------------------------------------------
# Fans no longer draws it, but the rooms not yet on the shared three-window
# plate still do, and these two guards were written here first.

def test_the_kit_plates_readings_survive_a_phone_losing_the_photograph():
    """The figures ARE the screen. A phone that dropped them would be
    showing a picture of an instrument instead of this artist's numbers."""
    import re
    css = io.open("static/css/room-kit.css", encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # The sheet carries more than one 560px block (the plate's, and the
    # standby's), so this reads every one of them.
    blocks = code.split("@media (max-width: 560px)")[1:]
    assert blocks, "no narrow block at all"
    assert any(".rk-pl-img { display: none; }" in b for b in blocks), (
        "the photograph steps aside on a phone")
    for b in blocks:
        assert not re.search(r"\.rk-pl-win[^{:]*\{[^}]*display:\s*none", b), (
            "the readings must survive the plate")


def test_the_kit_plate_has_a_container_context_and_is_never_sized_off_its_height():
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
    """It sat in the head of the map panel, then under the Audience Monitor
    plate, and now under the rooms' plate and the map's own panel. The mark
    is what stops a demo account's generated audience being read as a real
    one, so it moves with the readings rather than going out with them."""
    c, uid = _account()
    # It belongs to the READINGS, so it appears once there are some. On
    # the page from zero there is no figure on the plate to mark as live or
    # as an example, and the foot that carries it is not drawn at all.
    empty = c.get("/room/fans").get_data(as_text=True)
    assert "fr-pl-foot" not in empty, "nothing to mark on the page from zero"
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
    panel = body.split('class="fr-panel fr-map-panel"', 1)[1].split("</section>", 1)[0]
    assert "No fan cities yet" in panel, "the words live in the map's own panel"
    assert "Cities arrive with your smart links" in panel
    assert "<svg viewBox=" not in panel, "nothing plotted, nothing drawn"


def test_a_fan_on_file_gets_the_populated_room_untouched():
    """One real fan and the room is the room: readings on the plate, the
    lifecycle rail, next best moves, tiles in the open - none of the
    onboarding page."""
    import links_store as mls
    c, uid = _account()
    cid = mls.create_campaign(uid, "f-%s" % uuid.uuid4().hex[:6], {"title": "HP"})
    mls.upsert_fan(uid, "one@example.net", cid, name="One")
    body = c.get("/room/fans").get_data(as_text=True)
    assert 'class="fr-start"' not in body and "Choose your starting point" not in body
    assert "The fan lifecycle" in body and "Next best moves" in body
    assert '<details class="fr-fold">' not in body
    assert "fr-z-win" not in body, "the plate carries readings, not the modules"


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = [("fans", "/fans", "i", "Fans", "d", "live"),
             ("fan-crm", "/fan-crm", "i", "Fan CRM", "d", "live"),
             ("fan-club", "/fan-club", "i", "Fan Club", "d", "hidden"),
             ("marketplace", "/marketplace", "i", "Marketplace", "d", "live")]
    tiles = {t["key"]: t for t in fan_room.build([], {"total": 0}, cards)["tiles"]}
    assert tiles["fan-club"]["state"] == "hidden" and tiles["fan-club"]["status"] == "Hidden"
    assert tiles["fans"]["state"] != "hidden"


# --- the Fans audit of 2026-09-23 --------------------------------------------

def _boom(*_a, **_k):
    raise RuntimeError("fans: store down")


@pytest.mark.parametrize("target", ["list_fans", "for_account", "get_fan_club"])
def test_a_failed_read_is_the_rooms_error_page_at_503(monkeypatch, target):
    """fans-1: the one room of eight whose reads sat outside any try. A
    failed read was Werkzeug's bare 500 - no shell, no way out - where the
    six sibling rooms give their own error page at 503."""
    import fan_audience
    c, _uid = _account()
    where = {"list_fans": mls, "for_account": fan_audience, "get_fan_club": store}[target]
    monkeypatch.setattr(where, target, _boom)
    r = c.get("/room/fans")
    assert r.status_code == 503, target
    page = r.get_data(as_text=True)
    assert "We could not load Fans" in page and 'id="sb-main"' in page
    assert 'href="/room/fans"' in page and 'href="/links/fans"' in page
    assert "Choose your starting point" not in page and "room-plate" not in page, (
        "a failed read is never a fresh account")


def test_the_club_member_read_is_inside_the_same_try(monkeypatch):
    c, _uid = _account()
    monkeypatch.setattr(store, "get_fan_club", lambda _uid: {"id": "club"})
    monkeypatch.setattr(store, "list_club_members", _boom)
    assert c.get("/room/fans").status_code == 503


def test_the_new_fans_csv_fails_as_the_rooms_error_page_too(monkeypatch):
    c, _uid = _account()
    monkeypatch.setattr(mls, "list_fans", _boom)
    r = c.get("/room/fans/new.csv?days=30")
    assert r.status_code == 503 and "We could not load Fans" in r.get_data(as_text=True), (
        "never an empty file that reads as nobody new")


def test_the_spec_help_questions_are_on_the_page_from_zero():
    """fans-6: zero_page() handed the template HELP_QUESTIONS and nothing
    read them. Stage and Studio render theirs."""
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    help_panel = body.split('id="fr-help-h"', 1)[1].split("</section>", 1)[0]
    for q in fan_room.HELP_QUESTIONS:
        assert "<li>%s</li>" % q in help_panel, q


def test_the_ask_button_opens_the_ask_box_on_this_page():
    """fans-12: id="fr-ask" was set for the corner Ask box and nothing wired
    it, so a signed-in artist left the app for the public Contact page.
    /contact stays the fallback with scripts off, as on the Command
    Center."""
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert 'href="/contact" id="fr-ask"' in body
    script = body.split('getElementById("fr-ask")', 1)
    assert len(script) == 2, "the button is wired"
    assert 'getElementById("sbq-open")' in script[1] and "q.focus()" in script[1]
    assert 'id="sbq-open"' in body, "the box it opens is on the page"


def test_each_link_lands_on_the_explanation_it_names():
    """fans-13: "How fan capture works" opened the campaign list (for a new
    account, "No links yet"), and "Import requirements" was the import
    card's own door under a second name. Both now open the section of
    /fans that explains them - and those sections are there."""
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    links = body.split('class="fr-z-links"', 1)[1].split("</p>", 1)[0]
    assert 'href="/fans?returnTo=/room/fans#fr-alt-h">How fan capture works' in links
    assert 'href="/fans?returnTo=/room/fans#fr-needs-h">Import requirements' in links
    assert 'href="/links?returnTo=/room/fans"' not in body
    landing = c.get("/fans?returnTo=/room/fans").get_data(as_text=True)
    assert 'id="fr-alt-h"' in landing and "asks for an email on the way through" in landing
    assert 'id="fr-needs-h"' in landing and "What the file needs" in landing
    # Business-13 (owner, 2026-09-22: "rooms are called by their bare
    # names") renamed every room's back link after this test was
    # written; it now reads "Back to Fans", not "Back to the fans room".
    assert "Back to Fans" in landing and "the fans room" not in landing


def test_the_drawer_is_named_once():
    """The summary and an sr-only heading carried the same words, so the
    drawer's name was read twice (publishing-12's pattern, on this room's
    drawer too). The heading is the summary's text now."""
    c, _uid = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert body.count(">More fan tools<") == 1
    assert '<summary class="fr-fold-sum"><h2 class="fr-fold-h" id="fr-tools-h">More fan tools</h2>' in body
    assert 'aria-labelledby="fr-tools-h"' in body


def test_the_discover_tile_says_what_the_page_does_and_is_not_sample():
    """fans-10 and fans-17: the tile promised "Find listeners and scenes"
    for a catalogue search, and once a fan was on file it wore the Sample
    pill, although a real account's /discover shows real records only."""
    assert fan_room.TILE_COPY["discover"] == ("Discover", "Search the catalogue and play a preview")
    c, uid = _account()
    zero = c.get("/room/fans").get_data(as_text=True)
    mls.upsert_fan(uid, "tile-%s@example.net" % uid[:6], None)
    body = c.get("/room/fans").get_data(as_text=True)
    for page in (zero, body):
        assert "Find listeners and scenes" not in page
    tile = body.split('data-room-card="discover"', 1)[1].split("</a>", 1)[0]
    assert "Search the catalogue and play a preview" in tile
    assert "Sample" not in tile, "a real account's search is not example data"


def test_the_capture_path_keeps_its_way_back_after_the_save():
    """fans-4: POST /links/new?type=bio&returnTo=/room/fans redirected to
    /links/<cid>/edit with the way back dropped, and the landing offered
    "Back to Marketing" - the very bug returnTo exists to fix."""
    c, uid = _account()
    r = c.post("/links/new?type=bio&returnTo=/room/fans",
               data={"title": "Fan Hub %s" % uid[:6], "campaign_type": "bio"})
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "/edit?returnTo=/room/fans" in loc, loc
    landing = c.get(loc).get_data(as_text=True)
    # Same rename (business-13) as above.
    assert 'href="/room/fans" id="sb-room-back"' in landing and "Back to Fans" in landing
    # and a door with no way back is not given one, nor a foreign one
    bare = c.post("/links/new", data={"title": "Bare %s" % uid[:6]})
    assert bare.headers["Location"].endswith("/edit")
    evil = c.post("/links/new?returnTo=//evil.example/x", data={"title": "Evil %s" % uid[:6]})
    assert "evil" not in evil.headers["Location"]


def test_the_rooms_start_copy_matches_the_doors_it_offers():
    """fans-15: a seat without the Marketing room is offered the import
    alone, and was still told "Start with a fan campaign", under "Choose
    your starting point" and a rack saying "Choose how to add your first
    fans" above one card."""
    both = fan_room.zero_page(True, True)
    assert both["help_line"] == "Start with a fan campaign if you do not already have a contact list."
    assert both["starts_heading"] == "Choose your starting point"
    assert both["screens"][1]["v"] == "Choose how to add your first fans", "the spec's words"
    one = fan_room.zero_page(False, True, ("import",))
    assert "fan campaign" not in one["help_line"] and "importing" in one["help_line"]
    assert one["starts_heading"] == "Your starting point"
    assert one["screens"][1]["v"] != "Choose how to add your first fans"
    assert [s[0] for s in one["starts"]] == ["import"] and not one["locked"]
    none = fan_room.zero_page(False, False, ("capture", "import"))
    assert none["locked"] == fan_room.LOCKED and none["help_line"] == fan_room.LOCKED
    assert none["starts_heading"] == "How fans are added"


def test_a_read_seat_is_offered_no_door_and_told_who_can():
    """fans-2, in the builder: a seat without edit access gets no capture
    or import door and no move whose point is a save."""
    cards = [("fans", "/fans", "i", "Fans", "d", "live")]
    fr = fan_room.build([], {"total": 0}, cards, can_add="seat")
    assert fr["can_capture"] is False and fr["can_import"] is False
    assert fr["zero"]["locked"] == fan_room.LOCKED
    rows = [{"email": "a@x.net", "tags": "[]", "created": "2026-01-01"}]
    moves = fan_room.moves(rows, {"total": 5, "segments": []}, 30, TODAY,
                           link_visits=50, can_write=False)
    assert all(m["cta"] not in ("Import your list", "Add a capture") for m in moves)
    assert fan_room.build([], {"total": 0}, cards)["can_capture"] is True, "the owner keeps it"
