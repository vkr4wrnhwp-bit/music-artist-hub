"""Advertised upload caps have to be caps this app can actually honour.

Werkzeug rejects an oversize request before routing, so any cap the app prints
above app.config["MAX_CONTENT_LENGTH"] is a number it never enforces. The Remix
Lab offered 250 MB and the Audio Studio 200 MB against a 25 MB ceiling: adding
a normal WAV master produced a bare "Request Entity Too Large / The data value
transmitted exceeds the capacity limit" - no sentence, no limit, no way back.
"""
import io
import uuid

import pytest


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


def test_every_advertised_cap_is_one_the_server_will_accept(application):
    """The rule, checked against all of them at once so a new module cannot
    quietly advertise a number the front door rejects."""
    import audio_desk
    import audio_studio
    import db as store
    import remix_lab_config
    import stemsplit_provider
    import tour_os

    ceiling = application.config["MAX_CONTENT_LENGTH"]
    advertised = {
        "remix_lab_config.UPLOAD_MAX_MB": remix_lab_config.UPLOAD_MAX_MB * 1024 * 1024,
        "audio_studio.MAX_UPLOAD_BYTES": audio_studio.MAX_UPLOAD_BYTES,
        "audio_desk.MAX_MEETING_BYTES": audio_desk.MAX_MEETING_BYTES,
        "db.MAX_BEAT_BYTES": store.MAX_BEAT_BYTES,
        "stemsplit_provider.MAX_UPLOAD": stemsplit_provider.MAX_UPLOAD,
        "tour_os.MAX_UPLOAD": tour_os.MAX_UPLOAD,
    }
    for name, value in advertised.items():
        assert value <= ceiling, (
            "%s advertises %d MB against a %d MB ceiling - Werkzeug rejects "
            "the request before the handler runs, so that number is printed "
            "and never enforced" % (name, value // (1024 * 1024),
                                    ceiling // (1024 * 1024)))


def test_the_ceiling_clears_a_full_length_wav_master(application):
    """Ten minutes of 44.1 kHz / 16-bit stereo is about 100 MB, and that is an
    ordinary thing to drop into the Remix Lab or the Rack."""
    assert application.config["MAX_CONTENT_LENGTH"] >= 105 * 1024 * 1024


def _artist(application):
    email = "up-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "A", "email": email,
                                 "password": "up-pass-123"})
    client.post("/login", data={"email": email, "password": "up-pass-123"})
    return client


def _oversize(application, client, **kwargs):
    over = application.config["MAX_CONTENT_LENGTH"] + 1024
    return client.post("/vault/upload",
                       data={"file": (io.BytesIO(bytes(over)), "master.wav")},
                       content_type="multipart/form-data", **kwargs)


def test_an_oversize_upload_is_explained_rather_than_dumped(application):
    """What the artist saw was the server's own error text. This is the only
    place that can replace it: no route body runs for a rejected request."""
    response = _oversize(application, _artist(application))

    assert response.status_code == 413
    body = response.get_data(as_text=True)
    assert "too large" in body.lower()
    assert "MB" in body
    assert "Request Entity Too Large" not in body


def test_a_json_endpoint_gets_json_back(application):
    """An XHR upload handed an HTML error page reports a parse failure, which
    sends whoever is debugging it somewhere else entirely."""
    response = _oversize(application, _artist(application),
                         headers={"X-Requested-With": "XMLHttpRequest"})

    assert response.status_code == 413
    assert response.get_json()["max_mb"] == (
        application.config["MAX_CONTENT_LENGTH"] // (1024 * 1024))
