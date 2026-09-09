"""The Pulse search button looked dead, and the page blamed the typist.

Live, 2026-09-09: Spotify was answering `invalid_client: Invalid client
secret`, `search_artists` swallowed it, the route said ok with an empty
list, and the page said "No artists found - check the spelling." The
owner could not complete the one-time setup that gates the whole page,
and nothing on screen pointed at the credential.
"""
import json
import uuid

import pytest

import app as appmod
import spotify_provider as sp

PASSWORD = "pulse-honesty-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def client(application):
    c = application.test_client()
    email = "pulse-%s@example.net" % uuid.uuid4().hex[:10]
    c.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    return c


class _Refused(Exception):
    def read(self):
        return json.dumps({"error": "invalid_client",
                           "error_description": "Invalid client secret"}).encode()


def test_a_refused_credential_is_reported_as_spotifys_not_as_a_typo(client, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "wrong")
    monkeypatch.setattr(sp, "app_token", lambda: (_ for _ in ()).throw(_Refused()))
    answer = client.get("/pulse/search?q=devora").get_json()
    assert answer["ok"] is True and answer["results"] == []
    assert answer["refused"] == "Invalid client secret"
    assert sp.last_refusal() == "Invalid client secret"


def test_no_credentials_names_the_two_variables(client, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    answer = client.get("/pulse/search?q=devora").get_json()
    assert answer["results"] == []
    assert "SPOTIFY_CLIENT_ID" in answer["refused"] and "SPOTIFY_CLIENT_SECRET" in answer["refused"]


def test_a_real_miss_still_reads_as_a_miss(client, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "right")
    monkeypatch.setattr(sp, "app_token", lambda: "tok")
    monkeypatch.setattr(sp, "_api", lambda path, token: {"artists": {"items": []}})
    answer = client.get("/pulse/search?q=zzzzzz").get_json()
    assert answer["results"] == [] and answer["refused"] == "", (
        "nothing refused: the page may say check the spelling")


def test_the_page_prints_whichever_it_was(client):
    body = client.get("/pulse").get_data(as_text=True)
    assert "Spotify refused this app's credentials: " in body
    assert "No artists found" in body


def test_a_number_spotify_did_not_send_is_not_a_zero(monkeypatch):
    """Live, 2026-09-09: the owner picked King 810 and Artist Pulse read
    "SPOTIFY FOLLOWERS 0" and "POPULARITY 0/100" beside a working Deezer
    count of 9,579. Spotify omits those fields for some apps, and
    `.get("total", 0)` turned the silence into a number - a wrong claim
    about the artist, and the one figure that tells two same-named
    profiles apart in the picker."""
    import spotify_provider as sp
    assert sp._count(None) is None
    assert sp._count(0) == 0, "a real nought is still a nought"
    assert sp._count(104233) == 104233

    monkeypatch.setattr(sp, "pulse_configured", lambda: True)
    monkeypatch.setattr(sp, "app_token", lambda: "t")
    monkeypatch.setattr(sp, "_api", lambda path, token: {"artists": {"items": [
        {"id": "a1", "name": "King 810"},                      # no followers key at all
        {"id": "a2", "name": "Other", "followers": {"total": 12}, "popularity": 7},
    ]}})
    rows = sp.search_artists("king 810")
    assert rows[0]["followers"] is None and rows[0]["popularity"] is None
    assert rows[1]["followers"] == 12 and rows[1]["popularity"] == 7


def test_a_snapshot_can_say_not_measured(tmp_path, monkeypatch):
    """The columns were NOT NULL DEFAULT 0, so the only way to record
    "Spotify sent nothing" was to record a nought - and once the provider
    started returning None, writing it would have broken the page."""
    import db as store
    store.record_pulse_snapshot("u-notmeasured", None, None, 9579)
    rows = [r for r in store.list_pulse_snapshots("u-notmeasured")]
    assert rows and rows[-1]["followers"] is None and rows[-1]["popularity"] is None
    assert rows[-1]["deezer_fans"] == 9579, "the number that WAS measured is kept"
