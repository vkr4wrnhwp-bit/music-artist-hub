"""The Artist Twin's "Save as EPK bio" wiped the press kit.

It posted {bio} alone to /epk/save, the editor's whole-kit save, and the
saved tagline, genres, location, socials, contacts and press quotes were
replaced by nothing (audit, 2026-09-26). The Twin now posts to /epk/bio,
which changes the bio and keeps everything else.
"""
import io
import os
import uuid

import pytest

import db as store
from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "twin-bio-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "twinbio-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Bio", "email": email, "password": PW})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _saved(client):
    with client._app.app_context():
        return (store.get_epk(client._uid) or {}).get("data") or {}


def test_the_twin_bio_keeps_the_rest_of_the_press_kit(artist):
    kit = {"tagline": "Night drives, loud", "bio": "Old bio.", "location": "Charlotte",
           "genres": "hip hop, soul",
           "socials": {"instagram": "@nightdrive"},
           "contact": {"booking": "book@example.net"},
           "press": [{"quote": "A real one", "source": "The Paper", "url": ""}]}
    assert artist.post("/epk/save", json=kit).get_json()["ok"]
    before = _saved(artist)
    r = artist.post("/epk/bio", json={"bio": "New bio from the Twin."})
    assert r.status_code == 200 and r.get_json()["ok"]
    after = _saved(artist)
    assert after["bio"] == "New bio from the Twin."
    for key in ("tagline", "location", "genres", "socials", "contact", "press"):
        assert after.get(key) == before.get(key), key


def test_the_bio_door_needs_a_bio_and_a_signed_in_artist(artist):
    assert artist.post("/epk/bio", json={"bio": "  "}).status_code == 400
    assert create_app().test_client().post("/epk/bio", json={"bio": "x"}).status_code == 401


def test_the_bio_is_capped_like_the_editor(artist):
    artist.post("/epk/bio", json={"bio": "b" * 5000})
    assert len(_saved(artist)["bio"]) == 1200


def test_the_twin_page_posts_to_the_bio_door_not_the_whole_kit_save():
    t = io.open(os.path.join(HERE, "templates", "artist_twin.html"), encoding="utf-8").read()
    push = t.split('getElementById("push-epk")', 1)[1].split("});", 1)[0]
    assert 'fetch("/epk/bio"' in push and '"/epk/save"' not in push
