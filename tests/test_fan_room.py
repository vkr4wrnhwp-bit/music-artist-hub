"""The Fan Room: the Fans room's opening screen (owner's mockup, 2026-09-19).

The layout is the mockup's; the figures are the account's own, and the
mockup's own figures, names and promises never reach a real page.
"""
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
    assert "Fan Room" in body and "Your owned audience" in body
    assert "Bring in the fans you already have" in body
    assert "No fan cities on file yet" in body
    for gone in MOCKUP_ONLY:
        assert gone not in body, gone


def test_the_figures_are_the_accounts_own():
    c, uid = _account("Real Artist")
    for i in range(3):
        fid = mls.upsert_fan(uid, "fan%d-%s@example.net" % (i, uid[:6]), None)
        mls.set_fan_place(fid, "US", "Atlanta")
    body = c.get("/room/fans").get_data(as_text=True)
    assert '<span class="fr-big-n">3</span>' in body
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
