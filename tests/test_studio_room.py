# -*- coding: utf-8 -*-
"""Ask the Room.

The property under test is not cleverness - it is grounding. Every answer
must come from what the project actually holds, carry the spec's structure
(observation / why / confidence / missing / action), admit what a stereo
master cannot reveal, and never claim to have heard anything. A room that
guesses fluently is worse than no room at all.
"""
import io
import json
import math
import os
import struct
import uuid

import pytest

import studio_room


MEASURED = {"integrated": -6.2, "true_peak": -0.2, "lra": 2.1, "bpm": 120.1,
            "bpm_confidence": 0.9, "key": "A minor", "key_fit": 0.49,
            "loudest_at": 74.0}


def _ctx(**over):
    base = {"measurements": {}, "findings": [], "comments": [], "versions": [],
            "checklist": [], "rail": [], "masters": [], "project": {}}
    base.update(over)
    return base


# --- the structure ------------------------------------------------------------

def test_every_answer_carries_the_spec_structure():
    questions = ["what is blocking the release", "is this too compressed",
                 "is it clipping", "why does my vocal disappear on the phone",
                 "what changed between versions", "what notes are open",
                 "what should I send the engineer", "what bpm is it",
                 "how do i become famous"]
    for q in questions:
        a = studio_room.ask(q, _ctx(measurements=MEASURED))
        for key in ("observation", "why", "confidence", "action", "topic"):
            assert key in a, (q, key)
        assert a["confidence"] in ("strong", "moderate", "limited"), q


def test_the_room_never_claims_to_have_ears():
    """The one hard rule. Nothing here listened to anything."""
    for q in ("is this too compressed", "vocal on the phone", "low end ready",
              "chorus feels smaller", "what next", "nonsense question"):
        a = studio_room.ask(q, _ctx(measurements=MEASURED))
        text = json.dumps(a).lower()
        for banned in ("i heard", "i listened", "sounds like", "i can hear"):
            assert banned not in text, (q, banned)


# --- grounding ----------------------------------------------------------------

def test_a_loudness_answer_cites_the_measured_number():
    a = studio_room.ask("is this too compressed?", _ctx(measurements=MEASURED))
    assert "-6.2" in a["observation"]
    assert "2.1" in a["observation"]
    assert a["confidence"] in ("strong", "moderate")


def test_an_unmeasured_project_admits_it_rather_than_guessing():
    a = studio_room.ask("is this too loud?", _ctx())
    assert "not been measured" in a["observation"]
    assert a["confidence"] == "limited"
    assert a["missing"]


def test_vocal_questions_admit_the_stereo_limit():
    """"Vocal Translation 82" on a bare stereo file is the fabrication the
    spec forbids; the room's version of that answer is the truth."""
    a = studio_room.ask("why does my vocal disappear on the phone?",
                        _ctx(measurements=MEASURED))
    assert "cannot be measured" in a["observation"]
    assert a["confidence"] == "limited"
    assert "stems" in a["missing"]
    assert "Phone" in a["action"]          # points at the real sim chips


def test_the_vocal_answer_surfaces_a_matching_open_note():
    a = studio_room.ask("vocal buried?", _ctx(
        measurements=MEASURED,
        comments=[{"status": "open", "body": "vocal buried under the synth",
                   "start_seconds": 84.0}]))
    assert "vocal buried under the synth" in a["observation"]
    assert "1:24" in a["observation"]


def test_blocking_answers_read_the_real_checklist():
    a = studio_room.ask("what is blocking the release?", _ctx(checklist=[
        {"key": "locked", "label": "A version is locked", "ok": False,
         "required": True, "detail": "Lock the version that ships."},
        {"key": "title", "label": "The project has a title", "ok": True,
         "required": True, "detail": "Signal Fire"},
    ]))
    assert "1 required check" in a["observation"]
    assert "version is locked" in a["observation"].lower()

    done = studio_room.ask("what is blocking the release?", _ctx(checklist=[
        {"key": "locked", "label": "A version is locked", "ok": True,
         "required": True, "detail": "ok"}]))
    assert "Every required delivery check is met" in done["observation"]


def test_what_next_puts_a_blocking_finding_first():
    a = studio_room.ask("what should I fix first?", _ctx(
        measurements=MEASURED,
        findings=[{"status": "open", "severity": "blocking",
                   "category": "true_peak", "start_seconds": 42.0,
                   "explanation": "Over the ceiling.",
                   "recommendation": "Bring it under -1 dBTP."}]))
    assert "true peak" in a["observation"]
    assert "0:42" in a["observation"]
    assert a["confidence"] == "strong"


def test_version_comparison_reports_the_record_and_names_its_limit():
    a = studio_room.ask("what changed between mix versions?", _ctx(
        versions=[{"version_name": "Master A",
                   "change_summary": "Normalised for Spotify: -6.2 to -14.0"},
                  {"version_name": "Source", "change_summary": "Uploaded"}]))
    assert "-6.2 to -14.0" in a["observation"]
    assert "not built" in a["why"] or "not built" in (a["missing"] or "")


def test_the_fallback_lists_what_it_can_answer_instead_of_bluffing():
    a = studio_room.ask("what color should the album art be?",
                        _ctx(measurements=MEASURED))
    assert a["topic"] == "fallback"
    assert "blocking the release" in a["action"]


def test_no_answer_promises_commercial_success():
    for q in ("will this be a hit", "what next", "is this ready"):
        text = json.dumps(studio_room.ask(q, _ctx(measurements=MEASURED))).lower()
        for banned in ("hit", "viral", "chart"):
            assert banned not in text, (q, banned)


# --- the route ----------------------------------------------------------------

@pytest.fixture(scope="module")
def application():
    os.environ["STUDIO_V1_ENABLED"] = "1"
    import app as appmod
    return appmod.app


def _artist(application):
    email = "rm-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "rm-pass-123"})
    client.post("/login", data={"email": email, "password": "rm-pass-123"})
    return client


def _project_with_audio(client):
    pid = client.post("/studio/new", data={
        "title": "Signal Fire", "project_type": "master_single"}
    ).headers["Location"].rstrip("/").split("/")[-1]
    client.post("/studio/session/%s/rights" % pid,
                data={"confirmed_by": "Artist"})
    rate = 8000
    frames = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * n / rate)))
                      for n in range(rate))
    wav = (b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt "
           + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
           + b"data" + struct.pack("<I", len(frames)) + frames)
    client.post("/studio/session/%s/upload" % pid,
                data={"file": (io.BytesIO(wav), "m.wav")},
                content_type="multipart/form-data")
    return pid


def test_the_panel_renders_the_answer_in_the_cockpit(application):
    client = _artist(application)
    pid = _project_with_audio(client)
    response = client.post("/studio/session/%s/room" % pid,
                           data={"q": "what is blocking the release?"},
                           follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "Ask the Room" in body
    assert "Observation" in body
    assert "required check" in body
    assert "Confidence:" in body


def test_another_account_cannot_ask_about_your_project(application):
    client = _artist(application)
    pid = _project_with_audio(client)
    other = _artist(application)
    assert other.post("/studio/session/%s/room" % pid,
                      data={"q": "anything"}).status_code == 404


def test_studio_front_door_lands_in_the_cockpit(application):
    """The owner looked at /studio twice and saw no updates while the console
    sat one click away. With a project, /studio IS the console now."""
    client = _artist(application)
    pid = _project_with_audio(client)
    response = client.get("/studio")
    assert response.status_code in (301, 302)
    assert pid in response.headers["Location"]

    fresh = _artist(application)
    assert fresh.get("/studio").status_code == 200   # no project: the start page
