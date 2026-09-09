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
