"""The day-of-show page, as the owner ruled it (2026-09-07, by numbered
mockup).

The event header (the room, "Show N of M · artist", the venue, the date
· city · status as a select that posts itself); one button, Send
advance; "From your sheet" only when the import gave us a ticket link or
a guarantee; then ONE grid, "Add to this show", holding every feature in
a fixed order - a + row until it is on the show, a folded row in the same
place once it is. Nothing is pre-added: a fresh show is nineteen + rows
and no meter, because nothing has been measured. The meter appears once
a feature is on and counts only what the features on the show own.

The audit (2026-09-07) added two rows - Openers & set times after Times,
Crew on this show after Venue & contacts - a quiet Day sheet link beside
the one button, the sheet's support, capacity and promoter, the calendar
day's note above the show notes, and one "All N dates" line ending every
body. The bar names the run-wide view each entry opens.
"""
import os
import re

import tour_os
import tour_store as ts
from tests.test_tour_date_page import (_user, _tour, _show, _fresh, _page, _sections, _chips,  # noqa: F401
                                       _member_join, flask_app)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES = ["times", "lineup", "advance", "venue", "crew", "deal", "notes", "hotel", "travel", "guests", "vip",
            "settlement", "merch", "marketing", "content", "setlist", "files", "tasks", "activity"]


def _grid(html):
    """Every cell of the feature grid in order: a key for a row on the
    show, +key for a plus row."""
    grid = html.split('id="features"')[1].split("<script>")[0]
    return [(m.group(1) or ("+" + m.group(2))) for m in
            re.finditer(r'<section class="to-sec[^"]*" id="([a-z]+)"|class="to-feature-add" data-chip="([a-z]+)"', grid)]


def _open(html):
    return re.findall(r'<section class="to-sec[^"]*" id="([a-z]+)" data-section="[a-z]+">\s*<details class="to-sec-d" open>', html)


def _header(html):
    return re.split(r'id="(sheet|readiness|add-to-show)"', html.split('id="event"')[1])[0]


def _head_of(html, key):
    return html.split('id="%s" data-section="%s"' % (key, key))[1].split("</summary>")[0]


def _sheet(html):
    return re.split(r'id="(readiness|add-to-show)"', html.split('id="sheet"')[1])[0]


def _add(client, tid, sid, key, action="add"):
    return client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": key, "action": action})


def _readiness(tid, sid):
    return tour_os._readiness_for(ts.get_tour(tid), ts.get_show(tid, sid))


# --- 1, 2, 4, 5: a fresh show ---------------------------------------------------

def test_a_fresh_show_is_the_header_the_button_and_nineteen_plus_rows(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    sid2 = _show(client, tid, "2030-05-03", "Room Two")
    html = _page(client, tid, sid)
    assert [k for k, *_ in tour_os.FEATURE_ORDER] == FEATURES, "the grid order is fixed"
    assert _grid(html) == ["+" + k for k in FEATURES], "every feature a + row, in order, nothing pre-added"
    assert _sections(html) == [] and _open(html) == []
    # A + row is the icon disc, a +, and the name - nothing else.
    row = html.split('data-chip="hotel"')[1].split("</form>")[0]
    assert '<span class="plus" aria-hidden="true">+</span><span class="to-sec-title">Hotel</span></button>' in row
    assert 'title="Add a hotel"' in row and ">Add a hotel<" not in html
    # No meter, no strip, no status row, no prev/next, no day sheet, no sheet block.
    assert 'id="readiness"' not in html and "to-strip" not in html and 'class="to-ready' not in html
    assert 'aria-label="Readiness' not in html and "% ready" not in html and "applicable" not in html
    assert ">0%<" not in html and "not started" not in html
    assert "to-strip-status" not in html and html.count('class="to-status-form') == 1, "the status lives in the header only"
    assert "/shows/%s" % sid2 not in html
    assert 'id="sheet"' not in html and "From your sheet" not in html
    # The header: thumb, eyebrow, venue, date · city · status, and one button.
    head = _header(html)
    assert '<span class="to-thumb to-thumb--mono to-thumb--lg" aria-hidden="true">TB</span>' in head
    assert '<p class="to-eyebrow">Show 1 of 2 · Test Artist</p>' in head
    assert ">The Basement East</h1>" in head
    assert "Nashville, TN" in head and "America/Chicago" not in head
    form = re.search(r'<form method="post" action="/tours/%s/shows/%s/ext" class="to-status-form to-head-status">(.*?)</form>'
                     % (tid, sid), head, re.S)
    assert form and 'value="hold" selected' in form.group(1) and ">Update<" in form.group(1)
    assert tuple(re.findall(r'<option value="([a-z]+)"', form.group(1))) == ts.SHOW_STATUSES
    assert head.count('class="to-btn to-btn--small"') == 1 and "Send advance" in head
    assert 'href="/tours/%s/shows/%s?tab=send" data-reveal="send"' % (tid, sid) in head
    # Beside it, one quiet link to the day sheet - not a second button.
    assert '<a class="to-quiet-link" href="/tours/%s/shows/%s/day-sheet">Day sheet</a>' % (tid, sid) in head
    assert head.count("Day sheet") == 1
    assert ".to-head-status select" in html and "requestSubmit" in html
    # Readiness, honestly: nothing on, nothing measured.
    r = _readiness(tid, sid)
    assert r["total"] == 0 and r["checks"] == [] and r["pct"] == 0
    assert ts.get_show(tid, sid)["readiness_config"] == []
    # The list pages say the same - never 0%.
    for path in ("/tours/%s" % tid, "/tours/%s/shows" % tid, "/tours/%s/calendar?month=2030-05" % tid):
        page = client.get(path).get_data(as_text=True)
        assert "not started" in page and ">0%<" not in page and "0% ready" not in page, path


# --- 4, 5: adding features --------------------------------------------------------

def test_adding_times_and_hotel_makes_them_rows_in_place_and_brings_the_meter(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    r = _add(client, tid, sid, "times")
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=times")
    assert ts.get_show(tid, sid)["readiness_config"] == ["times"]
    html = _page(client, tid, sid)
    assert _grid(html) == ["times"] + ["+" + k for k in FEATURES[1:]], "the row took the + row's place"
    assert _open(html) == [], "nothing opens until the URL asks"
    head = _head_of(html, "times")
    assert re.search(r'class="sb-lamp\s*">empty</span>', head) and "No times yet" in head
    assert "Stamp standard show day" in html, "the body is there, folded"
    assert 'name="acts"' not in html, "the bill is its own row, not on the show yet"
    assert "Remove from this show" in html
    # Times owns no readiness item: the strip is up, but nothing is measured yet.
    assert 'id="readiness"' in html and "not started" in html and "nothing counted yet" in html
    assert 'aria-label="Readiness' not in html and ">0%<" not in html
    assert "* The meter grows with the features you add to this show." in html
    assert _open(_page(client, tid, sid, "times")) == ["times"]

    _add(client, tid, sid, "hotel")
    assert ts.get_show(tid, sid)["readiness_config"] == ["times", "hotel"]
    html = _page(client, tid, sid)
    expect = ["+" + k for k in FEATURES]
    expect[0], expect[7] = "times", "hotel"
    assert _grid(html) == expect, "grid order kept; the other seventeen stay + rows"
    assert sum(1 for c in _grid(html) if c.startswith("+")) == 17
    r = _readiness(tid, sid)
    assert r["total"] == 1 and [c["key"] for c in r["checks"]] == ["hotel"]
    assert "0 of 1 applicable" in html and 'class="to-ready lo"' in html and 'aria-label="Readiness: 0%"' in html
    assert "<b>Next:</b> Hotel" in html
    assert 'name="property"' in html and "No hotel yet" in html
    assert html.count("Remove from this show") == 2


def test_the_meter_counts_only_what_the_features_on_the_show_own(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    assert tour_os.SECTION_CATEGORIES["advance"] == ("advance", "production", "catering", "hospitality",
                                                     "confirmation", "contract")
    assert tour_os.SECTION_CATEGORIES["deal"] == ("deposit",)
    assert tour_os.SECTION_CATEGORIES["venue"] == ("venue", "promoter")
    assert tour_os.SECTION_CATEGORIES["times"] == () and tour_os.SECTION_CATEGORIES["notes"] == ()
    assert tour_os.SECTION_CATEGORIES["activity"] == ()
    assert set(tour_os.CORE_CATEGORIES) == {"advance", "production", "catering", "hospitality",
                                            "confirmation", "contract", "deposit", "venue", "promoter"}
    _add(client, tid, sid, "advance")
    r = _readiness(tid, sid)
    assert {c["key"] for c in r["checks"]} == set(tour_os.SECTION_CATEGORIES["advance"]) and r["total"] == 6
    _add(client, tid, sid, "deal")
    r = _readiness(tid, sid)
    assert "deposit" in {c["key"] for c in r["checks"]} and r["total"] == 6, "no deposit required: n/a, not counted"
    _add(client, tid, sid, "venue")
    r = _readiness(tid, sid)
    assert {"venue", "promoter"} <= {c["key"] for c in r["checks"]} and r["total"] == 8
    # Rows count without an opt-in: one ground leg brings travel and ground.
    client.post("/tours/%s/travel/add" % tid, data={"show_id": sid, "day_date": "2030-05-02", "mode": "ground"})
    r = _readiness(tid, sid)
    assert {"travel", "ground"} <= {c["key"] for c in r["checks"]} and r["total"] == 10
    html = _page(client, tid, sid)
    assert "%d of %d applicable" % (r["done"], r["total"]) in html
    assert "travel" in _grid(html) and "+travel" not in _grid(html)


# --- 3: from your sheet --------------------------------------------------------------

def test_the_sheet_shows_exactly_the_ticket_link_and_the_guarantee(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid), data={"ticket_url": "https://tickets.example/x/1"})
    html = _page(client, tid, sid)
    assert "From your sheet" in html and 'id="sheet"' in html
    sheet = _sheet(html)
    assert '<a class="to-chip" href="https://tickets.example/x/1" target="_blank" rel="noopener">tickets.example</a>' in sheet
    assert sheet.count('<span class="to-fig">') == 1 and "guarantee" not in sheet
    client.post("/tours/%s/shows/%s/money" % (tid, sid), data={"guarantee": "1500", "deal_type": "flat"})
    html = _page(client, tid, sid)
    sheet = _sheet(html)
    assert sheet.count('<span class="to-fig">') == 2
    assert '<span class="to-fig"><span>guarantee</span><b>1500 USD</b></span>' in sheet
    assert "capacity" not in sheet and "promoter" not in sheet, "nothing given, nothing stated"
    # Support, capacity and promoter are stated as plain facts once the sheet holds them (the audit).
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"promoter": "Local Promoter", "capacity": "500"})
    client.post("/tours/%s/shows/%s/lineup" % (tid, sid), data={"acts": "Opener One\nHeadliner"})
    sheet = _sheet(_page(client, tid, sid))
    assert '<span class="to-fig"><span>support</span><b>Opener One, Headliner</b></span>' in sheet
    assert '<span class="to-fig"><span>capacity</span><b>500</b></span>' in sheet
    assert '<span class="to-fig"><span>promoter</span><b>Local Promoter</b></span>' in sheet
    assert sheet.count('<span class="to-fig">') == 5 and "<form" not in sheet and "<details" not in sheet
    # The rows those came from are on the show now, because they hold data.
    assert "marketing" in _grid(html) and "deal" in _grid(html)
    # A viewer without financials sees the tickets and never the guarantee.
    crew, _m = _member_join(flask_app, client, tid, ["view", "edit"])
    theirs = _page(crew, tid, sid)
    assert "tickets.example" in theirs and "1500 USD" not in theirs and "guarantee" not in theirs.split('id="features"')[0]
    assert "+deal" not in _grid(theirs) and "deal" not in _grid(theirs)


# --- 4: activity is opt-in only -----------------------------------------------------------

def test_activity_never_appears_unless_added(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/shows/%s/notes" % (tid, sid), data={"notes": "Load in through the alley."})
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": "confirmed"})
    assert ts.list_changes(tid), "there is a log"
    html = _page(client, tid, sid)
    assert _grid(html)[-1] == "+activity" and 'id="activity"' not in html
    assert "notes" in _grid(html), "a feature with data is on; the log is not data"
    _add(client, tid, sid, "activity")
    html = _page(client, tid, sid)
    assert _grid(html)[-1] == "activity" and _open(html) == []
    head = _head_of(html, "activity")
    assert re.search(r"\d+ changes?", head) and 'sb-lamp sb-lamp--on">set</span>' in head
    assert "Remove from this show" in html.split('id="activity"')[1]
    _add(client, tid, sid, "activity", "remove")
    assert ts.get_show(tid, sid)["readiness_config"] == []
    assert _grid(_page(client, tid, sid))[-1] == "+activity"
    # The old deep link still shows it, without adding it.
    assert _open(_page(client, tid, sid, "activity")) == ["activity"]
    assert ts.get_show(tid, sid)["readiness_config"] == []


# --- 1: the status select ---------------------------------------------------------------------

def test_the_status_select_is_in_the_header_line_and_posts_to_ext(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    url = "/tours/%s/shows/%s" % (tid, sid)
    r = client.post(url + "/ext", data={"status": "confirmed"}, headers={"Referer": "http://localhost" + url})
    assert r.status_code == 302 and r.headers["Location"].endswith(url)
    assert ts.get_show(tid, sid)["status"] == "confirmed"
    head = _header(_page(client, tid, sid))
    assert 'value="confirmed" selected' in head
    line = head.split('class="to-sub to-head-line"')[1].split("</form>")[0]
    assert "Nashville, TN" in line and 'name="status"' in line, "date · city · status, one line"
    # A viewer reads the status as a chip and gets no form.
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    theirs = _page(viewer, tid, sid)
    assert "to-status-form" not in theirs and '<span class="to-chip to-chip--ok">confirmed</span>' in _header(theirs)


# --- scope ---------------------------------------------------------------------------------------

def test_a_viewer_without_edit_sees_no_plus_rows_for_core_features(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    hotel, _h = _member_join(flask_app, client, tid, ["view", "hotel"], label="Hotels")
    assert _grid(_page(hotel, tid, sid)) == ["+hotel"], "only the feature their scope can add"
    assert _add(hotel, tid, sid, "times").status_code == 403
    assert _add(hotel, tid, sid, "hotel").status_code == 302
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    html = _page(viewer, tid, sid)
    assert _grid(html) == ["hotel"], "what is on the show, and no + rows at all"
    assert _add(viewer, tid, sid, "notes").status_code == 403
    editor, _e = _member_join(flask_app, client, tid, ["view", "edit"], label="Editor")
    grid = _grid(_page(editor, tid, sid))
    assert "+times" in grid and "+advance" in grid and "+venue" in grid and "+notes" in grid and "+activity" in grid
    assert "+deal" not in grid and "+settlement" not in grid, "money needs financials"
    assert _add(editor, tid, sid, "deal").status_code == 403
    assert _add(editor, tid, sid, "notes").status_code == 302
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel", "notes"]


# --- add / remove --------------------------------------------------------------------------------------

def test_remove_works_on_an_empty_feature_and_is_refused_on_one_with_data(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    for key in ("notes", "advance", "settlement"):
        _add(client, tid, sid, key)
    assert ts.get_show(tid, sid)["readiness_config"] == ["notes", "advance", "settlement"]
    r = _add(client, tid, sid, "settlement", "remove")
    assert r.status_code == 302 and ts.get_show(tid, sid)["readiness_config"] == ["notes", "advance"]
    client.post("/tours/%s/shows/%s/notes" % (tid, sid), data={"notes": "Load in through the alley."})
    r = _add(client, tid, sid, "notes", "remove")
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=notes")
    assert ts.get_show(tid, sid)["readiness_config"] == ["notes", "advance"], "data keeps it on"
    html = _page(client, tid, sid)
    notes = html.split('id="notes" data-section="notes"')[1].split("</section>")[0]
    assert "Remove from this show" not in notes and 'sb-lamp sb-lamp--on">set</span>' in notes
    advance = html.split('id="advance" data-section="advance"')[1].split("</section>")[0]
    assert "Remove from this show" in advance
    # A feature with data nobody added is on, and cannot be removed either.
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"promoter": "Local Promoter"})
    assert "venue" in _grid(_page(client, tid, sid))
    _add(client, tid, sid, "venue", "remove")
    assert "venue" in _grid(_page(client, tid, sid))
    assert client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": "nope", "action": "add"}).status_code == 404


def test_the_settlement_is_its_own_feature(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid, "settlement")
    assert _open(html) == ["settlement"] and re.search(r'<section class="to-sec is-target[^"]*" id="settlement"', html)
    assert 'id="settlement-form"' in html and 'name="settlement_amount"' in html
    assert 'name="guarantee"' not in html, "the deal is its own row, and not on the show"
    r = client.post("/tours/%s/shows/%s/money" % (tid, sid), data={"settlement_amount": "1250", "settlement_status": "settled"})
    assert r.headers["Location"].endswith("?tab=settlement")
    html = _page(client, tid, sid)
    assert "settlement" in _grid(html) and "settled · 1250 USD" in _head_of(html, "settlement")
    assert "+deal" in _grid(html), "a settlement figure is not a deal"


# --- the review's defects, pinned ----------------------------------------------------------------

def test_adding_an_expense_lands_on_the_settlement_and_opens_nothing_else(flask_app):
    """The ledger lives in the Settlement feature. The redirect used to say
    ?tab=money, which is the Deal: a feature nobody added, drawn open by
    the redirect while the row that held the new expense stayed folded."""
    client, owner, tid, sid = _fresh(flask_app)
    r = client.post("/tours/%s/expenses/add" % tid, data={"show_id": sid, "amount": "40", "vendor": "Backline"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/shows/%s?tab=settlement" % sid)
    html = _page(client, tid, sid, "settlement")
    assert _sections(html) == ["settlement"] and _open(html) == ["settlement"]
    assert "+deal" in _grid(html), "the Deal stays a + row"
    assert "1 expense" in _head_of(html, "settlement") and 'sb-lamp sb-lamp--on">set</span>' in _head_of(html, "settlement")
    html = _page(client, tid, sid)
    assert _open(html) == [] and _sections(html) == ["settlement"], "nothing opens by itself"


def test_the_meter_is_up_whenever_the_show_is_measured_even_if_the_viewer_cannot_read_the_row(flask_app):
    """A feature on the show counts for everyone; a viewer without its
    scope loses the row, not the meter. The show page and the tour list
    score the same date the same way for the same viewer."""
    client, owner, tid, sid = _fresh(flask_app)
    _add(client, tid, sid, "settlement")
    editor, _e = _member_join(flask_app, client, tid, ["view", "edit"], label="Editor")
    html = _page(editor, tid, sid)
    grid = _grid(html)
    assert "settlement" not in grid and "+settlement" not in grid, "money needs financials"
    assert 'id="readiness"' in html and "0 of 1 applicable" in html and 'aria-label="Readiness: 0%"' in html
    assert "<b>Next:</b> Settlement" in html
    for path in ("/tours/%s" % tid, "/tours/%s/shows" % tid):
        row = editor.get(path).get_data(as_text=True)
        assert "<b>0%</b>" in row and "1 missing" in row, (path, "the list and the page agree")
    # The deal joins in: its deposit counts for a viewer who may not read it.
    client.post("/tours/%s/shows/%s/money" % (tid, sid),
                data={"guarantee": "1500", "deal_type": "flat", "deposit_required": "500"})
    assert _readiness(tid, sid)["total"] == 2
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    theirs = _page(viewer, tid, sid)
    assert _grid(theirs) == [], "nothing they may read, and no + rows"
    assert 'id="readiness"' in theirs and "0 of 2 applicable" in theirs
    assert "1500 USD" not in theirs and 'id="sheet"' not in theirs, "the figure itself stays behind financials"
    assert "* The meter grows with the features you add to this show." in theirs
    # Nothing on: no meter for anyone, on any page.
    sid2 = _show(client, tid, "2030-05-04", "Room Two")
    assert 'id="readiness"' not in _page(viewer, tid, sid2)


def test_the_times_lamp_reads_what_the_viewer_can_see(flask_app):
    """A lamp is only for state, and the state is what the row shows this
    viewer: a management-only schedule item is a set lamp for the owner
    and an empty one - beside 'No times yet' - for a viewer who cannot see it."""
    client, owner, tid, sid = _fresh(flask_app)
    r = client.post("/tours/%s/schedule/add" % tid, data={
        "show_id": sid, "title": "Settlement meeting", "start_time": "23:30", "visibility": "management"})
    assert r.status_code == 302
    head = _head_of(_page(client, tid, sid), "times")
    assert 'sb-lamp sb-lamp--on">set</span>' in head and "1 item · 0 confirmed" in head
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    html = _page(viewer, tid, sid)
    assert "times" in _grid(html), "the show holds times, so the row is on"
    head = _head_of(html, "times")
    assert re.search(r'class="sb-lamp\s*">empty</span>', head) and "No times yet" in head
    assert "sb-lamp--on" not in head and "Settlement meeting" not in html


def test_the_header_status_select_rule_outranks_the_dates_row_rule():
    """Both classes sit on the header form; the compact rule must win on
    specificity, not on source order (which it lost)."""
    css = open(os.path.join(HERE, "static", "css", "tour-os.css"), encoding="utf-8").read()
    head = re.search(r"\.to-head-line \.to-head-status select \{([^}]*)\}", css)
    assert head and "min-height: 28px" in head.group(1) and "padding: 2px 8px" in head.group(1)
    assert re.search(r"(?m)^\.to-head-status select \{", css) is None, "the bare rule is gone"
    rows = re.search(r"\.to-status-form select \{([^}]*)\}", css)
    assert rows and "min-height: 32px" in rows.group(1), "the Dates rows keep theirs"


def test_the_tour_pages_load_the_people_table_once_however_many_dates(flask_app, monkeypatch):
    """Readiness per show used to fetch the tour-wide people list once per
    date. One list per request, and the advance rows once per date."""
    client, owner, tid, sid = _fresh(flask_app)
    calls = {"people": 0, "advance": 0}
    real_people, real_advance = ts.list_people, ts.list_advance

    def people(*a, **k):
        calls["people"] += 1
        return real_people(*a, **k)

    def advance(*a, **k):
        calls["advance"] += 1
        return real_advance(*a, **k)

    monkeypatch.setattr(ts, "list_people", people)
    monkeypatch.setattr(ts, "list_advance", advance)
    paths = ("/tours/%s" % tid, "/tours/%s/shows" % tid, "/tours/%s/calendar?month=2030-05" % tid)

    def load(path):
        calls["people"] = calls["advance"] = 0
        assert client.get(path).status_code == 200, path
        return dict(calls)

    one = {p: load(p) for p in paths}
    for d in ("2030-05-03", "2030-05-04", "2030-05-05"):
        _show(client, tid, d, "Room " + d[-2:])
    four = {p: load(p) for p in paths}
    for p in paths:
        assert four[p]["people"] == one[p]["people"], (p, "people loads must not grow with the dates")
        # readiness reads the advance rows once per date; home and the list
        # read them once more per date for the advance recipients
        assert one[p]["advance"] <= 2 and four[p]["advance"] <= 8, (p, one[p], four[p])


# --- the assets --------------------------------------------------------------------------------------------

def test_the_sheet_and_the_worker_moved_on():
    css = open(os.path.join(HERE, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-feature-grid" in css and ".to-feature-btn" in css and ".to-head-status" in css and ".to-sheet" in css
    assert ".to-features {" not in css and ".to-strip-status" not in css
    shell = open(os.path.join(HERE, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 25
    sw = open(os.path.join(HERE, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 211
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 212, "the audit bumped the worker"
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 26
    assert ".to-sec-all" in css and ".to-bar-note" in css and ".to-quiet-link" in css
    page = open(os.path.join(HERE, "templates", "tour", "show.html"), encoding="utf-8").read()
    assert "tail_sections" not in page and "chips" not in page and "prev_show" not in page
    assert not os.path.exists(os.path.join(HERE, "templates", "tour", "show", "_people.html")), "the crew list is its own row now"


# --- the audit (2026-09-07) -----------------------------------------------------------------------------

def _body_of(html, key):
    return html.split('id="%s" data-section="%s"' % (key, key))[1].split("</section>")[0]


def _person(client, tid, name, shows=None, **extra):
    data = {"name": name, "category": "Crew", "role": extra.pop("role", "FOH")}
    data.update(extra)
    if shows:
        data["shows"] = shows
    r = client.post("/tours/%s/people/save" % tid, data=data)
    assert r.status_code == 302
    return next(p["id"] for p in ts.list_people(tid) if p["name"] == name)


def test_the_bill_is_its_own_row_after_times_with_its_own_status_line(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    assert FEATURES.index("lineup") == FEATURES.index("times") + 1
    assert tour_os.SECTION_CATEGORIES["lineup"] == () and tour_os.SECTION_ADD_SCOPE["lineup"] == "edit"
    r = _add(client, tid, sid, "lineup")
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=lineup")
    html = _page(client, tid, sid)
    assert _grid(html)[:2] == ["+times", "lineup"], "the bill is on; times is not"
    head = _head_of(html, "lineup")
    assert ">Openers &amp; set times<" in head and "No openers yet" in head
    assert re.search(r'class="sb-lamp\s*">empty</span>', head)
    assert 'name="acts"' in _body_of(html, "lineup"), "the bill form lives here"
    client.post("/tours/%s/shows/%s/lineup" % (tid, sid), data={"acts": "Opener One\nOpener Two\nHeadliner"})
    html = _page(client, tid, sid)
    head = _head_of(html, "lineup")
    assert "3 acts on the bill" in head and 'sb-lamp sb-lamp--on">set</span>' in head
    assert "+times" in _grid(html), "acts are not times"
    # Times is the schedule alone: its line never mentions the bill.
    client.post("/tours/%s/schedule/add" % tid, data={"show_id": sid, "title": "Doors", "start_time": "19:00"})
    html = _page(client, tid, sid)
    times = _head_of(html, "times")
    assert "1 item · 0 confirmed" in times and "bill" not in times and "act" not in times
    assert 'name="acts"' not in _body_of(html, "times")
    # A viewer reads the bill and gets no form.
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    theirs = _page(viewer, tid, sid)
    assert "lineup" in _grid(theirs) and "Opener One" in theirs and 'name="acts"' not in theirs


def test_the_crew_row_assigns_people_to_the_date_and_saves_call_times(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    sid2 = _show(client, tid, "2030-05-03", "Room Two")
    assert FEATURES.index("crew") == FEATURES.index("venue") + 1
    assert tour_os.SECTION_CATEGORIES["crew"] == () and tour_os.SECTION_ADD_SCOPE["crew"] == "edit"
    assert tour_os.TAB_SECTION["people"] == "crew"
    everyone = _person(client, tid, "Tour Manager", role="TM")           # on every date
    foh = _person(client, tid, "Front Of House", shows=[sid2])           # on the other date only
    html = _page(client, tid, sid)
    assert "+crew" in _grid(html), "nobody named on this date yet"
    html = _page(client, tid, sid, "crew")
    body = _body_of(html, "crew")
    assert 'action="/tours/%s/shows/%s/crew"' % (tid, sid) in body
    assert 'name="assign" value="%s"' % foh in body and 'name="assign" value="%s" checked' % foh not in body
    assert ">on every date<" in body and 'name="assign" value="%s"' % everyone not in body, "every-date people are not per-show"
    assert 'name="call:%s"' % everyone in body and 'name="call:%s"' % foh in body
    assert "Nobody assigned" not in _head_of(html, "crew") and "1 on this date" in _head_of(html, "crew")
    r = client.post("/tours/%s/shows/%s/crew" % (tid, sid),
                    data={"assign": [foh], "call:%s" % foh: "15:00", "call:%s" % everyone: "13:30"})
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=crew")
    assert sorted(ts.get_person(tid, foh)["shows"]) == sorted([sid2, sid])
    assert ts.get_person(tid, everyone)["shows"] == []
    assert ts.list_show_calls(tid, sid) == {foh: "15:00", everyone: "13:30"}
    assert ts.list_show_calls(tid, sid2) == {}, "a call time is per date"
    html = _page(client, tid, sid)
    assert "crew" in _grid(html) and "+crew" not in _grid(html)
    head = _head_of(html, "crew")
    assert "2 on this date" in head and 'sb-lamp sb-lamp--on">set</span>' in head
    body = _body_of(html, "crew")
    assert 'name="assign" value="%s" checked' % foh in body and 'value="15:00"' in body and 'value="13:30"' in body
    assert any(c["field"] == "crew" and "Front Of House" in c["after"] for c in ts.list_changes(tid))
    assert any(c["field"] == "call times" for c in ts.list_changes(tid))
    # A view-only member reads the same rows and cannot change them.
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    theirs = _page(viewer, tid, sid)
    assert "crew" in _grid(theirs)
    body = _body_of(theirs, "crew")
    assert "Front Of House" in body and "15:00" in body and "13:30" in body and ">on every date<" in body
    assert 'name="assign"' not in body and 'name="call:' not in body and "Save crew" not in body
    assert viewer.post("/tours/%s/shows/%s/crew" % (tid, sid), data={"assign": []}).status_code == 403
    # Unticking takes them off this date; unticking their last date is refused, not turned into 'every date'.
    client.post("/tours/%s/shows/%s/crew" % (tid, sid), data={})
    assert ts.get_person(tid, foh)["shows"] == [sid2] and ts.list_show_calls(tid, sid) == {}
    client.post("/tours/%s/shows/%s/crew" % (tid, sid2), data={})
    assert ts.get_person(tid, foh)["shows"] == [sid2], "one date cannot become every date by an untick"


def test_venue_and_contacts_no_longer_lists_the_crew(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    _person(client, tid, "Tour Manager", role="TM")
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"promoter": "Local Promoter"})
    html = _page(client, tid, sid, "venue")
    body = _body_of(html, "venue")
    assert "Tour Manager" not in body and "Contacts on this date" not in body and 'id="people"' not in body
    assert "No venue record linked · Local Promoter" in _head_of(html, "venue"), "the room and the promoter"
    # The old ?tab=people link lands on the crew row.
    html = _page(client, tid, sid, "people")
    assert _open(html) == ["crew"] and 'id="people"' in _body_of(html, "crew")


def test_a_calendar_day_note_shows_above_the_show_notes(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    day = next(d for d in ts.list_days(tid) if d.get("show_id") == sid)
    html = _page(client, tid, sid, "notes")
    assert "From the calendar" not in html
    r = client.post("/tours/%s/days/%s/edit" % (tid, day["id"]), data={"notes": "Bus call moved to 09:00."})
    assert r.status_code == 302
    html = _page(client, tid, sid, "notes")
    body = _body_of(html, "notes")
    note = body.split('id="day-note"')[1].split("</p>")[0]
    assert "<strong>From the calendar:</strong> Bus call moved to 09:00." in note
    assert 'href="/tours/%s/calendar"' % tid in note
    assert note.index("From the calendar") < body.index('name="notes"'), "above the textarea"
    assert "Bus call moved" not in body.split('name="notes"')[1], "read-only here; it is edited on the calendar"


def test_the_day_sheet_link_is_in_the_header_for_everyone_who_may_open_it(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    link = '<a class="to-quiet-link" href="/tours/%s/shows/%s/day-sheet">Day sheet</a>' % (tid, sid)
    assert link in _header(_page(client, tid, sid))
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    theirs = _page(viewer, tid, sid)
    assert link in _header(theirs) and "Send advance" not in _header(theirs)
    assert viewer.get("/tours/%s/shows/%s/day-sheet" % (tid, sid)).status_code == 200


def test_every_body_ends_with_one_all_dates_line_to_its_run_wide_page(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    _show(client, tid, "2030-05-03", "Room Two")
    _show(client, tid, "2030-05-04", "Room Three")
    for key, page in (("hotel", "hotels"), ("guests", "guests"), ("crew", "people"), ("times", "schedule"),
                      ("deal", "money"), ("settlement", "money"), ("activity", "changes"), ("content", "content")):
        body = _body_of(_page(client, tid, sid, key), key)
        assert body.count("All 3 dates ›") == 1, key
        assert '<p class="to-sec-all"><a href="/tours/%s/%s">All 3 dates ›</a></p>' % (tid, page) in body, key
    assert "All shows" not in _page(client, tid, sid, "content"), "one wording"
    assert "All 3 dates" not in _body_of(_page(client, tid, sid, "lineup"), "lineup"), "no run-wide page for the bill"
    # The line goes only where the viewer may: a run-wide page is gated the
    # same way its section is, so an editor without guests gets neither.
    editor, _e = _member_join(flask_app, client, tid, ["view", "edit"], label="Editor")
    body = _body_of(_page(editor, tid, sid, "hotel"), "hotel")
    assert "All 3 dates ›" in body and "/tours/%s/hotels" % tid in body
    theirs = _page(editor, tid, sid, "crew")
    assert "/tours/%s/people" % tid in _body_of(theirs, "crew")
    for gated in ("guests", "vip", "merch", "money", "marketing", "content", "files"):
        assert "/tours/%s/%s" % (tid, gated) not in theirs, gated
    guests, _g = _member_join(flask_app, client, tid, ["view", "guests"], label="Guests")
    body = _body_of(_page(guests, tid, sid, "guests"), "guests")
    assert '<p class="to-sec-all"><a href="/tours/%s/guests">All 3 dates ›</a></p>' % tid in body


def test_the_bar_names_the_run_and_says_so_under_itself(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    line = '<p class="to-bar-note">Every date on this tour. Open a show to work one night.</p>'
    venues = client.get("/tours/%s/venues" % tid).get_data(as_text=True)
    bar = venues.split('class="to-tabs to-bar"')[1].split("</nav>")[0]
    labels = re.findall(r'class="to-tab[^"]*"[^>]*>([^<]+)<', bar)
    assert labels[:7] == ["Home", "Import", "Venue book", "Crew directory", "All travel &amp; hotels", "Tour money", "All files"]
    assert line in venues and venues.count("to-bar-note") == 1
    travel = client.get("/tours/%s/hotels" % tid).get_data(as_text=True)
    sub = travel.split('class="to-subnav"')[1].split("</nav>")[0]
    assert re.findall(r">([^<]+)</a>", sub) == ["Flights &amp; ground", "Hotels &amp; rooming", "Route"]
    assert line in travel
    show = _page(client, tid, sid)
    assert "to-bar-note" not in show, "the plate already says the show"
    home = client.get("/tours/%s" % tid).get_data(as_text=True)
    assert "to-bar-note" not in home and 'class="to-tabs to-bar"' not in home, "the bare list carries neither"
