"""Approving past a show's guest allocation is refused, on the server.

Make-it-real audit, 2026-09-23 (not_real_today[11]; the 2026-09-11
overclaims list, item 1): the empty guest list promised "approving past
the allocation is refused, not silently allowed", but the Approve button
(guest_update) had no allocation check: the page only lit "Over
allocation" afterwards. Now the change is refused before anything is
saved and the page says who did not fit and why. Adding a guest as
approved past the allocation lands them pending, and now says so.

What is NOT refused: working the door of a list that is already over
because the allocation was lowered after approvals (check in, undo, no
show, deny). Only a change that takes more spots is.
"""
import pytest

import app as appmod
import tour_store as ts
from tests.test_tour_date_page import _show, _tour, _user


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _allocation(c, tid, sid, n):
    r = c.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"guest_allocation": str(n)})
    assert r.status_code == 302


def _add(c, tid, sid, name, count=1, status="pending"):
    r = c.post("/tours/%s/shows/%s/guests/add" % (tid, sid),
               data={"name": name, "count": str(count), "status": status, "category": "Personal"})
    assert r.status_code == 302
    return r, [g for g in ts.list_guests(tid, sid) if g["name"] == name][0]


def _set(c, tid, sid, gid, **form):
    return c.post("/tours/%s/shows/%s/guests/%s" % (tid, sid, gid), data=form)


def _guest(tid, gid):
    return ts.get_guest(tid, gid)


def test_approving_past_the_allocation_is_refused_and_said(flask_app):
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _allocation(c, tid, sid, 2)
    _r, ana = _add(c, tid, sid, "Ana Full", count=2, status="approved")
    assert ana["status"] == "approved", "exactly the allocation fits"
    _r, ben = _add(c, tid, sid, "Ben Waiting")
    r = _set(c, tid, sid, ben["id"], status="approved")
    assert r.status_code == 302 and "full=%s" % ben["id"] in r.headers["Location"]
    assert _guest(tid, ben["id"])["status"] == "pending", "nothing was saved"
    s = ts.guest_summary(tid, sid, "2")
    assert s["used"] == 2 and not s["over"]
    page = c.get("/tours/%s/shows/%s?tab=guests&full=%s" % (tid, sid, ben["id"])).get_data(as_text=True)
    assert 'id="guest-refused"' in page and "Not approved." in page and "Ben Waiting" in page
    assert "allocation of 2" in page


def test_raising_an_approved_party_past_the_allocation_is_refused(flask_app):
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _allocation(c, tid, sid, 3)
    _r, ana = _add(c, tid, sid, "Ana Party", count=2, status="approved")
    assert _set(c, tid, sid, ana["id"], count="3").status_code == 302
    assert _guest(tid, ana["id"])["count"] == 3, "up to the allocation is fine"
    r = _set(c, tid, sid, ana["id"], count="4")
    assert "full=%s" % ana["id"] in r.headers["Location"]
    assert _guest(tid, ana["id"])["count"] == 3


def test_checking_in_a_denied_guest_past_the_allocation_is_refused_too(flask_app):
    """checked_in takes a spot like approved does; it is not a way round."""
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _allocation(c, tid, sid, 1)
    _add(c, tid, sid, "Ana One", count=1, status="approved")
    _r, cy = _add(c, tid, sid, "Cy Denied")
    _set(c, tid, sid, cy["id"], status="denied")
    r = _set(c, tid, sid, cy["id"], status="checked_in")
    assert "full=" in r.headers["Location"]
    assert _guest(tid, cy["id"])["status"] == "denied"


def test_the_door_still_works_on_a_list_already_over(flask_app):
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _allocation(c, tid, sid, 3)
    _r, ana = _add(c, tid, sid, "Ana Door", count=2, status="approved")
    _r, cy = _add(c, tid, sid, "Cy Door", count=1, status="approved")
    _allocation(c, tid, sid, 2)          # lowered after the approvals: over by one
    assert ts.guest_summary(tid, sid, "2")["over"]
    for status in ("checked_in", "approved", "checked_in"):
        r = _set(c, tid, sid, ana["id"], status=status)
        assert "full=" not in r.headers["Location"]
        assert _guest(tid, ana["id"])["status"] == status
    assert "full=" not in _set(c, tid, sid, cy["id"], status="no_show").headers["Location"]
    assert _guest(tid, cy["id"])["status"] == "no_show"
    # ...but bringing the no-show back onto the list is taking a spot again.
    assert "full=" in _set(c, tid, sid, cy["id"], status="approved").headers["Location"]
    assert _guest(tid, cy["id"])["status"] == "no_show"


def test_no_allocation_means_no_refusal(flask_app):
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _r, big = _add(c, tid, sid, "Big Party", count=12)
    r = _set(c, tid, sid, big["id"], status="approved")
    assert "full=" not in r.headers["Location"]
    assert _guest(tid, big["id"])["status"] == "approved"


def test_adding_an_approved_guest_past_the_allocation_lands_pending_and_says_so(flask_app):
    c, _owner = _user(flask_app)
    tid = _tour(c)
    sid = _show(c, tid)
    _allocation(c, tid, sid, 1)
    r, dee = _add(c, tid, sid, "Dee Pair", count=2, status="approved")
    assert dee["status"] == "pending"
    assert "held=%s" % dee["id"] in r.headers["Location"]
    page = c.get("/tours/%s/shows/%s?tab=guests&held=%s" % (tid, sid, dee["id"])).get_data(as_text=True)
    assert "Added as pending, not approved." in page and "Dee Pair" in page and "party of 2" in page
    # A guest who fits is approved and nothing is said.
    _allocation(c, tid, sid, 5)
    r, eve = _add(c, tid, sid, "Eve Fits", count=1, status="approved")
    assert eve["status"] == "approved" and "held=" not in r.headers["Location"]


def test_the_store_rule_on_its_own():
    """guest_over_allocation, the one rule both routes use."""
    import db as store
    import uuid
    uid = "u-%s" % uuid.uuid4().hex[:8]
    tid = ts.create_tour(uid, {"name": "Rule Run", "status": "planning"})
    sid = store.add_tour_show(uid, "2030-01-02", "Rule Room", "Rule City", "")
    ts.attach_show(tid, sid, "")
    gid = ts.add_guest(tid, uid, sid, {"name": "A", "count": 3, "status": "approved"})
    assert ts.guest_over_allocation(tid, sid, "", None, "approved", 50) == 0, "no allocation set"
    assert ts.guest_over_allocation(tid, sid, "4", None, "approved", 1) == 0
    assert ts.guest_over_allocation(tid, sid, "4", None, "approved", 3) == 2
    assert ts.guest_over_allocation(tid, sid, "4", None, "pending", 9) == 0, "pending takes no spot"
    assert ts.guest_over_allocation(tid, sid, "2", gid, "checked_in", 3) == 0, "no more spots than before"
    assert ts.guest_over_allocation(tid, sid, "3", gid, "approved", 5) == 2
