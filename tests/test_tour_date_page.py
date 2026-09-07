"""One date, one page.

The owner's words: "a lot of the tabs can be located inside the actual
date and the event ... you can add a plus sign next to hotels and vip
etc, they can add them if they want to, these pages are overwhelming."
Then, 2026-09-07, by numbered mockup: nothing is pre-added.

So: one grid of every feature, each a `+` row until it is added, has
rows, or is deep-linked - the core features included. Readiness follows
the same rule - a date nobody said needs a hotel is not "missing a
hotel", and a date with nothing on it has not been measured at all - and
every old ?tab= URL still answers, because bookmarks and the offline
cache hold them.
"""
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import tour_os
import tour_store as ts

PASSWORD = "date-pass-123"
CORE = ["times", "lineup", "advance", "venue", "crew", "deal", "notes", "activity"]
OPTIONAL = ["hotel", "travel", "guests", "vip", "settlement", "merch", "marketing",
            "content", "setlist", "files", "tasks"]
# The grid order: the core features, the optional ones, Activity last.
FEATURES = [k for k in CORE if k != "activity"] + OPTIONAL + ["activity"]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Tour Owner"):
    email = "date-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _tour(client):
    r = client.post("/tours/new", data={
        "name": "Test Run", "artist_name": "Test Artist", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    assert r.status_code == 302
    return r.headers["Location"].rstrip("/").split("/")[-1]


def _show(client, tour_id, date_="2030-05-02", venue="The Basement East"):
    r = client.post("/tours/%s/days/add" % tour_id, data={
        "date": date_, "kind": "show", "venue": venue, "city": "Nashville, TN", "tz": "America/Chicago"})
    assert r.status_code == 302
    return r.headers["Location"].split("/shows/")[1].split("?")[0]


def _fresh(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    return client, owner, tid, _show(client, tid)


def _page(client, tid, sid, tab=None):
    url = "/tours/%s/shows/%s" % (tid, sid) + ("?tab=%s" % tab if tab else "")
    r = client.get(url)
    assert r.status_code == 200, (url, r.status_code)
    return r.get_data(as_text=True)


def _sections(html):
    return re.findall(r'<section class="to-sec[^"]*" id="([a-z]+)"', html)


def _chips(html):
    return set(re.findall(r'data-chip="([a-z]+)"', html))


def _sections_post(client, tid, sid, key, action):
    return client.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": key, "action": action})


def _member_join(flask_app, owner_client, tid, scopes, label="Crew"):
    member_client, member = _user(flask_app, label)
    owner_client.post("/tours/%s/team/invite" % tid,
                      data={"email": member["email"], "name": label, "role": "crew", "scopes": scopes})
    m = ts.get_member_by_email(tid, member["email"])
    assert member_client.get("/tours/join/%s" % m["invite_token"]).status_code == 302
    return member_client, member


def _readiness(tid, sid):
    return tour_os._readiness_for(ts.get_tour(tid), ts.get_show(tid, sid))


# --- the page -----------------------------------------------------------------

def test_a_fresh_date_is_nineteen_plus_rows_and_nothing_else(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    assert tour_os.CORE_KEYS == CORE and tour_os.SECTION_KEYS == CORE + OPTIONAL
    assert [k for k, *_ in tour_os.FEATURE_ORDER] == FEATURES and len(FEATURES) == 19
    html = _page(client, tid, sid)
    assert _sections(html) == []                    # nothing pre-added
    assert _chips(html) == set(FEATURES)            # a + row for every feature, the core ones too
    # No body is on the page - that is the point.
    assert 'name="property"' not in html            # the hotel form
    assert 'name="package"' not in html             # the VIP form
    assert 'name="opening__' not in html            # merch counts
    assert 'name="acts"' not in html and 'name="status__catering"' not in html
    assert 'name="guarantee"' not in html and 'name="notes"' not in html
    assert 'id="settlement"' not in html and 'name="settlement_amount"' not in html
    # Nothing on, nothing measured: no score, no meter, no 'missing'.
    assert not re.search(r"\d+ of \d+ applicable", html) and 'id="readiness"' not in html
    assert "No numbers entered" not in html and ">0%<" not in html


def test_adding_a_section_puts_it_on_the_page_in_place_of_its_plus_row(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    r = _sections_post(client, tid, sid, "hotel", "add")
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=hotel")
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel"]
    html = _page(client, tid, sid)
    assert _sections(html) == ["hotel"] and "hotel" not in _chips(html)
    assert _chips(html) == set(FEATURES) - {"hotel"}
    assert 'name="property"' in html                # the form, one line tall until used
    assert "Remove from this show" in html          # empty, so it can come off again
    assert any(c["field"] == "sections" and c["after"] == "hotel" for c in ts.list_changes(tid))
    # Adding twice does not double it up.
    _sections_post(client, tid, sid, "hotel", "add")
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel"]
    # A core feature is added the same way.
    r = _sections_post(client, tid, sid, "times", "add")
    assert r.status_code == 302 and r.headers["Location"].endswith("?tab=times")
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel", "times"]
    html = _page(client, tid, sid)
    assert _sections(html) == ["times", "hotel"], "the grid order, not the order added"
    assert "Stamp standard show day" in html and 'name="acts"' not in html, "the bill is its own row"


def test_a_deep_link_still_opens_a_section_nobody_added(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    html = _page(client, tid, sid, "vip")
    assert _sections(html) == ["vip"] and 'name="package"' in html
    assert "vip" not in _chips(html)
    assert ts.get_show(tid, sid)["readiness_config"] == []      # looking is not adding
    # The old tabs that now live inside a section open that section's disclosure.
    html = _page(client, tid, sid, "send")
    assert _sections(html) == ["advance"] and "advance" not in _chips(html)
    assert 'name="to"' in html and '<details class="to-fold" id="send" open>' in html
    html = _page(client, tid, sid, "settlement")
    assert _sections(html) == ["settlement"] and 'id="settlement-form"' in html
    assert "deal" in _chips(html), "the settlement is its own feature; the deal stays a + row"
    assert ts.get_show(tid, sid)["readiness_config"] == []


def test_remove_is_refused_while_the_section_has_rows(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    _sections_post(client, tid, sid, "hotel", "add")
    client.post("/tours/%s/hotels/add" % tid, data={"show_id": sid, "property": "Kept Hotel", "checkin": "2030-05-02"})
    r = _sections_post(client, tid, sid, "hotel", "remove")
    assert r.status_code == 302
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel"]
    html = _page(client, tid, sid)
    assert "Kept Hotel" in html and "Remove from this show" not in html
    # An empty one comes off, and the page goes back to the + row.
    _sections_post(client, tid, sid, "vip", "add")
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel", "vip"]
    _sections_post(client, tid, sid, "vip", "remove")
    assert ts.get_show(tid, sid)["readiness_config"] == ["hotel"]
    assert "vip" in _chips(_page(client, tid, sid))


def test_hotel_and_travel_edits_stay_on_the_date_page(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    client.post("/tours/%s/hotels/add" % tid, data={"show_id": sid, "property": "Edit Me Hotel", "checkin": "2030-05-02"})
    lid = ts.list_lodging(tid)[0]["id"]
    html = _page(client, tid, sid)
    assert "?tab=hotel&amp;edit=%s" % lid in html                 # the list's Edit link
    html = _page(client, tid, sid, "hotel&edit=%s" % lid)
    assert "/hotels/%s/edit" % lid in html and 'value="Edit Me Hotel"' in html
    assert 'href="/tours/%s/shows/%s?tab=hotel">Cancel' % (tid, sid) in html
    client.post("/tours/%s/travel/add" % tid, data={"show_id": sid, "day_date": "2030-05-02", "mode": "ground", "vehicle": "Sprinter"})
    trid = ts.list_travel(tid)[0]["id"]
    html = _page(client, tid, sid, "travel&edit=%s" % trid)
    assert "/travel/%s/edit" % trid in html and 'value="Sprinter"' in html
    assert 'href="/tours/%s/shows/%s?tab=travel">Cancel' % (tid, sid) in html
    # The tour-level pages keep their own links.
    assert "/hotels?edit=%s" % lid in client.get("/tours/%s/hotels" % tid).get_data(as_text=True)


# --- readiness ------------------------------------------------------------------

def test_readiness_counts_nothing_until_a_feature_is_on(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    r = _readiness(tid, sid)
    assert r["total"] == 0 and r["checks"] == [] and r["missing"] == [] and r["pct"] == 0
    # A core feature brings the categories it owns, and no other.
    _sections_post(client, tid, sid, "advance", "add")
    r1 = _readiness(tid, sid)
    assert {c["key"] for c in r1["checks"]} == set(tour_os.SECTION_CATEGORIES["advance"])
    assert r1["total"] == 6
    # An optional one brings its category in, unmet.
    _sections_post(client, tid, sid, "hotel", "add")
    r2 = _readiness(tid, sid)
    assert r2["total"] == 7
    assert any(c["key"] == "hotel" and c["state"] is False for c in r2["checks"])
    # Rows count without an opt-in: one ground leg brings travel and ground.
    client.post("/tours/%s/travel/add" % tid, data={"show_id": sid, "day_date": "2030-05-02", "mode": "ground"})
    r3 = _readiness(tid, sid)
    assert {"travel", "ground"} <= {c["key"] for c in r3["checks"]} and r3["total"] == 9
    # The page says the same number.
    assert "%d of %d applicable" % (r3["done"], r3["total"]) in _page(client, tid, sid)
    # The engine, asked with no config, still scores everything (tests of
    # the arithmetic depend on that); the page is what narrowed it.
    assert "guest_list" not in {c["key"] for c in r3["checks"]}


# --- scope --------------------------------------------------------------------------

def test_a_member_without_financials_sees_no_deal_and_no_settlement_plus_row(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    crew, member = _member_join(flask_app, client, tid, ["view", "edit"])
    html = _page(crew, tid, sid)
    assert _sections(html) == []
    chips = _chips(html)
    assert "deal" not in chips and "settlement" not in chips
    assert {"times", "advance", "venue", "notes", "activity", "hotel"} <= chips   # edit may add these
    assert 'name="guarantee"' not in html and 'id="settlement"' not in html
    assert crew.get("/tours/%s/shows/%s?tab=money" % (tid, sid)).status_code == 403
    assert crew.get("/tours/%s/shows/%s?tab=settlement" % (tid, sid)).status_code == 403
    assert _sections_post(crew, tid, sid, "settlement", "add").status_code == 403
    assert _sections_post(crew, tid, sid, "deal", "add").status_code == 403
    assert ts.get_show(tid, sid)["readiness_config"] == []
    # The owner puts the deal on; the crew still sees neither the row nor the + row.
    client.post("/tours/%s/shows/%s/money" % (tid, sid), data={"guarantee": "1500", "deal_type": "flat"})
    assert "deal" in _sections(_page(client, tid, sid))
    theirs = _page(crew, tid, sid)
    assert "deal" not in _sections(theirs) and "deal" not in _chips(theirs)
    assert "1500 USD" not in theirs and 'name="guarantee"' not in theirs
    # A viewer with no edit scope gets no + rows at all, and cannot add by POST.
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    assert _chips(_page(viewer, tid, sid)) == set()
    assert _sections_post(viewer, tid, sid, "hotel", "add").status_code == 403


# --- the old deep links -------------------------------------------------------------

def test_every_old_tab_url_still_answers_and_lands_on_its_element(flask_app):
    client, owner, tid, sid = _fresh(flask_app)
    assert len(tour_os.SHOW_TABS) == 23
    for tab, _label in tour_os.SHOW_TABS:
        r = client.get("/tours/%s/shows/%s?tab=%s" % (tid, sid, tab))
        assert r.status_code == 200, (tab, r.status_code)
        html = r.get_data(as_text=True)
        if tab == "overview":
            assert "is-target" not in html and _sections(html) == []
            continue
        assert ('id="%s"' % tab) in html, tab
        section = tour_os.TAB_SECTION.get(tab, tab)
        assert re.search(r'<section class="to-sec is-target[^"]*" id="%s"' % section, html), tab
        assert _sections(html) == [section], "the target alone is treated as on"
    assert ts.get_show(tid, sid)["readiness_config"] == [], "looking is not adding"
    # An unknown tab is the page as designed.
    assert client.get("/tours/%s/shows/%s?tab=nonsense" % (tid, sid)).status_code == 200


def test_the_assets_moved_on_with_the_page():
    sw = open(os.path.join(HERE, "static", "js", "sw.js"), encoding="utf-8").read()
    # A MINIMUM, not an exact match. Pinning the literal version made
    # this test fail on every later unrelated bump - which is what it
    # did when Show Passport shipped v170. What the test is actually
    # for is "the worker moved on when this feature landed", and >=
    # says that without taxing every future static change.
    got = int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1))
    assert got >= 169, "the service worker must be bumped on a static change"
    shell = open(os.path.join(HERE, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    # Same rule as the worker: a minimum, so later sheet bumps do not fail it.
    assert int(re.search(r"tour-os\.css\?v=(\d+)", shell).group(1)) >= 6
    css = open(os.path.join(HERE, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert "@media print" in css and ".to, .to *" in css and ".to-chip-btn" in css
