# -*- coding: utf-8 -*-
"""Live: a stem reaches the performance page, wherever it is stored.

GET /live/stem/<id> is the only way the performance page gets audio, and at
b6c1d949 it delivered nothing on either kind of storage:

  on this server's disk  it looked for store.uploads_dir(), which db.py has
                         never had, so every local stem was a 404;
  in the bucket          it redirected to a signed URL, which the page's
                         fetch() follows cross-origin, and the bucket sends
                         no CORS headers (the Audio Studio found this live,
                         2026-09-15), so the fetch failed.

Now both are served through the app. Nothing reaches the network here: the
bucket is monkeypatched.
"""
import os
import uuid

import pytest

import blob_store

WAV = (b"RIFF" + (36 + 8).to_bytes(4, "little") + b"WAVEfmt "
       + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
       + (1).to_bytes(2, "little") + (8000).to_bytes(4, "little")
       + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little")
       + (16).to_bytes(2, "little") + b"data" + (8).to_bytes(4, "little")
       + b"\x00\x01\x00\x02\x00\x03\x00\x04")


@pytest.fixture(scope="module")
def application():
    os.environ["LIVE_LAB_ENABLED"] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture(scope="module", autouse=True)
def _restore_flag():
    saved = os.environ.get("LIVE_LAB_ENABLED")
    yield
    if saved is None:
        os.environ.pop("LIVE_LAB_ENABLED", None)
    else:
        os.environ["LIVE_LAB_ENABLED"] = saved


def _artist(application):
    email = "ls-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Rig", "email": email,
                                 "password": "ls-pass-123"})
    client.post("/login", data={"email": email, "password": "ls-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


def _stem(application, client, user, path):
    """A set with one scene holding one stem that points at `path`.
    Returns the stem's URL from the manifest the performance page reads."""
    import db as store

    with application.app_context():
        file_id = store.add_vault_file(user["id"], path, "Kick", "stems")
    set_id = client.post("/live/new", data={"name": "Friday"}) \
        .headers["Location"].rstrip("/").split("/")[-1]
    client.post("/live/%s/scene" % set_id, data={"name": "Intro"})
    manifest = client.get("/live/%s/manifest.json" % set_id).get_json()
    scene_id = manifest["project"]["scenes"][0]["id"]
    client.post("/live/%s/scene/%s/stem" % (set_id, scene_id),
                data={"vault_file_id": file_id})
    assets = client.get("/live/%s/manifest.json" % set_id).get_json()["assets"]
    assert len(assets) == 1, assets
    return list(assets.values())[0]


def test_a_stem_on_this_servers_disk_is_served(application):
    client, user = _artist(application)
    name = "vault_%s.wav" % uuid.uuid4().hex[:10]
    with open(os.path.join(application.config["UPLOADS_DIR"], name), "wb") as handle:
        handle.write(WAV)
    url = _stem(application, client, user, "/uploads/" + name)

    response = client.get(url)
    assert response.status_code == 200
    assert response.data == WAV
    assert response.mimetype.startswith("audio/")


def test_a_stem_in_the_bucket_is_streamed_not_redirected(application, monkeypatch):
    client, user = _artist(application)
    url = _stem(application, client, user, "r2:vault/kick-%s.wav" % uuid.uuid4().hex[:8])
    asked = []

    def fake_fetch(path, timeout=30):
        asked.append(path)
        return WAV

    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "fetch", fake_fetch)
    response = client.get(url)
    assert response.status_code == 200, response.headers.get("Location")
    assert "Location" not in response.headers
    assert response.data == WAV
    assert asked and asked[0].startswith("r2:vault/kick-")


def test_a_bucket_that_cannot_be_read_is_a_503_not_a_dead_redirect(application, monkeypatch):
    client, user = _artist(application)
    url = _stem(application, client, user, "r2:vault/gone-%s.wav" % uuid.uuid4().hex[:8])
    monkeypatch.setattr(blob_store, "fetch", lambda path, timeout=30: None)
    assert client.get(url).status_code == 503


def test_another_account_still_cannot_read_the_stem(application):
    client, user = _artist(application)
    name = "vault_%s.wav" % uuid.uuid4().hex[:10]
    with open(os.path.join(application.config["UPLOADS_DIR"], name), "wb") as handle:
        handle.write(WAV)
    url = _stem(application, client, user, "/uploads/" + name)
    stranger, _other = _artist(application)
    assert stranger.get(url).status_code == 404


def test_a_path_that_climbs_out_of_uploads_is_refused(application):
    client, user = _artist(application)
    url = _stem(application, client, user, "/uploads/../../secret.wav")
    assert client.get(url).status_code == 404
