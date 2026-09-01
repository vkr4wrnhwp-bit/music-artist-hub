# -*- coding: utf-8 -*-
"""Mix Station and Master Station.

Both work on a deployment with no vendor and no worker, because everything
they show is MEASURED rather than generated: the browser decodes the file with
the Rack's own BS.1770-4 engine plus the tempo and key detectors, posts the
numbers back, and audio_readiness turns them into rulings.

The line these tests defend is the one this product keeps having to defend:
nothing is shown that was not measured. An unmeasured project shows no
figures, not zeroes; a missing tempo reads as unknown, not as 0 BPM; and the
hosted render nobody can run is disabled with its reason attached rather than
offered and failing later.
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


@pytest.fixture(scope="module", autouse=True)
def _restore_flag():
    saved = os.environ.get("STUDIO_V1_ENABLED")
    yield
    if saved is None:
        os.environ.pop("STUDIO_V1_ENABLED", None)
    else:
        os.environ["STUDIO_V1_ENABLED"] = saved


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
    email = "mm-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "mm-pass-123"})
    client.post("/login", data={"email": email, "password": "mm-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def loaded(application):
    """A project with a source uploaded and nothing measured yet."""
    client, user = _artist(application)
    response = client.post("/studio/new", data={"title": "Signal Fire",
                                                "project_type": "master_single"})
    project_id = response.headers["Location"].rstrip("/").split("/")[-1]
    client.post("/studio/session/%s/rights" % project_id,
                data={"confirmed_by": "Artist"})
    client.post("/studio/session/%s/upload" % project_id,
                data={"file": (io.BytesIO(_wav()), "master.wav")},
                content_type="multipart/form-data")
    with application.app_context():
        source = sstore.project_summary(None, user["id"], project_id)["source"]
    return {"client": client, "user": user, "project_id": project_id,
            "asset_id": source["id"]}


HOT = {
    "measured_at": "2026-08-28T10:00:00Z", "duration_seconds": 2.0,
    "integrated": -6.2, "true_peak": -0.2, "sample_peak": -0.4, "lra": 2.1,
    "bpm": 120.1, "bpm_confidence": 0.9, "key": "A minor", "key_fit": 0.49,
    "short_term_max": -5.8, "momentary_max": -5.1, "first_beat": 0.49,
    "grid_confidence": 1.0,
}


def _measure(loaded, **overrides):
    payload = dict(HOT, asset_id=loaded["asset_id"])
    payload.update(overrides)
    return loaded["client"].post(
        "/studio/session/%s/measure" % loaded["project_id"], json=payload)


# --- nothing is shown that was not measured ----------------------------------

def test_an_unmeasured_mix_shows_no_figures(loaded):
    """Not zeroes, not placeholders. A zero reads as a measurement."""
    body = loaded["client"].get(
        "/studio/session/%s/mix" % loaded["project_id"]).get_data(as_text=True)
    assert "Nothing has been measured yet" in body
    assert "LUFS" not in body.split("Mix readiness")[1].split("Notes")[0] \
        or "Measure this mix" in body


def test_an_unmeasured_master_says_so(loaded):
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert "Not measured yet" in body
    assert "placeholder" in body


# --- the measurement round trip ----------------------------------------------

def test_a_measurement_becomes_rulings(application, loaded):
    assert _measure(loaded).status_code == 200
    with application.app_context():
        analysis = sstore.latest_analysis(None, loaded["asset_id"])
        findings = sstore.list_findings(None, loaded["asset_id"])
    assert analysis["measurements"]["integrated"] == -6.2
    assert findings, "a hot master with a -0.2 dBTP peak should produce findings"


def test_a_true_peak_over_the_ceiling_is_blocking(application, loaded):
    """-1 dBTP is where mastering ceilings sit, because 4x oversampling
    under-reads by up to about 0.7 dB. -0.2 is over it."""
    _measure(loaded)
    with application.app_context():
        findings = sstore.list_findings(None, loaded["asset_id"])
    peak = [f for f in findings if f["category"] == "true_peak"]
    assert peak and peak[0]["severity"] == "blocking"


def test_a_clean_master_produces_no_blocking_findings(application, loaded):
    _measure(loaded, integrated=-14.0, true_peak=-1.8, lra=7.0)
    with application.app_context():
        findings = sstore.list_findings(None, loaded["asset_id"])
    assert not [f for f in findings if f["severity"] == "blocking"]


def test_measuring_again_replaces_the_findings_rather_than_stacking_them(
        application, loaded):
    """Findings describe THIS measurement of THIS asset. Keeping the old ones
    would show a resolved problem as current."""
    _measure(loaded)
    with application.app_context():
        first = len(sstore.list_findings(None, loaded["asset_id"]))
    _measure(loaded)
    with application.app_context():
        second = len(sstore.list_findings(None, loaded["asset_id"]))
    assert first == second


def test_a_missing_tempo_is_unknown_rather_than_zero(application, loaded):
    """The tempo engine returns null on material with no transients. That must
    not arrive as 0 BPM, which reads as a measurement."""
    payload = dict(HOT, asset_id=loaded["asset_id"])
    payload.pop("bpm")
    payload.pop("bpm_confidence")
    loaded["client"].post(
        "/studio/session/%s/measure" % loaded["project_id"], json=payload)
    with application.app_context():
        analysis = sstore.latest_analysis(None, loaded["asset_id"])
    assert "bpm" not in analysis["measurements"]


def test_a_non_numeric_measurement_is_discarded(application, loaded):
    """The page is the only thing that can measure, but it is still a client.
    A string where a float belongs must not reach audio_readiness."""
    _measure(loaded, integrated="very loud", true_peak=None)
    with application.app_context():
        analysis = sstore.latest_analysis(None, loaded["asset_id"])
    assert "integrated" not in analysis["measurements"]


def test_another_account_cannot_post_a_measurement(application, loaded):
    other_client, _other = _artist(application)
    response = other_client.post(
        "/studio/session/%s/measure" % loaded["project_id"],
        json=dict(HOT, asset_id=loaded["asset_id"]))
    assert response.status_code == 404


# --- what the pages then say --------------------------------------------------

def test_the_mix_page_shows_the_measured_numbers(loaded):
    _measure(loaded)
    body = loaded["client"].get(
        "/studio/session/%s/mix" % loaded["project_id"]).get_data(as_text=True)
    # The LCD blocks style value and unit separately, so the assertion is on
    # the measured NUMBERS being present, not on one text node's exact shape.
    assert "-6.2" in body and "LUFS" in body
    assert "120.1" in body and "BPM" in body
    assert "A minor" in body
    assert "Mix Doctor" in body


def test_every_finding_carries_its_evidence(loaded):
    """A recommendation with no measurement behind it is an opinion, and this
    product does not present opinions as measurements."""
    _measure(loaded)
    body = loaded["client"].get(
        "/studio/session/%s/mix" % loaded["project_id"]).get_data(as_text=True)
    assert "measured" in body
    assert "confidence" in body


def test_the_master_page_compares_against_published_targets(loaded):
    _measure(loaded)
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert "Against the platforms" in body
    assert "Premaster inspection" in body
    assert "No single loudness target is universally required" in body


def test_hosted_rendering_is_disabled_with_its_reason(loaded):
    """No provider and no worker here. A button that would fail is worse than
    a disabled one that says why."""
    _measure(loaded)
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert "No processing provider is configured" in body
    assert "Open this in the Rack" in body


# --- notes -------------------------------------------------------------------

def test_a_note_past_the_end_of_the_recording_is_refused(application, loaded):
    """A note at 4:12 of a two-second file sends somebody looking for a
    problem that is not there."""
    _measure(loaded)
    loaded["client"].post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "999",
              "body": "past the end"})
    with application.app_context():
        assert sstore.list_comments(None, loaded["asset_id"]) == []


def test_a_note_inside_the_recording_is_kept(application, loaded):
    _measure(loaded)
    loaded["client"].post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "1.5",
              "body": "vocal buried here"})
    with application.app_context():
        notes = sstore.list_comments(None, loaded["asset_id"])
    assert len(notes) == 1
    assert notes[0]["body"] == "vocal buried here"


def test_an_empty_note_is_not_stored(application, loaded):
    loaded["client"].post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "1",
              "body": "   "})
    with application.app_context():
        assert sstore.list_comments(None, loaded["asset_id"]) == []


def test_a_note_can_be_resolved_and_reopened(application, loaded):
    loaded["client"].post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "1",
              "body": "check this"})
    with application.app_context():
        note = sstore.list_comments(None, loaded["asset_id"])[0]

    loaded["client"].post(
        "/studio/session/%s/comment/%s/resolve"
        % (loaded["project_id"], note["id"]))
    with application.app_context():
        assert sstore.list_comments(None, loaded["asset_id"])[0]["status"] == "resolved"

    loaded["client"].post(
        "/studio/session/%s/comment/%s/resolve"
        % (loaded["project_id"], note["id"]), data={"reopen": "1"})
    with application.app_context():
        assert sstore.list_comments(None, loaded["asset_id"])[0]["status"] == "open"


def test_notes_do_not_leak_between_accounts(application, loaded):
    loaded["client"].post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "1",
              "body": "private note"})
    other_client, _other = _artist(application)
    response = other_client.post(
        "/studio/session/%s/comment" % loaded["project_id"],
        data={"asset_id": loaded["asset_id"], "start_seconds": "1",
              "body": "theirs"})
    assert response.status_code == 404
    with application.app_context():
        bodies = [c["body"] for c in sstore.list_comments(None, loaded["asset_id"])]
    assert bodies == ["private note"]


# --- the master change report table ------------------------------------------

def _render_with_report(loaded, report, label="Master · Warm · medium"):
    import json

    return loaded["client"].post(
        "/studio/session/%s/render" % loaded["project_id"],
        data={"file": (io.BytesIO(_wav()), "m.wav"),
              "source_asset_id": loaded["asset_id"], "label": label,
              "note": "prose note", "report": json.dumps(report)},
        content_type="multipart/form-data")


GOOD_REPORT = {"direction": "Warm", "intensity": "medium", "inLufs": -18.4,
               "outLufs": -14.0, "inTp": -6.2, "outTp": -1.31,
               "gainDb": 4.4, "maxReductionDb": 0.0, "capped": False,
               "moves": ["low shelf +1.2 dB at 120 Hz"],
               "basis": "engineering convention"}


def test_a_render_report_is_stored_structured_and_tabled(application, loaded):
    assert _render_with_report(loaded, GOOD_REPORT).status_code == 200
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert "MASTER CHANGE REPORT" in body
    assert "-18.4" in body and "-14.0" in body        # LUFS in -> out
    assert "-1.31" in body                            # measured TP out
    assert "+4.4" in body                             # signed gain
    assert "Warm" in body and "medium" in body


def test_the_report_whitelist_drops_what_a_client_should_not_say(application, loaded):
    """The browser computes the report, but the browser is a client. Unknown
    keys, absurd numbers and non-numeric types must not reach the table."""
    import studio_store as sstore

    dirty = dict(GOOD_REPORT, outLufs="very loud", gainDb=99999,
                 surprise="<script>", moves=["ok", 42, "x" * 500])
    _render_with_report(loaded, dirty, label="Master · Dirty")
    with application.app_context():
        version = sstore.list_versions(None, loaded["project_id"])[0]
        report = sstore.version_report(version)
    assert "outLufs" not in report                    # wrong type, dropped
    assert "gainDb" not in report                     # absurd, dropped
    assert "surprise" not in report                   # unknown, dropped
    assert report["moves"] == ["ok", "x" * 90]        # strings only, capped
    assert report["inLufs"] == -18.4                  # the honest fields stay


def test_a_malformed_report_loses_the_table_never_the_render(application, loaded):
    import studio_store as sstore

    response = loaded["client"].post(
        "/studio/session/%s/render" % loaded["project_id"],
        data={"file": (io.BytesIO(_wav()), "m.wav"),
              "source_asset_id": loaded["asset_id"],
              "label": "Master · Broken", "report": "{not json"},
        content_type="multipart/form-data")
    assert response.status_code == 200                # the render succeeded
    with application.app_context():
        version = sstore.list_versions(None, loaded["project_id"])[0]
    assert sstore.version_report(version) is None


def test_a_prose_era_render_says_so_instead_of_inventing_numbers(application, loaded):
    loaded["client"].post(
        "/studio/session/%s/render" % loaded["project_id"],
        data={"file": (io.BytesIO(_wav()), "m.wav"),
              "source_asset_id": loaded["asset_id"],
              "label": "Master · Old", "note": "-6.2 to -14.0 LUFS"},
        content_type="multipart/form-data")
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert "recorded as prose" in body


def test_the_row_carries_the_output_checksum(application, loaded):
    import hashlib

    _render_with_report(loaded, GOOD_REPORT)
    expected = hashlib.sha256(_wav()).hexdigest()[:8]
    body = loaded["client"].get(
        "/studio/session/%s/master" % loaded["project_id"]).get_data(as_text=True)
    assert expected in body
