"""Pulling the words up off a recording.

Asked for live, 2026-09-10: "i think there should be a ai lyric
generator that pulls the words up".

What this is, and is not: a transcript of what was actually sung. Not
invented lyrics. The words on a master belong to whoever wrote them,
and a machine guessing at a mumbled line and presenting it as the lyric
would be putting words in somebody's mouth — and into a registration,
which is where lyric sheets end up.

The capability was already in the product (TRANSCRIPTION, with a real
adapter and a mock) and had no lane using it. Wiring it up exposed a
real hole: a job that finishes on the create call never polls, so
_store_result never ran, and a transcription's words — which live
behind status(), not on the create response — were never written down
anywhere at all.
"""
import os
import uuid

import pytest

import audio_store as astore
import audio_works as works
import db as store


@pytest.fixture(scope="module")
def application():
    for flag in ("AUDIO_INTELLIGENCE_ENABLED", "LYRIC_SHEET_ENABLED"):
        os.environ[flag] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture
def sheet(application):
    """An artist who has just pulled the words up off a take."""
    import audio_studio as astudio
    email = "lyr-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "lyr-pass-123"})
    client.post("/login", data={"email": email, "password": "lyr-pass-123"})
    with application.app_context():
        user = store.get_user_by_email(email)
        name = "take-%s.wav" % uuid.uuid4().hex[:8]
        src = astore.create_asset(None, user["id"], "studio:" + name,
                                  file_name=name)
        with open(os.path.join(astudio._studio_dir(), name), "wb") as f:
            f.write(b"RIFF" + bytes(2000))
        item = works.create_work(user["id"], "lyric_sheet", title="Cold Corner",
                                 source_asset_id=src)
        works.confirm_rights(item["id"], user["name"])
        works.submit_work(item["id"])
    return {"client": client, "user": user, "work_id": item["id"], "asset": src}


def test_the_words_are_written_down_where_they_can_be_read_again(application, sheet):
    """The hole this found: a job that finishes on the create call never
    polls, so nothing ever stored what it produced."""
    with application.app_context():
        stored = astore.transcript_for_asset(None, sheet["asset"])
    assert stored, "the transcript was produced and then dropped on the floor"
    assert stored["segments"], "with no words in it there is nothing to show"


def test_the_page_shows_the_words_against_the_clock(sheet):
    page = sheet["client"].get("/audio-studio/%s" % sheet["work_id"])
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "The words" in body
    assert body.count("data-lyric-at") > 1, (
        "every line carries the time it starts, so it can be checked "
        "against the take")
    assert "Heard off the recording, not written" in body, (
        "the page must not let a transcript be mistaken for a lyric")


def test_the_sheet_downloads_as_plain_text(sheet):
    r = sheet["client"].post("/audio-studio/%s/lyrics.txt" % sheet["work_id"])
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    body = r.get_data(as_text=True)
    assert body.strip(), "an empty file is worse than no button"
    assert body.startswith("["), "each line is timed"


def test_somebody_elses_words_are_a_404(application, sheet):
    stranger = application.test_client()
    email = "lyr-other-%s@example.net" % uuid.uuid4().hex[:8]
    stranger.post("/signup", data={"name": "Other", "email": email,
                                   "password": "lyr-pass-123"})
    stranger.post("/login", data={"email": email, "password": "lyr-pass-123"})
    r = stranger.post("/audio-studio/%s/lyrics.txt" % sheet["work_id"])
    assert r.status_code == 404


def test_the_lane_needs_the_rights_confirmation(application):
    """It reads a master. A meeting transcript does not need this; this does."""
    import audio_policy
    assert audio_policy.FEATURES["lyric_sheet"]["rights"] is True


def test_speaker_labels_are_off(application):
    """A double-tracked chorus is not two people."""
    import audio_providers as ap
    with application.app_context():
        item = works.create_work("u-x", "lyric_sheet", title="x",
                                 source_asset_id=None)
        request = works._build_request(item, "transcription", ap)
    assert request.diarize is False
    assert request.timestamps is True


def test_the_kind_says_what_it_produces(application):
    capability, label, needs_source = works.WORK_KINDS["lyric_sheet"]
    assert capability == "transcription", "not a generator"
    assert label == "Lyric sheet"
    assert needs_source, "there is nothing to transcribe without a recording"
