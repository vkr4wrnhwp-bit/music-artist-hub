"""Phase 3 of the TOUR restructure: one tour product.

The Tour Hub (/tour) is folded into TOUR (/tours). Its addresses survive as
bookmarks, its POST routes still answer old forms, the public /showday and
/rider pages are untouched, and the pipeline it owned - hold, confirmed,
advanced, played, settled - now lives on the tour's Dates page, with the
hub's own two lines kept word for word.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod
import command_center
import db as store
import hubs
import tour_os
import tour_store as ts

PASSWORD = "fold-pass-123"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSES = ("hold", "confirmed", "advanced", "played", "settled")
LEGEND = ("Statuses, honestly: hold = penciled in, confirmed = date locked, advanced = "
          "venue has your plot and details, played = done, settled = you got paid.")
PIPELINE = ("Every show, one pipeline: hold → confirmed → advanced → played → settled. "
            "Keep the status honest and nothing falls through the cracks on show day.")


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Fold Owner"):
    email = "fold-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})   # the Money Queue is artist-tier
    return client, store.get_user_by_email(email)


def _tour(client, name="Fold Run", start="2030-05-01", end="2030-05-10", **over):
    data = {"name": name, "artist_name": "Fold Artist", "start_date": start, "end_date": end,
            "home_tz": "America/New_York", "currency": "USD"}
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


def _member_join(flask_app, owner_client, tid, role, scopes, label="Crew Member"):
    member_client, member = _user(flask_app, label)
    owner_client.post("/tours/%s/team/invite" % tid,
                      data={"email": member["email"], "name": label, "role": role, "scopes": scopes})
    m = ts.get_member_by_email(tid, member["email"])
    assert m and m["invite_token"]
    assert member_client.get("/tours/join/%s" % m["invite_token"]).status_code == 302
    return member_client, member


def _status(owner, sid):
    return store.get_tour_show(owner["id"], sid)["status"]


# --- one constant -----------------------------------------------------------

def test_the_five_statuses_are_defined_once():
    assert ts.SHOW_STATUSES == STATUSES
    assert tour_os._STATUS_ORDER == list(STATUSES)
    literal = '("hold", "confirmed", "advanced", "played", "settled")'
    for name in ("app.py", "tour_os.py"):
        src = io.open(os.path.join(HERE, name), encoding="utf-8").read()
        assert literal not in src, "%s still spells the statuses out" % name
    assert literal in io.open(os.path.join(HERE, "tour_store.py"), encoding="utf-8").read()


# --- /tour is a bookmark into TOUR -------------------------------------------

def test_tour_redirects_for_a_user_without_and_with_tours(flask_app):
    anon = flask_app.test_client()
    r = anon.get("/tour")
    assert r.status_code == 302 and "/login" in r.headers["Location"]

    client, owner = _user(flask_app)
    for path in ("/tour", "/tour?view=board"):
        r = client.get(path)
        assert r.status_code == 302 and r.headers["Location"] == "/tours", path
    # The most recent tour wins, whichever was created first.
    newer = _tour(client, "Later Run", start="2031-01-05", end="2031-01-20")
    older = _tour(client, "Earlier Run", start="2029-03-01", end="2029-03-10")
    assert ts.list_tours(owner["id"])[0]["id"] == newer
    for path in ("/tour", "/tour?view=board"):
        r = client.get(path)
        assert r.status_code == 302 and r.headers["Location"] == "/tours/%s/shows" % newer, path
    assert client.get(r.headers["Location"]).status_code == 200


def test_tour_show_redirects_attached_unattached_and_404s_strangers(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    attached = _show(client, tid, "2030-05-02", "Attached Room")
    r = client.get("/tour/%s" % attached)
    assert r.status_code == 302 and r.headers["Location"] == "/tours/%s/shows/%s" % (tid, attached)
    assert client.get(r.headers["Location"]).status_code == 200
    # A show that is not on any tour is adopted onto the owner's tour on the
    # way through, so the old link lands on its date page, never a dead end.
    loose = store.add_tour_show(owner["id"], "2030-06-01", "Loose Room", "Memphis, TN", "")
    r = client.get("/tour/%s" % loose)
    assert r.status_code == 302 and r.headers["Location"] == "/tours/%s/shows/%s" % (tid, loose)
    assert store.get_tour_show(owner["id"], loose)["tour_id"] == tid
    assert "existing show(s) not on a tour" not in client.get("/tours").get_data(as_text=True)
    # Strangers get a 404 for both, never a redirect that confirms the id.
    stranger, _s = _user(flask_app, "Stranger")
    assert stranger.get("/tour/%s" % attached).status_code == 404
    assert stranger.get("/tour/%s" % loose).status_code == 404
    assert client.get("/tour/%s" % uuid.uuid4().hex).status_code == 404


# --- the Dates page carries the pipeline -------------------------------------

def test_the_dates_page_carries_the_pipeline_and_the_legend_verbatim(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-02", "Pipeline Room")
    page = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert PIPELINE in page and LEGEND in page
    # The legend sits beneath the table, the pipeline line above it.
    assert page.index(PIPELINE) < page.index("<table") < page.index(LEGEND)
    form = re.search(r'<form method="post" action="/tours/%s/shows/%s/ext" class="to-status-form">(.*?)</form>'
                     % (tid, sid), page, re.S)
    assert form, "no status form on the row"
    options = re.findall(r'<option value="([a-z]+)"', form.group(1))
    assert tuple(options) == STATUSES
    assert 'value="hold" selected' in form.group(1)
    assert ">Update<" in form.group(1)                       # the no-script fallback
    assert '.to-status-form select' in page and "requestSubmit" in page
    # A view-only member reads the status as a chip and gets no form.
    crew, _m = _member_join(flask_app, client, tid, "crew", ["view"])
    theirs = crew.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert LEGEND in theirs and "to-status-form" not in theirs
    assert 'name="status"' not in theirs


def test_status_changes_from_dates_go_through_ext_and_hacked_is_rejected(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-02", "Status Room")
    assert _status(owner, sid) == "hold"
    for st in ("confirmed", "advanced", "played", "settled"):
        r = client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": st},
                        headers={"Referer": "http://localhost/tours/%s/shows" % tid})
        assert r.status_code == 302 and r.headers["Location"].endswith("/tours/%s/shows" % tid)
        assert _status(owner, sid) == st
    # The guard: a made-up status changes nothing.
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": "hacked"})
    assert _status(owner, sid) == "settled"
    # Going back down is allowed from the page (only the importer is forward-only).
    client.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": "hold"})
    assert _status(owner, sid) == "hold"
    # The change is logged like any other show change.
    page = client.get("/tours/%s/changes" % tid).get_data(as_text=True)
    assert "Status Room" in page


# --- money --------------------------------------------------------------------

def test_money_queue_reads_tour_settlements_first_then_legacy_sheets(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show(client, tid, "2030-05-02", "Settled A")
    b = _show(client, tid, "2030-05-03", "Settled B")
    mq = client.get("/money-queue").get_data(as_text=True)
    assert "Settled tour income" not in mq
    # A settlement marked settled with an amount counts; without an amount
    # it does not (nothing typed is not zero).
    client.post("/tours/%s/shows/%s/money" % (tid, a),
                data={"settlement_amount": "1,250", "settlement_status": "settled"})
    client.post("/tours/%s/shows/%s/money" % (tid, b), data={"settlement_status": "settled"})
    assert ts.settled_income(owner["id"]) == {a: 1250.0}
    mq = client.get("/money-queue").get_data(as_text=True)
    assert "Settled tour income" in mq and "$1250.00" in mq and "1 settled show" in mq
    assert 'href="/tours"' in mq and "TOUR →" in mq and "Tour Hub" not in mq
    # A legacy hub sheet on a show with no TOUR settlement is added to it.
    legacy = store.add_tour_show(owner["id"], "2029-01-10", "Old Sheet Room", "", "")
    store.update_tour_show_status(owner["id"], legacy, "settled")
    store.save_show_settlement(owner["id"], legacy, {"deal_type": "flat", "guarantee": "300",
                                                     "merch_gross": "100", "merch_cut_pct": "0",
                                                     "expenses": "50"})
    mq = client.get("/money-queue").get_data(as_text=True)
    assert "$1600.00" in mq and "2 settled shows" in mq
    # The same show settled on TOUR is read from TOUR, not counted twice.
    client.post("/tours/%s/shows/attach" % tid, data={"show_id": legacy})
    client.post("/tours/%s/shows/%s/money" % (tid, legacy),
                data={"settlement_amount": "350", "settlement_status": "settled"})
    mq = client.get("/money-queue").get_data(as_text=True)
    assert "$1600.00" in mq and "2 settled shows" in mq
    # Strangers' settlements never leak into another account's queue.
    other, _o = _user(flask_app, "Other")
    assert "Settled tour income" not in other.get("/money-queue").get_data(as_text=True)


def test_the_money_page_settled_line_and_the_route_flags(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    a = _show(client, tid, "2030-05-02", "Room One", city="Nashville, TN")
    b = _show(client, tid, "2030-05-02", "Room Two", city="Memphis, TN")
    c = _show(client, tid, "2030-05-03", "Room Three", city="Chicago, IL")
    money = client.get("/tours/%s/money" % tid).get_data(as_text=True)
    assert "Settled: no settlement entered yet" in money
    assert "straight sums of what you entered, nothing estimated" in money
    client.post("/tours/%s/shows/%s/money" % (tid, a),
                data={"settlement_amount": "900", "settlement_status": "settled"})
    client.post("/tours/%s/shows/%s/money" % (tid, c),
                data={"settlement_amount": "600.50", "settlement_status": "settled"})
    money = client.get("/tours/%s/money" % tid).get_data(as_text=True)
    assert "1500.50" in money and "2 settled shows" in money
    # Route: two shows on one day, then the next day - flagged from dates alone.
    route = client.get("/tours/%s/map" % tid).get_data(as_text=True)
    assert "same day" in route and "back to back" in route
    assert "flagged from the dates alone" in route


# --- navigation: one tour entry ------------------------------------------------

def test_navigation_has_exactly_one_tour_entry(flask_app):
    stage = hubs.get_hub("stage")["modules"]
    tour_items = [(k, href) for k, href, *_ in stage if href.startswith("/tour")
                  and not href.startswith("/tour-board")]
    assert tour_items == [("tours", "/tours")]
    assert "tour" not in hubs.LIVE_KEYS and "tours" in hubs.LIVE_KEYS
    assert "tour" not in hubs.live_keys()
    hrefs = [i["href"] for i in hubs.command_index()]
    assert "/tours" in hrefs and "/tour" not in hrefs
    assert "/tours" in command_center.MODULE_BY_ROUTE and "/tour" not in command_center.MODULE_BY_ROUTE
    assert command_center.MODULE_BY_ROUTE["/tours"][1] == "TOUR"
    client, owner = _user(flask_app)
    desk = client.get("/desk/stage").get_data(as_text=True)
    assert desk.count('href="/tours" data-live=') == 1 and "Tour Hub" not in desk
    assert 'href="/tour"' not in desk
    rail = client.get("/lights").get_data(as_text=True).split('id="lx-rail"')[1].split("</nav>")[0]
    assert 'href="/tours"' in rail and 'href="/tour"' not in rail
    for name in ("templates/tour.html", "templates/tour_show.html"):
        assert not os.path.exists(os.path.join(HERE, name)), name
    for path in ("/tours", "/money-queue", "/lights", "/desk/stage"):
        assert "Tour Hub" not in client.get(path).get_data(as_text=True), path


# --- what survives: old forms and the public pages ------------------------------

def test_legacy_hub_posts_and_public_pages_still_answer(flask_app):
    client, owner = _user(flask_app)
    tid = _tour(client)
    r = client.post("/tour/add", data={"date": "2030-05-04", "venue": "Old Form Room",
                                       "city": "Denton, TX"})
    assert r.status_code == 302
    sid = [s for s in store.list_tour_shows(owner["id"]) if s["venue"] == "Old Form Room"][0]["id"]
    assert _status(owner, sid) == "hold"
    client.post("/tour/%s/status" % sid, data={"status": "confirmed"})
    assert _status(owner, sid) == "confirmed"
    client.post("/tour/%s/status" % sid, data={"status": "hacked"})
    assert _status(owner, sid) == "confirmed"
    client.post("/tour/%s/advance" % sid, data={"backline": "House provides bass rig",
                                                "dayof_contact": "Sam 555-0100", "load_in": "4pm",
                                                "deal": "$500 flat"})
    client.post("/tour/%s/share" % sid)
    token = store.get_tour_show(owner["id"], sid)["share_token"]
    anon = flask_app.test_client()
    showday = anon.get("/showday/%s" % token).get_data(as_text=True)
    rider = anon.get("/rider/%s" % token).get_data(as_text=True)
    assert "Old Form Room" in showday and "4pm" in showday and "555-0100" in showday
    assert "Old Form Room" in rider and "House provides bass rig" in rider
    for text in (showday, rider):
        assert "$500" not in text                        # money never, on public pages
    assert anon.get("/showday/nope").status_code == 404
    assert anon.get("/rider/nope").status_code == 404
    # On the tour, the date page's Send advance section carries the rider link.
    client.post("/tours/%s/shows/attach" % tid, data={"show_id": sid})
    send = client.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).get_data(as_text=True)
    assert "/rider/%s" % token in send
    # And the hub bookmark now lands on that date.
    r = client.get("/tour/%s" % sid)
    assert r.status_code == 302 and r.headers["Location"] == "/tours/%s/shows/%s" % (tid, sid)


def test_the_assets_moved_on_with_the_fold():
    sw = io.open(os.path.join(HERE, "static", "js", "sw.js"), encoding="utf-8").read()
    assert 'VERSION = "sb-v168"' in sw
    shell = io.open(os.path.join(HERE, "templates", "tour", "_shell.html"), encoding="utf-8").read()
    assert "tour-os.css?v=6" in shell
    css = io.open(os.path.join(HERE, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-status-form" in css and ".to-legend" in css
    assert "@media print" in css and ".to, .to *" in css
