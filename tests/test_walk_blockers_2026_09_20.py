"""The blockers the 2026-09-20 page walk found, pinned.

Six read-only agents walked every page as a signed-in artist and a second
pass re-checked their findings. Three things could hurt a real account:
a Vault contract served to anyone with its address, a 500 on a sync pack
whose title somebody had already used, and "Switch to Fan" dropping a
paying subscriber's tier while Stripe kept billing them.
"""
import io
import os
import uuid

import pytest

import app as appmod
import db as store

PW = "walk-test-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _uploads_dir():
    d = os.path.join(os.path.dirname(store.db_path()), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _account(name="Walk Artist", plan="label"):
    email = "walk-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid, email


def _write_upload(fname, body):
    path = os.path.join(_uploads_dir(), fname)
    with open(path, "wb") as fh:
        fh.write(body)
    return path


def test_a_vault_document_is_served_only_to_its_owner():
    owner, uid, _ = _account()
    other, _uid2, _ = _account()
    fname = "doc_%s.pdf" % uuid.uuid4().hex
    path = _write_upload(fname, b"%PDF-1.4 walk")
    store.add_document(uid, "contract.pdf", "/uploads/" + fname, "Contract", "")
    try:
        anon = appmod.app.test_client().get("/uploads/" + fname)
        assert anon.status_code in (302, 303) and "/login" in anon.headers["Location"]
        assert other.get("/uploads/" + fname).status_code == 404
        r = owner.get("/uploads/" + fname)
        assert r.status_code == 200 and r.data.startswith(b"%PDF")
        r.close()
        # A document name nobody holds is a 404 even for a signed-in account.
        assert owner.get("/uploads/doc_%s.pdf" % uuid.uuid4().hex).status_code == 404
    finally:
        try:
            os.remove(path)
        except OSError:
            pass  # Windows keeps a served file open a moment; the dir is temporary


def test_public_uploads_stay_public():
    """Press photos, cover art, link images and sync audio are public by
    design; only documents are gated."""
    fname = "epk_%s.txt" % uuid.uuid4().hex
    path = _write_upload(fname, b"press photo stand-in")
    try:
        assert appmod.app.test_client().get("/uploads/" + fname).status_code == 200
    finally:
        try:
            os.remove(path)
        except OSError:
            pass  # Windows keeps a served file open a moment; the dir is temporary


def _pack(client, title):
    return client.post("/sync/clearance-packs", data={
        "title": title, "main_audio": (io.BytesIO(b"ID3fake"), "t.mp3")},
        content_type="multipart/form-data")


def test_two_sync_packs_with_the_same_title_both_exist():
    c, uid, _ = _account()
    assert _pack(c, "Same Title").status_code == 302
    assert _pack(c, "Same Title").status_code == 302
    packs = store.list_sync_packs(uid)
    assert len(packs) == 2
    assert len({p["slug"] for p in packs}) == 2
    # Another account using the same title is fine too.
    c2, uid2, _ = _account()
    assert _pack(c2, "Same Title").status_code == 302
    assert len(store.list_sync_packs(uid2)) == 1


def test_a_paying_subscriber_cannot_drop_to_fan_from_the_upgrade_page(monkeypatch):
    monkeypatch.setenv("RENDER", "1")
    c, uid, email = _account(plan="pro")
    store.set_stripe_ids(uid, "cus_walk", "sub_walk")
    r = c.post("/plan/switch", data={"plan": "fan"})
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/billing")
    assert store.get_user_by_email(email)["plan"] == "pro"


def test_an_account_without_a_subscription_can_still_step_down():
    c, uid, email = _account(plan="pro")
    r = c.post("/plan/switch", data={"plan": "fan"})
    assert r.status_code in (302, 303)
    assert store.get_user_by_email(email)["plan"] == "fan"
