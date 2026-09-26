# -*- coding: utf-8 -*-
"""Artist Twin is labelled for what it is: template-built drafts.

artist_twin.generate() fills templates from the sources the artist approves;
no model writes anything. The labels said otherwise: "AI Artist Twin" on the
start page, "A private writing agent" in the directory, "Your Private
Writing Agent" as the page heading, and "The strategist read on your next
best moves" in the sidebar (make-real brief, 2026-09-23). Putting a model
behind generate() would make each draft cost money, which is the owner's
decision, so until he makes it the labels say "built from templates".
"""
import re
import uuid

import pytest

import app as appmod


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _artist(flask_app):
    email = "tw-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Twin Artist", "email": email,
                                 "password": "tw-pass-123"})
    client.post("/login", data={"email": email, "password": "tw-pass-123"})
    return client


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_the_page_heading_is_not_a_writing_agent(flask_app):
    body = _text(_artist(flask_app).get("/artist-twin").get_data(as_text=True))
    assert "Private Writing Agent" not in body
    assert "Drafts from your own data" in body
    assert "Built from templates" in body


def test_the_directory_line_says_template_built():
    import command_center as cc

    _route, _name, blurb, _status, _disc = cc.MODULE_BY_ROUTE["/artist-twin"]
    assert "writing agent" not in blurb
    assert "built from templates" in blurb


def test_the_sidebar_line_says_template_built():
    import hubs

    lines = [desc for _hub, _name, _tag, items in hubs.HUBS
             for key, _href, _icon, _label, desc in items if key == "artist-twin"]
    assert lines, "the Artist Twin entry left the sidebar"
    for desc in lines:
        assert "strategist read on your next best moves" not in desc
        assert "Template-built" in desc


def test_the_start_page_label_does_not_say_ai(flask_app):
    body = flask_app.test_client().get("/artist-twin/start").get_data(as_text=True)
    assert '<div class="sb-label text-sb-gold">AI Artist Twin</div>' not in body
    assert '<div class="sb-label text-sb-gold">Artist Twin</div>' in body


def test_generate_is_still_the_template_path(flask_app):
    """The label is only honest while this is true. When a model goes behind
    generate(), this test and the labels change together."""
    import artist_twin

    with flask_app.app_context():
        facts, _used = artist_twin.gather_context("nobody-%s" % uuid.uuid4().hex, set())
    facts["name"] = "Nova"
    text = artist_twin.generate("bio_snippet", facts, "premium", [])
    again = artist_twin.generate("bio_snippet", facts, "premium", [])
    assert text == again           # deterministic: a template, not a model
    assert text.startswith("Nova is building something deliberate.")
