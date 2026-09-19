"""Signal Audio Briefs: what gets said, and who gets to hear it.

A brief is listened to while driving. Nobody cross-checks a voice, and a
spoken number carries more authority than the same number on a screen. So the
property under test is that every sentence traces back to a row, and that a
brief which cannot say anything says so rather than filling the time.

The second property is tenancy: a brief names the artists an organisation is
watching and says why. That is its strategy, read aloud.
"""
import os
import uuid

import pytest

import audio_briefs as briefs

OWNER = "brief-owner-%s@example.net" % uuid.uuid4().hex[:8]
STRANGER = "brief-stranger-%s@example.net" % uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def application():
    os.environ["OWNER_EMAILS"] = OWNER
    os.environ["AUDIO_INTELLIGENCE_ENABLED"] = "1"
    os.environ["SIGNAL_AUDIO_BRIEFS_ENABLED"] = "1"
    import app as appmod
    return appmod.app


def _account(application, email):
    client = application.test_client()
    client.post("/signup", data={"name": "T", "email": email, "password": "br-pass-123"})
    client.post("/login", data={"email": email, "password": "br-pass-123"})
    return client


@pytest.fixture
def member(application):
    return _account(application, OWNER)


@pytest.fixture
def stranger(application):
    return _account(application, STRANGER)


# --- the script ------------------------------------------------------------

def test_an_empty_window_is_said_out_loud():
    """Silence is a bug the listener cannot tell apart from a broken player.
    'Nothing crossed a threshold' is information."""
    script = briefs.compose_script([])
    assert "Nothing crossed" in script
    assert script.strip().endswith("End of brief.")


def test_it_does_not_claim_nothing_happened():
    """No alert is not the same as no activity, and a brief that implies
    otherwise is making a claim the data does not support."""
    script = briefs.compose_script([])
    assert "not the same as nothing happening" in script


def test_every_number_in_the_script_comes_from_the_rows():
    alerts = [{"severity": "info", "canonical_name": "A", "title": "Moved", "body": ""},
              {"severity": "info", "canonical_name": "B", "title": "Moved", "body": ""}]
    script = briefs.compose_script(alerts, window_days=7)
    assert "There are 2 alerts." in script
    assert "covering the last 7 days" in script


def test_the_voice_does_not_repeat_itself():
    """A body that merely restates the title is dropped. A voice saying the
    same thing twice is how a listener stops paying attention."""
    line = briefs._speak_alert({"canonical_name": "Paper Cranes",
                                "title": "Editorial playlist add",
                                "body": "Editorial playlist add"})
    assert line.lower().count("editorial playlist add") == 1


def test_a_long_run_is_counted_not_recited():
    """A spoken list of forty artists is noise with a number in it."""
    many = [{"severity": "info", "canonical_name": "Artist %d" % i,
             "title": "Moved", "body": ""} for i in range(20)]
    script = briefs.compose_script(many)
    spoken = sum(1 for line in script.split("\n") if line.startswith("Artist "))
    assert spoken == briefs.MAX_SPOKEN_ITEMS
    assert "12 more" in script


def test_the_script_is_deterministic():
    alerts = [{"severity": "critical", "canonical_name": "X", "title": "Fell", "body": "Why"}]
    assert briefs.compose_script(alerts) == briefs.compose_script(alerts)


def test_an_alert_with_no_artist_still_reads_as_a_sentence():
    line = briefs._speak_alert({"canonical_name": "", "title": "Data source refreshed",
                                "body": ""})
    assert line == "Data source refreshed."


# --- the workflow ----------------------------------------------------------

def _seed_and_write(application, client):
    import signal_store as sstore
    with application.app_context():
        org = sstore.default_org()
        sstore.raise_alert(org["id"], "gap", "Streams fell 42 percent",
                           "One playlist removal.", severity="critical")
    resp = client.post("/signal/briefs/new", data={"window": "7"})
    assert resp.status_code in (301, 302), resp.get_data(as_text=True)[:300]
    return resp.headers["Location"].rstrip("/").split("/")[-1]


def test_a_written_brief_contains_the_real_alert_text(application, member):
    brief_id = _seed_and_write(application, member)
    with application.app_context():
        assert "42 percent" in briefs.get_brief(brief_id)["script"]


def test_the_brief_pages_are_retired_and_the_row_is_kept(application, member):
    """Audio Briefs left Signal's menu (owner, 2026-09-19: "bad, bad, bad
    from signal"); the list and detail pages land on the Signal dashboard
    and the brief row stays."""
    brief_id = _seed_and_write(application, member)
    for path in ("/signal/briefs", "/signal/briefs/%s" % brief_id):
        r = member.get(path)
        assert r.status_code == 302 and r.headers["Location"].rstrip("/").endswith("/signal"), path
    menu = member.get("/signal/").get_data(as_text=True)
    assert 'href="/signal/briefs"' not in menu and "Audio Briefs" not in menu
    with application.app_context():
        assert briefs.get_brief(brief_id) is not None


def test_speaking_produces_a_real_playable_file(application, member):
    brief_id = _seed_and_write(application, member)
    member.post("/signal/briefs/%s/speak" % brief_id)

    resp = member.get("/signal/briefs/%s/audio" % brief_id)
    assert resp.status_code == 200
    assert resp.get_data()[:4] == b"RIFF", "not a well-formed WAV"


def test_the_script_is_kept_beside_the_audio(application, member):
    """Audio cannot be skimmed, searched or quoted, or checked against its
    source without listening to all of it. The page that showed the script
    is retired (2026-09-19); the script stays on the row."""
    brief_id = _seed_and_write(application, member)
    member.post("/signal/briefs/%s/speak" % brief_id)
    with application.app_context():
        brief = briefs.get_brief(brief_id)
    assert "End of brief." in brief["script"] and brief["job_id"]


def test_speaking_twice_does_not_render_twice(application, member):
    """Speech is charged per character and the script cannot change."""
    import audio_store as astore

    brief_id = _seed_and_write(application, member)
    member.post("/signal/briefs/%s/speak" % brief_id)
    with application.app_context():
        first = briefs.get_brief(brief_id)["job_id"]
    member.post("/signal/briefs/%s/speak" % brief_id)
    with application.app_context():
        second = briefs.get_brief(brief_id)["job_id"]
        job = astore.get_job(None, second)
    assert first == second, "a second render was dispatched"
    assert job["attempts"] == 1


# --- tenancy ---------------------------------------------------------------

def test_a_non_member_cannot_fetch_the_audio(application, member, stranger):
    """The audio route is deliberately not a shareable URL: a brief names who
    an organisation is watching."""
    brief_id = _seed_and_write(application, member)
    member.post("/signal/briefs/%s/speak" % brief_id)

    resp = stranger.get("/signal/briefs/%s/audio" % brief_id)
    assert resp.status_code != 200, "a brief leaked to a non-member"


def test_a_signed_out_visitor_cannot_fetch_the_audio(application, member):
    brief_id = _seed_and_write(application, member)
    member.post("/signal/briefs/%s/speak" % brief_id)

    resp = application.test_client().get("/signal/briefs/%s/audio" % brief_id)
    assert resp.status_code != 200


def test_the_feature_is_absent_when_switched_off(application, member, monkeypatch):
    monkeypatch.delenv("SIGNAL_AUDIO_BRIEFS_ENABLED", raising=False)
    resp = member.post("/signal/briefs/new", data={"window": "7"})
    assert resp.status_code == 404
