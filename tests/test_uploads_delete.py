# -*- coding: utf-8 -*-
"""Four more places that could write a file and never take it back.

The press kit's missing delete was the one the owner noticed. It was not
the only one. Every route below wrote into the uploads directory and
offered no way out, so the disk only ever grew:

  * Cover Studio - `/artwork/upload` and `/artwork/save` write a file per
    try and record nothing. Nothing listed them, so every second idea
    orphaned the first one permanently.
  * Campaign cover art - `_ml_cover_upload` names each file with a fresh
    UUID, so REPLACING a cover left the old one on the disk with nothing
    pointing at it, and there was no control that cleared the cover.
  * Sync clearance packs - up to three audio files per pack, and no
    delete on the packs page at all.
  * Track lockbox - `/tracks/<id>/delete` removes a whole track, but one
    wrongly-attached document could not be removed on its own.

Each fix copies the shape of the EPK one, including the rule it borrowed
from `/vault/<id>/delete`: a stored file is unlinked only when its
basename matches the pattern that route itself writes, so a file shared
with the Vault loses its reference and keeps its bytes.

The controls are asserted against the extracted button element, never
against the whole page: the class names and the confirmation strings also
appear in page scripts, and `in page` would pass on the script alone.
"""
import io
import os
import re
import uuid

import pytest

import db as store
import links_store as mls
from app import create_app

PASSWORD = "uploads-delete-123"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
MP3 = b"ID3\x03\x00\x00\x00" + b"0" * 128


def _uploads_dir():
    """Where the app writes: beside the database, as create_app computes it."""
    return os.path.join(os.path.dirname(store.db_path()), "uploads")


def _disk(path):
    return os.path.join(_uploads_dir(), os.path.basename(path))


def _account(app_obj, tag):
    """A real account of its own.

    Not the demo login: the suite shares one database and the demo
    account's rows are asserted on elsewhere.
    """
    client = app_obj.test_client()
    email = "%s-%s@example.net" % (tag, uuid.uuid4().hex[:10])
    client.post("/signup", data={"name": "Rue Delta", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return {"client": client, "uid": store.get_user_by_email(email)["id"],
            "email": email}


@pytest.fixture
def app_obj():
    return create_app()


@pytest.fixture
def artist(app_obj):
    return _account(app_obj, "updel")


@pytest.fixture
def stranger(app_obj):
    """A second signed-in account. Not a logged-out client: the question
    is whether being signed in as SOMEBODY is enough to reach another
    artist's file, which a 401 would never test."""
    return _account(app_obj, "updel-other")


def _empty_state(page):
    """The studio's empty-state paragraph as rendered. It is always in the
    markup and carries `hidden` when there is something to list, so the
    element - not the page - is what says which state is on screen."""
    m = re.search(r'<p id="art-uploads-empty"[^>]*>', page)
    return m.group(0) if m else ""


def _button(page, cls, attr=""):
    """One rendered control, or "". Scoped to the element on purpose."""
    m = re.search(r'<button[^>]*class="[^"]*%s[^>]*%s[^>]*>' % (cls, attr), page)
    return m.group(0) if m else ""


# =========================================================================
# 1 - Cover Studio uploads
# =========================================================================

def _art_upload(client, name="idea.png"):
    r = client.post("/artwork/upload",
                    data={"art": (io.BytesIO(PNG), name)},
                    content_type="multipart/form-data")
    assert r.get_json()["ok"]
    return r.get_json()["path"]


def test_a_studio_upload_can_be_taken_back_off_the_disk(artist):
    path = _art_upload(artist["client"])
    assert os.path.exists(_disk(path))

    body = artist["client"].post("/artwork/upload/delete",
                                 json={"name": os.path.basename(path)}).get_json()

    assert body == {"ok": True, "removed": True, "file": True}
    assert not os.path.exists(_disk(path))
    # And the studio no longer lists it.
    page = artist["client"].get("/artwork").get_data(as_text=True)
    assert os.path.basename(path) not in page


def test_the_finished_cover_in_the_vault_is_not_the_studios_to_delete(artist):
    """"Save cover to uploads" posts to /vault/upload, which writes
    `vault_<user>_<ms>` - a file the Vault owns and lists. The studio must
    neither offer it nor be able to reach it."""
    client = artist["client"]
    client.post("/vault/upload",
                data={"file": (io.BytesIO(PNG), "final-cover.png"),
                      "kind": "cover_art", "label": "Final cover"},
                content_type="multipart/form-data")
    vault = store.list_vault_files(artist["uid"])[0]
    assert os.path.exists(_disk(vault["path"]))

    page = client.get("/artwork").get_data(as_text=True)
    assert os.path.basename(vault["path"]) not in page
    # Named directly it is not addressable either.
    assert client.post("/artwork/upload/delete",
                       json={"name": os.path.basename(vault["path"])}).status_code == 404
    assert os.path.exists(_disk(vault["path"]))
    assert store.list_vault_files(artist["uid"])            # still listed


def test_deleting_a_studio_file_that_is_already_gone_is_a_successful_no_op(artist):
    path = _art_upload(artist["client"])
    name = os.path.basename(path)
    artist["client"].post("/artwork/upload/delete", json={"name": name})

    again = artist["client"].post("/artwork/upload/delete", json={"name": name})

    assert again.status_code == 200
    assert again.get_json() == {"ok": True, "removed": False, "file": False}


def test_a_stranger_cannot_delete_another_artists_studio_file(artist, stranger):
    path = _art_upload(artist["client"])

    r = stranger["client"].post("/artwork/upload/delete",
                                json={"name": os.path.basename(path)})

    # 404, not a 403 that would confirm the file exists and belongs to
    # somebody. The name simply does not resolve for this account.
    assert r.status_code == 404
    assert os.path.exists(_disk(path))


def test_the_studio_control_appears_only_once_a_file_is_stored(artist):
    client = artist["client"]
    page = client.get("/artwork").get_data(as_text=True)
    assert _button(page, "art-upload-remove") == ""
    assert "hidden" not in _empty_state(page)          # the empty state is showing

    path = _art_upload(client)
    btn = _button(client.get("/artwork").get_data(as_text=True), "art-upload-remove")
    assert btn
    assert "sb-btn-danger" in btn
    # It names the file that goes, and what else it costs.
    assert "return confirm('Delete %s? The file is deleted." % os.path.basename(path) in btn

    client.post("/artwork/upload/delete", json={"name": os.path.basename(path)})
    page = client.get("/artwork").get_data(as_text=True)
    assert _button(page, "art-upload-remove") == ""
    assert "Nothing saved from this studio yet." in page


# =========================================================================
# 2 - Campaign cover art
# =========================================================================

def _campaign(client, title="Cover Campaign", cover=True):
    data = {"title": title}
    if cover:
        data["cover_file"] = (io.BytesIO(PNG), "cover.png")
    r = client.post("/links/new", data=data, content_type="multipart/form-data")
    return r.headers["Location"].split("/")[2]


def test_replacing_a_campaign_cover_removes_the_file_it_replaced(artist):
    """Every _ml_cover_upload writes a fresh UUID name, so before this the
    replaced file stayed on the disk with nothing referencing it - a new
    orphan for every re-upload."""
    client = artist["client"]
    cid = _campaign(client)
    first = mls.get_campaign(cid)["cover_url"]
    assert os.path.basename(first).startswith("mlcover_")
    assert os.path.exists(_disk(first))

    client.post("/links/%s/edit" % cid,
                data={"title": "Cover Campaign",
                      "cover_file": (io.BytesIO(PNG), "new-cover.png")},
                content_type="multipart/form-data")

    second = mls.get_campaign(cid)["cover_url"]
    assert second != first
    assert os.path.exists(_disk(second))
    assert not os.path.exists(_disk(first))


def test_a_campaign_cover_can_be_cleared_back_to_empty(artist):
    client = artist["client"]
    cid = _campaign(client)
    cover = mls.get_campaign(cid)["cover_url"]

    client.post("/links/%s/cover/delete" % cid)

    assert mls.get_campaign(cid)["cover_url"] == ""
    assert not os.path.exists(_disk(cover))


def test_a_vault_cover_loses_the_reference_and_keeps_its_bytes(artist):
    """A campaign can point at a file it does not own - a Vault image, a
    Cover Studio file, a pasted URL. Clearing the field must not reach
    into any of them."""
    client = artist["client"]
    client.post("/vault/upload",
                data={"file": (io.BytesIO(PNG), "art.png"),
                      "kind": "cover_art", "label": "Art"},
                content_type="multipart/form-data")
    vault = store.list_vault_files(artist["uid"])[0]
    cid = _campaign(client, cover=False)
    client.post("/links/%s/edit" % cid,
                data={"title": "Cover Campaign", "cover_url": vault["path"]})
    assert mls.get_campaign(cid)["cover_url"] == vault["path"]

    client.post("/links/%s/cover/delete" % cid)

    assert mls.get_campaign(cid)["cover_url"] == ""
    assert os.path.exists(_disk(vault["path"]))             # still on disk
    assert any(v["id"] == vault["id"]                       # still in the Vault
               for v in store.list_vault_files(artist["uid"]))


def test_clearing_a_campaign_that_has_no_cover_is_a_successful_no_op(artist):
    cid = _campaign(artist["client"], cover=False)
    assert mls.get_campaign(cid)["cover_url"] == ""

    r = artist["client"].post("/links/%s/cover/delete" % cid)

    assert r.status_code == 302
    assert mls.get_campaign(cid)["cover_url"] == ""


def test_a_stranger_cannot_clear_another_artists_cover(artist, stranger):
    cid = _campaign(artist["client"])
    cover = mls.get_campaign(cid)["cover_url"]

    r = stranger["client"].post("/links/%s/cover/delete" % cid)

    assert r.status_code == 404
    assert mls.get_campaign(cid)["cover_url"] == cover
    assert os.path.exists(_disk(cover))


def test_the_cover_control_appears_only_once_a_cover_is_stored(artist):
    client = artist["client"]
    cid = _campaign(client, cover=False)
    page = client.get("/links/%s/edit" % cid).get_data(as_text=True)
    assert _button(page, "ml-cover-remove") == ""

    client.post("/links/%s/edit" % cid,
                data={"title": "Cover Campaign",
                      "cover_file": (io.BytesIO(PNG), "c.png")},
                content_type="multipart/form-data")
    btn = _button(client.get("/links/%s/edit" % cid).get_data(as_text=True),
                  "ml-cover-remove")
    assert btn
    assert "sb-btn-danger" in btn
    assert "onclick=\"return confirm('Remove the cover art? The file is deleted.')\"" in btn

    client.post("/links/%s/cover/delete" % cid)
    assert _button(client.get("/links/%s/edit" % cid).get_data(as_text=True),
                   "ml-cover-remove") == ""


def test_a_borrowed_cover_does_not_promise_to_delete_the_vault_copy(artist):
    client = artist["client"]
    client.post("/vault/upload",
                data={"file": (io.BytesIO(PNG), "borrowed.png"),
                      "kind": "cover_art", "label": "Borrowed"},
                content_type="multipart/form-data")
    vault = store.list_vault_files(artist["uid"])[0]
    cid = _campaign(client, cover=False)
    client.post("/links/%s/edit" % cid,
                data={"title": "Cover Campaign", "cover_url": vault["path"]})

    btn = _button(client.get("/links/%s/edit" % cid).get_data(as_text=True),
                  "ml-cover-remove")

    assert "the Vault copy stays." in btn
    assert "The file is deleted." not in btn
