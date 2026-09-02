"""The Control Room: three readiness questions, kept apart.

How the mix measures, how it stands as a master, whether the project can
ship - each its own list, each entry a word a person can read rather than
a number for a yes/no test. The Doctor reads findings first, then the
platform rulings, then the metrics, and says what it could not measure.
The lifecycle rail carries the conditions behind each stage. The delivery
button is the first gap on the required list. The build stamp lives under
System status, not on the record.
"""
import io
import struct
import uuid

import pytest

import app as appmod
import db as store
import studio_metrics as sm
import studio_score
import studio_store as sstore

PASSWORD = "room-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Preview Artist"):
    email = "room-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _wav(seconds=1, sr=8000):
    body = b"".join(struct.pack("<hh", int(6000 * ((n // 20) % 2) - 3000), 0) for n in range(seconds * sr))
    return (b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, sr, sr * 4, 4, 16)
            + b"data" + struct.pack("<I", len(body)) + body)


def _project(client, user):
    r = client.post("/studio/new", data={"title": "Signal Fire", "artist_name": "Preview Artist",
                                          "project_type": "master_single"})
    pid = r.headers["Location"].rstrip("/").split("/")[-1].split("?")[0]
    client.post("/studio/session/%s/rights" % pid, data={"confirmed_by": "Preview Artist"})
    r = client.post("/studio/session/%s/upload" % pid, data={"file": (io.BytesIO(_wav()), "signal-fire-mix.wav")},
                    content_type="multipart/form-data")
    assert r.status_code in (200, 302), r.status_code
    summary = sstore.project_summary(None, user["id"], pid)
    return pid, summary["source"]["id"]


MEASURED = {"integrated": -13.8, "true_peak": -6.1, "sample_peak": -6.3, "lra": 8.4,
            "bpm": 94.0, "bpm_confidence": 0.4, "key": "E minor", "key_fit": 0.6,
            "duration_seconds": 253.0, "measured_at": "2026-09-02T10:00:00Z"}


# --- the view models ---------------------------------------------------------

def test_metrics_read_as_words_never_as_a_score_for_a_yes_no_test():
    by = {x["key"]: x for x in sm.mix_metrics(MEASURED)}
    assert (by["headroom"]["state"], by["headroom"]["value"]) == ("pass", "-6.1 dBTP")
    assert by["clipping"]["state"] == "clear"
    assert (by["loudness"]["state"], by["loudness"]["value"]) == ("in_range", "-13.8 LUFS")
    assert by["dynamics"]["state"] == "healthy" and by["dynamics"]["value"] == "8.4 LU range"
    assert (by["tempo"]["state"], by["tempo"]["value"]) == ("low_confidence", "94 BPM")
    assert (by["key"]["state"], by["key"]["value"]) == ("medium_confidence", "E minor")
    assert by["stereo"]["state"] == "not_measured"
    assert by["vocal"]["state"] == "needs_stems" and by["lowend"]["state"] == "needs_reference"
    for x in by.values():
        assert x["state_label"] in sm.STATES.values()
        assert "100" not in str(x["value"] or "")
    # Red is for an over, not for a low-confidence reading.
    assert by["tempo"]["tone"] == "warn" and by["headroom"]["tone"] == "good"


def test_an_over_is_the_one_red_reading():
    by = {x["key"]: x for x in sm.mix_metrics({"true_peak": 0.4, "sample_peak": 0.2})}
    assert by["clipping"]["state"] == "review" and by["clipping"]["tone"] == "crit"
    assert by["headroom"]["state"] == "review" and by["headroom"]["tone"] == "crit"


def test_nothing_measured_reads_not_measured():
    metrics = sm.mix_metrics({})
    assert all(x["state"] == "not_measured" for x in metrics if x["key"] in
               ("headroom", "clipping", "loudness", "dynamics", "tempo", "key"))
    assert sm.measured_count(metrics) == 0


def test_a_weak_detection_is_not_reported_as_a_value():
    by = {x["key"]: x for x in sm.mix_metrics({"bpm": 120.0, "bpm_confidence": 0.2, "key": "C", "key_fit": 0.1})}
    assert by["tempo"]["state"] == "not_measured" and "Not confident enough" in by["tempo"]["note"]
    assert by["key"]["state"] == "not_measured" and by["key"]["value"] is None


def test_master_readiness_keeps_translation_as_a_listening_tool():
    by = {x["key"]: x for x in sm.master_metrics(MEASURED)}
    assert by["translation"]["state"] == "simulation"
    assert by["tonal"]["state"] == "not_measured"
    assert "vocal" not in by and "tempo" not in by      # mastering framing only


def test_the_section_summary_is_words_from_the_audio_tests_only():
    n = sm.mix_score(sm.mix_metrics(MEASURED))
    assert (n["measured"], n["total"], n["pass"]) == (4, 4, 4)
    assert n["summary"] == "All 4 audio tests pass" and n["tone"] == "good"
    assert "100" not in n["summary"]
    n = sm.mix_score(sm.mix_metrics({"true_peak": 0.4, "sample_peak": 0.2, "integrated": -13.8}))
    assert n["summary"] == "1 of 3 pass · 2 review" and n["tone"] == "crit"
    n = sm.mix_score(sm.mix_metrics({"integrated": -13.8}))
    assert n["summary"] == "1 of 4 measured, all pass"
    assert sm.mix_score(sm.mix_metrics({}))["summary"] is None
    # Version completeness is scored upstream for the Mix room, never here.
    scores = studio_score.mix_readiness(MEASURED, [{"status": "draft"}])
    assert "versions" in {c["key"] for c in scores["categories"]}


def test_system_status_speaks_before_it_lists_wiring():
    rows = [("analysis", True, "", ""), ("storage", True, "", ""),
            ("processing", False, "", ""), ("worker", False, "", "")]
    notes = sm.system_notes(rows)
    assert notes[0].startswith("Master rendering is not enabled")
    assert "queued" in notes[1] and len(notes) == 2
    assert sm.system_notes([("analysis", True, "", "")]) == []


def _checklist(**ok):
    keys = ["source", "rights", "measured", "blocking", "locked", "title"]
    return [{"key": k, "label": k, "ok": ok.get(k, True), "required": True, "detail": ""} for k in keys] + \
           [{"key": "artist", "label": "artist", "ok": False, "required": False, "detail": ""}]


def test_the_delivery_button_is_the_first_gap_on_the_required_list():
    assert sm.delivery(_checklist())["cta"]["label"] == "Prepare delivery"
    assert sm.delivery(_checklist())["ready"] is True
    d = sm.delivery(_checklist(locked=False))
    assert d["cta"] == {"label": "Lock final version", "room": "versions", "key": "locked"}
    assert d["ready"] is False and (d["required_met"], d["required_total"]) == (5, 6)
    assert sm.delivery(_checklist(rights=False, locked=False))["cta"]["label"] == "Confirm rights"
    assert sm.delivery(_checklist(title=False))["cta"]["label"] == "Add project title"
    assert sm.delivery([])["ready"] is False


def test_the_doctor_reads_findings_then_rulings_then_metrics():
    finding = {"status": "open", "severity": "blocking", "category": "clipping",
               "explanation": "The file clips at 1:02. Overs on a master are rejected by most stores.",
               "confidence": "strong", "evidence_source": "measured",
               "start_seconds": 62.0, "measured_evidence": {"peak": 0.3}, "missing_inputs": "[]",
               "recommendation": "Pull the limiter ceiling down."}
    ruling = {"key": "loudness", "level": "watch", "headline": "Louder than the band",
              "detail": "-9 LUFS.", "evidence": "integrated -9.0", "action": "Let the platform do it."}
    metrics = sm.mix_metrics({"integrated": -9.0})
    d = sm.mix_doctor([finding], [ruling], metrics)
    assert d["kind"] == "finding" and d["blocking"] and d["at"] == 62.0 and d["test"].startswith("Pull")
    assert d["headline"] == "The file clips at 1:02" and d["body"].startswith("Overs on a master")
    assert d["label"] == "Clipping"
    d = sm.mix_doctor([{"status": "resolved", "severity": "blocking"}], [ruling], metrics)
    assert d["kind"] == "ruling" and d["headline"] == "Louder than the band"
    d = sm.mix_doctor([], [], metrics)
    assert d["kind"] == "metric" and d["headline"].startswith("Loudness")
    d = sm.mix_doctor([], [], sm.mix_metrics(MEASURED))
    assert d["kind"] == "clear" and "Stereo image" in d["missing"]
    d = sm.mix_doctor([], [], sm.mix_metrics({}))
    assert d["kind"] == "unmeasured"


def test_the_lifecycle_carries_its_conditions():
    project = {"rights_confirmed_at": "2026-09-02", "release_id": ""}
    summary = {"source": {"id": "a"}, "versions": [{"status": "draft"}]}
    checklist = _checklist(locked=False)
    stages = sm.lifecycle_detail(studio_score.lifecycle(project, summary, checklist), project, summary, checklist)
    by = {s["key"]: s for s in stages}
    assert by["create"]["state"] == "done" and by["create"]["next"] == ""
    assert by["finish"]["state"] == "done"
    assert by["approve"]["state"] == "current" and ("A version approved", False) in by["approve"]["conditions"]
    assert ("Final version locked", False) in by["protect"]["conditions"]
    assert by["protect"]["next"] == "Lock the version that ships."
    assert len(by["deliver"]["conditions"]) == 6


def test_activity_folds_consecutive_repeats_without_losing_them():
    events = [{"event_type": "rights.confirmed", "created_at": "2026-09-02T10:00:00"},
              {"event_type": "rights.confirmed", "created_at": "2026-09-02T10:00:01"},
              {"event_type": "rights.confirmed", "created_at": "2026-09-02T10:00:02"},
              {"event_type": "asset.uploaded", "created_at": "2026-09-02T10:01:00"},
              {"event_type": "rights.confirmed", "created_at": "2026-09-02T10:02:00"}]
    rows = sm.collapse_activity(events)
    assert [(r["event_type"], r["count"]) for r in rows] == [
        ("rights.confirmed", 3), ("asset.uploaded", 1), ("rights.confirmed", 1)]


def test_team_state_is_a_fact_of_the_seat():
    assert sm.team_state({"team_status": "active", "team_user_id": "u1", "team_member_id": "t1"}) == "active"
    assert sm.team_state({"team_status": "pending", "team_user_id": None, "team_member_id": "t1"}) == "invite_pending"
    assert sm.team_state({"team_status": None, "team_user_id": None, "team_member_id": ""}) == "credit"


# --- the room ----------------------------------------------------------------

def test_the_room_puts_the_record_first(flask_app):
    client, user = _user(flask_app)
    pid, asset = _project(client, user)
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert 'class="sr-hero"' in body and 'id="sr-title">Signal Fire<' in body
    assert 'id="sb-console-wave"' in body and 'id="sb-transport"' in body and 'class="sr-transport"' in body
    assert '<span class="sr-tab is-on" aria-current="page">Control Room</span>' in body
    assert 'data-stage="finish"' in body and body.count("sr-stage--done") >= 2
    # The build stamp is out of the record and under System status.
    hero = body.split('class="sr-hero"')[1].split("</section>")[0]
    assert "build " not in hero
    system = body.split('data-panel="system"')[1]
    assert "Master rendering is not enabled" in system     # a person's sentence first
    engineering = system.split('class="sr-engineering"')[1]
    assert "build sb-v" in engineering and "No processing provider" in engineering and "No background worker" in engineering
    # Nothing measured yet: honest empty states and the button that changes that.
    assert 'data-panel="mix-readiness"' in body and "unmeasured" in body and 'id="sb-measure-go"' in body
    assert 'data-doctor="unmeasured"' in body and "Nothing has been measured yet" in body
    assert "Measure the audio" in body            # the delivery button is the first gap
    assert 'data-ready="no"' in body
    assert 'id="sb-sims"' in body and "your ears are the meter" in body


def test_measuring_changes_the_readings_and_the_button(flask_app):
    client, user = _user(flask_app)
    pid, asset = _project(client, user)
    r = client.post("/studio/session/%s/measure" % pid, json=dict(MEASURED, asset_id=asset))
    assert r.status_code == 200
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    mix = body.split('data-panel="mix-readiness"')[1].split("</section>")[0]
    assert "-13.8 LUFS" in mix and "In range" in mix
    assert "94 BPM" in mix and "Low confidence" in mix
    assert "E minor" in mix and "Medium confidence" in mix
    assert "Not measured" in mix and "Needs stems" in mix
    assert "All 4 audio tests pass" in mix and ">100<" not in mix   # words, no fake full marks
    assert 'data-doctor="unmeasured"' not in body      # the Doctor now has something to read
    assert "Lock final version" in body and 'data-lock="1"' in body
    assert "4:13" in body                                 # the duration, from the measurement


def test_locking_the_version_moves_delivery_to_prepare(flask_app):
    client, user = _user(flask_app)
    pid, asset = _project(client, user)
    client.post("/studio/session/%s/measure" % pid, json=dict(MEASURED, asset_id=asset))
    vid = sstore.project_summary(None, user["id"], pid)["versions"][0]["id"]
    r = client.post("/studio/session/%s/version/%s/status" % (pid, vid), data={"status": "locked"})
    assert r.status_code == 302
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert 'data-ready="yes"' in body and "Prepare delivery" in body and "Ready for delivery." in body
    rail = body.split('class="sr-rail"')[1].split("</nav>")[0]
    assert 'data-stage="protect"' in rail and rail.count("sr-stage--done") >= 4


def test_credit_only_people_show_as_credit_and_gain_nothing(flask_app):
    client, user = _user(flask_app)
    pid, asset = _project(client, user)
    client.post("/studio/session/%s/team" % pid, data={"display_name": "MixedByCee", "role": "mix_engineer"})
    body = client.get("/studio/session/%s" % pid).get_data(as_text=True)
    assert "ON THIS RECORD" in body and "MixedByCee" in body
    assert 'data-team-state="credit"' in body and 'data-access="credit"' in body and "Credit only" in body
    stranger, _ = _user(flask_app, "Stranger")
    assert stranger.get("/studio/session/%s" % pid).status_code == 404


def test_the_other_rooms_share_the_tabs(flask_app):
    client, user = _user(flask_app)
    pid, asset = _project(client, user)
    for room in ("mix", "master", "versions", "deliver"):
        r = client.get("/studio/session/%s/%s" % (pid, room))
        assert r.status_code == 200, room
        assert 'class="sr-tabs"' in r.get_data(as_text=True), room
