# -*- coding: utf-8 -*-
"""Street Banker Studio, phase 1: the vertical slice.

Create a project, confirm rights, upload a source, get version 1, see the
waveform and the measurement. One workflow that works end to end, rather than
twenty screens that each do a third of something.

The flag fixture is module-scoped and restores the environment, because
studio_config reads os.environ at call time - a test that sets a flag and
leaves it set makes every later test depend on the order it happened to run in.
"""
import io
import math
import os
import struct
import uuid

import pytest


@pytest.fixture(scope="module")
def application():
    os.environ["STUDIO_V1_ENABLED"] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture(scope="module", autouse=True)
def _restore_flag():
    saved = os.environ.get("STUDIO_V1_ENABLED")
    yield
    if saved is None:
        os.environ.pop("STUDIO_V1_ENABLED", None)
    else:
        os.environ["STUDIO_V1_ENABLED"] = saved


def _wav(seconds=1, rate=8000, level=8000):
    body = b"".join(
        struct.pack("<h", int(level * math.sin(2 * math.pi * 220 * n / rate)))
        for n in range(seconds * rate))
    header = (b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt "
              + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
              + b"data" + struct.pack("<I", len(body)))
    return header + body


def _artist(application):
    email = "sr-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "sr-pass-123"})
    client.post("/login", data={"email": email, "password": "sr-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


def _project(client, title="Signal Fire"):
    response = client.post("/studio/new", data={
        "title": title, "artist_name": "Preview Artist",
        "project_type": "stereo_mix_review"})
    return response.headers["Location"].rstrip("/").split("/")[-1]


@pytest.fixture
def ready(application):
    """An artist with a project whose rights are confirmed."""
    client, user = _artist(application)
    project_id = _project(client)
    client.post("/studio/session/%s/rights" % project_id,
                data={"confirmed_by": "Preview Artist"})
    return {"client": client, "user": user, "project_id": project_id}


# --- the flag ----------------------------------------------------------------

def test_every_route_is_absent_while_the_flag_is_off(application):
    """404 rather than a redirect: a redirect tells a prober the route exists
    and is merely switched off, and it bounces a bookmark somewhere confusing
    after a deployment turns the flag back off."""
    client, _user = _artist(application)
    project_id = _project(client)

    os.environ["STUDIO_V1_ENABLED"] = "0"
    try:
        for path in ("/studio", "/studio/new", "/studio/projects",
                     "/studio/session/%s" % project_id,
                     "/studio/session/%s/versions" % project_id,
                     "/studio/session/%s/mix" % project_id,
                     "/studio/session/%s/master" % project_id):
            assert client.get(path).status_code == 404, path
    finally:
        os.environ["STUDIO_V1_ENABLED"] = "1"


def test_the_sidebar_entry_follows_the_flag(application):
    """A nav link to a route that 404s is worse than no nav link."""
    client, _user = _artist(application)
    assert 'href="/studio"' in client.get("/overview").get_data(as_text=True)

    os.environ["STUDIO_V1_ENABLED"] = "0"
    try:
        assert 'href="/studio"' not in client.get("/overview").get_data(as_text=True)
    finally:
        os.environ["STUDIO_V1_ENABLED"] = "1"


# --- creating ----------------------------------------------------------------

def test_a_project_needs_a_name(application):
    client, _user = _artist(application)
    response = client.post("/studio/new", data={"title": "   "})
    assert response.status_code == 400
    assert b"find it again" in response.data


def test_creating_a_project_lands_on_its_session(application):
    client, _user = _artist(application)
    project_id = _project(client)
    body = client.get("/studio/session/%s" % project_id).get_data(as_text=True)
    assert "Signal Fire" in body


def test_another_account_cannot_open_the_session(application, ready):
    other_client, _other = _artist(application)
    assert other_client.get(
        "/studio/session/%s" % ready["project_id"]).status_code == 404


# --- rights before anything else ---------------------------------------------

def test_nothing_uploads_before_rights_are_confirmed(application):
    """Rights are per project, not once for the account, and the refusal is
    server-side rather than a disabled button."""
    client, _user = _artist(application)
    project_id = _project(client)
    response = client.post("/studio/session/%s/upload" % project_id,
                           data={"file": (io.BytesIO(_wav()), "m.wav")},
                           content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"rights" in response.data.lower()


def test_confirmation_records_a_name_and_a_date(application, ready):
    body = ready["client"].get(
        "/studio/session/%s" % ready["project_id"]).get_data(as_text=True)
    assert "Confirmed by Preview Artist" in body


# --- the upload --------------------------------------------------------------

def test_an_upload_becomes_a_source_and_version_one(application, ready):
    import studio_store as sstore

    response = ready["client"].post(
        "/studio/session/%s/upload" % ready["project_id"],
        data={"file": (io.BytesIO(_wav()), "master.wav")},
        content_type="multipart/form-data")
    assert response.status_code in (301, 302)

    with application.app_context():
        summary = sstore.project_summary(None, ready["user"]["id"],
                                         ready["project_id"])
    assert summary["source"] is not None
    assert summary["source"]["asset_role"] == "original"
    assert summary["source"]["sha256"]
    assert len(summary["versions"]) == 1
    assert summary["versions"][0]["version_number"] == 1


def test_the_same_file_twice_is_refused_rather_than_stored_twice(application, ready):
    """Checksummed on the way in. Two copies of one master is how a project
    ends up with two answers to which file is current."""
    data = _wav()
    ready["client"].post("/studio/session/%s/upload" % ready["project_id"],
                         data={"file": (io.BytesIO(data), "master.wav")},
                         content_type="multipart/form-data")
    response = ready["client"].post(
        "/studio/session/%s/upload" % ready["project_id"],
        data={"file": (io.BytesIO(data), "master-copy.wav")},
        content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"already on this project" in response.data


def test_a_non_audio_file_is_refused(application, ready):
    response = ready["client"].post(
        "/studio/session/%s/upload" % ready["project_id"],
        data={"file": (io.BytesIO(b"%PDF-1.4"), "rider.pdf")},
        content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"not an audio file" in response.data


def test_an_empty_file_is_refused(application, ready):
    response = ready["client"].post(
        "/studio/session/%s/upload" % ready["project_id"],
        data={"file": (io.BytesIO(b""), "empty.wav")},
        content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"empty" in response.data.lower()


# --- serving the audio -------------------------------------------------------

def test_the_source_is_served_to_its_owner(application, ready):
    import studio_store as sstore

    ready["client"].post("/studio/session/%s/upload" % ready["project_id"],
                         data={"file": (io.BytesIO(_wav()), "master.wav")},
                         content_type="multipart/form-data")
    with application.app_context():
        asset = sstore.project_summary(None, ready["user"]["id"],
                                       ready["project_id"])["source"]
    response = ready["client"].get("/studio/asset/%s" % asset["id"])
    assert response.status_code == 200
    assert response.get_data().startswith(b"RIFF")


def test_another_account_cannot_fetch_the_audio(application, ready):
    """A master is the most valuable file an artist owns. Ownership is
    re-checked per request rather than handed out in a link."""
    import studio_store as sstore

    ready["client"].post("/studio/session/%s/upload" % ready["project_id"],
                         data={"file": (io.BytesIO(_wav()), "master.wav")},
                         content_type="multipart/form-data")
    with application.app_context():
        asset = sstore.project_summary(None, ready["user"]["id"],
                                       ready["project_id"])["source"]

    other_client, _other = _artist(application)
    assert other_client.get("/studio/asset/%s" % asset["id"]).status_code == 404
    assert application.test_client().get(
        "/studio/asset/%s" % asset["id"]).status_code in (301, 302, 401, 404)


# --- the session page states facts -------------------------------------------

def test_the_session_page_measures_rather_than_asserts(application, ready):
    """The page must not print a loudness figure the server invented. It ships
    the markup and the engine; the number is produced in the browser from the
    file itself."""
    ready["client"].post("/studio/session/%s/upload" % ready["project_id"],
                         data={"file": (io.BytesIO(_wav()), "master.wav")},
                         content_type="multipart/form-data")
    body = ready["client"].get(
        "/studio/session/%s" % ready["project_id"]).get_data(as_text=True)

    assert "loudness.js" in body
    assert 'id="sb-wave"' in body
    assert "SBLoudness" in body
    assert "measuring" in body          # the placeholder, not a fabricated value


def test_the_page_says_what_this_deployment_cannot_do(application, ready):
    """No worker and no provider here, and the page says both rather than
    offering buttons that would fail."""
    body = ready["client"].get(
        "/studio/session/%s" % ready["project_id"]).get_data(as_text=True)
    assert "No background worker" in body
    assert "No processing provider" in body


def test_no_room_claims_to_be_unbuilt_any_more(application, ready):
    """Every room - Session, Rack, Mix, Master, Versions, Deliver - is real
    now. A leftover "not built yet" label would disable a working feature,
    which is the same dishonesty as enabling a broken one."""
    body = ready["client"].get(
        "/studio/session/%s" % ready["project_id"]).get_data(as_text=True)
    assert "not built yet" not in body


def test_mix_and_master_need_a_source_before_they_open(application):
    """Both rooms are about a recording. Opening one with nothing uploaded
    would be a page that cannot answer its own question."""
    client, _user = _artist(application)
    project_id = _project(client)
    body = client.get("/studio/session/%s" % project_id).get_data(as_text=True)
    assert "Upload a source first" in body


# --- the Rack, still there ---------------------------------------------------

def test_the_rack_handoff_carries_the_project(application, ready):
    ready["client"].post("/studio/session/%s/upload" % ready["project_id"],
                         data={"file": (io.BytesIO(_wav()), "master.wav")},
                         content_type="multipart/form-data")
    response = ready["client"].get(
        "/studio/session/%s/rack" % ready["project_id"])
    assert response.status_code in (301, 302)
    assert "/rack?project=%s" % ready["project_id"] in response.headers["Location"]


def test_the_bare_rack_still_works_with_no_project(application):
    """Studio does not replace /rack. It is in the sidebar, the palette and
    command_center, and it is where the Audio Studio sends stems."""
    client, _user = _artist(application)
    assert client.get("/rack").status_code == 200
    assert client.get("/rack?stems=abc123").status_code == 200
