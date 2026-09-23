"""A signing link, and the contract behind it, close together.

Found by the make-it-real pass of 2026-09-23: /sign/<token>/document
served the lockbox contract to anyone holding the link long after the
link was used. The signing page checked `used` before taking a decision;
the document route never read it. Split sheets and producer agreements
are private contracts, so a link that has done its job must stop
handing one out.

One rule now answers for both routes (app.py _sign_link):

  * a token nobody minted, or whose track or lockbox slot is gone, is
    not valid
  * a token the artist has since replaced, by resending the request or
    asking the same person again, is not valid either: the newest link
    is the live one, and an old one can no longer flip a decision
  * a token that has recorded a decision shows that decision, and no
    document
  * only a live, undecided link shows the document and takes a decision
"""
import io
import os
import uuid

import pytest

import app as appmod
import db as store

PW = "sign-link-pw-1234"
SLOT = "producer_agreement"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _uploads_dir():
    d = os.path.join(os.path.dirname(store.db_path()), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass  # Windows keeps a served file open a moment; the dir is temporary


@pytest.fixture
def world():
    email = "sign-%s@example.net" % uuid.uuid4().hex[:8]
    owner = appmod.app.test_client()
    owner.post("/signup", data={"name": "Signing Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "label")
    owner.post("/login", data={"email": email, "password": PW})
    title = "Hellhounds %s" % uuid.uuid4().hex[:6]
    owner.post("/tracks/add", data={"title": title})
    track = next(t for t in store.list_os_tracks(uid) if t["title"] == title)
    marker = b"%PDF-1.4 producer agreement " + uuid.uuid4().hex.encode()
    owner.post("/tracks/%s/lockbox/%s" % (track["id"], SLOT),
               data={"action": "upload", "file": (io.BytesIO(marker), "producer.pdf")},
               content_type="multipart/form-data")
    owner.post("/tracks/%s/lockbox/%s" % (track["id"], SLOT),
               data={"action": "approver", "email": "producer@example.net", "name": "Prod"})
    path = store.get_os_track(uid, track["id"])["lockbox"][SLOT]["file"]
    w = {"owner": owner, "uid": uid, "track": track, "marker": marker,
         "anon": appmod.app.test_client()}
    yield w
    _remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))


def _approval(w, email="producer@example.net"):
    box = store.get_os_track(w["uid"], w["track"]["id"])["lockbox"][SLOT]
    return next(a for a in box["approvals"] if a["email"] == email)


def _newest_token(w):
    with store.get_db() as db:
        return db.execute(
            "SELECT token FROM sign_tokens WHERE user_id = ? AND track_id = ?"
            " ORDER BY rowid DESC LIMIT 1", (w["uid"], w["track"]["id"])).fetchone()["token"]


def _doc(w, token):
    r = w["anon"].get("/sign/%s/document" % token)
    body = r.data
    r.close()
    return r.status_code, body


def _page(w, token):
    return w["anon"].get("/sign/" + token).get_data(as_text=True)


def test_a_live_link_shows_the_document(world):
    token = _approval(world)["token"]
    assert "/sign/%s/document" % token in _page(world, token)
    assert _doc(world, token) == (200, world["marker"])


def test_the_document_is_refused_once_the_link_has_signed(world):
    token = _approval(world)["token"]
    world["anon"].post("/sign/" + token, data={"decision": "signed"})
    assert _approval(world)["state"] == "signed"
    status, body = _doc(world, token)
    assert status == 404, "a used link must stop handing out the contract"
    assert world["marker"] not in body
    page = _page(world, token)
    assert "Signed" in page
    assert "/sign/%s/document" % token not in page


def test_a_declined_link_says_declined_and_refuses_the_document(world):
    token = _approval(world)["token"]
    world["anon"].post("/sign/" + token, data={"decision": "declined"})
    assert _doc(world, token)[0] == 404
    page = _page(world, token)
    # It used to read "Signed" for every used link, whatever was decided.
    assert "Declined" in page and ">Signed<" not in page


def test_a_resent_request_retires_the_old_link(world):
    old = _approval(world)["token"]
    world["owner"].post("/tracks/%s/lockbox/%s" % (world["track"]["id"], SLOT),
                        data={"action": "resend", "email": "producer@example.net"})
    new = _approval(world)["token"]
    assert new != old
    assert _doc(world, old)[0] == 404
    assert "isn't valid anymore" in _page(world, old)
    # The old link can no longer record a decision.
    world["anon"].post("/sign/" + old, data={"decision": "declined"})
    assert _approval(world)["state"] == "pending"
    assert _doc(world, new) == (200, world["marker"])


def test_asking_the_same_person_again_makes_the_new_link_the_live_one(world):
    """Adding an approver who is already on the slot mints and emails a new
    link. It used to leave the approval on the old token, so the page's
    copy-the-link box and the email carried different links, both live."""
    old = _approval(world)["token"]
    world["owner"].post("/tracks/%s/lockbox/%s" % (world["track"]["id"], SLOT),
                        data={"action": "approver", "email": "producer@example.net",
                              "name": "Prod"})
    emailed = _newest_token(world)
    assert emailed != old
    assert _approval(world)["token"] == emailed, "the page shows the link that was sent"
    assert _doc(world, emailed) == (200, world["marker"])
    assert _doc(world, old)[0] == 404


def test_a_deleted_track_closes_the_link(world):
    token = _approval(world)["token"]
    world["owner"].post("/tracks/%s/delete" % world["track"]["id"])
    assert _doc(world, token)[0] == 404
    assert "isn't valid anymore" in _page(world, token)


def test_an_unknown_token_is_refused_on_both_routes(world):
    stranger = uuid.uuid4().hex
    assert _doc(world, stranger)[0] == 404
    assert "isn't valid anymore" in _page(world, stranger)
