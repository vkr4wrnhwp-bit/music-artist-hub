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


def _statement(uid):
    """One statement on file: the populated analyser, not the page from zero."""
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 2640.0, "period": "2026-01"}])


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
    screens = re.findall(r'<li class="cz-screen".*?</li>', body, re.S)
    assert len(screens) == 3
    reported, _nc, kept = screens
    assert "cz-screen-v--fig" in reported, "reported is a figure"
    # KEPT is the absence: words, set as words, and no figure at all.
    assert "cz-screen-v--none" in kept and ">Not measured<" in kept
    assert "cz-screen-v--fig" not in kept
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
    """Its tile is a door, not a reading. When this was written
    artist_os._LANE_SHARE applied six hardcoded coefficients to the
    WHOLE-ACCOUNT total once per track, so its estimate could exceed
    everything the catalogue had ever earned. Since 2026-09-23 each figure
    is a share of that track's own rows (tests/test_real_money.py), but the
    queue prints no total and the tile still carries none: a sum of
    estimates is not a reading either."""
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

def test_an_empty_account_meets_the_page_from_zero_not_an_empty_analyser():
    """The page from zero (owner's Business spec + mockup, 2026-09-23). The
    analyser waits for paperwork; a new account meets the Command Center's
    three-screen plate, STATIC, with this room's words, and the spec's
    order under it. No date range, no income total, no profit, no recovery
    estimate, no percentage, no nought - and none of the analyser's parts."""
    import re as _re
    c, _uid = _account()
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "room-plate.webp" in body, "the rooms' photographed three-window plate"
    assert "business-plate.webp" not in body, "the analyser waits for paperwork"
    assert "rk-cine" not in body and "rk-tip-win" not in body and "rk-tick-win" not in body, "nothing rotates"
    assert "bz-fig" not in body and "bz-win" not in body, "no reading, measured or not"
    # the three screens, the spec's words exactly, none of them a door
    for k, v in bz.ZERO_RACK:
        assert k in body and v in body, (k, v)
    assert body.count('<li class="cz-screen"') == 3 and 'class="cz-screen-v" href' not in body
    # the header: the spec's subtitle, the account chip kept, the one door
    assert "See what you earned, what you spent, and what still needs attention." in body
    assert "Business Artist" in body, "the account selector still says whose information it is"
    assert 'class="rk-cta" href="%s"' % bz.DOOR.replace("&", "&amp;") in body and "Upload your first statement" in body
    assert bz.DOOR == "/statements?returnTo=/room/business&from=business-zero-state", "exactly as the spec writes it"
    # the card and the four categories, each a door by its own room card
    assert "Start with your first statement" in body and "Upload a statement" in body
    assert 'class="bz-z-btn" href="%s"' % bz.DOOR.replace("&", "&amp;") in body
    assert "Upload statement</a>" in body and "How statements work" in body
    assert "What Business will organize" in body
    for _k, name, line, _card in bz.LENSES:
        assert name.replace("&", "&amp;") in body and line in body, name
    for href in ("/statements", "/revenue-os", "/recovery", "/vault"):
        assert 'class="bz-z-lens" href="%s?returnTo=/room/business"' % href in body, href
    # the five steps as education, numbered, Upload lit
    for _k, name, line in bz.WORKFLOW:
        assert name in body and line in body, name
    rail = body.split("How Business works")[1].split("Your money picture will appear here")[0]
    assert "%" not in rail and "Complete" not in rail and "In progress" not in rail
    assert 'class="rk-step is-first"' in body and "rk-step--ahead" not in body
    assert '<span class="rk-ring" aria-hidden="true">1</span>' in rail and '>5</span>' in rail
    # the two empties in words, help, the drawer open under four categories
    assert "Your money picture will appear here" in body and "No income is measured yet" in body
    assert "Missing statements never become $0." in body
    assert 'href="/statements?returnTo=/room/business#intake">Supported statements' in body
    assert "Import history" not in body, "an empty history is the empty table the spec forbids"
    assert "Not sure which statement to upload?" in body and 'href="/contact">Ask Street Banker' in body
    assert '<details class="bz-z-fold" open>' in body and "More Business tools" in body, (
        "the drawer starts OPEN (owner, 2026-09-23: people need to see it)")
    drawer = body.split('<details class="bz-z-fold"')[1]
    titles = _re.findall(r'<h3 class="bz-band">([^<]+)</h3>', drawer)
    assert titles == ["Statements &amp; royalties", "Costs &amp; profit", "Recovery &amp; claims", "Contracts &amp; people"], titles
    # every tool this plan has, in the spec's order (Label-only cards such
    # as the roster and services are not this Artist account's to draw)
    drawn = _re.findall(r'data-room-card="([a-z-]+)"', drawer)
    expected = [k for _t, keys in bz.ZERO_BANDS for k in keys]
    assert set(drawn) <= set(expected) and drawn == [k for k in expected if k in set(drawn)], drawn
    for must_have in ("royalties", "statements", "tax", "recovery", "vault", "contracts", "deals"):
        assert must_have in drawn, must_have
    # no money, no nought, no date range, no comparison
    text = _re.sub(r"<style.*?</style>|<script.*?</script>|<[^>]+>", " ", body, flags=_re.S)
    money = [m for m in _re.findall(r"\$\s?[\d,]+(?:\.\d+)?", text) if m.replace("$", "").strip() != "0"]
    assert not money, money
    assert not _re.search(r"(?<![\d.])0%", text)
    zone = body.split("Start with your first statement", 1)[1].split("More Business tools", 1)[0]
    for control in ('name="range"', 'name="period"', "Compare", "Last 30 days", "<select"):
        assert control not in zone, control
    assert "Explore more tools" not in body and "Where the money is" not in body


def test_the_desk_carries_the_way_back_and_the_saved_statement_says_the_line():
    c, uid = _account()
    page = c.get("/room/business?from=business-zero-state").get_data(as_text=True)
    assert bz.DONE_LINE not in page, "the param alone says nothing"
    _statement(uid)
    assert bz.DONE_LINE in c.get("/room/business?from=business-zero-state").get_data(as_text=True)
    assert bz.DONE_LINE not in c.get("/room/business").get_data(as_text=True)


def test_the_done_line_is_said_by_the_record_not_the_param():
    assert bz.done_line("business-zero-state", 0) == ""
    assert bz.done_line(None, 2) == ""
    assert bz.done_line("statement", 2) == ""
    assert bz.done_line("business-zero-state", 1) == bz.DONE_LINE


def test_new_account_is_empty_on_every_count_the_spec_names():
    assert bz.new_account([], [], [], [], []) is True
    assert bz.new_account([{"id": "s"}], [], [], [], []) is False
    assert bz.new_account([], [{"amount": 1}], [], [], []) is False
    assert bz.new_account([], [], [{"amount": 5}], [], []) is False
    assert bz.new_account([], [], [], [{"id": "c"}], []) is False
    assert bz.new_account([], [], [], [], [{"id": "d"}]) is False


def test_one_statement_brings_the_analyser_back_untouched():
    c, uid = _account()
    _statement(uid)
    body = _room(c.get("/room/business").get_data(as_text=True))
    # the working room on the rooms' shared three-window plate (owner,
    # 2026-09-23), each screen named since the plate prints no names
    assert "room-plate.webp?v=" in body and "business-plate" not in body
    assert re.findall(r'<span class="cz-screen-k">([^<]+)</span>', body) == ["Reported", "Not collected", "Kept"]
    assert "Explore more tools" in body
    assert "Start with your first statement" not in body and "bz-z-fold" not in body
    titles = re.findall(r'<h3 class="bz-band">([^<]+)</h3>', body)
    assert titles == ["The money you have", "The money you&#39;re owed", "The paperwork and the people"], (
        "the populated room keeps its own three bands (owner, 2026-09-22)")


def test_a_seat_that_may_not_write_gets_no_door_and_a_category_it_cannot_open_is_words():
    z = bz.zero_page(can_add="seat", can_open=lambda href: href != "/vault", cards=_CARDS)
    assert z["project"]["can"] == "seat"
    by = {l["key"]: l for l in z["lenses"]}
    assert by["people"]["href"] == "" and by["statements"]["href"] == "/statements"
    assert [b["title"] for b in z["bands"]][-1] == "Contracts & people"
    assert "vault" not in [t["key"] for b in z["bands"] for t in b["tiles"]]
    assert bz.zero_page(cards=_CARDS)["project"]["can"] is True


def test_a_failed_read_is_the_error_page_never_a_new_account(monkeypatch):
    """Owner's spec: never convert a loading failure into the new-account
    state. Before this, costs, claims and disputes each fell back to
    nothing on their own, which read as a fresh account."""
    def boom(*_a, **_k):
        raise RuntimeError("business: store down")
    monkeypatch.setattr(store, "list_recovery_cases", boom)
    c, _uid = _account()
    r = c.get("/room/business")
    assert r.status_code == 503
    page = r.get_data(as_text=True)
    assert "We could not load Business" in page
    assert 'href="/room/business"' in page and 'href="/statements"' in page and "Open statements" in page
    assert "Start with your first statement" not in page and "room-plate" not in page


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
    c, uid = _account()
    _statement(uid)
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "room-plate.webp?v=" in body


def test_each_screen_says_its_name_once_and_the_estimate_is_named():
    """The rooms' plate prints no names (owner, 2026-09-23), so each screen
    carries its own - once. Not collected stays two readings, never one
    sum: the actual figure, and the estimate NAMED as an estimate under it."""
    c, uid = _account()
    _statement(uid)
    body = _room(c.get("/room/business").get_data(as_text=True))
    rack = body.split('class="cz-rack"', 1)[1].split("</section>", 1)[0]
    for word in ("Reported", "Not collected", "Kept"):
        assert rack.count(">%s<" % word) == 1, word
    nc = re.findall(r'<li class="cz-screen".*?</li>', rack, re.S)[1]
    assert "Actual unattributed" in nc and "estimated missing" in nc


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
    c, uid = _account()
    pages = [_room(c.get("/room/business").get_data(as_text=True))]
    _statement(uid)
    pages.append(_room(c.get("/room/business").get_data(as_text=True)))
    for body in pages:
        for claim in ("you will recover", "guaranteed", "owed to you",
                      "On The Table", "at stake"):
            assert claim.lower() not in body.lower(), claim


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


def test_the_owners_hidden_mark_stays_on_a_zero_page_tile():
    """rooms.build keeps a page the owner hid as a card in state "hidden"
    for the owner alone; the drawer from zero carries that mark to its
    tile as the populated Marketing room does, instead of dropping it."""
    cards = {k: v + ("hidden" if k == "vault" else "live",) for k, v in _CARDS.items()}
    z = bz.zero_page(cards=cards)
    tiles = {t["key"]: t for b in z["bands"] for t in b["tiles"]}
    assert tiles["vault"]["state"] == "hidden" and tiles["statements"]["state"] != "hidden"


def test_the_owners_hidden_mark_stays_on_a_populated_room_tile():
    """The populated room's tiles carry the owner's mark too: the same
    pill the drawer from zero shows, by the same state."""
    cards = {k: v + ("hidden" if k == "valuation" else "live",) for k, v in _CARDS.items()}
    out = bz.build(None, None, None, None, None, None, "", [], [], [], cards)
    tiles = {t["key"]: t for b in out["bands"] for t in b["tiles"]}
    assert tiles["valuation"]["state"] == "hidden" and tiles["statements"]["state"] != "hidden"


# --- the audit of 2026-09-23 ---------------------------------------------

_CSV = b"Title,Store,Amount,Period\nHigher Places,Spotify,2640.00,2026-01\n"


def test_the_real_upload_from_the_door_comes_back_with_the_done_line():
    """Audit business-1/17: the desk's form has no action, so it posts to
    the door's own address. The save redirected to bare /statements and
    dropped returnTo and from, so the done line was unreachable except by
    typing ?from= by hand. The save now carries the way back."""
    c, uid = _account()
    door = c.get(bz.DOOR).get_data(as_text=True)
    form = door.split('<form method="post" enctype="multipart/form-data"', 1)[1].split(">", 1)[0]
    assert "action=" not in form, "the form posts to the door's own address"
    r = c.post(bz.DOOR, data={"statement": (io.BytesIO(_CSV), "q1.csv")},
               content_type="multipart/form-data")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/room/business?from=business-zero-state")
    assert len(store.get_statements(uid)) == 1
    room = c.get(r.headers["Location"]).get_data(as_text=True)
    assert bz.DONE_LINE in room


def test_an_upload_with_a_way_back_but_no_from_keeps_the_way_back():
    c, _uid = _account()
    r = c.post("/statements?returnTo=/room/business",
               data={"statement": (io.BytesIO(_CSV), "q1.csv")}, content_type="multipart/form-data")
    assert r.headers["Location"].endswith("/statements?returnTo=/room/business")
    r = c.post("/statements?returnTo=//evil.example&from=x",
               data={"statement": (io.BytesIO(_CSV), "q2.csv")}, content_type="multipart/form-data")
    assert r.headers["Location"].endswith("/statements") and "evil" not in r.headers["Location"]


def test_an_open_business_action_keeps_the_account_off_the_zero_page():
    """Audit business-2, spec 3: new_account only after confirming no
    Business actions. An open action filed under Business is work."""
    import command_center as cc
    assert bz.new_account([], [], [], [], [], [{"id": "a"}]) is False
    c, uid = _account()
    aid = cc.create_action(uid, "Chase the missing BMI statement", room="business", priority="high")
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "Start with your first statement" not in body
    cc.set_action_status(aid, uid, "complete")
    body = _room(c.get("/room/business").get_data(as_text=True))
    assert "Start with your first statement" in body, "a finished action is not open work"
    cc.create_action(uid, "Pitch the single", room="marketing")
    assert "Start with your first statement" in _room(c.get("/room/business").get_data(as_text=True))


def test_the_card_promises_only_what_the_upload_reads():
    """Audit business-3: the card said "CSV, spreadsheet, or PDF"; the
    upload reads CSV only and printed a PDF's raw bytes as its headers."""
    desc = bz.ZERO_PROJECT["desc"]
    assert "CSV" in desc and "PDF" not in desc and "spreadsheet" not in desc
    c, uid = _account()
    for name, data in (("statement.pdf", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj"),
                       ("statement.xlsx", b"PK\x03\x04\x14\x00\x06\x00\x08\x00"),
                       ("statement.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00")):
        page = c.post("/statements", data={"statement": (io.BytesIO(data), name)},
                      content_type="multipart/form-data").get_data(as_text=True)
        err = page.split('class="sd-error" role="alert">', 1)[1].split("</div>", 1)[0]
        assert "Headers seen" not in err and "%PDF" not in err and "PK" not in err, err
        assert "Export" in err and "CSV" in err, err
    assert store.get_statements(uid) == []


def test_the_intake_says_what_happens_to_a_file_before_it_is_chosen():
    """Audit business-5, spec 6 and 22: before the file chooser, the
    types, the size, what is kept, currencies, undo and duplicates - as
    they are today, claiming nothing unbuilt."""
    c, _uid = _account()
    page = c.get(bz.DOOR).get_data(as_text=True)
    intake = page.split('id="intake"', 1)[1].split("<form", 1)[0]
    for said in ("CSV", "210 MB", "file itself is not kept", "currency", "Remove", "twice"):
        assert said in intake, said


def test_ask_street_banker_opens_the_corner_box():
    """Audit business-6: the help button went to the public Contact page
    while the corner box of the same name sat on the page."""
    c, _uid = _account()
    page = c.get("/room/business").get_data(as_text=True)
    assert '<a class="bz-z-more" id="bz-ask" href="/contact">' in page
    script = page.split('getElementById("bz-ask")', 1)[1][:600]
    assert 'getElementById("sbq-open")' in script and "preventDefault" in script
    assert 'id="sbq-open"' in page, "the corner box it opens is on the page"


def test_business_is_the_current_page_in_the_sidebar(monkeypatch):
    """Audit business-7, spec 21: the room link says aria-current, not
    only a colour."""
    monkeypatch.setenv("NAV_ROOMS", "1")
    c, _uid = _account()
    page = c.get("/room/business").get_data(as_text=True)
    links = re.findall(r'<a href="/room/business"[^>]*>', page)
    assert links and all('aria-current="page"' in a for a in links), links
    assert not any("aria-current" in a for a in re.findall(r'<a href="/room/fans"[^>]*>', page))
    inside = c.get("/statements").get_data(as_text=True)
    links = [a for a in re.findall(r'<a href="/room/business"[^>]*>', inside) if "sb-room-back" not in a]
    assert links and all('aria-current="true"' in a for a in links), links


def test_the_workflow_stacks_on_a_phone():
    """Audit business-8, spec 20: "workflow vertical" on mobile. The kit's
    rail is a sideways scroller under 860px; the page from zero's rail
    stacks instead, scoped to this page so the kit's lock is untouched."""
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    rail = re.search(r"@media \(max-width: 860px\) \{[^@]*?\.bz-z-flow \.rk-rail \{([^}]*)\}", css)
    assert rail and "flex-direction: column" in rail.group(1) and "overflow-x: visible" in rail.group(1)
    c, _uid = _account()
    assert "business-room.css?v=6" in c.get("/room/business").get_data(as_text=True)


def test_the_way_back_names_the_room_as_the_sidebar_does():
    """Audit business-13: a returnTo back link read "Back to the business
    room"; rooms are called by their bare names (owner, 2026-09-22)."""
    c, _uid = _account()
    page = c.get("/statements?returnTo=/room/business").get_data(as_text=True)
    back = page.split('id="sb-room-back"', 1)[1].split("</a>", 1)[0].split("</svg>", 1)[1]
    assert "Back to Business" in back and "room" not in back
    page = c.get("/connections?returnTo=%2Froom%2Fanalytics%3Ffrom%3Dconnect").get_data(as_text=True)
    assert "Back to Analytics" in page.split('id="sb-room-back"', 1)[1].split("</a>", 1)[0]


def test_the_demo_sees_the_business_showcase():
    """Audit business-18: the demo's Business showcase was right and
    unpinned."""
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = _room(demo.get("/room/business").get_data(as_text=True))
    assert "Sample data" in body and "Start with your first statement" not in body
    assert "room-plate.webp?v=" in body


def _team(access):
    import team_areas

    def acct(name):
        email = "%s-%s@example.net" % (name, uuid.uuid4().hex[:8])
        cl = appmod.app.test_client()
        cl.post("/signup", data={"name": name, "email": email, "password": PW})
        uid = store.get_user_by_email(email)["id"]
        store.set_user_plan(uid, "pro")
        cl.post("/login", data={"email": email, "password": PW})
        return cl, uid, email
    owner, oid, _ = acct("bzowner")
    member, _mid, memail = acct("bzseat")
    assert owner.post("/team/invite", data={
        "email": memail, "role": "manager", "access": access, "areas_sent": "1",
        "areas": list(team_areas.keys())}).get_json()["ok"]
    row = [m for m in store.list_team(oid) if m["email"] == memail][0]
    member.post("/team/join/" + row["invite_token"], data={})
    member.post("/portal/%s/open" % oid)
    return member


def test_a_read_seat_is_offered_no_upload_door_at_the_route():
    body = _room(_team("read").get("/room/business").get_data(as_text=True))
    assert "Start with your first statement" in body
    assert bz.DOOR.replace("&", "&amp;") not in body and 'class="rk-cta"' not in body
    assert bz.ZERO_PROJECT["locked"] in body
    body = _room(_team("edit").get("/room/business").get_data(as_text=True))
    assert 'class="rk-cta" href="%s"' % bz.DOOR.replace("&", "&amp;") in body


@pytest.mark.parametrize("read", ["get_statement_rows", "get_statements", "list_expenses",
                                  "list_recovery_cases", "list_disputes"])
def test_every_failed_read_is_the_error_page(monkeypatch, read):
    def boom(*_a, **_k):
        raise RuntimeError("business: store down")
    c, _uid = _account()
    monkeypatch.setattr(store, read, boom)
    r = c.get("/room/business")
    assert r.status_code == 503 and "We could not load Business" in r.get_data(as_text=True)


def test_a_failed_action_read_is_the_error_page(monkeypatch):
    import command_center as cc

    def boom(*_a, **_k):
        raise RuntimeError("actions down")
    c, _uid = _account()
    monkeypatch.setattr(cc, "list_actions", boom)
    assert c.get("/room/business").status_code == 503
