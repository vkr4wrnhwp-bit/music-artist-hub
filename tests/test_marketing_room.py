"""The Marketing Room: the Marketing room's opening screen (owner's design,
2026-09-21).

The layout is his; the figures are the account's own, and his own example
figures never reach a real page. The honesty rules these lock:

  a real account with nothing on record is told so in words, never in zeros
  the demo account is the only one shown the example figures
  every figure traces to a record this account holds
  the range chooser governs the hero band, and the rail is the whole record
  the rollout row pushes our smart link without requiring it (owner)
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import db as store
import links_store as mls
import marketing_room as mr
import press_store
import rollout_store as ros
import rooms

PW = "marketing-room-1"

# Every figure his design drew. None of these may reach a real account.
# HIS_EXAMPLE is the whole example, checked against an account with nothing
# on record at all. HIS_FIGURES is the counts alone, checked against an
# account with records of its own, because a real artist may perfectly well
# have a media contact in one of the example's cities.
HIS_FIGURES = ("12,480", "2,140", "47 opens", "6 coverage hits",
               "18 contacts", "5 pitches", "Sample data.")
HIS_EXAMPLE = HIS_FIGURES + ("386", "Toronto", "Berlin", "Sydney")


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account(name="Room Artist"):
    email = "mktroom-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _link_events(user_id, kinds, days_ago=1):
    """Smart link events on this account's own campaign, at a chosen age.
    Written the way the public link route writes them, with a timestamp the
    window can be tested against."""
    cid = mls.create_campaign(user_id, "mkt-%s" % uuid.uuid4().hex[:8],
                              {"title": "Test single"})
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
    with store.get_db() as db:
        for kind, n in kinds.items():
            for _i in range(n):
                db.execute("INSERT INTO ml_events (campaign_id, event_type, created)"
                           " VALUES (?,?,?)", (cid, kind, when))
    return cid


# --- the page, in every account state --------------------------------------

def test_an_empty_account_is_told_in_words_and_never_shown_a_zero():
    """The state a new artist sees first. Nothing is on record, so nothing
    is counted: each instrument says so in words."""
    c, _uid = _account()
    body = c.get("/room/marketing").get_data(as_text=True)
    assert ">Marketing</h1>" in body
    assert "Help independent musicians get heard and get written about." in body
    assert "No visits in this window" in body
    assert "None yet" in body                          # Clicks and Pre-saves
    for words in ("No announcements ready", "No pitches sent", "No opens logged",
                  "No coverage logged", "No smart link visits"):
        assert words in body, words
    assert "Nothing is waiting on you here." in body   # no action is not a zero row
    assert "No contact cities on file yet." in body
    assert "Read from your own records" in body        # the Live mark, not Sample
    for gone in HIS_EXAMPLE:
        assert gone not in body, gone


def test_every_figure_traces_to_a_record_this_account_holds():
    c, uid = _account("Real Artist")
    _link_events(uid, {"page_view": 9, "service_click": 4, "presave_notify": 2})
    press_store.add_contact(uid, {"name": "Ada Wren", "outlet": "The Pressing",
                                  "email": "ada@example.net", "city": "Nashville",
                                  "country": "US"})
    press_store.add_contact(uid, {"name": "Bo Vale", "outlet": "Loud Quarterly",
                                  "email": "bo@example.net", "city": "Berlin",
                                  "country": "DE"})
    rid = press_store.create_release(uid, {"title": "New single"})
    press_store.update_release(uid, rid, {"status": "ready"})
    press_store.add_coverage(uid, {"outlet": "The Pressing", "headline": "A review"})
    ros.create_campaign(uid, {"title": "Rollout with no link"})

    body = c.get("/room/marketing").get_data(as_text=True)
    assert '<span class="mk-big-n">9</span>' in body and "visits" in body
    assert "Real Artist" in body                       # the account, not a stand-in
    assert "1 announcement ready" in body              # the rail counts the record
    assert "9 smart link visits" in body
    assert "2 contacts" in body and "Contacts never pitched" in body
    assert "1 announcement" in body and "Send now" in body
    assert "1 item" in body and "Add quote" in body
    assert "1 rollout" in body and 'href="/rollout-studio"' in body
    assert "Nashville" in body and "Berlin" in body     # its own contact cities
    for gone in HIS_FIGURES:
        assert gone not in body, gone


def test_the_window_governs_the_band_and_the_rail_holds_the_record():
    """The chooser reaches all three hero figures, because every one of
    them is an ml_events row with its own timestamp. The rail is the whole
    record, and the line under the controls says which is which."""
    c, uid = _account()
    _link_events(uid, {"page_view": 3, "service_click": 1}, days_ago=1)
    _link_events(uid, {"page_view": 40}, days_ago=45)
    band = c.get("/room/marketing?days=7").get_data(as_text=True)
    assert '<span class="mk-big-n">3</span>' in band
    assert "43 smart link visits" in band, "the rail is the record, not the window"
    assert "counted over the last 7 days" in band
    wide = c.get("/room/marketing?days=90").get_data(as_text=True)
    assert '<span class="mk-big-n">43</span>' in wide


def test_the_window_is_one_of_three():
    c, _uid = _account()
    head = c.get("/room/marketing?days=7").get_data(as_text=True).split("mk-range-menu")[0]
    assert "Last 7 days" in head
    head = c.get("/room/marketing?days=5000").get_data(as_text=True).split("mk-range-menu")[0]
    assert "Last 30 days" in head


def test_the_demo_is_the_only_account_shown_the_example():
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = demo.get("/room/marketing").get_data(as_text=True)
    assert "Sample data." in body and "mk-mark--sample" in body
    assert "Read from your own records" not in body, "the example is never called Live"
    for figure in ("12,480", "2,140", "386", "18 contacts", "Toronto"):
        assert figure in body, figure
    # and a real account, on the same code path, gets none of it
    c, _uid = _account()
    real = c.get("/room/marketing").get_data(as_text=True)
    assert "Sample data." not in real and "12,480" not in real


def test_the_demo_figures_are_never_written_to_the_database():
    """fan_audience's rule: the showcase is an in-memory literal and the
    route is the only thing that decides who sees it."""
    before = mr.showcase(30)
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    demo.get("/room/marketing")
    with store.get_db() as db:
        rows = db.execute("SELECT COUNT(*) FROM press_contacts").fetchone()[0]
        cities = db.execute("SELECT COUNT(*) FROM press_contacts"
                            " WHERE city IN ('Toronto', 'Sydney')").fetchone()[0]
    assert cities == 0, "the example's cities are not contact records"
    assert rows >= 0
    assert mr.showcase(30) == before


# --- the owner's ruling on the rollout row ---------------------------------

def test_the_rollout_row_pushes_our_link_and_requires_nothing():
    """Owner, 2026-09-21: "you should not require them to use our smart
    link. If they need a different one or they like using a different
    service they can. But we should push them for ours." So the row states
    the consequence, offers ours, and never says another service is out."""
    c, uid = _account()
    ros.create_campaign(uid, {"title": "No link yet"})
    body = c.get("/room/marketing").get_data(as_text=True)
    row = body.split("Rollout with no smart link connected", 1)[1][:700]
    assert "Post attribution needs a Street Banker link" in row
    assert "keep the service you already use" in row
    for banned in ("required", "Required", "must ", "not allowed", "only way"):
        assert banned not in row, banned
    assert 'href="/rollout-studio"' in row


def test_a_rollout_with_our_link_connected_is_not_on_the_list():
    c, uid = _account()
    mlc = mls.create_campaign(uid, "mkt-%s" % uuid.uuid4().hex[:8], {"title": "Single"})
    ros.create_campaign(uid, {"title": "Linked", "ml_campaign_id": mlc})
    body = c.get("/room/marketing").get_data(as_text=True)
    assert "Rollout with no smart link connected" not in body


# --- the closing grid and the card moves ----------------------------------

def test_the_closing_grid_is_his_three_tiles_in_his_order():
    import re
    c, _uid = _account()
    body = c.get("/room/marketing").get_data(as_text=True)
    assert re.findall(r'data-room-card="([a-z-]+)"', body) == ["press-desk", "epk", "referrals"]
    assert "Explore more tools" in body
    assert "Everything you need to tell your story and reach more listeners." in body
    assert "All in one" in body
    assert "Not shared yet" in body, "the press kit pill says what is true"


def test_reach_left_the_room_for_the_suites_strip_and_rollout_for_releases():
    marketing = [k for _r, _n, _p, keys in rooms.ROOMS if _r == "marketing" for k in keys]
    assert marketing == ["links", "press-desk", "epk", "referrals"]
    releases = [k for _r, _n, _p, keys in rooms.ROOMS if _r == "releases" for k in keys]
    assert "rollout" in releases
    assert "reach" in [row[0] for row in __import__("hubs").tool_suites()], \
        "REACH is still reachable, on the suites strip"


def test_the_press_pages_keep_their_own_tab_strip_in_this_layout(monkeypatch):
    """Collapsing four press cards into one tile would strand three pages
    without their strip, so the strip draws in both layouts again."""
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = appmod.create_app()
    c = app_obj.test_client()
    email = "mktstrip-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Strip", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": "pro"})
    for path in ("/press-desk", "/press-desk/contacts", "/press-desk/coverage",
                 "/press-desk/announcements", "/epk"):
        body = c.get(path).get_data(as_text=True)
        assert 'href="/press-desk/contacts"' in body, path
        assert 'href="/press-desk/announcements"' in body, path
        assert 'href="/press-desk/coverage"' in body, path


# --- the builder ----------------------------------------------------------

CARDS = [("press-desk", "/press-desk", "i", "Press Desk", "d", "live"),
         ("epk", "/epk", "i", "Press kit", "d", "live"),
         ("referrals", "/referrals", "i", "Referrals", "d", "live")]


def test_the_range_is_one_of_three():
    assert mr.days_from("7") == 7 and mr.days_from(90) == 90
    assert mr.days_from("5000") == mr.DEFAULT_RANGE
    assert mr.days_from(None) == mr.DEFAULT_RANGE


def test_a_stage_with_nothing_counted_says_so_in_words():
    lines = [s["line"] for s in mr.stages({})]
    assert lines == ["No announcements ready", "No pitches sent", "No opens logged",
                     "No coverage logged", "No smart link visits"]
    one = {"ready": 1, "sent": 1, "opens": 1, "coverage": 1, "visits_all": 1}
    assert [s["line"] for s in mr.stages(one)] == [
        "1 announcement ready", "1 pitch sent", "1 open logged",
        "1 coverage hit", "1 smart link visit"]


def test_a_zero_is_not_an_action():
    assert mr.actions({}) == []
    assert [a["title"] for a in mr.actions({"no_quote": 2})] == ["Coverage with no quote"]
    assert mr.actions({"no_quote": 2})[0]["figure"] == "2 items"


def test_the_actions_keep_his_order():
    every = {"never-pitched": 1, "unsent": 1, "silent": 1, "no_link": 1, "no_quote": 1}
    assert [a["title"] for a in mr.actions(every)] == [
        "Contacts never pitched", "Announcement written but not sent",
        "Pitch opened several times with no coverage",
        "Rollout with no smart link connected", "Coverage with no quote"]


def test_a_tile_says_what_is_true_of_it():
    assert mr.tile_status("press-desk", "live") == ("gold", "All in one")
    assert mr.tile_status("epk", "live", kit_live=True) == ("good", "Live")
    assert mr.tile_status("epk", "live", kit_live=False) == ("off", "Not shared yet")
    assert mr.tile_status("referrals", "live") == ("", "")
    assert mr.tile_status("press-desk", "hidden") == ("off", "Hidden")
    assert mr.tile_status("epk", "sample") == ("info", "Sample")


def test_the_map_plots_only_a_city_the_table_can_place():
    """board_taxonomy.METROS places all seven of his cities. A city it does
    not know is never plotted, and the count of those is kept so the
    footnote can say how many were left off."""
    for city in ("Toronto", "New York", "London", "Berlin", "Los Angeles",
                 "Nashville", "Sydney"):
        assert mr.coords_for(city), city
    cities = [{"city": "London", "country": "GB", "count": 5},
              {"city": "Neverwhere", "country": "XX", "count": 3},
              {"city": "Sydney", "country": "AU", "count": 1}]
    m = mr.constellation(cities)
    assert [d["city"] for d in m["dots"]] == ["London", "Sydney"]
    assert m["off_cities"] == 1 and m["off_contacts"] == 3
    for d in m["dots"]:
        assert 0 <= d["x"] <= m["w"] and 0 <= d["y"] <= m["h"]
    assert mr.constellation([{"city": "Neverwhere", "country": "", "count": 2}]) is None


def test_the_map_names_a_few_dots_and_never_two_on_one_spot():
    """The Fan Room names four and his seven cities would overlap into mush.
    This names at most three, always starting with the largest, and skips a
    city whose name would land on a name already drawn. The skipped one
    keeps its dot and its row in the ranked list beside the map."""
    cities = [{"city": c, "country": "US", "count": n} for c, n in
              [("New York", 9), ("Nashville", 7), ("Atlanta", 5),
               ("Austin", 3), ("Denver", 2)]]
    m = mr.constellation(cities)
    named = [d for d in m["dots"] if d["label"]]
    assert named and named[0]["city"] == "New York"
    for i, a in enumerate(named):
        for b in named[i + 1:]:
            assert not mr._boxes_meet(_box(a), _box(b)), (
                "%s and %s would overlap" % (a["city"], b["city"]))
    assert len(m["dots"]) == 5, "every city keeps its dot and its list row"


def test_the_cities_are_grouped_from_the_records_as_written():
    rows = [{"city": "Berlin", "country": "DE"}, {"city": "berlin", "country": "DE"},
            {"city": "", "country": "US"}, {"city": "Sydney", "country": "AU"}]
    cities, blank = mr.group_cities(rows)
    assert blank == 1
    assert [(c["city"], c["count"]) for c in cities] == [("Berlin", 2), ("Sydney", 1)]


def test_the_fans_counter_columns_are_never_read():
    """ml_fans.total_visits and total_clicks are permanently zero: nothing
    in the application increments them. The room reads ml_events."""
    import io
    import os
    src = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "marketing_room.py"), encoding="utf-8").read()
    body = src.split('"""', 2)[2]          # past the module note, which names them
    assert "total_visits" not in body and "total_clicks" not in body
    assert "ml_events" in body and "presave_notify" in body


def test_the_other_rooms_keep_their_card_grid():
    c, _uid = _account()
    body = c.get("/room/publishing").get_data(as_text=True)
    assert "data-room-card" in body and "mk-hero" not in body
# --- the honesty review of 2026-09-21 --------------------------------------
# Nine findings, each reproduced on 7778083c before the fix under it, so one
# test per finding and none of them can come back.

def _box(dot):
    """The box a drawn name occupies, as constellation() reserved it."""
    return mr._label_box(dot["x"], dot["y"],
                         max(len(dot["city"]), len("{:,}".format(dot["count"]))),
                         dot["right"])


def _css():
    """This room's styling: the shared kit plus its own sheet.

    The shared parts moved into static/css/room-kit.css on 2026-09-22, so a
    rule this page relies on may be declared under .mk-chip there rather
    than here. Reading both is reading what the page actually gets.
    """
    import io
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = []
    for name in ("room-kit.css", "marketing-room.css"):
        out.append(io.open(os.path.join(base, "static", "css", name),
                           encoding="utf-8").read())
    return chr(10).join(out)


def _epk_pill(c):
    body = c.get("/room/marketing").get_data(as_text=True)
    return body.split('data-room-card="epk"', 1)[1][:900]


def test_1_the_press_kit_pill_waits_for_a_kit_that_was_saved():
    """Live was read off the public address, and _ensure_epk_slug mints one
    on a plain view of /epk, and from /fan-club without /epk being opened at
    all. So an artist who had written nothing was told the kit was Live.
    Against "Not shared yet", Live means shared, so it waits for what a real
    save writes: the data column of epk_profiles."""
    c, uid = _account()
    assert "Not shared yet" in _epk_pill(c)
    c.get("/epk")                                   # a plain page view
    assert (store.get_epk(uid) or {}).get("slug"), "the view minted the address"
    assert not (store.get_epk(uid) or {}).get("data"), "and saved nothing"
    assert "Not shared yet" in _epk_pill(c), "an address alone is not a saved kit"
    c.post("/epk/save", json={"bio": "We are a band from Leeds."})
    pill = _epk_pill(c)
    assert ">Live<" in pill and "Not shared yet" not in pill


def test_2_the_cities_are_grouped_by_city_and_country_as_the_footnote_says():
    """The footnote says "by city and country"; the code keyed on the city
    alone and kept whichever country the first row carried, so London CA and
    London GB were one row under one flag."""
    rows = [{"city": "London", "country": "GB"},
            {"city": "London", "country": "CA"}, {"city": "London", "country": "CA"}]
    cities, _blank = mr.group_cities(rows)
    assert [(c["city"], c["country"], c["count"]) for c in cities] == [
        ("London", "CA", 2), ("London", "GB", 1)]


def test_3_a_city_is_placed_only_where_the_two_countries_agree():
    """coords_for() never looked at the record's country, so London, Ontario
    plotted in England and a Birmingham contact in the UK landed in Alabama,
    contradicting the country code printed in the row beside the dot."""
    assert mr.coords_for("London", "GB") == (51.51, -0.13)
    assert mr.coords_for("London", "CA") is None
    assert mr.coords_for("London", "United Kingdom") == (51.51, -0.13)
    assert mr.coords_for("Birmingham", "US") == (33.52, -86.81)
    assert mr.coords_for("Birmingham", "GB") is None
    assert mr.coords_for("London") == (51.51, -0.13), "no country contradicts nothing"
    cities, _b = mr.group_cities(
        [{"city": "London", "country": "GB"}, {"city": "London", "country": "CA"},
         {"city": "London", "country": "CA"}])
    m = mr.constellation(cities)
    assert [(d["city"], d["country"]) for d in m["dots"]] == [("London", "GB")]
    assert m["off_cities"] == 1 and m["off_contacts"] == 2, "counted in the footnote"


def test_4_one_metro_is_one_row_and_one_dot():
    """"New York" and "NYC" were two dots on the identical coordinate with a
    zero-length line between them, two ranked rows and the smaller one
    unnamed. board_taxonomy knows 148 alias spellings, so an imported media
    list could split one city six ways. They resolve through the alias map
    now, and the row carries the metro's own name."""
    rows = [{"city": "New York", "country": "US"}, {"city": "NYC", "country": "US"},
            {"city": "Brooklyn", "country": "US"}, {"city": "ny", "country": ""},
            {"city": "Nowhereville", "country": "US"}]
    cities, _blank = mr.group_cities(rows)
    assert [(c["city"], c["count"]) for c in cities] == [
        ("New York", 4), ("Nowhereville", 1)]
    m = mr.constellation(cities)
    assert [d["city"] for d in m["dots"]] == ["New York"]
    assert m["lines"] == [], "no line from a city to itself"
    assert m["off_cities"] == 1, "a city with no metro keeps its spelling, unplaced"
    assert cities[0]["q"] == "", "no one word finds all four, so the link opens the list"
    assert cities[1]["q"] == "Nowhereville"


def test_5_two_names_hold_their_distance_in_rendered_pixels():
    """LABEL_GAP was 78 viewBox units compared against a label drawn at a
    fixed 13px, so the guarantee was 78 screen pixels on a 604px panel and 33
    on the 254px panel of a 320px phone, where New York and London were
    measured overlapping by 10px across and 26px down. The rule is now the
    boxes the names will really occupy at MIN_LABEL_PANEL, and below that
    width the stylesheet draws the first name only."""
    m = mr.constellation(mr.showcase(30)["cities"])
    named = [d for d in m["dots"] if d["label"]]
    assert len(named) == 3, "his design still names three on a full-width panel"
    for i, a in enumerate(named):
        for b in named[i + 1:]:
            assert not mr._boxes_meet(_box(a), _box(b)), (
                "%s and %s meet at a %dpx panel" % (a["city"], b["city"],
                                                    mr.MIN_LABEL_PANEL))
    css = _css()
    assert "container: mkmap / inline-size" in css
    assert "@container mkmap (max-width: %dpx)" % (mr.MIN_LABEL_PANEL - 1) in css
    assert ".mk-map-label ~ .mk-map-label { display: none; }" in css
    assert "max-width: %dpx" % mr.LABEL_MAX_PX in css, "the cap the rule assumes"


def test_6_a_long_account_name_never_widens_the_page():
    """.mk-chip was nowrap with no cap and it holds the account's own name,
    so "The Midnight Telegraph Orchestra and Chorus" made the document 372px
    wide inside a 320px viewport and the whole page scrolled sideways. It is
    capped and ellipsised now, the shape of Motion's account line, with the
    name whole on hover and read out in full."""
    long_name = "The Midnight Telegraph Orchestra and Chorus"
    c, _uid = _account(long_name)
    body = c.get("/room/marketing").get_data(as_text=True)
    chip = body.split('class="mk-chip"', 1)[1][:400]
    assert 'class="mk-chip-name" title="%s"' % long_name in chip
    assert long_name in chip, "the whole name is still the text, so it is read out"
    css = _css()
    import re as _re
    rule = _re.search(r"\.mk-chip[^-{][^{]*\{([^}]*)\}", css).group(1)
    assert "max-width: 100%" in rule and "min-width: 0" in rule
    name = _re.search(r"\.mk-chip-name[^{]*\{([^}]*)\}", css).group(1)
    assert "text-overflow: ellipsis" in name and "overflow: hidden" in name


def test_7_the_rollout_row_opens_the_list_of_all_of_them():
    """The row counted every rollout with no link and opened the newest one,
    so it read "3 rollouts" beside a button that showed one, leaving the
    other two unreachable from here."""
    c, uid = _account()
    for i in range(3):
        ros.create_campaign(uid, {"title": "Rollout %d" % i})
    body = c.get("/room/marketing").get_data(as_text=True)
    row = body.split("Rollout with no smart link connected", 1)[1][:800]
    assert "3 rollouts" in row
    assert 'class="mk-act-cta" href="/rollout-studio"' in row
    assert "no_link_href" not in body


def test_8_no_action_is_offered_to_a_seat_that_would_be_bounced():
    """The rollout card moved to the Releases room, so a seat given Marketing
    and not Releases saw the row and was turned away at the page it opens."""
    import team_areas

    def seat(href):
        return team_areas.allows("marketing", href.split("?")[0])

    every = {"never-pitched": 1, "unsent": 1, "silent": 1, "no_link": 1, "no_quote": 1}
    assert len(mr.actions(every)) == 5, "the artist is shown all five"
    shown = [a["title"] for a in mr.actions(every, seat)]
    assert "Rollout with no smart link connected" not in shown
    assert len(shown) == 4
    # the other four rows, and the room's other destinations, are this room's
    for _f, _i, _t, _d, _s, _p, _c, href in mr.ACTIONS:
        if href != "/rollout-studio":
            assert seat(href), href
    for href in ("/links", "/press-desk", "/epk", "/referrals",
                 "/press-desk/announcements/new", "/press-desk/contacts"):
        assert seat(href), href


def test_9_the_room_reaches_smart_links_in_both_layouts():
    """With the rooms layout on, the whole page carried 55 links and not one
    went to /links: collapsing the cards took its tile away and the design
    has none. The hero's large figure is smart link data, so the figure is
    the door, in the empty state as well."""
    import re
    for rooms_on in ("1", "0"):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("NAV_ROOMS", rooms_on)
            app_obj = appmod.create_app()
            c = app_obj.test_client()
            email = "mktlinks-%s@example.net" % uuid.uuid4().hex[:8]
            c.post("/signup", data={"name": "Door", "email": email, "password": PW})
            c.post("/plan/switch", data={"plan": "pro"})
            body = c.get("/room/marketing").get_data(as_text=True)
            assert "No visits in this window" in body, "the empty state"
            assert '<a class="mk-big" href="/links"' in body, rooms_on
            assert "Open Smart Links" in body
            assert [h for h in re.findall(r'href="([^"]*)"', body)
                    if h.startswith("/links")], "NAV_ROOMS=%s" % rooms_on
            assert c.get("/links").status_code == 200


def test_the_rollout_finding_says_connect():
    """Owner, 2026-09-22: "Add link" read as "make me a new smart link".
    The finding is a rollout with no link CONNECTED."""
    import marketing_room as mk
    labels = [row[6] for row in mk.ACTIONS]
    assert "Connect a link" in labels
    assert "Add link" not in labels
