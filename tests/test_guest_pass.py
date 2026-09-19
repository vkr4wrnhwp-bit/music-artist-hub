"""Guest passes and the owner's lock.

Owner, 2026-09-17: an account given Label access uses every tool, "but i want
the accounts to disappear after 72 hrs", then: "don't delete it. Just shut it
off... and give me the ability still to lock them and unlock them." So a
guest pass shuts the account off 72 hours after it is made, the owner can
lock and unlock any account, and nothing here deletes anything.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import app as appmod
import db as store

PW = "guest-pass-pass-1"


def _addr(tag):
    return "%s-%s@example.net" % (tag, uuid.uuid4().hex[:8])


def _owner(monkeypatch):
    email = _addr("owner")
    monkeypatch.setenv("SIGNUP_MODE", "open")
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Owner", "email": email, "password": PW})
    monkeypatch.setenv("OWNER_EMAILS", email)
    c.post("/login", data={"email": email, "password": PW})
    return c


def _guest(owner, monkeypatch, guest=True):
    email = _addr("guest")
    data = {"email": email, "plan": "label"}
    if guest:
        data["guest"] = "1"
    owner.post("/admin/invite", data=data)
    token = [i for i in store.list_signup_invites() if i["email"] == email][0]["token"]
    c = appmod.app.test_client()
    r = c.post("/signup", data={"name": "Guest", "email": email, "password": PW, "invite": token})
    assert r.status_code == 302
    return c, store.get_user_by_email(email)


def test_a_guest_pass_gets_label_and_seventy_two_hours_from_arrival(monkeypatch):
    owner = _owner(monkeypatch)
    c, user = _guest(owner, monkeypatch)
    assert user["plan"] == "label"
    ends = datetime.fromisoformat(user["access_ends"])
    left = ends - datetime.now(timezone.utc)
    assert timedelta(hours=71, minutes=55) < left <= timedelta(hours=72)
    assert c.get("/command-center").status_code == 200
    # An ordinary invitation has no end.
    _, plain = _guest(owner, monkeypatch, guest=False)
    assert plain["access_ends"] is None


def test_when_the_pass_runs_out_the_account_is_shut_off_not_deleted(monkeypatch):
    owner = _owner(monkeypatch)
    c, user = _guest(owner, monkeypatch)
    c.post("/links/new", data={"title": "Kept"})          # whatever they made stays
    store.set_access_ends(user["id"], (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds"))
    r = c.get("/command-center")
    assert r.status_code == 302 and "/login" in r.headers["Location"], "the open session ends on its next request"
    r = c.post("/login", data={"email": user["email"], "password": PW})
    assert "Your guest access has ended" in r.get_data(as_text=True)
    assert c.get("/suites/go/the-room").status_code == 302 and "/login" in c.get("/suites/go/the-room").headers["Location"]
    assert store.get_user(user["id"]) is not None, "shut off, never deleted"
    # The owner gives it 72 more hours and it opens again.
    owner.post("/admin/account", data={"user_id": user["id"], "action": "extend"})
    assert c.post("/login", data={"email": user["email"], "password": PW}).status_code == 302
    assert c.get("/command-center").status_code == 200
    owner.post("/admin/account", data={"user_id": user["id"], "action": "permanent"})
    assert store.get_user(user["id"])["access_ends"] is None


def test_the_owner_locks_and_unlocks_any_account(monkeypatch):
    owner = _owner(monkeypatch)
    c, user = _guest(owner, monkeypatch, guest=False)
    owner.post("/admin/account", data={"user_id": user["id"], "action": "lock"})
    assert c.get("/command-center").status_code == 302
    assert "This account is locked" in c.post("/login", data={"email": user["email"], "password": PW}).get_data(as_text=True)
    page = owner.get("/settings").get_data(as_text=True)
    assert user["email"] in page and ">Locked<" in page and 'value="unlock"' in page
    owner.post("/admin/account", data={"user_id": user["id"], "action": "unlock"})
    assert c.post("/login", data={"email": user["email"], "password": PW}).status_code == 302
    assert c.get("/command-center").status_code == 200


def test_only_the_owner_holds_the_door_and_never_against_themselves(monkeypatch):
    owner = _owner(monkeypatch)
    c, user = _guest(owner, monkeypatch, guest=False)
    assert c.post("/admin/account", data={"user_id": user["id"], "action": "lock"}).status_code == 404
    assert not store.get_user(user["id"])["locked"]
    me = store.get_user_by_email(re.search(r"owner-[0-9a-f]+@example\.net", owner.get("/settings").get_data(as_text=True)).group(0))
    owner.post("/admin/account", data={"user_id": me["id"], "action": "lock"})
    assert not store.get_user(me["id"])["locked"], "the owner cannot lock themselves out"
