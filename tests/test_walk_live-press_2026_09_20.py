"""The live and press findings of the 2026-09-20 page walk, pinned.

Six things a signed-in artist or the person they sent a link to would
read wrong: a listing page counting its own replies as zero, a press kit
calling an empty strip complete, a journalist told to reply to an address
the page never printed, a band itinerary listing every show twice, a tour
calendar full of links to nowhere, and a show whose first view scored the
content plan before it existed.
"""
import re
import uuid

import pytest

import app as appmod
import board_store as bs
import db as store
import epk_config
import press_store
import tour_engine as eng
import tour_store as ts

PW = "walk-live-press-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(name="Walk Artist"):
    email = "walk-lp-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _tour(client, **over):
    data = {"name": "Walk Run", "artist_name": "Walk", "start_date": "2030-05-01",
            "end_date": "2030-06-10", "home_tz": "America/New_York", "currency": "USD"}
    data.update(over)
    r = client.post("/tours/new", data=data)
    assert r.status_code == 302
    return r.headers["Location"].rstrip("/").split("/")[-1]


def _show(client, tour_id, date_, venue, city="Nashville, TN"):
    r = client.post("/tours/%s/days/add" % tour_id,
                    data={"date": date_, "kind": "show", "venue": venue, "city": city,
                          "tz": "America/Chicago"})
    assert r.status_code == 302
    return r.headers["Location"].split("/shows/")[1].split("?")[0]


# --- Team-Up Board: the listing page counts its own replies ------------------

def test_the_listing_page_counts_the_same_replies_as_the_board():
    poster, _pu = _account("Poster")
    r = poster.post("/tour-board/post", data={
        "kind": "venue", "title": "Saturday slots at Walk Hall", "region_code": "metro-charlotte",
        "region_text": "Charlotte, NC", "window_start": "2030-10-01", "window_end": "2030-10-31",
        "details": "Cap 250"})
    lid = r.headers["Location"].rsplit("/", 1)[1]
    replier, _ru = _account("Walk Stranger")
    r = replier.post("/tour-board/%s/reply" % lid, data={"message": "We pull 200 in Charlotte."})
    assert r.status_code == 302
    assert bs.reply_counts([lid])[lid]["threads"] == 1
    board = poster.get("/tour-board").get_data(as_text=True)
    assert "1 reply" in board
    page = poster.get("/tour-board/%s" % lid).get_data(as_text=True)
    assert "0 replies" not in page
    assert "1 reply" in page


# --- EPK Builder: an empty strip is not Complete -----------------------------

def _rail_status(body, label):
    m = re.search(r'font-semibold">%s</span>\s*<span class="section-status[^"]*">([^<]+)</span>'
                  % re.escape(label), body)
    assert m, label
    return m.group(1).strip()


def test_an_account_with_nothing_measured_is_told_stats_and_tracks_need_info():
    c, _uid = _account()
    body = c.get("/epk").get_data(as_text=True)
    assert "Not measured" in body
    assert _rail_status(body, "Career Stats") == "Needs Info"
    assert _rail_status(body, "Top Tracks") == "Needs Info"


def test_stats_and_tracks_read_complete_only_from_data():
    account = {"name": "Walk", "initials": "W"}
    value = {"low": 0, "mid": 0, "high": 0}
    empty = epk_config.get_epk_data(account, value, stats_override=epk_config.not_measured_stats(),
                                    top_tracks_override=[], top_platform_override="")
    status = {s["key"]: s["status"] for s in empty["sections"]}
    assert status["stats"] == "Needs Info" and status["tracks"] == "Needs Info"
    measured = epk_config.get_epk_data(
        account, value,
        stats_override=epk_config.real_stats([], 2, {"monthly_listeners": 120, "label": "FakeCharts"}),
        top_tracks_override=[{"title": "One", "streams": None, "streams_compact": "",
                              "earned": 12.0, "owner": ""}],
        top_platform_override="Spotify")
    status = {s["key"]: s["status"] for s in measured["sections"]}
    assert status["stats"] == "Complete" and status["tracks"] == "Complete"
    # The showcase keeps its sample strip, and the sample strip is not a blank.
    demo = epk_config.get_epk_data(account, {"low": 1, "mid": 2, "high": 3}, demo=True)
    status = {s["key"]: s["status"] for s in demo["sections"]}
    assert status["stats"] == "Complete" and status["tracks"] == "Complete"


# --- Press Desk: the journalist's page names a reply address or says nothing --

def _pitch_token(client, uid, **release_fields):
    client.post("/press-desk/contacts/new", data={
        "name": "Dee Okafor", "outlet": "Nightdrive Mag", "role": "Writer",
        "email": "dee-%s@example.com" % uuid.uuid4().hex[:6]})
    data = {"title": "New single", "kind": "Single", "headline": "Walk announces",
            "body": "First.\n\nSecond.", "listen_url": "https://example.com/listen"}
    data.update(release_fields)
    client.post("/press-desk/announcements/new", data=data)
    release = press_store.list_releases(uid)[0]
    ids = [c["id"] for c in press_store.list_contacts(uid)]
    client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": ids,
        "subject": "{artist} - {title}", "body": "Hi {name}, for {outlet}: {link}",
        "mode": "own_inbox"})
    pitch = press_store.list_pitches(uid)[0]
    return press_store.pitch_recipients(uid, pitch["id"])[0]["token"]


def test_reply_to_the_address_above_is_only_said_when_an_address_is_above():
    c, uid = _account()
    token = _pitch_token(c, uid)
    body = appmod.app.test_client().get("/press/%s" % token).get_data(as_text=True)
    assert "mailto:" not in body
    assert "Reply to the address above" not in body
    assert "through Street Banker" in body
    c2, uid2 = _account()
    token2 = _pitch_token(c2, uid2, contact_name="Walk Mgmt", contact_email="press@example.com")
    body = appmod.app.test_client().get("/press/%s" % token2).get_data(as_text=True)
    assert "mailto:press@example.com" in body
    assert "Reply to the address above" in body


# --- Band itinerary: one row per day -----------------------------------------

def test_the_band_itinerary_lists_each_show_day_once():
    c, _uid = _account()
    tid = _tour(c)
    _show(c, tid, "2030-05-03", "Walk Hall", "Nashville, TN")
    _show(c, tid, "2030-06-01", "Old Hall", "Austin, TX")
    c.post("/tours/%s/days/add" % tid, data={"date": "2030-05-04", "kind": "travel",
                                             "title": "Drive to Austin", "city": "Memphis, TN"})
    c.post("/tours/%s/share/new" % tid, data={"scope": "band"})
    link = next(l for l in ts.list_share_links(tid) if l["scope"] == "band")
    body = appmod.app.test_client().get("/tour-share/%s" % link["token"]).get_data(as_text=True)
    route = body.split('class="to-route"')[1].split("</ol>")[0]
    assert route.count("<li") == 3
    for d in ("2030-05-03", "2030-05-04", "2030-06-01"):
        assert route.count(eng.fmt_day_long(d)) == 1, d
    assert "Walk Hall" in route and "Old Hall" in route and "Drive to Austin" in route


# --- Tour index calendar: an empty day is a cell, not a link to nowhere ------

def test_empty_calendar_days_on_the_tour_index_are_not_links():
    c, _uid = _account()
    tid = _tour(c)
    sid = _show(c, tid, "2030-05-03", "Walk Hall")
    body = c.get("/tours?month=2030-05").get_data(as_text=True)
    cal = body.split('id="all-cal"')[1].split("</div>\n  </div>")[0]
    assert 'href="#"' not in cal
    assert 'href="/tours/%s/shows/%s"' % (tid, sid) in cal
    assert cal.count('<span class="to-cal-day') >= 30
    assert cal.count('<a class="to-cal-day') == 1


# --- A show's first view scores the content plan it holds --------------------

def test_adding_the_content_feature_seeds_the_plan_before_the_first_view():
    c, _uid = _account()
    tid = _tour(c)
    sid = _show(c, tid, "2030-05-03", "Walk Hall")
    assert ts.list_content(tid, show_id=sid) == []
    r = c.post("/tours/%s/shows/%s/sections" % (tid, sid), data={"key": "content", "action": "add"})
    assert r.status_code == 302
    n = len(ts.CONTENT_DEFAULTS)
    assert len(ts.list_content(tid, show_id=sid)) == n
    first = c.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    assert "0 of 0 content items" not in first
    assert "0 of %d content items assigned" % n in first
    again = c.get("/tours/%s/shows/%s" % (tid, sid)).get_data(as_text=True)
    assert "0 of %d content items assigned" % n in again
    assert len(ts.list_content(tid, show_id=sid)) == n
