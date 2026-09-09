# -*- coding: utf-8 -*-
"""Removing an EPK asset actually removes it.

The press kit could upload an asset, replace it, and hide it - and that
was all. `visibility` only clears the `public` flag, so an artist who
wanted a press photo gone got a row that stayed in `epk_assets` and a
file that stayed in the uploads directory for good. "Hidden" is not
"gone", and for a photograph of a person that difference is the whole
point.

What has to hold now: an uploaded asset and its file both disappear; a
Vault-backed asset gives up its EPK slot and nothing else, because that
file is the Vault's and the Vault still lists it; deleting an empty slot
is a success, not an error; the control is only offered when there is
something to remove, and it says what it will destroy before it does.
"""
import io
import os
import re
import uuid

import pytest

import db as store
from app import create_app

PASSWORD = "epk-delete-123"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _uploads_dir():
    """Where the app writes: beside the database, as create_app computes it."""
    return os.path.join(os.path.dirname(store.db_path()), "uploads")


def _disk(path):
    return os.path.join(_uploads_dir(), os.path.basename(path))


@pytest.fixture
def artist():
    """A real account of its own.

    Not the demo login: the suite shares one database, and the demo
    account's EPK assets are asserted on elsewhere.
    """
    app_obj = create_app()
    client = app_obj.test_client()
    email = "epkdel-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Delta Rue", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    uid = store.get_user_by_email(email)["id"]
    client.get("/epk")                       # mints the public slug
    return {"app": app_obj, "client": client, "uid": uid,
            "slug": store.get_epk(uid)["slug"]}


def _remove_button(page, kind):
    """The rendered Remove control for one slot, or "".

    Scoped to the element on purpose: the class name and both
    confirmation strings also appear in the page's own script, which
    builds the control for a slot filled without a reload. A bare `in
    page` would pass on the script alone and prove nothing about what
    the artist can actually click.
    """
    m = re.search(r'<button[^>]*class="asset-remove[^>]*data-kind="%s"[^>]*>' % kind,
                  page)
    return m.group(0) if m else ""


def _upload(client, kind="press_photo", name="shot.png"):
    r = client.post("/epk/asset/" + kind,
                    data={"asset": (io.BytesIO(PNG), name)},
                    content_type="multipart/form-data")
    assert r.get_json()["ok"]
    return r.get_json()["path"]


# --- the row and the file --------------------------------------------------------

def test_deleting_an_uploaded_asset_leaves_no_row_and_no_file(artist):
    path = _upload(artist["client"])
    assert os.path.exists(_disk(path))
    assert any(a["kind"] == "press_photo"
               for a in store.get_epk_assets(artist["uid"]))

    body = artist["client"].post("/epk/asset/press_photo/delete").get_json()

    assert body["ok"] and body["removed"]
    assert not any(a["kind"] == "press_photo"
                   for a in store.get_epk_assets(artist["uid"]))
    assert not os.path.exists(_disk(path))


def test_a_vault_backed_asset_gives_up_the_slot_and_nothing_else(artist):
    """`from-vault` points the slot at a file the Vault owns and still
    lists. Clearing the slot must not reach into the Vault - the same
    rule /vault/<id>/delete follows in the other direction, where it only
    unlinks names it recognises as its own."""
    client = artist["client"]
    client.post("/vault/upload",
                data={"file": (io.BytesIO(PNG), "vaultshot.png"),
                      "kind": "press_photo", "label": "Vault shot"},
                content_type="multipart/form-data")
    vid = store.list_vault_files(artist["uid"])[0]["id"]
    ok = client.post("/epk/asset/live_photo/from-vault",
                     json={"vault_id": vid}).get_json()
    assert ok["ok"]
    vpath = ok["path"]
    assert os.path.exists(_disk(vpath))

    assert client.post("/epk/asset/live_photo/delete").get_json()["ok"]

    assert not any(a["kind"] == "live_photo"
                   for a in store.get_epk_assets(artist["uid"]))
    assert os.path.exists(_disk(vpath))                    # still on disk
    assert any(v["id"] == vid                              # still in the Vault
               for v in store.list_vault_files(artist["uid"]))


def test_deleting_a_slot_that_holds_nothing_is_a_successful_no_op(artist):
    body = artist["client"].post("/epk/asset/cover_art/delete")
    assert body.status_code == 200
    assert body.get_json() == {"ok": True, "removed": False, "file": False}


def test_an_unknown_kind_is_refused(artist):
    assert artist["client"].post("/epk/asset/nonsense/delete").status_code == 400


def test_a_stranger_cannot_delete_anything(artist):
    anon = artist["app"].test_client()
    assert anon.post("/epk/asset/press_photo/delete").status_code == 401
    assert anon.post("/epk/photo/delete").status_code == 401


# --- the control itself ----------------------------------------------------------

def test_the_remove_control_appears_only_once_there_is_something_to_remove(artist):
    client = artist["client"]
    page = client.get("/epk").get_data(as_text=True)
    assert _remove_button(page, "logo") == ""

    _upload(client, "logo", "logo.png")
    btn = _remove_button(client.get("/epk").get_data(as_text=True), "logo")
    assert btn
    # It names what goes, before it goes.
    assert "onclick=\"return confirm('Remove the Logo? The file is deleted.')\"" in btn
    assert "sb-btn-danger" in btn

    client.post("/epk/asset/logo/delete")
    assert _remove_button(client.get("/epk").get_data(as_text=True), "logo") == ""


def test_the_vault_backed_control_does_not_promise_to_delete_the_vault_copy(artist):
    client = artist["client"]
    client.post("/vault/upload",
                data={"file": (io.BytesIO(PNG), "vshot.png"),
                      "kind": "press_photo", "label": "V"},
                content_type="multipart/form-data")
    vid = store.list_vault_files(artist["uid"])[0]["id"]
    client.post("/epk/asset/cover_art/from-vault", json={"vault_id": vid})
    btn = _remove_button(client.get("/epk").get_data(as_text=True), "cover_art")
    assert "The Vault copy stays." in btn
    assert "The file is deleted." not in btn


def test_the_public_kit_stops_showing_a_removed_asset(artist):
    client = artist["client"]
    _upload(client, "logo", "logo.png")
    slug = artist["slug"]
    anon = artist["app"].test_client()
    public = anon.get("/epk/" + slug).get_data(as_text=True)
    assert "Logo" in public

    client.post("/epk/asset/logo/delete")

    public = anon.get("/epk/" + slug).get_data(as_text=True)
    assert "Logo" not in public
    # And the press-kit ZIP has nothing left to bundle.
    assert anon.get("/epk/%s/kit.zip" % slug).status_code == 404


# --- the artist photo ------------------------------------------------------------

def test_the_artist_photo_can_be_removed_row_and_file(artist):
    client = artist["client"]
    r = client.post("/epk/photo", data={"photo": (io.BytesIO(PNG), "me.png")},
                    content_type="multipart/form-data")
    photo = r.get_json()["photo"]
    assert os.path.exists(_disk(photo))
    page = client.get("/epk").get_data(as_text=True)
    btn = re.search(r'<button[^>]*id="photo-remove"[^>]*>', page).group(0)
    assert ("onclick=\"return confirm('Remove the artist photo? "
            "The file is deleted.')\"" in btn)
    assert "sb-btn-danger" in btn

    body = client.post("/epk/photo/delete").get_json()

    assert body["ok"] and body["removed"]
    assert store.get_epk(artist["uid"])["photo"] in (None, "")
    assert not os.path.exists(_disk(photo))
    # The slot shows its empty state again, and offers nothing to remove.
    page = client.get("/epk").get_data(as_text=True)
    assert re.search(r'<button[^>]*id="photo-remove"[^>]*>', page) is None
    assert 'id="epk-photo-fallback"' in page


def test_removing_a_photo_that_was_never_set_is_a_no_op(artist):
    body = artist["client"].post("/epk/photo/delete")
    assert body.status_code == 200
    assert body.get_json() == {"ok": True, "removed": False, "file": False}
