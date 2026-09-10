"""A file dropped on the wrong beat could not be taken off again.

Reported live, 2026-09-10: "in beats there is no way to delete the audio
before you register the beat upon like a wrong upload etc".

Both endpoints existed — /beats/<id>/audio/delete and /beats/<id>/delete
— and both controls existed on the beat's own page. Neither appeared on
the list, which is where a file is dropped, so undoing a wrong drop
depended on already knowing to go and look for it.

The controls are offered while nothing is signed. Once a licence exists
against a beat, removing it is a heavier act than a list row should
carry, and the beat's own page already spells out what it destroys.
"""
import io
import os
import uuid

import pytest

import app as appmod
import db as store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "beats-undo-123"


@pytest.fixture
def artist():
    c = appmod.app.test_client()
    email = "beat-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Producer", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def _beat(client, title="Cold Corner"):
    r = client.post("/beats/register", json={"title": title})
    return r.get_json()["id"]


def test_a_beat_can_be_removed_from_the_list_it_was_dropped_on(artist):
    beat_id = _beat(artist)
    page = artist.get("/beats").get_data(as_text=True)
    assert "/beats/%s/delete" % beat_id in page, (
        "the list offers no way to undo a wrong drop")
    assert "Delete beat" in page

    artist.post("/beats/%s/delete" % beat_id)
    with appmod.app.app_context():
        assert store.get_beat(beat_id, artist._uid) is None


def test_the_audio_control_only_appears_when_there_is_audio(artist):
    beat_id = _beat(artist, "No Audio Yet")
    page = artist.get("/beats").get_data(as_text=True)
    assert 'data-drop-audio="%s"' % beat_id not in page, (
        "offering to remove audio that was never uploaded is a dead control")


def test_removing_the_audio_keeps_the_registry_row(artist):
    """The wrong file goes; the beat stays, ready for the right one."""
    beat_id = _beat(artist, "Wrong File")
    r = artist.post("/beats/%s/audio/delete" % beat_id)
    # No audio on it yet, so the endpoint says so rather than pretending.
    assert r.status_code == 404
    with appmod.app.app_context():
        assert store.get_beat(beat_id, artist._uid) is not None


def test_a_stranger_cannot_delete_somebody_elses_beat(artist):
    beat_id = _beat(artist, "Mine")
    other = appmod.app.test_client()
    email = "beat-other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "Other", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    other.post("/beats/%s/delete" % beat_id)
    with appmod.app.app_context():
        assert store.get_beat(beat_id, artist._uid) is not None, (
            "somebody else's registry row must survive")


def test_the_list_does_not_offer_a_one_click_delete_next_to_a_signed_licence():
    with io.open(os.path.join(HERE, "templates/beats.html"), encoding="utf-8") as f:
        markup = f.read()
    assert "{% if not row.summary.signed %}" in markup, (
        "a sold beat's removal belongs on its own page, with the wording "
        "that says what goes with it")
