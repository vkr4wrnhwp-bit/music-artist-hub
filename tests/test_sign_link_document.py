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
import artist_os
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


# --- The document a signature was given for (2026-09-23 review) ------------
#
# A signature is for one document. Replacing or removing the file in a slot
# used to leave every approval as it was: a split sheet signed at 50/50 and
# then swapped for 90/10 read "ready" and unlocked pitching, and a pending
# link kept taking a decision after its document was removed. Now any
# change of file sets every approval in the slot to "needs resend" and
# retires its link, so the new document is signed by someone who saw it.

def _upload(w, slot, body, name="doc.pdf"):
    r = w["owner"].post("/tracks/%s/lockbox/%s" % (w["track"]["id"], slot),
                        data={"action": "upload", "file": (io.BytesIO(body), name)},
                        content_type="multipart/form-data")
    assert r.status_code == 302


def _ask(w, slot, email, name="Signer"):
    w["owner"].post("/tracks/%s/lockbox/%s" % (w["track"]["id"], slot),
                    data={"action": "approver", "email": email, "name": name})
    box = store.get_os_track(w["uid"], w["track"]["id"])["lockbox"][slot]
    return next(a for a in box["approvals"] if a["email"] == email)


def _report(w):
    rep = artist_os.lockbox_report(store.get_os_track(w["uid"], w["track"]["id"]))
    return {d["key"]: d for d in rep["docs"]}, rep["caps"]


def _cleanup(w, slot):
    path = (store.get_os_track(w["uid"], w["track"]["id"])["lockbox"]
            .get(slot, {}).get("file") or "")
    if path:
        _remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))


def test_a_signature_does_not_carry_over_to_a_replaced_document(world):
    _upload(world, "split_sheet", b"%PDF-1.4 split 50/50 " + uuid.uuid4().hex.encode(), "split.pdf")
    token = _ask(world, "split_sheet", "cowriter@example.net")["token"]
    world["anon"].post("/sign/" + token, data={"decision": "signed"})
    docs, caps = _report(world)
    assert docs["split_sheet"]["state"] == "ready" and caps["pitch"]   # before the swap

    _cleanup(world, "split_sheet")
    _upload(world, "split_sheet", b"%PDF-1.4 split 90/10 " + uuid.uuid4().hex.encode(), "split.pdf")

    docs, caps = _report(world)
    assert docs["split_sheet"]["state"] != "ready", (
        "the new split sheet was never signed by anyone")
    assert caps["pitch"] is False
    approval = docs["split_sheet"]["approvals"][0]
    assert approval["state"] == "needs resend"
    assert not approval.get("token")
    assert "isn't valid anymore" in _page(world, token)
    assert _doc(world, token)[0] == 404
    # The track page offers to ask again, and a resend reopens it.
    world["owner"].post("/tracks/%s/lockbox/split_sheet" % world["track"]["id"],
                        data={"action": "resend", "email": "cowriter@example.net"})
    fresh = _report(world)[0]["split_sheet"]["approvals"][0]
    assert fresh["state"] == "pending" and fresh["token"] and fresh["token"] != token
    assert _doc(world, fresh["token"])[0] == 200
    _cleanup(world, "split_sheet")


def test_removing_the_document_closes_a_pending_link(world):
    token = _approval(world)["token"]
    world["owner"].post("/tracks/%s/lockbox/%s/delete" % (world["track"]["id"], SLOT))

    assert "isn't valid anymore" in _page(world, token)
    assert _doc(world, token)[0] == 404
    world["anon"].post("/sign/" + token, data={"decision": "signed"})
    assert _approval(world)["state"] == "needs resend", (
        "a link whose document was removed must not record a signature")

    # A new document goes to the same signer, who has not signed it.
    _upload(world, SLOT, b"%PDF-1.4 producer agreement v2")
    docs, _caps = _report(world)
    assert docs[SLOT]["state"] == "awaiting signatures"
    _cleanup(world, SLOT)


def test_a_decision_given_before_any_document_is_asked_again_once_one_arrives(world):
    """The signing page lets a signer decide before a file is attached. That
    decision was about no paper at all, so it does not sign the first
    document either. A link still pending when the first file lands stays
    live: its signer has decided nothing yet, and now sees the file."""
    early = _ask(world, "beat_license", "beats@example.net")["token"]
    pending = _ask(world, "beat_license", "waiting@example.net")["token"]
    world["anon"].post("/sign/" + early, data={"decision": "signed"})

    body = b"%PDF-1.4 beat licence " + uuid.uuid4().hex.encode()
    _upload(world, "beat_license", body, "beat.pdf")

    docs, _caps = _report(world)
    by_email = {a["email"]: a for a in docs["beat_license"]["approvals"]}
    assert by_email["beats@example.net"]["state"] == "needs resend"
    assert by_email["waiting@example.net"]["state"] == "pending"
    assert by_email["waiting@example.net"]["token"] == pending
    assert docs["beat_license"]["state"] == "awaiting signatures"
    assert _doc(world, pending) == (200, body)
    _cleanup(world, "beat_license")


# --- Links emailed before the deploy (2026-09-23 review, S2) ---------------
#
# Before this branch, asking the same person again minted and emailed a new
# link but left the approval on the old token. The live-link rule reads the
# approval's token, so on deploy the link in the newest email would have
# been refused while the older one stayed live. A start-up pass
# (db.align_sign_tokens) points each approval at its newest link.

def test_the_newest_emailed_link_stays_live_across_the_deploy(world):
    old = _approval(world)["token"]
    emailed = uuid.uuid4().hex
    # Exactly what the old "ask again" path left on disk: a newer row, and
    # the approval still on the old token.
    store.add_sign_token(emailed, world["uid"], world["track"]["id"], SLOT,
                         "producer@example.net")
    assert _approval(world)["token"] == old

    store.init_db()                                  # the deploy's start-up

    assert _approval(world)["token"] == emailed
    assert _doc(world, emailed) == (200, world["marker"])
    assert _doc(world, old)[0] == 404


def test_the_start_up_pass_leaves_a_retired_link_retired(world):
    """An approval set to "needs resend" has no token on purpose. The pass
    must not hand it one back from the old rows."""
    token = _approval(world)["token"]
    world["owner"].post("/tracks/%s/lockbox/%s/delete" % (world["track"]["id"], SLOT))
    store.init_db()
    assert not _approval(world).get("token")
    assert _doc(world, token)[0] == 404
