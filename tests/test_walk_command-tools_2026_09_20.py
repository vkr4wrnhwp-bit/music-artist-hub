"""The Command Center and its tools, as the 2026-09-20 page walk found them.

The walk signed in as an artist and worked the front door: the royalty
goal, the Create-action button that five pages carry, the money band's
month labels, the sidebar's Search box, the tutor's switch, and what a
mistyped address answers with. Ten things could be pressed into telling a
lie or into a 500, and each one is pinned here.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import command_center as cc
import db as store

PW = "walk-ct-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(name="Walk Artist", plan="label"):
    email = "walkct-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _statement(uid, periods):
    """One dollar figure per period, so the months land in a known order."""
    store.save_statement(uid, "walk.csv",
                         [{"title": "Song %d" % i, "source": "Test DSP",
                           "amount": amount, "period": period}
                          for i, (period, amount) in enumerate(periods)])


def _results_count(body):
    m = re.search(r"(\d+) results? for", body)
    return int(m.group(1)) if m else None


# --- the royalty goal -------------------------------------------------------

def test_a_goal_of_nan_is_refused_rather_than_crashing():
    """float("nan") cleared `amount <= 0` (NaN compares false against
    everything) and SQLite bound it as NULL, so saving it raised a 500."""
    c, uid = _account()
    r = c.post("/overview/goal", data={"amount": "nan"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/overview?goal=invalid")
    assert store.get_royalty_goal(uid) is None


def test_an_infinite_goal_is_refused_and_the_ring_never_prints_inf():
    c, uid = _account()
    for amount in ("inf", "1e400", "-inf"):
        r = c.post("/overview/goal", data={"amount": amount})
        assert r.headers["Location"].endswith("/overview?goal=invalid"), amount
        assert store.get_royalty_goal(uid) is None, amount
    assert "$inf" not in c.get("/command-center").get_data(as_text=True)


def test_a_goal_past_any_real_one_is_refused_and_a_real_one_is_kept():
    c, uid = _account()
    r = c.post("/overview/goal", data={"amount": "1000000001"})
    assert r.headers["Location"].endswith("/overview?goal=invalid")
    assert store.get_royalty_goal(uid) is None
    c.post("/overview/goal", data={"amount": "30000", "kind": "yearly"})
    assert store.get_royalty_goal(uid)["amount"] == 30000


def test_a_refused_goal_says_so_on_the_page_it_lands_on():
    """It used to bounce to a page that said nothing at all, so the band
    still read "No goal set" and the artist could only guess why."""
    c, uid = _account()
    # The goal lives on the working page; a brand-new account meets the
    # page from zero (2026-09-22), so this one holds a statement.
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])
    body = c.get("/overview?goal=invalid").get_data(as_text=True)
    assert 'id="goal-error"' in body
    assert "Enter an amount above zero" in body
    # And the page says nothing of the sort when the goal was fine.
    assert "Enter an amount above zero" not in c.get("/overview").get_data(as_text=True)


# --- Create action ----------------------------------------------------------

def test_an_empty_create_action_makes_nothing():
    c, uid = _account()
    before = len(cc.list_actions(uid))
    r = c.post("/actions/from-alert", data={})
    assert r.status_code == 302
    assert len(cc.list_actions(uid)) == before
    r = c.post("/actions/from-alert", data={"title": "   "})
    assert len(cc.list_actions(uid)) == before


def test_every_page_with_a_create_action_button_confirms_it():
    """Six pages post to /actions/from-alert and only /recovery read the
    confirmation back, so the Growth Score and the Trust Score created a
    row and showed nothing."""
    c, uid = _account()
    r = c.post("/actions/from-alert", data={"title": "TS action"},
               headers={"Referer": "http://localhost/trust-score"})
    assert r.status_code == 302 and "action=TS%20action" in r.headers["Location"]
    assert any(a["title"] == "TS action" for a in cc.list_actions(uid))
    for path in ("/trust-score", "/qualification", "/command-center", "/recovery"):
        body = c.get(path + "?action=TS%20action").get_data(as_text=True)
        assert "TS action" in body, path
        assert 'role="status"' in body, path
        assert 'href="/actions"' in body, path
    # One line, not two, on the page that used to carry its own.
    assert c.get("/recovery?action=TS%20action").get_data(as_text=True).count(
        "is on your") == 1


def test_the_confirmation_is_not_offered_to_a_signed_out_visitor():
    body = appmod.app.test_client().get("/?action=Anything").get_data(as_text=True)
    assert "is on your" not in body


# --- the money band ---------------------------------------------------------

def test_the_money_band_names_the_period_it_holds():
    """It read "This month" and "Last month" whatever the statements said,
    so an account whose newest period was April was told April was this
    month while the chart caption underneath named April."""
    c, uid = _account()
    _statement(uid, [("2026-04", 788.99), ("2026-05", 715.69)])
    body = c.get("/command-center").get_data(as_text=True)
    assert "May 2026" in body and "vs Apr 2026" in body
    assert ">This month<" not in body
    assert ">Last month<" not in body


def test_the_money_band_still_says_this_month_when_it_is():
    c, uid = _account()
    now = datetime.now(timezone.utc)
    prev = now.replace(day=1) - timedelta(days=1)
    _statement(uid, [("%04d-%02d" % (prev.year, prev.month), 100.0),
                     ("%04d-%02d" % (now.year, now.month), 200.0)])
    body = c.get("/command-center").get_data(as_text=True)
    assert ">This month<" in body
    assert "vs last month" in body


# --- the Search box ---------------------------------------------------------

def test_search_finds_the_fan_room_and_the_connections_page():
    """Connections is defined but sits in no room, so build() never
    yielded it; and no indexed entry carried the Fans room's own screen
    title, which is "Fan Room"."""
    c, _uid = _account()
    for q in ("fan+room", "Connections", "Data+and+connections"):
        body = c.get("/search?q=" + q).get_data(as_text=True)
        assert (_results_count(body) or 0) >= 1, q
    assert "/room/fans" in c.get("/search?q=fan+room").get_data(as_text=True)
    assert "/connections" in c.get("/search?q=Connections").get_data(as_text=True)


def test_a_page_is_listed_once_even_though_it_has_an_alias():
    """The alias carries the same address as the room, and page_hits keeps
    one entry per address, so "fans" answers with what it always did."""
    c, _uid = _account()
    assert _results_count(c.get("/search?q=fans").get_data(as_text=True)) == 3


# --- the admin doors --------------------------------------------------------

def test_a_signed_in_artist_gets_a_404_from_every_admin_address():
    """/admin sent them to the Operator Desk's refusal and /admin/audio to
    a login form they had already passed. Every other /admin page answered
    404, and now these two do."""
    c, _uid = _account()
    for path in ("/admin", "/admin/audio", "/admin/readiness"):
        assert c.get(path).status_code == 404, path


def test_a_signed_out_visitor_is_still_sent_to_sign_in():
    c = appmod.app.test_client()
    for path in ("/admin", "/admin/audio"):
        r = c.get(path)
        assert r.status_code in (301, 302), path
        assert "/login" in (r.headers.get("Location") or ""), path


# --- the tutor switch -------------------------------------------------------

def test_the_tutor_switch_only_goes_back_to_a_page_here():
    c, _uid = _account()
    for back in ("https://example.org/x", "//example.org/x", "/\\example.org",
                 "http://example.org", "", "javascript:alert(1)"):
        r = c.post("/tutor/toggle", data={"on": "1", "back": back})
        assert r.headers["Location"].endswith("/command-center"), back
    r = c.post("/tutor/toggle", data={"on": "0", "back": "/royalties?view=lanes"})
    assert r.headers["Location"].endswith("/royalties?view=lanes")


# --- a bad address ----------------------------------------------------------

def test_a_bad_address_is_answered_in_the_app_with_a_way_back():
    """Werkzeug's bare 207-byte "Not Found" carried no chrome and no link,
    so the only way on was the browser's back button."""
    c, _uid = _account()
    for path in ("/scores", "/help", "/room/bogus", "/analytics"):
        r = c.get(path)
        assert r.status_code == 404, path
        body = r.get_data(as_text=True)
        assert "sb-plate" in body, path
        assert "Page not found" in body, path
        assert 'href="/command-center"' in body, path
        assert "The requested URL was not found" not in body, path


def test_an_api_address_keeps_its_json_404():
    c, _uid = _account()
    r = c.get("/api/there-is-no-such-thing")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("ok") is False


def test_a_signed_out_visitor_still_meets_the_login_wall_first():
    """The wall answers an unknown address before routing does, so the new
    page is for the signed-in reader it was written for."""
    r = appmod.app.test_client().get("/no-such-page-at-all")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_a_missing_static_file_is_not_answered_with_a_page():
    r = appmod.app.test_client().get("/static/no-such-file.css")
    assert r.status_code == 404
    assert "sb-plate" not in r.get_data(as_text=True)
