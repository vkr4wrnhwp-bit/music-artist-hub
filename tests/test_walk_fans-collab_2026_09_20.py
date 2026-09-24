"""The fans and collab findings of the 2026-09-20 page walk, pinned.

Five things a signed-in artist met: a Fan Room card promising profiles and
segments over a page that has neither, a Shopify import promised to
accounts that cannot run it, a demo Fan CRM that said "No fans captured
yet" under an Audience counting 14,430, the shared demo login posting to
the live collab board and applying to real members' briefs, and a fan
removal that finished in silence.
"""
import uuid

import pytest

import app as appmod
import db as store
import fan_room
import links_store as mls

PW = "walk-fans-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(name="Walk Artist", plan="label"):
    email = "walkfans-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid, email


def _demo():
    d = appmod.app.test_client()
    d.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    duid = store.get_user_by_email("demo@streetbanker.io")["id"]
    with d.session_transaction() as s:
        assert s.get("user_id") == duid, "demo login failed"
    return d, duid


def _set(fid, **cols):
    with store.get_db() as db:
        db.execute("UPDATE ml_fans SET %s WHERE id = ?" % ", ".join("%s = ?" % k for k in cols),
                   tuple(cols.values()) + (fid,))


def _tile(body, key):
    start = body.index('data-room-card="%s"' % key)
    return body[start:body.index("</a>", start)]


# --- 1. the Fan CRM card says what the page is ------------------------------

def test_the_fan_crm_card_says_what_the_page_is():
    c, uid, _ = _account()
    for i in range(5):
        mls.upsert_fan(uid, "fan%d-%s@example.net" % (i, uid[:6]), None)
    room = c.get("/room/fans").get_data(as_text=True)
    tile = _tile(room, "fan-crm")
    assert "Profiles &amp; segments" not in room and "Profiles & segments" not in room
    assert "Everyone on file, searchable and exportable" in tile
    assert "5 fans" in tile and "segment" not in tile
    crm = c.get("/links/fans").get_data(as_text=True)
    assert "segment" not in crm.lower() and "profile" not in crm.lower()


def test_the_card_is_lit_by_the_fan_count_not_the_band_count():
    club = {"on": False, "members": 0}
    assert fan_room.tile_status("fan-crm", {"total": 0, "segments": []}, 0, 30, club, 0, "live") == ("off", "Nobody yet")
    assert fan_room.tile_status("fan-crm", {"total": 1, "segments": [{"name": "Cold", "count": 1}]}, 0, 30, club, 0, "live") == ("good", "1 fan")
    assert fan_room.tile_status("fan-crm", {"total": 1200, "segments": []}, 0, 30, club, 0, "live") == ("good", "1,200 fans")


def test_the_two_moves_land_on_the_fans_they_name():
    c, uid, _ = _account()
    hot = mls.upsert_fan(uid, "hot-%s@example.net" % uid[:6], None, "Hot Fan")
    cold = mls.upsert_fan(uid, "cold-%s@example.net" % uid[:6], None, "Cold Fan")
    nomail = mls.upsert_fan(uid, "", None, "No Mail")
    _set(hot, intent_level="Hot", intent_score=80)
    room = c.get("/room/fans").get_data(as_text=True)
    assert 'href="/links/fans?missing=email"' in room and "Find 1 missing email" in room
    assert 'href="/links/fans?intent=top"' in room and "Reward your 1 most engaged fan" in room

    missing = c.get("/links/fans?missing=email").get_data(as_text=True)
    assert "Showing the 1 fan on file with no email address." in missing
    assert "No Mail" in missing and "hot-" not in missing and "cold-" not in missing
    assert 'href="/links/fans">Show everyone' in missing

    top = c.get("/links/fans?intent=top").get_data(as_text=True)
    assert "Showing the 1 fan scored Hot or Superfan." in top
    assert "hot-%s@example.net" % uid[:6] in top and "cold-" not in top and "No Mail" not in top

    # A filter with nobody behind it says so, not "No fans captured yet".
    _set(nomail, email="late-%s@example.net" % uid[:6])
    none = c.get("/links/fans?missing=email").get_data(as_text=True)
    assert "Everyone on file has an email address." in none
    assert "No fans captured yet" not in none
    everyone = c.get("/links/fans").get_data(as_text=True)
    assert "Show everyone" not in everyone and "hot-" in everyone and "cold-" in everyone


# --- 2. Shopify is promised only where it can run ----------------------------

def test_shopify_is_promised_only_to_an_account_that_can_import_it(monkeypatch):
    # An account with no fans meets the Fans page from zero (2026-09-22),
    # where importing is the "Bring an audience you already have" card; the
    # "Bring in the fans you already have" move, and its Shopify wording for
    # the owner, are pinned at the builder by the test below.
    c, _uid, email = _account()
    body = c.get("/room/fans").get_data(as_text=True)
    assert "Bring an audience you already have" in body
    assert "Shopify" not in body, "a non-owner is never promised a Shopify import"
    assert c.post("/links/fans/import/shopify").status_code == 404


def test_the_move_copy_follows_the_flag():
    audience = {"total": 0, "segments": [], "geo": {}}
    from datetime import date
    first = fan_room.moves([], audience, 30, date(2026, 9, 20))[0]
    assert first["desc"] == "Import a list. You preview it first."
    first = fan_room.moves([], audience, 30, date(2026, 9, 20), shopify=True)[0]
    assert first["desc"] == "Import a list or Shopify customers. You preview it first."


# --- 3. the demo Fan CRM shows the showcase it counts elsewhere -------------

def test_the_demo_fan_crm_shows_the_showcase_the_audience_counts():
    d, duid = _demo()
    # Every test file a worker runs shares one database (conftest), and
    # test_app's Spotify pre-save test captures a fan on this same demo
    # account. When that file ran first, the demo had a fan, the page
    # rightly took the showcase back, and this test failed on ordering,
    # not on the product (2026-09-23). The showcase stands in only while
    # the demo has captured nobody, so this test sets that up itself.
    for fan in mls.list_fans(duid):
        mls.delete_fan(duid, fan["id"])
    assert mls.list_fans(duid) == []
    body = d.get("/links/fans").get_data(as_text=True)
    assert "Showcase." in body and "au-showcase" in body
    assert "the first 200 of 14,430 are listed" in body
    assert "showcase-" in body and body.count("<tr") == 201       # header + 200 rows
    assert "No fans captured yet" not in body
    # Nothing on the showcase can be imported, exported or removed.
    assert "data-au-import" not in body and "Bring in a list" not in body
    assert "/delete" not in body and "export.csv" not in body
    # Search still works over the generated rows, and a short result is
    # not called "the first 200".
    hit = d.get("/links/fans?q=Jasmine").get_data(as_text=True)
    assert "Jasmine Reed" in hit and "the first 200" not in hit
    assert mls.list_fans(duid) == [], "reading the showcase wrote nothing"


def test_a_real_account_never_sees_the_showcase_rows():
    c, uid, _ = _account()
    mls.upsert_fan(uid, "mine-%s@example.net" % uid[:6], None)
    body = c.get("/links/fans").get_data(as_text=True)
    assert "showcase-" not in body and "Showcase." not in body
    assert "data-au-import" in body and "export.csv" in body and "/delete" in body


# --- 4. the shared demo login writes nothing on the marketplace ------------

def _counts(duid, rid):
    with store.get_db() as db:
        return (db.execute("SELECT COUNT(*) FROM collab_requests WHERE user_id = ?", (duid,)).fetchone()[0],
                db.execute("SELECT COUNT(*) FROM collab_replies WHERE request_id = ?", (rid,)).fetchone()[0],
                db.execute("SELECT COUNT(*) FROM collab_saves WHERE user_id = ?", (duid,)).fetchone()[0],
                db.execute("SELECT COUNT(*) FROM collab_ratings WHERE user_id = ?", (duid,)).fetchone()[0])


def test_the_demo_login_writes_nothing_on_the_marketplace_lock_or_no_lock():
    demo, duid = _demo()
    store.set_demo_lock(duid, False)          # the owner has not set the lock
    member, muid, _ = _account("Real Member")
    member.post("/marketplace/post", data={"kind": "bid", "role": "Producer",
                                           "title": "real brief", "details": "y"})
    with store.get_db() as db:
        rid = db.execute("SELECT id FROM collab_requests WHERE user_id = ?", (muid,)).fetchone()[0]
    before = _counts(duid, rid)
    assert before[0] == 0 and before[1] == 0

    r = demo.post("/marketplace/post", data={"kind": "bid", "role": "Producer",
                                             "title": "demo brief", "details": "x"})
    assert r.status_code == 302 and r.headers["Location"] == "/marketplace?tab=briefs&demo=member#post"
    r = demo.post("/marketplace/%s/apply" % rid, data={"message": "hi", "contact": "demo@streetbanker.io"})
    assert r.status_code == 302 and r.headers["Location"] == "/marketplace?demo=member"
    r = demo.post("/marketplace/%s/save" % rid, data={"back": "/marketplace?tab=briefs"})
    assert r.headers["Location"] == "/marketplace?tab=briefs&demo=member"
    r = demo.post("/marketplace/%s/report" % rid)
    assert r.headers["Location"] == "/marketplace?demo=member"
    r = demo.post("/marketplace/%s/choose/nothing" % rid, data={"chosen": "1"})
    assert r.headers["Location"] == "/marketplace?tab=briefs&demo=member#brief-%s" % rid
    r = demo.post("/marketplace/%s/rate/%s" % (rid, muid), data={"stars": "5"})
    assert r.headers["Location"] == "/marketplace?tab=projects&demo=member"

    assert _counts(duid, rid) == before
    assert store.get_kv("collab_report:%s:%s" % (rid, duid)) is None
    assert not [n for n in store.list_notifications(muid) if "application" in (n.get("title") or "").lower()]
    board = member.get("/marketplace").get_data(as_text=True)
    assert "demo brief" not in board

    page = demo.get("/marketplace?demo=member").get_data(as_text=True)
    assert "Not saved. The demo account is not a member of the marketplace" in page


def test_a_member_still_posts_and_applies():
    a, auid, _ = _account("Poster")
    b, buid, _ = _account("Applicant")
    a.post("/marketplace/post", data={"kind": "bid", "role": "Producer",
                                      "title": "member brief", "details": "y"})
    with store.get_db() as db:
        rid = db.execute("SELECT id FROM collab_requests WHERE user_id = ?", (auid,)).fetchone()[0]
    r = b.post("/marketplace/%s/apply" % rid, data={"message": "hi", "contact": "b@example.net"})
    assert r.headers["Location"] == "/marketplace?applied=1"
    assert "Not saved" not in b.get("/marketplace").get_data(as_text=True)


# --- 5. removing a fan says so ----------------------------------------------

def test_removing_a_fan_says_so():
    c, uid, _ = _account()
    fid = mls.upsert_fan(uid, "gone-%s@example.net" % uid[:6], None)
    assert "Removed." not in c.get("/links/fans").get_data(as_text=True)
    r = c.post("/links/fans/%s/delete" % fid)
    assert r.status_code == 302 and r.headers["Location"] == "/links/fans?removed=1"
    after = c.get(r.headers["Location"]).get_data(as_text=True)
    assert "Removed." in after and "Their record, consent log and link activity are gone." in after
    assert "gone-%s@example.net" % uid[:6] not in after


def test_a_real_capture_takes_the_demo_crm_back_from_the_showcase():
    """The demo login can capture a real fan through a real smart link.
    A real capture is never hidden behind generated rows."""
    import links_store as mls
    import app as appmod
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    duid = store.get_user_by_email("demo@streetbanker.io")["id"]
    before = mls.list_fans(duid)
    mls.upsert_fan(duid, "realcapture@example.net", "", name="Real Capture")
    body = demo.get("/links/fans").get_data(as_text=True)
    assert "realcapture@example.net" in body
    assert len(mls.list_fans(duid)) == len(before) + 1
