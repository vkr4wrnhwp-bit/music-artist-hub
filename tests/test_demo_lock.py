"""The read-only demo lock.

Owner, 2026-09-14: "make the demo account read only for everyone but
me". A shared demo login is handed to friends and distributors; anyone
with it could upload, delete statements or empty the account. The rules
this file holds:

  * only an owner can lock or unlock, by address, from Settings; an
    owner login itself cannot be locked
  * locked, every state-changing request is refused: a page form is
    bounced back with the reason in the shell's bar, a script call gets
    a 403 JSON answer with the same words; reading is untouched
  * signing out still works, so a visitor is never trapped
  * the Sample pages and Billing leave the locked account's menu and
    palette; the routes still answer
  * unlocked, the same requests save again
"""
import io
import uuid

import pytest

import db as store
import hubs
from app import create_app

PW = "demo-lock-12345"
CSV = ("Reporting Period,Artist,Track Title,Digital Service Provider,Royalty\n"
       "JUN-26,Hungry Gods,Narrow,Spotify,100.00\n")


def _fresh(app_obj, email=None):
    client = app_obj.test_client()
    email = email or ("lock-%s@example.net" % uuid.uuid4().hex[:8])
    client.post("/signup", data={"name": "Locked Demo", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._email = email
    return client


@pytest.fixture
def world(monkeypatch):
    app_obj = create_app()
    owner = _fresh(app_obj)
    demo = _fresh(app_obj)
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    return app_obj, owner, demo


def _statements(app_obj, email):
    with app_obj.app_context():
        return len(store.get_statements(store.get_user_by_email(email)["id"]))


def _upload(client):
    return client.post("/statements", data={"statement": (io.BytesIO(CSV.encode()), "jun.csv")},
                       content_type="multipart/form-data")


def test_only_an_owner_can_lock_and_the_page_shows_the_switch(world):
    app_obj, owner, demo = world
    assert demo.post("/admin/demo-lock", data={"email": owner._email}).status_code == 404
    body = owner.get("/settings").get_data(as_text=True)
    assert 'id="demo-lock"' in body and "No account is locked right now" in body
    r = owner.post("/admin/demo-lock", data={"email": demo._email.upper(), "action": "lock"})
    assert r.status_code == 302 and "demo_lock=locked" in r.headers["Location"]
    body = owner.get("/settings?demo_lock=locked&to=%s" % demo._email).get_data(as_text=True)
    assert "is locked. Everyone signed in as it is read only" in body
    assert demo._email in body and "· locked" in body
    r = owner.post("/admin/demo-lock", data={"email": owner._email, "action": "lock"})
    assert "demo_lock=owner" in r.headers["Location"]
    r = owner.post("/admin/demo-lock", data={"email": "nobody@example.net", "action": "lock"})
    assert "demo_lock=unknown" in r.headers["Location"]


def test_locked_reads_everything_and_changes_nothing(world):
    app_obj, owner, demo = world
    assert _upload(demo).status_code == 302 and _statements(app_obj, demo._email) == 1
    owner.post("/admin/demo-lock", data={"email": demo._email, "action": "lock"})

    for path in ("/command-center", "/statements", "/royalties", "/settings", "/epk", "/links"):
        page = demo.get(path)
        assert page.status_code == 200, path
        assert "shared demo account and it is read only" in page.get_data(as_text=True), path

    r = _upload(demo)
    assert r.status_code == 302 and "demo=readonly" in r.headers["Location"], r.headers.get("Location")
    assert _statements(app_obj, demo._email) == 1, "the upload was refused"
    r = demo.post("/statements", data={"statement": (io.BytesIO(CSV.encode()), "x.csv")},
                  content_type="multipart/form-data", headers={"Referer": "http://localhost/statements?period=JUN-26"})
    assert r.headers["Location"].endswith("/statements?period=JUN-26&demo=readonly")
    body = demo.get("/statements?demo=readonly").get_data(as_text=True)
    assert "That change was not saved" in body

    for path, data in (("/settings/profile", {"name": "Hijacked"}),
                       ("/plan/switch", {"plan": "label"}),
                       ("/account/reset", {"confirm": demo._email}),
                       ("/account/delete", {"confirm": demo._email})):
        r = demo.post(path, data=data)
        assert r.status_code == 302 and "demo=readonly" in r.headers["Location"], path
    with app_obj.app_context():
        u = store.get_user_by_email(demo._email)
        assert u is not None and u["plan"] == "pro" and u["name"] == "Locked Demo"

    r = demo.post("/team/invite", data={"email": "x@example.net", "role": "manager"},
                  headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 403 and r.get_json()["ok"] is False
    assert "read only" in r.get_json()["error"]
    r = demo.post("/team/invite", json={"email": "x@example.net", "role": "manager"})
    assert r.status_code == 403 and r.get_json()["demo"] == "readonly"


def test_the_way_out_stays_open_and_unlocking_restores_writes(world):
    app_obj, owner, demo = world
    owner.post("/admin/demo-lock", data={"email": demo._email, "action": "lock"})
    r = demo.post("/logout")
    assert r.status_code == 302 and "demo=readonly" not in r.headers["Location"]
    again = app_obj.test_client()
    r = again.post("/login", data={"email": demo._email, "password": PW})
    assert r.status_code == 302 and "/login" not in r.headers["Location"]
    assert "demo=readonly" in _upload(again).headers["Location"], "a fresh sign-in is still locked"
    r = owner.post("/admin/demo-lock", data={"email": demo._email, "action": "unlock"})
    assert "demo_lock=unlocked" in r.headers["Location"]
    assert _upload(again).status_code == 302
    assert _statements(app_obj, demo._email) == 1
    assert "shared demo account" not in again.get("/statements").get_data(as_text=True)


def test_the_sample_pages_and_billing_leave_the_locked_menu(world):
    app_obj, owner, demo = world
    hidden = hubs.demo_hidden_keys()
    assert "billing" in hidden and hidden - {"billing"}, "the Sample pages are in the set"
    hrefs = {}
    for _h, _n, _t, items in hubs.nav_hubs():
        for key, href, _i, _l, _d in items:
            hrefs[key] = href
    for _g, items in (hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        for key, href, _i, _l, _d in items:
            hrefs[key] = href
    before = demo.get("/command-center").get_data(as_text=True)
    assert 'href="/billing"' in before
    owner.post("/admin/demo-lock", data={"email": demo._email, "action": "lock"})
    after = demo.get("/command-center").get_data(as_text=True)
    aside = after.split("</aside>")[0]
    for key in hidden:
        if key in hrefs:
            assert 'href="%s"' % hrefs[key] not in aside, key
    assert 'href="/statements"' in aside and 'href="/royalties"' in aside
    assert demo.get("/billing").status_code == 200, "reachable, just not offered"
    # the owner's own menu is untouched
    assert 'href="/billing"' in owner.get("/command-center").get_data(as_text=True).split("</aside>")[0]
