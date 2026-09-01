# -*- coding: utf-8 -*-
"""The Team panel, and the sharing chain behind it.

A member row is a CREDIT. A member row bound to an accepted team seat is
ACCESS. The whole chain - studio_members row, team_members row, accepted
status, matching user id - is re-checked on every request, so removing any
link ends access on the very next one. That is the Partner OS rule, and these
tests hold Studio to it: what a collaborator can do (open, listen, note), what
they can never do (upload, render, approve, ship), and every way it must end.
"""
import io
import math
import os
import struct
import uuid

import pytest

import studio_store as sstore


@pytest.fixture(scope="module")
def application():
    os.environ["STUDIO_V1_ENABLED"] = "1"
    import app as appmod
    return appmod.app


def _wav():
    rate = 8000
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * n / rate)))
        for n in range(rate))
    return (b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(frames)) + frames)


def _account(application, label="artist"):
    email = "tm-%s-%s@example.net" % (label, uuid.uuid4().hex[:8])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": "tm-pass-123"})
    client.post("/login", data={"email": email, "password": "tm-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def shared(application):
    """An owner with a project and audio, and an engineer who accepted a team
    invite and was added to the project bound to that seat."""
    import db as store

    owner_client, owner = _account(application, "owner")
    engineer_client, engineer = _account(application, "engineer")

    project_id = owner_client.post("/studio/new", data={
        "title": "Signal Fire", "project_type": "master_single"}
    ).headers["Location"].rstrip("/").split("/")[-1]
    owner_client.post("/studio/session/%s/rights" % project_id,
                      data={"confirmed_by": "Owner"})
    owner_client.post("/studio/session/%s/upload" % project_id,
                      data={"file": (io.BytesIO(_wav()), "m.wav")},
                      content_type="multipart/form-data")

    with application.app_context():
        invite = store.add_team_invite(owner["id"], engineer["email"],
                                       "manager")
        store.accept_team_invite(invite["invite_token"], engineer["id"])
        seat = [t for t in store.list_team(owner["id"])
                if t["email"] == engineer["email"]][0]
        member_id = sstore.add_member(None, owner["id"], project_id,
                                      "MixedByCee", "mix_engineer",
                                      team_member_id=seat["id"])
        source = sstore.project_summary(None, owner["id"],
                                        project_id)["source"]
    return {"owner_client": owner_client, "owner": owner,
            "engineer_client": engineer_client, "engineer": engineer,
            "project_id": project_id, "member_id": member_id,
            "seat_id": seat["id"], "source": source}


# --- what a collaborator CAN do ----------------------------------------------

def test_a_bound_member_can_open_the_cockpit(shared):
    response = shared["engineer_client"].get(
        "/studio/session/%s" % shared["project_id"])
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Signal Fire" in body
    assert "mix engineer" in body          # the viewer banner names the role


def test_a_collaborator_can_listen_to_the_audio(shared):
    response = shared["engineer_client"].get(
        "/studio/asset/%s" % shared["source"]["id"])
    assert response.status_code == 200
    assert response.get_data().startswith(b"RIFF")


def test_a_collaborator_can_leave_a_note(application, shared):
    shared["owner_client"].post(
        "/studio/session/%s/measure" % shared["project_id"],
        json={"asset_id": shared["source"]["id"], "measured_at": "x",
              "duration_seconds": 1.0, "integrated": -14.0, "true_peak": -1.8})
    response = shared["engineer_client"].post(
        "/studio/session/%s/comment" % shared["project_id"],
        data={"asset_id": shared["source"]["id"], "start_seconds": "0.5",
              "body": "kick and bass clashing here"})
    assert response.status_code in (301, 302)
    with application.app_context():
        notes = sstore.list_comments(None, shared["source"]["id"])
    assert any("clashing" in n["body"] for n in notes)


def test_shared_projects_appear_on_the_engineers_project_list(shared):
    body = shared["engineer_client"].get("/studio/projects").get_data(as_text=True)
    assert "Shared with you" in body
    assert "Signal Fire" in body


# --- what a collaborator can NEVER do ----------------------------------------

def test_a_collaborator_cannot_upload_render_approve_or_ship(application, shared):
    client = shared["engineer_client"]
    pid = shared["project_id"]
    with application.app_context():
        version_id = sstore.list_versions(None, pid)[0]["id"]

    assert client.post("/studio/session/%s/upload" % pid,
                       data={"file": (io.BytesIO(_wav()), "x.wav")},
                       content_type="multipart/form-data").status_code == 404
    assert client.post("/studio/session/%s/render" % pid,
                       data={"file": (io.BytesIO(_wav()), "m.wav"),
                             "source_asset_id": shared["source"]["id"]},
                       content_type="multipart/form-data").status_code == 404
    assert client.post("/studio/session/%s/version/%s/status"
                       % (pid, version_id),
                       data={"status": "approved"}).status_code == 404
    assert client.post("/studio/session/%s/deliver/package" % pid
                       ).status_code == 404
    assert client.post("/studio/session/%s/rights" % pid,
                       data={"confirmed_by": "Not Me"}).status_code == 404
    assert client.post("/studio/session/%s/team" % pid,
                       data={"display_name": "Friend"}).status_code == 404


# --- every way access must end -----------------------------------------------

def test_removing_the_member_ends_access_on_the_next_request(application, shared):
    assert shared["engineer_client"].get(
        "/studio/session/%s" % shared["project_id"]).status_code == 200
    shared["owner_client"].post(
        "/studio/session/%s/team/%s/remove"
        % (shared["project_id"], shared["member_id"]))
    assert shared["engineer_client"].get(
        "/studio/session/%s" % shared["project_id"]).status_code == 404
    assert shared["engineer_client"].get(
        "/studio/asset/%s" % shared["source"]["id"]).status_code == 404


def test_removing_the_team_seat_ends_access_too(application, shared):
    """The binding is to the SEAT. Cutting the seat cuts every project it
    reached, which is what firing an engineer has to mean."""
    import db as store

    with application.app_context():
        store.remove_team_member(shared["owner"]["id"], shared["seat_id"])
    assert shared["engineer_client"].get(
        "/studio/session/%s" % shared["project_id"]).status_code == 404


def test_a_credit_only_member_grants_nobody_access(application, shared):
    """A name with no seat is a credit. Nobody can ride in on it."""
    with application.app_context():
        sstore.add_member(None, shared["owner"]["id"], shared["project_id"],
                          "Tay Keith", "producer")
    stranger_client, _stranger = _account(application, "stranger")
    assert stranger_client.get(
        "/studio/session/%s" % shared["project_id"]).status_code == 404


def test_a_pending_invite_grants_nothing_until_accepted(application, shared):
    """Invited is not accepted. The chain requires status = accepted."""
    import db as store

    pending_client, pending = _account(application, "pending")
    with application.app_context():
        invite = store.add_team_invite(shared["owner"]["id"],
                                       pending["email"], "manager")
        seat = [t for t in store.list_team(shared["owner"]["id"])
                if t["email"] == pending["email"]][0]
        sstore.add_member(None, shared["owner"]["id"], shared["project_id"],
                          "Pending Person", "viewer",
                          team_member_id=seat["id"])
    assert pending_client.get(
        "/studio/session/%s" % shared["project_id"]).status_code == 404

    with application.app_context():
        store.accept_team_invite(invite["invite_token"], pending["id"])
    assert pending_client.get(
        "/studio/session/%s" % shared["project_id"]).status_code == 200


# --- the panel itself --------------------------------------------------------

def test_the_panel_tells_access_from_credit(shared):
    import re

    body = shared["owner_client"].get(
        "/studio/session/%s" % shared["project_id"]).get_data(as_text=True)
    assert "ON THIS RECORD" in body
    assert "MixedByCee" in body
    assert 'data-access="live"' in body

    shared["owner_client"].post(
        "/studio/session/%s/team" % shared["project_id"],
        data={"display_name": "Tay Keith", "role": "producer"})
    body = shared["owner_client"].get(
        "/studio/session/%s" % shared["project_id"]).get_data(as_text=True)
    assert 'data-access="credit"' in body


def test_a_note_can_be_assigned_and_shows_its_assignee(application, shared):
    shared["owner_client"].post(
        "/studio/session/%s/measure" % shared["project_id"],
        json={"asset_id": shared["source"]["id"], "measured_at": "x",
              "duration_seconds": 1.0, "integrated": -14.0, "true_peak": -1.8})
    shared["owner_client"].post(
        "/studio/session/%s/comment" % shared["project_id"],
        data={"asset_id": shared["source"]["id"], "start_seconds": "0.4",
              "body": "tighten the low end", "assigned_to": shared["member_id"]})
    body = shared["owner_client"].get(
        "/studio/session/%s/mix" % shared["project_id"]).get_data(as_text=True)
    assert "tighten the low end" in body
    assert "MixedByCee" in body
