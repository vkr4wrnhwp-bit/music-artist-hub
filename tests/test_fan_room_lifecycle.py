"""The Fan Room's lifecycle rail counts real fans at each stage.

Until 2026-09-23 the rail was five fixed (key, name, line) tuples -
Discover "Find new listeners", Capture "Turn interest into fans" and so
on - drawn on every populated room with no count behind any stage. Each
stage now carries the count the account's own records support, and a
stage with nothing counted says so in words (never a nought).
"""
import uuid

import app as appmod
import db as store
import fan_room
import links_store as mls

PW = "lifecycle-pass-12345"


def _account():
    email = "life-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Life Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _rail(body):
    part = body.split('<ol class="fr-life-rail">', 1)[1].split("</ol>", 1)[0]
    out = {}
    for li in part.split('data-stage="')[1:]:
        key = li.split('"', 1)[0]
        out[key] = li.split("</b>", 1)[1].split("<span>", 1)[1].split("</span>", 1)[0].strip()
    return out


def test_each_stage_is_counted_from_the_rows():
    rows = [
        {"email": "a@x.net", "name": "Ann", "total_clicks": 2},
        {"email": "b@x.net", "name": "", "city": "Atlanta", "total_presaves": 1},
        {"email": "c@x.net", "name": "", "total_visits": 3},
        {"email": "d@x.net", "name": ""},
    ]
    st = {s["key"]: s for s in fan_room.lifecycle(rows, link_visits=40,
                                                  club={"on": True, "members": 1})}
    assert [s["key"] for s in fan_room.lifecycle(rows)] == [
        "discover", "capture", "know", "activate", "belong"]
    assert st["discover"]["line"] == "40 smart link visits"
    assert st["capture"]["line"] == "4 fans on file"
    assert st["know"]["line"] == "2 with a name or place"
    # a visit alone is not a click: c@ is not Activated
    assert st["activate"]["line"] == "2 clicked or pre-saved"
    assert st["belong"]["line"] == "1 Fan Club member"


def test_nothing_counted_is_words_never_a_nought():
    rows = [{"email": "a@x.net", "name": ""}]
    st = {s["key"]: s["line"] for s in fan_room.lifecycle(rows, 0, {"on": True, "members": 0})}
    assert st == {"discover": "No smart link visits", "capture": "1 fan on file",
                  "know": "No names or places yet", "activate": "Nobody has clicked yet",
                  "belong": "No members yet"}
    no_club = fan_room.lifecycle(rows, 0, {"on": False, "members": 0})
    assert no_club[-1]["line"] == "No Fan Club yet"
    for s in fan_room.lifecycle(rows, 0, None):
        assert not s["line"].startswith("0"), s


def test_the_room_draws_the_accounts_own_counts_on_the_rail():
    c, uid = _account()
    cid = mls.create_campaign(uid, "life-%s" % uuid.uuid4().hex[:6], {"title": "Life"})
    named = mls.upsert_fan(uid, "named@example.net", cid, name="Named Fan")
    mls.upsert_fan(uid, "plain@example.net", cid)
    mls.bump_fan(named, "total_clicks")
    for _ in range(3):
        mls.track(cid, "page_view")
    store.save_fan_club(uid, "Inner Circle", "b", 500, ["Early drops"], True)
    store.add_club_member(uid, "named@example.net", "cus_l", "sub_l_%s" % uuid.uuid4().hex[:6])
    body = c.get("/room/fans").get_data(as_text=True)
    assert "The fan lifecycle" in body
    assert _rail(body) == {
        "discover": "3 smart link visits",
        "capture": "2 fans on file",
        "know": "1 with a name or place",
        "activate": "1 clicked or pre-saved",
        "belong": "1 Fan Club member",
    }
    # the old aspiration lines are gone from the rail
    for line in ("Find new listeners", "Turn interest into fans", "Enrich profiles and data",
                 "Drive engagement and revenue", "Create a lasting community"):
        assert line not in body, line
