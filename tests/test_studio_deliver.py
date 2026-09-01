# -*- coding: utf-8 -*-
"""Approve, lock, deliver - the end of the workflow.

This is the part the whole product exists for: being able to say which of the
eleven files on the drive is the one that ships, and proving it later. So the
tests here are mostly about refusal. A package that can be built before the
version is locked is a package that can ship the wrong file, and a checklist
that ticks a line it did not check is worse than no checklist at all.
"""
import io
import json
import math
import os
import struct
import uuid
import zipfile

import pytest

import studio_store as sstore


@pytest.fixture(scope="module")
def application():
    os.environ["STUDIO_V1_ENABLED"] = "1"
    import app as appmod
    return appmod.app


def _wav(seconds=2, rate=44100):
    frames = b"".join(
        struct.pack("<hh", int(9000 * math.sin(2 * math.pi * 220 * n / rate)),
                    int(9000 * math.sin(2 * math.pi * 220 * n / rate)))
        for n in range(seconds * rate))
    header = (b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt "
              + struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 4, 4, 16)
              + b"data" + struct.pack("<I", len(frames)))
    return header + frames


def _artist(application):
    email = "dl-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "dl-pass-123"})
    client.post("/login", data={"email": email, "password": "dl-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def uploaded(application):
    client, user = _artist(application)
    project_id = client.post("/studio/new", data={
        "title": "Signal Fire", "artist_name": "Preview Artist",
        "project_type": "master_single"}
    ).headers["Location"].rstrip("/").split("/")[-1]
    client.post("/studio/session/%s/rights" % project_id,
                data={"confirmed_by": "Preview Artist"})
    client.post("/studio/session/%s/upload" % project_id,
                data={"file": (io.BytesIO(_wav()), "master.wav")},
                content_type="multipart/form-data")
    with application.app_context():
        summary = sstore.project_summary(None, user["id"], project_id)
    return {"client": client, "user": user, "project_id": project_id,
            "asset_id": summary["source"]["id"],
            "version_id": summary["versions"][0]["id"]}


def _clean_measurement(uploaded):
    return uploaded["client"].post(
        "/studio/session/%s/measure" % uploaded["project_id"],
        json={"asset_id": uploaded["asset_id"],
              "measured_at": "2026-08-28T10:00:00Z", "duration_seconds": 2.0,
              "integrated": -14.0, "true_peak": -1.8, "sample_peak": -2.0,
              "lra": 7.0})


def _status(uploaded, status):
    return uploaded["client"].post(
        "/studio/session/%s/version/%s/status"
        % (uploaded["project_id"], uploaded["version_id"]),
        data={"status": status})


def _ready(uploaded):
    _clean_measurement(uploaded)
    _status(uploaded, "approved")
    _status(uploaded, "locked")


# --- the checklist is computed, never asserted -------------------------------

def test_the_checklist_reads_the_project_rather_than_ticking_boxes(
        application, uploaded):
    with application.app_context():
        lines = {c["key"]: c for c in
                 sstore.delivery_checklist(None, uploaded["user"]["id"],
                                           uploaded["project_id"])}
    assert lines["source"]["ok"]
    assert lines["rights"]["ok"]
    assert not lines["measured"]["ok"], "nothing has been measured yet"
    assert not lines["locked"]["ok"], "nothing has been locked yet"


def test_every_line_says_why_not_just_no(application, uploaded):
    with application.app_context():
        lines = sstore.delivery_checklist(None, uploaded["user"]["id"],
                                          uploaded["project_id"])
    for line in lines:
        assert line["detail"], line["key"]


def test_a_blocking_finding_keeps_delivery_shut(application, uploaded):
    """A master over the true-peak ceiling is not deliverable, and the reason
    is the measurement rather than an opinion."""
    uploaded["client"].post(
        "/studio/session/%s/measure" % uploaded["project_id"],
        json={"asset_id": uploaded["asset_id"], "measured_at": "x",
              "duration_seconds": 2.0, "integrated": -6.0, "true_peak": -0.1,
              "sample_peak": -0.2, "lra": 2.0})
    _status(uploaded, "approved")
    _status(uploaded, "locked")
    with application.app_context():
        lines = {c["key"]: c for c in
                 sstore.delivery_checklist(None, uploaded["user"]["id"],
                                           uploaded["project_id"])}
    assert not lines["blocking"]["ok"]


# --- refusal -----------------------------------------------------------------

def test_the_package_is_refused_before_the_work_is_done(uploaded):
    response = uploaded["client"].post(
        "/studio/session/%s/deliver/package" % uploaded["project_id"])
    assert response.status_code == 400
    assert b"Not yet" in response.data


def test_the_button_is_disabled_with_a_reason(uploaded):
    body = uploaded["client"].get(
        "/studio/session/%s/deliver" % uploaded["project_id"]).get_data(as_text=True)
    assert "Every required line above has to be met first" in body


# --- approval and locking ----------------------------------------------------

def test_approving_records_the_checksum_of_the_bytes_approved(
        application, uploaded):
    """"Approved on the 3rd" is a memory. "Approved sha256 9f2c..." survives
    somebody re-uploading a different file under the same name."""
    _clean_measurement(uploaded)
    _status(uploaded, "approved")
    with application.app_context():
        approvals = sstore.list_approvals(None, uploaded["project_id"])
        asset = sstore.get_studio_asset(None, uploaded["user"]["id"],
                                        uploaded["asset_id"])
    assert approvals
    assert approvals[0]["asset_checksum"] == asset["sha256"]
    assert approvals[0]["asset_checksum"]


def test_a_locked_version_cannot_be_walked_back_through_the_route(
        application, uploaded):
    _ready(uploaded)
    _status(uploaded, "draft")
    _status(uploaded, "rejected")
    with application.app_context():
        version = sstore.get_version(None, uploaded["project_id"],
                                     uploaded["version_id"])
    assert version["status"] == "locked"


def test_another_account_cannot_approve_your_version(application, uploaded):
    other_client, _other = _artist(application)
    response = other_client.post(
        "/studio/session/%s/version/%s/status"
        % (uploaded["project_id"], uploaded["version_id"]),
        data={"status": "approved"})
    assert response.status_code == 404
    with application.app_context():
        assert sstore.list_approvals(None, uploaded["project_id"]) == []


# --- the package -------------------------------------------------------------

def test_the_package_holds_the_audio_and_its_paperwork(uploaded):
    _ready(uploaded)
    response = uploaded["client"].post(
        "/studio/session/%s/deliver/package" % uploaded["project_id"])
    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.data))
    names = archive.namelist()
    assert "manifest.json" in names
    assert "checksums.sha256" in names
    assert "provenance.json" in names
    assert any(n.startswith("audio/") for n in names)


def test_the_audio_in_the_package_is_the_real_file(uploaded):
    _ready(uploaded)
    archive = zipfile.ZipFile(io.BytesIO(uploaded["client"].post(
        "/studio/session/%s/deliver/package" % uploaded["project_id"]).data))
    audio = [n for n in archive.namelist() if n.startswith("audio/")][0]
    assert archive.read(audio).startswith(b"RIFF")


def test_the_checksum_manifest_matches_the_file_it_names(uploaded):
    """This is what lets whoever receives the package prove the file they got
    is the file that was approved."""
    import hashlib

    _ready(uploaded)
    archive = zipfile.ZipFile(io.BytesIO(uploaded["client"].post(
        "/studio/session/%s/deliver/package" % uploaded["project_id"]).data))
    line = archive.read("checksums.sha256").decode().strip().split("\n")[0]
    digest, name = line.split("  ", 1)
    assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_the_manifest_carries_the_approval_and_the_lock(uploaded):
    _ready(uploaded)
    archive = zipfile.ZipFile(io.BytesIO(uploaded["client"].post(
        "/studio/session/%s/deliver/package" % uploaded["project_id"]).data))
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["rights"]["confirmed_by"] == "Preview Artist"
    assert manifest["approvals"] and manifest["approvals"][0]["checksum"]
    assert [v["status"] for v in manifest["versions"]] == ["locked"]
    assert manifest["files"][0]["included"] is True


def test_the_package_says_what_it_could_not_include(application, uploaded):
    """A package quietly one file short is worse than one that says so."""
    _ready(uploaded)
    import studio

    with application.app_context():
        archive_bytes, _name = sstore.build_package(
            None, uploaded["user"]["id"], uploaded["project_id"],
            lambda _asset: None)          # storage that cannot be read
    manifest = json.loads(
        zipfile.ZipFile(io.BytesIO(archive_bytes)).read("manifest.json"))
    assert manifest["files"][0]["included"] is False
    assert "could not be read" in manifest["files"][0]["reason"]


def test_another_account_cannot_download_your_package(application, uploaded):
    _ready(uploaded)
    other_client, _other = _artist(application)
    assert other_client.post(
        "/studio/session/%s/deliver/package"
        % uploaded["project_id"]).status_code == 404


# --- what is honestly not connected ------------------------------------------

def test_the_page_says_what_it_does_not_do_yet(uploaded):
    """Distribution, Rollout and the Metadata Passport are real connections
    and they are not built. Nothing here pretends they happened."""
    body = uploaded["client"].get(
        "/studio/session/%s/deliver" % uploaded["project_id"]).get_data(as_text=True)
    assert "What is not connected yet" in body
    assert "Distribution" in body
