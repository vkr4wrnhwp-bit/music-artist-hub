"""Three more things that could be created and never removed.

Listing every POST route that creates something against every POST
route that removes something (2026-09-12) left three resources with no
way out: disputes (four statuses, no removal), rollouts (new, generate,
plan - never delete) and Operator Desk files (upload, download, and
that was all). Each can be removed now, by whoever may create it, and
by nobody else.
"""
import io
import uuid

import pytest

import db as store
import desk_store
import operator_desk
import rollout_store as ros
from app import create_app

PW = "round-two-12345"


def _artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "r2-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "R", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


# --- disputes -----------------------------------------------------------------

def test_a_dispute_can_be_removed_by_its_owner_only():
    artist = _artist()
    with artist._app.app_context():
        did = store.add_dispute(artist._uid, "Spotify", "missing payment", "May statement short", 120.0)
    body = artist.get("/disputes").get_data(as_text=True)
    assert "/disputes/%s/delete" % did in body

    stranger = _artist()
    stranger.post("/disputes/%s/delete" % did)
    with artist._app.app_context():
        assert [d["id"] for d in store.list_disputes(artist._uid)] == [did]

    r = artist.post("/disputes/%s/delete" % did)
    assert r.status_code == 302
    with artist._app.app_context():
        assert store.list_disputes(artist._uid) == []


# --- rollouts -----------------------------------------------------------------

def test_a_rollout_takes_its_posts_and_assets_with_it():
    artist = _artist()
    with artist._app.app_context():
        cid = ros.create_campaign(artist._uid, {"title": "Gone Rollout", "artist_name": "R"})
        ros.add_asset(cid, "lyrics", lyrics_text="words")
    body = artist.get("/rollout-studio/%s" % cid).get_data(as_text=True)
    assert "Delete rollout" in body and "/rollout-studio/%s/delete" % cid in body

    stranger = _artist()
    assert stranger.post("/rollout-studio/%s/delete" % cid).status_code == 404
    with artist._app.app_context():
        assert ros.get_campaign(cid, artist._uid) is not None

    r = artist.post("/rollout-studio/%s/delete" % cid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/rollout-studio")
    with artist._app.app_context():
        assert ros.get_campaign(cid, artist._uid) is None
        assert ros.list_assets(cid) == []
    assert "Gone Rollout" not in artist.get("/rollout-studio").get_data(as_text=True)


# --- operator desk files ------------------------------------------------------

@pytest.fixture
def desk_owner(monkeypatch):
    app_obj = create_app()
    email = "desk-r2-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setattr(operator_desk, "_is_owner_email", lambda e: e == email)
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Desk Owner", "email": email, "password": PW})
    client.post("/login", data={"email": email, "password": PW})
    client._app = app_obj
    return client


def test_a_desk_file_can_be_removed_and_stops_downloading(desk_owner):
    r = desk_owner.post("/operator-desk/files/upload",
                        data={"file": (io.BytesIO(b"%PDF-1.4 hello"), "contract.pdf"),
                              "category": "Other"},
                        content_type="multipart/form-data")
    assert r.status_code == 302
    files = desk_owner.get("/operator-desk/files").get_data(as_text=True)
    assert "contract.pdf" in files and "/delete" in files
    with desk_owner._app.app_context():
        record = [f for f in desk_store.list_files() if f["file_name"] == "contract.pdf"][0]
    assert desk_owner.get("/operator-desk/files/%s/download" % record["id"]).status_code == 200

    r = desk_owner.post("/operator-desk/files/%s/delete" % record["id"])
    assert r.status_code == 302
    with desk_owner._app.app_context():
        assert desk_store.get_file(record["id"]) is None
    assert desk_owner.get("/operator-desk/files/%s/download" % record["id"]).status_code == 404


def test_a_viewer_cannot_remove_desk_files(desk_owner):
    desk_owner.post("/operator-desk/files/upload",
                    data={"file": (io.BytesIO(b"%PDF-1.4 keep"), "keep.pdf"), "category": "Other"},
                    content_type="multipart/form-data")
    with desk_owner._app.app_context():
        record = [f for f in desk_store.list_files() if f["file_name"] == "keep.pdf"][0]
        email = "desk-viewer-%s@example.net" % uuid.uuid4().hex[:8]
        desk_store.add_user(email, "Viewer", "viewer")
    viewer = desk_owner._app.test_client()
    viewer.post("/signup", data={"name": "Viewer", "email": email, "password": PW})
    viewer.post("/login", data={"email": email, "password": PW})
    r = viewer.post("/operator-desk/files/%s/delete" % record["id"])
    assert r.status_code in (302, 403)
    with desk_owner._app.app_context():
        assert desk_store.get_file(record["id"]) is not None
