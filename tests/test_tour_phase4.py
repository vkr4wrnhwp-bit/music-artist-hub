"""Phase 4 of the tour audit: the small things.

Tour-wide set lists can be created from a screen (they could only be copied
before), VIP rolls up across the run under its own scope, two orphaned
templates are gone, and the two modules that were not TOUR say what they are.
"""
import os
import uuid

import pytest

import app as appmod
import db as store
import tour_os
import tour_store as ts

PASSWORD = "p4-pass-123"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner(flask_app):
    email = "p4-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "P4 Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "P4 Run", "artist_name": "P4 Artist", "start_date": "2030-07-01",
        "end_date": "2030-07-08", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-07-02", "kind": "show", "venue": "The Basement East", "city": "Nashville, TN",
        "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    return client, store.get_user_by_email(email), tid, sid


def test_tour_wide_set_lists_are_made_here_and_copied_on_a_date(flask_app):
    client, owner, tid, sid = _owner(flask_app)
    page = client.get("/tours/%s/setlists" % tid).get_data(as_text=True)
    assert "No tour-wide set list yet" in page
    r = client.post("/tours/%s/setlists" % tid, data={"action": "new", "name": "Main set"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s/setlists" % tid)
    lists = [sl for sl in ts.list_setlists(tid) if not sl.get("show_id")]
    assert len(lists) == 1 and lists[0]["name"] == "Main set"
    lid = lists[0]["id"]
    client.post("/tours/%s/setlists" % tid, data={
        "action": "save", "setlist_id": lid, "items": "Opener (3:10)\nSecond Song\nEncore: Last One (4:00)"})
    songs = ts.get_setlist(tid, lid)["songs"]
    assert [(s["title"], s["duration"], s["section"]) for s in songs] == [
        ("Opener", "3:10", "main"), ("Second Song", "", "main"), ("Last One", "4:00", "encore")]
    page = client.get("/tours/%s/setlists" % tid).get_data(as_text=True)
    assert "Main set" in page and "Opener (3:10)" in page and "Encore: Last One (4:00)" in page
    # The date's Set list section offers to copy it.
    date_page = client.get("/tours/%s/shows/%s?tab=setlist" % (tid, sid)).get_data(as_text=True)
    assert "Copy a tour list" in date_page and "Main set" in date_page
    client.post("/tours/%s/shows/%s/setlist" % (tid, sid), data={"action": "copy", "setlist_id": lid})
    assert len(ts.list_setlists(tid, sid)) == 1
    # A show's list cannot be edited or deleted through the tour-level route.
    show_lid = ts.list_setlists(tid, sid)[0]["id"]
    r = client.post("/tours/%s/setlists" % tid, data={"action": "save", "setlist_id": show_lid, "items": "x"})
    assert r.status_code == 404
    client.post("/tours/%s/setlists" % tid, data={"action": "delete", "setlist_id": show_lid})
    assert len(ts.list_setlists(tid, sid)) == 1
    # The tour-level list can be deleted here.
    client.post("/tours/%s/setlists" % tid, data={"action": "delete", "setlist_id": lid})
    assert not [sl for sl in ts.list_setlists(tid) if not sl.get("show_id")]


def test_vip_rolls_up_across_the_run_under_its_own_scope(flask_app):
    client, owner, tid, sid = _owner(flask_app)
    page = client.get("/tours/%s/vip" % tid).get_data(as_text=True)
    assert "No VIP packages on this run" in page
    r = client.post("/tours/%s/shows/%s/vip/add" % (tid, sid), data={
        "package": "Soundcheck party", "price": "150", "quantity": "3", "purchaser": "Taylor",
        "guest": "Taylor Example", "merch": "1"})
    assert r.status_code == 302
    page = client.get("/tours/%s/vip" % tid).get_data(as_text=True)
    assert "Nashville, TN" in page and 'href="/tours/%s/shows/%s?tab=vip"' % (tid, sid) in page
    row = page.split('data-k="Sold">')[1]
    assert row.startswith("3<")
    assert "450.00" in page                       # the owner holds financials: gross shows
    # The two new pages are in the More menu for an owner.
    bar = client.get("/tours/%s" % tid).get_data(as_text=True).split('class="to-tabs to-bar"')[1].split("</nav>")[0]
    assert ">Set lists<" in bar and ">VIP<" in bar
    # A viewer without the vip scope: no page, no menu entry.
    crew = {"is_owner": False, "scopes": ["view"]}
    keys = [t["key"] for t in tour_os._tour_bar(crew, "home")["more"]]
    assert "vip" not in keys and "setlists" in keys


def test_the_orphans_are_gone_and_the_modules_say_what_they_are():
    assert not os.path.exists(os.path.join(HERE, "templates", "tour", "show", "_overview.html"))
    assert not os.path.exists(os.path.join(HERE, "templates", "tour_board.html"))
    assert not os.path.exists(os.path.join(HERE, "touring.py"))
    assert not os.path.exists(os.path.join(HERE, "tour_config.py"))
    import product_tour_config
    import tour_hub_rules
    assert product_tour_config.TITLE == "Public product tour"
    assert tour_hub_rules.settlement_totals({"deal_type": "flat", "guarantee": "500"})["walk"] == 500.0
    assert "Tour Hub" in (tour_hub_rules.__doc__ or "")
