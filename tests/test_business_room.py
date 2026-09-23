"""The Business Room: the room's opening screen (owner's mockup, 2026-09-22).

Eighteen cards became one screen and sixteen doors, and the screen opens on
a photographed analyser with THREE windows that are never summed.

What these lock, in the order they were found:

  no total, ever - recovery_engine makes one and this room refuses to print it
  an actual and an estimate stay two readings, each named
  nothing unmeasured reads as a nought, and "kept" is not income-minus-nothing
  every window is on ONE basis, so Kept really is Reported less costs
  the streams come off the rows, not off a key analyze() never returned
  "Apple" is recording revenue, not neighbouring rights
  the plate's silkscreen is never printed twice
  a phone keeps the figures when it loses the photograph
"""
import io
import os
import re
import uuid

import pytest

import app as appmod
import business_room as bz
import db as store
import royalty_types

PW = "business-room-1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _room(page):
    return page.split("<!--room:business-->", 1)[1].split("<!--/room:business-->")[0]


def _account(name="Business Artist"):
    email = "bzroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _css():
    return io.open(os.path.join(HERE, "static", "css", "business-room.css"),
                   encoding="utf-8").read()


# --- the one figure this room must never produce -------------------------

def test_the_three_windows_are_never_added_together():
    """recovery_engine.build returns a total_at_stake that sums an actual
    with an estimate. The Recovery page refuses to print it; so does this
    screen, and build() has no code path that makes one."""
    out = bz.build(42380, 37839, 312, 1840, 28415, 26310,
                   "", [], [], [], {}, note="x")
    keys = [w["key"] for w in out["windows"]]
    assert keys == ["reported", "not-collected", "kept"]
    assert "total" not in out
    figures = [w["figure"] for w in out["windows"] if w["figure"]]
    for w in out["windows"]:
        for part in (w["split"] or ()):
            figures.append(part["figure"])
    printed = {f["value"] for f in figures}
    for forbidden in ("$2,152.00", "$44,220.00", "$2152.00"):  # 312+1840, 42380+1840
        assert forbidden not in printed, "an actual was added to an estimate"


def test_not_collected_is_two_readings_each_named_for_what_it_is():
    mid = bz.windows(1, None, 312, 1840, None, None)[1]
    assert mid["figure"] is None, "the middle window has no single figure"
    assert [p["label"] for p in mid["split"]] == ["Actual unattributed",
                                                  "Estimated missing"]
    assert [p["figure"]["value"] for p in mid["split"]] == ["$312.00", "$1,840.00"]
    assert mid["split"][1]["tag"] == "estimate"
    assert mid["split"][0]["tag"] == "", "a measurement is not tagged as one"
    # The estimate is marked TWICE without the tag being printed: the plate
    # silkscreens ESTIMATE inside that pane, and the label is the word.
    assert "Estimated" in mid["split"][1]["label"]


# --- a null is not a nought ----------------------------------------------

def test_every_figure_is_in_dollars_and_matches_the_statements_desk():
    """Owner, 2026-09-22: "Why did the money turn into like euros or
    something? It's not showing his dollar bills."

    It was a pound, because the mockup he rendered happened to carry one
    and I took it for a spec instead of reading the app - which has never
    had a pound in it. Every figure now prints through
    statements_desk.money, the same helper Statements, Royalties and
    Recovery use, so a reading on this plate reconciles character for
    character with the page behind it.
    """
    import statements_desk
    for value in (0, 312, 42380.5, 1840):
        assert bz.money(value)["value"] == statements_desk.money(value)
    assert bz.money(42380.5)["value"] == "$42,380.50"
    src = io.open(os.path.join(HERE, "business_room.py"), encoding="utf-8").read()
    for bad in ("£", "€", "GBP", "EUR"):
        assert bad not in src, bad


def test_an_unmeasured_figure_is_words_not_zero():
    assert bz.money(None) == {"value": "Not measured", "measured": False}
    assert "0" not in bz.money(None)["value"]


def test_a_genuine_zero_still_prints():
    """$0.00 unattributed on an account WITH statements is a measurement
    somebody took. It must not be mistaken for the absence."""
    assert bz.money(0) == {"value": "$0.00", "measured": True}


def test_no_move_is_drawn_when_there_is_nothing_to_compare():
    """A 0% would read as "no change" when the truth is "no previous
    period". One period is not a trend."""
    assert bz.change(100, None) is None
    assert bz.change(None, 100) is None
    assert bz.change(100, 0) is None
    assert bz.change(112, 100) == {"pct": "+12%", "up": True}


# --- one basis for the whole plate ---------------------------------------

def test_periods_come_off_the_rows_because_analyze_returns_none():
    """The first cut of the route read analysis["by_period"], a key
    analyze() has never returned. The window silently showed the lifetime
    total while the note under it said "One period on file" - on every
    account, including one with twelve."""
    import statements_engine
    assert statements_engine.analyze([
        {"title": "a", "source": "Spotify", "amount": 1.0, "period": "2026-01"},
    ]).get("by_period") is None

    order, totals, undated = bz.periods([
        {"source": "Spotify", "amount": 1200.0, "period": "2026-01"},
        {"source": "Apple Music", "amount": 640.0, "period": "2026-01"},
        {"source": "Spotify", "amount": 1500.0, "period": "2026-02"},
    ])
    assert order == ["2026-01", "2026-02"]
    assert totals["2026-01"] == 1840.0 and totals["2026-02"] == 1500.0
    assert undated == 0


def test_a_period_label_nobody_can_read_is_kept_out_of_the_ordering():
    """period_key sorts an unreadable shape to (9999, 0) - the very end -
    so leaving it in would hand "Q1-2026" to the window as the most
    recent period."""
    order, totals, undated = bz.periods([
        {"amount": 100.0, "period": "2026-01"},
        {"amount": 900.0, "period": "Q1-2026"},
        {"amount": 50.0, "period": ""},
    ])
    assert order == ["2026-01"]
    assert "Q1-2026" not in totals
    assert undated == 2, "both the unreadable and the blank are counted"


def test_the_reading_names_the_period_it_read():
    assert bz.reading(["2026-01", "2026-02"], {"2026-01": 1840, "2026-02": 1500},
                      3340) == (1500, 1840, "2026-02 vs. 2026-01")
    assert bz.reading(["2026-01"], {"2026-01": 1840}, 1840) == (
        1840, None, "2026-01 · the only period on file")


def test_with_no_readable_period_the_window_is_everything_and_says_so():
    got = bz.reading([], {}, 3340)
    assert got[0] == 3340 and got[1] is None
    assert "all statements" in got[2]
    assert bz.reading([], {}, None) == (None, None, "Needs a statement")


def test_costs_are_taken_from_the_same_period_as_the_income():
    """Subtracting every cost an account ever logged from one period's
    income is how a page comes to report a negative month."""
    spend = [{"amount": 120.0, "spend_date": "2026-02-04"},
             {"amount": 300.0, "spend_date": "2025-11-02"}]
    assert bz.costs_in(spend, "2026-02") == 120.0
    assert bz.costs_in(spend, "2026-01") == 0.0
    assert bz.costs_in(spend, "Q1-2026") is None, "an unreadable period tells us nothing"
    assert bz.costs_in(spend, "") is None


def test_kept_is_not_measured_when_no_costs_were_ever_logged():
    """Kept is income LESS costs. An account that has logged none has not
    said what it spent, so printing Reported again under KEPT would claim
    this artist kept every penny - a statement about their finances drawn
    from missing data."""
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "HP", "source": "Spotify", "amount": 1200.0, "period": "2026-01"}])
    store.save_statement(uid, "q2.csv", [
        {"title": "HP", "source": "Spotify", "amount": 1500.0, "period": "2026-02"}])
    # Owner, 2026-09-22, second ruling: the plate is on the flip like
    # every other room - the display until a statement exists, then the
    # readings in the screen's green. With a statement on file and no
    # cost ever logged, REPORTED is a figure and KEPT is a window with
    # nothing to read, which fills with the reel and says so beneath.
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "rk-cine" not in body, "a statement on file flips the plate off the display"
    assert "bz-fig" in body, "reported is a figure"
    assert "rk-reel--fill" in body, "kept has nothing to read: the reel fills it"
    assert "Not measured" in body, "and the small line still says what is missing"
    # The two noughts on this plate are measurements - every row of the
    # statement is titled, so nothing is unattributed - and they print.
    # KEPT is the absence, and it prints no figure at all.
    kept = body.split('<p class="bz-sr">Kept</p>', 1)[1].split("</div>", 1)[0]
    assert "bz-fig" not in kept and "rk-reel--fill" in kept
    assert "$" not in kept, "an absence is never a nought"
    order, totals, _ = bz.periods(store.get_statement_rows(uid))
    reported, prior, _note = bz.reading(order, totals, None)
    assert reported == 1500.0, "reported is the latest period"
    assert bz.costs_in([], order[-1]) == 0.0
    assert bz.money(None)["value"] == "Not measured", "kept is None with no costs on file"
    store.add_expense(uid, "Mastering", "Release-Ready", 120.0, "2026-02-04")
    spent = bz.costs_in(store.list_expenses(uid), order[-1])
    assert spent == 120.0
    assert bz.money(reported - spent)["value"] == "$1,380.00", "reported less that period's costs"


# --- where the money comes from ------------------------------------------

def test_apple_is_recording_revenue_and_not_neighbouring_rights():
    """"ppl" sits inside "apple". Matched as a substring it filed every
    Apple payment this app has ever read under neighbouring rights - on
    the Royalties desk, the Publishing room, recovery_mlc's lanes and
    artist_os alike."""
    assert royalty_types.classify("Apple") == "recording"
    assert royalty_types.classify("Apple Music") == "recording"
    assert royalty_types.classify("PPL") == "neighboring", "the real one still works"
    assert royalty_types.classify("Grand Metal") == "other", "and not 'meta'"
    # the long needles still match mid-string
    assert royalty_types.classify("Harry Fox Agency") == "mechanical"
    assert royalty_types.classify("CD Baby Pro") == "recording"


def test_the_streams_are_folded_out_of_the_rows():
    """The route used to read analysis["by_bucket"], which analyze() has
    never returned, so every stream read "—" on every account - telling an
    artist with a Spotify statement they had no measured streaming
    income."""
    rows = [{"source": "Spotify", "amount": 1200.0},
            {"source": "Apple Music", "amount": 640.0},
            {"source": "BMI", "amount": 88.0}]
    got = {s["label"]: s for s in bz.streams(rows)}
    assert got["Streaming"]["amount"] == "$1,840.00"
    assert got["Streaming"]["measured"] is True
    assert got["Performance"]["amount"] == "$88.00"
    assert got["Mechanicals"]["amount"] == "—", "no statement is not nought"
    assert got["Mechanicals"]["why"] == "No MLC statement"


def test_money_from_an_unclassifiable_source_is_never_hidden():
    """Four named streams and nothing else would swallow it between them."""
    got = {s["label"]: s for s in bz.streams([{"source": "Unknown", "amount": 312.0}])}
    assert got["Unclassified"]["amount"] == "$312.00"
    assert "Unclassified" not in {s["label"] for s in bz.streams([])}


def test_a_row_whose_amount_is_not_a_number_does_not_take_the_page_down():
    """One inf row took down every money page on 2026-09-20."""
    assert bz._amount(float("inf")) == 0.0
    assert bz._amount(float("nan")) == 0.0
    assert bz._amount(None) == 0.0 and bz._amount("x") == 0.0
    assert bz._amount("12.5") == 12.5


# --- the missing-money queue is a count, never a figure -------------------

def test_the_missing_money_tile_carries_no_dollars():
    """artist_os._LANE_SHARE applies six hardcoded coefficients to the
    WHOLE-ACCOUNT total once per track, so its estimate can exceed
    everything the catalogue has ever earned. Its tile is a door, not a
    reading."""
    name, line = bz.RENAMED["money-queue"]
    assert name == "Missing money"
    assert not re.search(r"[£$]\s?[\d,]+", line)


# --- the tiles ------------------------------------------------------------

_CARDS = {k: ("/" + k, "M1", k.title(), "desc") for k in (
    "royalties", "statements", "tax", "recovery", "money-queue", "cases",
    "disputes", "valuation", "revenue-os", "hours", "deals", "deal-simulator",
    "team", "portal", "services", "roster", "vault", "contracts")}


def test_tax_and_contracts_keep_their_tiles_because_they_are_their_own_pages():
    """They LOOK like free merges - each is a second view of another
    card's handler, /statements?view=tax and /vault?view=contracts. But
    both templates switch on that argument, so the bare page does not
    contain the other view. One handler, two pages; folding the tile away
    deletes the only door rather than tidying a page."""
    here = os.path.join(HERE, "templates")
    for template, view in (("statements.html", "tax"), ("vault.html", "contracts")):
        body = io.open(os.path.join(here, template), encoding="utf-8").read()
        assert '{%% if view == "%s" %%}' % view in body, (
            "%s no longer hides the %s view - the merge may now be real"
            % (template, view))

    keys = [t["key"] for t in bz.build(None, None, None, None, None, None,
                                       "", [], [], [], _CARDS)["tiles"]]
    assert len(keys) == 18, "eighteen cards, eighteen doors"
    assert "tax" in keys and "statements" in keys
    assert "contracts" in keys and "vault" in keys


def test_roster_portal_and_services_keep_their_tiles_because_nothing_else_links_them():
    """A grep for their hrefs finds no other door in the rooms layout, so
    this tile IS the way in. Dropping a tile does not tidy a page away, it
    strands it - the "no way out" shape from the route walk."""
    here = os.path.join(HERE, "templates")
    for key in ("roster", "portal", "services"):
        assert key in bz.TILES, key
        # A page linking back to its own parent is a way OUT, not a door
        # in, so the feature's own templates do not count.
        family = key.rstrip("s")
        doors = {f for f in os.listdir(here)
                 if f.endswith(".html") and not f.startswith(family)
                 and ('href="/%s"' % key) in
                 io.open(os.path.join(here, f), encoding="utf-8").read()}
        # base.html carries a label-plan hub rail for services, which the
        # rooms layout replaces. If a real door ever appears, this tile may
        # leave TILES - and this assertion is what will say so.
        assert doors <= {"base.html"}, (
            "%s now has another door (%s) - it may leave TILES" % (key, sorted(doors)))


def test_a_seat_that_cannot_open_a_page_is_not_shown_its_tile():
    out = bz.build(None, None, None, None, None, None, "", [], [], [], _CARDS,
                   can_open=lambda href: href not in ("/vault", "/team"))
    keys = [t["key"] for t in out["tiles"]]
    assert "vault" not in keys and "team" not in keys and "royalties" in keys


def test_a_renamed_tile_keeps_its_card_s_own_href():
    """Renaming is for what the card is CALLED on this screen; it must
    never quietly repoint a door."""
    tiles = {t["key"]: t for t in bz.build(None, None, None, None, None, None,
                                           "", [], [], [], _CARDS)["tiles"]}
    assert tiles["cases"]["name"] == "Claims"
    for key, tile in tiles.items():
        assert tile["href"] == _CARDS[key][0], key


# --- the page itself ------------------------------------------------------

def test_an_empty_account_opens_on_the_unit_and_prints_no_nought():
    """The room opens on the instrument whatever the account holds - the
    same mistake as Stage, made once and not again."""
    c, _uid = _account()
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "business-plate.webp" in body, "the photographed unit is always there"
    # Owner, 2026-09-22: a plate whose every window reads "Not measured"
    # is worse than no plate, so an account that has measured nothing
    # now meets the STANDBY - words about what will fill each window.
    # The zero rule is unchanged and still checked below.
    # The caption standby became the DISPLAY the same afternoon (owner:
    # "slot machine-y" - the big window sequences the room's features,
    # the small ones are a reel, a hint and a ticker, never a caption).
    # The zero rule is unchanged and still checked.
    import re as _re
    _f = _re.findall(r"rk-cine-frame[^>]*>\s*(?:<img[^>]*>\s*)?<b[^>]*>([^<]*)", body)
    assert _f == ['Statements', 'Royalties', 'Recovery', 'Profit &amp; Loss'], _f
    assert body.count("rk-tip-win") == 1 and body.count("rk-tick-win") == 1, "the hint and the ticker"
    assert "Upload a statement" in body, "the hero pill is the way in"
    assert "bz-fig" not in body, "no reading is drawn while nothing is measured"
    assert not re.search(r"\$\s?0\b", body), "a nought would be a claim"
    assert "rk-calm" not in body or "Nothing open." in body


def test_the_title_is_the_room_s_name_with_no_room_behind_it():
    """Owner, 2026-09-22: "the rooms don't need room behind the title.
    Stage is Stage not Stage Room." The sidebar has always called them by
    the bare name; the screens now agree with it."""
    import rooms
    c, _uid = _account()
    page = c.get("/room/business").get_data(as_text=True)
    name = [r[1] for r in rooms.ROOMS if r[0] == "business"][0]
    assert ">%s</h1>" % name in page
    assert "Business Room" not in page
    assert "<title>%s" % name in page, "the browser tab too"


def test_the_plate_image_carries_a_cache_version():
    """Studio's lost afternoon: the file was REPLACED in place, so browsers
    took the new stylesheet - whose fractions are measured against the new
    crop - and kept the old picture they already had."""
    c, _uid = _account()
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "business-plate.webp?v=" in body


def test_the_markup_never_prints_the_plate_s_own_silkscreen():
    """REPORTED, NOT COLLECTED and KEPT are printed on the photograph, and
    ACTUAL and ESTIMATE inside the two middle panes. Owner, 2026-09-22:
    "make sure you check for duplicate buttons and text". The names are in
    the markup for screen readers only."""
    c, _uid = _account()
    body = _room(c.get("/room/business").get_data(as_text=True))
    unit = body.split('class="bz-unit', 1)[1].split("</section>", 1)[0]
    for word in ("Reported", "Not collected", "Kept",
                 "Actual unattributed", "Estimated missing"):
        for hit in re.finditer(re.escape(">" + word), unit):
            before = unit[:hit.start()].rsplit("<", 1)[-1]
            # Either screen-reader class: this room's own bz-sr on the
            # readings, and the kit's rk-pl-sr on the standby windows.
            # They are the same device under two prefixes.
            assert ('class="bz-sr"' in before or 'class="rk-pl-sr"' in before), (
                '"%s" is printed on the plate; the markup prints it again' % word)


def test_the_rail_under_the_plate_uses_none_of_the_plate_s_words():
    """The first rung was "Reported" and the last was "Kept" - the same two
    words the photograph prints forty pixels above them."""
    names = {name for _key, name, _sub in bz.STEPS}
    assert not (names & {"Reported", "Not collected", "Kept"})
    assert names == {"Statements", "Matched", "Chased", "Recovered", "Costs"}


# --- the sheet ------------------------------------------------------------

def test_the_plate_has_a_container_context_for_its_own_text():
    """Studio's bug, in full: every text size on a plate is a clamp() in
    cqw, because the unit scales and its windows are fractions. cqw
    resolves against an inline-size container; with none, every one of
    those declarations is invalid and the type falls back to page-sized and
    bursts out of the windows. cqh does NOT resolve against an inline-size
    container, so nothing here may be sized off the height."""
    css = _css()
    unit = css.split(".bz-unit {", 1)[1].split("}", 1)[0]
    assert "container-type: inline-size" in unit
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)   # this sheet EXPLAINS cqh
    assert "cqh" not in code


def test_a_narrow_screen_keeps_the_figures_and_loses_the_photograph():
    """The figures ARE the screen. A phone that dropped them would show a
    picture of an instrument instead of this artist's money."""
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    narrow = css.split("@media (max-width: 560px)", 1)[1]
    assert ".bz-plate { display: none; }" in narrow
    assert not re.search(r"\.bz-(win|fig|split|part)[^{]*\{[^}]*display:\s*none", narrow), (
        "the readings must survive the plate")
    # and the silkscreen names have to become visible, since the plate that
    # printed them is gone
    assert ".bz-sr {" in narrow


def test_the_room_never_claims_money_will_be_recovered():
    c, _uid = _account()
    body = _room(c.get("/room/business").get_data(as_text=True))
    for claim in ("you will recover", "guaranteed", "owed to you",
                  "On The Table", "at stake"):
        assert claim.lower() not in body.lower(), claim


def test_the_plate_fractions_agree_between_the_module_and_the_sheet():
    """This room measured its windows in CSS before the shared kit existed,
    and the standby needs the same numbers in Python to position itself.
    Two copies with nothing between them drift the first time the plate is
    re-cropped, and the failure is silent: the readings stay on their glass
    and the standby lands beside it.
    """
    css = io.open(os.path.join(HERE, "static", "css", "business-room.css"),
                  encoding="utf-8").read()
    unit = css.split(".bz-unit {", 1)[1].split("}", 1)[0]

    def var(name):
        return float(re.search(r"--%s:\s*([\d.]+)%%" % name, unit).group(1))

    top, height = var("win-y"), var("win-h")
    for key, x_var, w_var in (("reported", "rep-x", "rep-w"),
                              ("not-collected", "mid-x", "mid-w"),
                              ("kept", "kept-x", "kept-w")):
        x, y, w, h = bz.PLATE[key]
        assert (x, y, w, h) == (var(x_var), top, var(w_var), height), (
            "%s: module says %s, the sheet says %s"
            % (key, (x, y, w, h), (var(x_var), top, var(w_var), height)))


def test_the_board_is_three_bands():
    """Owner, 2026-09-22: "group, do not delete." Sixteen tiles against
    three to six in every other room, and four of them - Recovery,
    Claims, Missing money, Disputes - are one job. Nothing moved and
    nothing went; the board just says which job each door belongs to.
    """
    out = bz.build(None, None, None, None, None, None, {}, [], [], [],
                   _CARDS)
    titles = [b["title"] for b in out["bands"]]
    assert titles == ["The money you have", "The money you're owed",
                      "The paperwork and the people"], titles

    # the four that are one job are in one band, and it is theirs alone
    owed = [t["key"] for t in out["bands"][1]["tiles"]]
    assert owed == ["recovery", "cases", "money-queue", "disputes"], owed

    # every tile still drawn, exactly once, and `tiles` still flat
    banded = [t["key"] for b in out["bands"] for t in b["tiles"]]
    assert banded == [t["key"] for t in out["tiles"]]
    assert len(banded) == len(set(banded)), "a tile drawn twice"


def test_an_empty_band_is_not_drawn():
    """A Label-only card or a seat's gate can empty a band, and a heading
    over nothing is worse than no heading."""
    only_money = {k: v for k, v in _CARDS.items()
                  if k in ("royalties", "statements")}
    out = bz.build(None, None, None, None, None, None, {}, [], [], [],
                   only_money)
    assert [b["title"] for b in out["bands"]] == ["The money you have"]
