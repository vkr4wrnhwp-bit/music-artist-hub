"""Three things the live vendor showed that the mocks never could.

Found on the production Audio Studio on 2026-09-05 with every flag and key
set and the provider answering: two dubs failed, and a Remix Lab brief came
back with every line "not measured" against a real recording.
"""
import json
import uuid

import pytest

import audio_elevenlabs as el
import audio_jobs
import audio_studio
import remix_lab_engine as rle


# --- 1. the real composition plan, in the engine's shape ---------------------

class _Section:
    def __init__(self, name, ms, styles=(), avoid=()):
        self.section_name = name
        self.duration_ms = ms
        self.positive_local_styles = list(styles)
        self.negative_local_styles = list(avoid)
        self.lines = []


class _MusicPrompt:
    """The vendor's plan, as the SDK returns it: styles and sections with
    durations. No tempo, no start times."""
    positive_global_styles = ["industrial metal", "downtempo", "distorted bass"]
    negative_global_styles = ["acoustic", "cheerful"]
    sections = [_Section("intro", 12000, ["ambient"]),
                _Section("verse", 30000, ["driving drums"]),
                _Section("chorus", 28000, ["wall of guitars"], ["clean vocals"])]


def test_the_vendor_plan_is_normalised_to_what_the_engine_reads():
    plan = el.normalise_plan(_MusicPrompt())
    assert [s["name"] for s in plan["sections"]] == ["intro", "verse", "chorus"]
    assert [s["start_ms"] for s in plan["sections"]] == [0, 12000, 42000]
    assert plan["sections"][2]["end_ms"] == 70000
    assert plan["global_styles"][0] == "industrial metal"
    assert plan["avoid_styles"] == ["acoustic", "cheerful"]
    assert "tempo_bpm" not in plan, "the vendor did not measure a tempo; none is invented"


def test_a_real_plan_grounds_the_brief_without_inventing_a_tempo():
    plan = el.normalise_plan(_MusicPrompt())
    brief = rle.compose_brief(plan, {"lane": "Club / DJ Edit", "tempoDirection": "Same"})
    by_head = {h: (b, s) for h, b, s in brief}
    assert rle.brief_is_grounded(brief)
    assert by_head["Structure"][1] == "measured" and "chorus at 0:42" in by_head["Structure"][0]
    assert "not measured" in by_head["Tempo"][0]
    assert by_head["What the provider heard"][1] == "measured"
    assert "industrial metal" in by_head["What the provider heard"][0]
    assert "acoustic" in by_head["What the provider heard"][0]


def test_the_plan_also_reads_as_a_plain_dict():
    plan = el.normalise_plan({"positive_global_styles": ["dub"], "negative_global_styles": [],
                              "sections": [{"section_name": "drop", "duration_ms": 5000,
                                            "positive_local_styles": [], "negative_local_styles": []}]})
    assert plan["sections"] == [{"name": "drop", "start_ms": 0, "end_ms": 5000,
                                 "styles": [], "avoid": []}]


def test_the_route_reads_the_plan_from_where_the_real_adapter_puts_it(monkeypatch):
    """The offline adapter returns the plan flat; the real one returns it
    under "plan". The route read the wrapper as the plan, which is how a
    real reading came back as nothing measured."""
    import io
    import os

    import app as appmod
    import audio_works

    for name in ("AUDIO_INTELLIGENCE_ENABLED", "REMIX_LAB_AUDIO_ENGINE_ENABLED"):
        monkeypatch.setenv(name, "1")
    real_shaped = {"plan": el.normalise_plan(_MusicPrompt()), "provider_song_id": "s1",
                   "is_mock": False}
    monkeypatch.setattr(audio_works, "submit_work",
                        lambda work_id: (audio_works.get_work(work_id), real_shaped))
    client = appmod.app.test_client()
    email = "rl-live-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Artist", "email": email, "password": "rl-pass-123"})
    client.post("/login", data={"email": email, "password": "rl-pass-123"})
    body = client.post("/remix-lab/brief", data={
        "rights_own": "1", "rights_likeness": "1", "remixLane": "Club / DJ Edit",
        "targetUse": "DJ pack", "energy": "High", "tempoDirection": "Same",
        "vocalTreatment": "Hook-first", "instrumentation": "Balanced",
        "riskLevel": "Exploratory",
        "file": (io.BytesIO(b"RIFF" + b"\0" * 600), "master.wav")},
        content_type="multipart/form-data").get_data(as_text=True)
    assert "chorus at 0:42" in body
    assert "industrial metal" in body
    assert "Nothing measured" not in body


# --- 2. the language, as a code the vendor accepts --------------------------------

def test_a_language_name_is_sent_as_the_code():
    assert audio_studio.DUBBING_LANGUAGES["french"] == "fr"
    assert audio_studio.DUBBING_LANGUAGES["fr"] == "fr"
    assert audio_studio.DUBBING_LANGUAGES["portuguese"] == "pt"


def test_an_unknown_language_is_refused_before_anything_is_spent():
    assert audio_studio.unknown_languages(["fr", "klingon"]) == ["klingon"]
    assert audio_studio.unknown_languages(["es"]) == []


@pytest.fixture(scope="module")
def studio_client():
    import app as appmod
    client = appmod.app.test_client()
    email = "dub-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Dubber", "email": email, "password": "dub-pass-123"})
    client.post("/login", data={"email": email, "password": "dub-pass-123"})
    return client


def test_the_form_maps_names_and_refuses_the_unknown(studio_client, monkeypatch):
    import io
    for name in ("AUDIO_INTELLIGENCE_ENABLED", "GLOBAL_RELEASE_PACK_ENABLED",
                 "DUBBING_ENABLED"):
        monkeypatch.setenv(name, "1")
    r = studio_client.post("/audio-studio/new", data={
        "lane": "release_pack", "languages": "French, klingon", "rights": "1",
        "file": (io.BytesIO(b"RIFF" + b"\0" * 600), "master.wav")},
        content_type="multipart/form-data")
    if r.status_code == 404:
        pytest.skip("the dubbing lane is off in this environment")
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "klingon is not a language" in body and "french (fr)" in body


# --- 3. the reason first ------------------------------------------------------------

class _ApiError(Exception):
    def __init__(self):
        self.status_code = 400
        self.headers = {"date": "Sat", "server": "uvicorn", "x-trace-id": "b263"}
        self.body = {"detail": {"type": "validation_error",
                                "message": "The provided language code 'french' is not supported."}}

    def __str__(self):
        return "headers: %s, status_code: %s, body: %s" % (self.headers, self.status_code, self.body)


def test_a_vendor_error_is_stored_reason_first():
    text = audio_jobs.describe_error(_ApiError())
    assert text.startswith("_ApiError 400:")
    assert "not supported" in text[:200]
    assert "uvicorn" not in text and "x-trace-id" not in text


def test_an_ordinary_exception_still_reads_as_itself():
    assert audio_jobs.describe_error(KeyError("audio_path")) == "KeyError: 'audio_path'"
