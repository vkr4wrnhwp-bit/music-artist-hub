# -*- coding: utf-8 -*-
"""The Press Desk promises only what the journalist's page shows.

Three places said an announcement's page carries "the audio, the artwork and
the details": the Announcements intro, the default pitch body (which goes
out to journalists), and the public page's own kit button ("Press kit,
photos and audio"). The page a journalist opens (press_release_public.html)
has never drawn an image or an audio player, and an announcement has no
link to any audio or artwork on file: the owner's announcement desk
(2026-09-20) has no field for either (overclaims list, 2026-09-11, item 15).

Attaching them means adding two pickers to a page the owner designed, which
is his call, so the words change now and the pickers wait for him. The
coupling test below keeps the promise and the page in step: the day the
public page draws an <audio> or an <img>, the intro may say so again.
"""
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import press_desk
import press_store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "templates", "press_release_public.html")


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _artist(flask_app):
    email = "pp-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Press Artist", "email": email,
                                 "password": "pp-pass-123"})
    client.post("/login", data={"email": email, "password": "pp-pass-123"})
    return client, store.get_user_by_email(email)


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _public_page(flask_app, epk_url="https://example.com/kit"):
    client, user = _artist(flask_app)
    client.post("/press-desk/contacts/new", data={
        "name": "Dee Okafor", "outlet": "Nightdrive Mag", "role": "Writer",
        "email": "dee-%s@example.com" % uuid.uuid4().hex[:6]})
    client.post("/press-desk/announcements/new", data={
        "kind": "Single", "headline": "The band announces Nightdrive",
        "body": "The news.", "listen_url": "https://example.com/listen",
        "epk_url": epk_url})
    release = press_store.list_releases(user["id"])[0]
    ids = [c["id"] for c in press_store.list_contacts(user["id"])]
    client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": ids,
        "subject": press_desk.DEFAULT_SUBJECT, "body": press_desk.DEFAULT_BODY,
        "mode": press_store.MODE_OWN_INBOX})
    pitch = press_store.list_pitches(user["id"])[0]
    recipient = press_store.pitch_recipients(user["id"], pitch["id"])[0]
    page = flask_app.test_client().get("/press/%s" % recipient["token"])
    assert page.status_code == 200
    return client, recipient, page.get_data(as_text=True)


def test_the_announcements_intro_no_longer_promises_audio_or_artwork(flask_app):
    client, _user = _artist(flask_app)
    body = _text(client.get("/press-desk/announcements").get_data(as_text=True))
    assert "with the audio, the artwork" not in body
    assert "Each one becomes a page a journalist can open, with the details and your links." in body


def test_the_intro_promises_only_what_the_public_page_draws(flask_app):
    """The coupling: a promise of audio needs an <audio> on the page, a
    promise of artwork needs an <img>."""
    public = open(PUBLIC, encoding="utf-8").read()
    client, _user = _artist(flask_app)
    intro = _text(client.get("/press-desk/announcements").get_data(as_text=True)).lower()
    if "<audio" not in public:
        assert "the audio" not in intro
    if "<img" not in public:
        assert "the artwork" not in intro


def test_the_default_pitch_does_not_tell_a_journalist_the_audio_is_there():
    assert "the audio" not in press_desk.DEFAULT_BODY
    assert "the artwork" not in press_desk.DEFAULT_BODY
    assert "{link}" in press_desk.DEFAULT_BODY


def test_a_sent_pitch_carries_the_honest_line(flask_app):
    _client, recipient, _page = _public_page(flask_app)
    assert "the audio, the artwork" not in recipient["body"]
    assert "The announcement, the details and the links are here:" in recipient["body"]


def test_the_public_kit_button_names_the_link_not_its_contents(flask_app):
    """The kit link is whatever address the artist typed; nothing checks
    it holds photos or audio."""
    _client, _recipient, page = _public_page(flask_app)
    assert "Press kit, photos and audio" not in page
    assert ">Press kit</a>" in page
