"""Report this post on the Collab Marketplace (owner-approved, 2026-09-19).

The rules the button was built under:
  * only a signed-in member can report, and never their own post;
  * one report per member per post, a repeat press is ignored;
  * the report reaches the owners as a notification of its own kind;
  * the page says "Reported. The Street Banker team will look at it."
"""
import uuid

import pytest

import db as store
from app import create_app


def _member(app_obj, name="Member"):
    client = app_obj.test_client()
    email = "rp%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": name, "email": email,
                                 "password": "secret123"})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "label")
    return client, uid, email


def _reports_for(owner_uid, rid):
    return [n for n in store.list_notifications(owner_uid, 200)
            if n["kind"] == "report" and rid in (n.get("link") or "")]


@pytest.fixture()
def app_obj():
    return create_app()


def test_a_member_reports_a_post_once_and_the_owners_hear_of_it(app_obj, monkeypatch):
    _owner, owner_uid, owner_email = _member(app_obj, "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner_email)
    poster, puid, _ = _member(app_obj, "Poster")
    poster.post("/marketplace/post", data={
        "kind": "split", "role": "Producer", "title": "Report check"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    me, uid, _ = _member(app_obj, "Reporter")

    # The opened brief offers the button to somebody else's post.
    body = me.get("/marketplace?brief=%s" % rid).get_data(as_text=True)
    assert "/marketplace/%s/report" % rid in body and "Report this post" in body

    r = me.post("/marketplace/%s/report" % rid,
                data={"back": "/marketplace?brief=%s#brief" % rid})
    assert r.status_code == 302
    assert r.headers["Location"].endswith(
        "/marketplace?brief=%s&reported=1#brief" % rid)
    notes = _reports_for(owner_uid, rid)
    assert len(notes) == 1
    assert "Report check" in notes[0]["body"] and "Reporter" in notes[0]["body"]

    # Back on the brief: the button has become the confirmation.
    body = me.get("/marketplace?brief=%s&reported=1" % rid).get_data(as_text=True)
    assert "Reported. The Street Banker team will look at it." in body
    assert "/marketplace/%s/report" % rid not in body

    # A repeat press is ignored: still one report, still one notification.
    me.post("/marketplace/%s/report" % rid)
    assert len(_reports_for(owner_uid, rid)) == 1
    assert store.get_kv("collab_report:%s:%s" % (rid, uid)) is not None


def test_your_own_post_cannot_be_reported(app_obj, monkeypatch):
    _owner, owner_uid, owner_email = _member(app_obj, "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner_email)
    poster, puid, _ = _member(app_obj, "Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Vocalist", "title": "My own post"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    body = poster.get("/marketplace?brief=%s" % rid).get_data(as_text=True)
    assert "Report this post" not in body
    r = poster.post("/marketplace/%s/report" % rid)
    assert r.status_code == 302
    assert _reports_for(owner_uid, rid) == []
    assert store.get_kv("collab_report:%s:%s" % (rid, puid)) is None


def test_signed_out_and_unknown_posts_report_nothing(app_obj, monkeypatch):
    _owner, owner_uid, owner_email = _member(app_obj, "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner_email)
    poster, puid, _ = _member(app_obj, "Poster")
    poster.post("/marketplace/post", data={
        "kind": "fun", "role": "Producer", "title": "Anon check"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    anon = app_obj.test_client()
    r = anon.post("/marketplace/%s/report" % rid)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert _reports_for(owner_uid, rid) == []
    me, _uid, _ = _member(app_obj, "Reporter")
    r = me.post("/marketplace/no-such-post/report")
    assert r.status_code == 302 and r.headers["Location"].endswith("/marketplace")
    assert not [n for n in store.list_notifications(owner_uid, 200)
                if n["kind"] == "report"]
