# -*- coding: utf-8 -*-
"""Two directory lines that said more than anyone has checked.

Light Designer said "real DMX out to an ENTTEC interface". The Web Serial
DMX path is in the code, but no run on a real ENTTEC interface is recorded
anywhere (docs/FEATURE-LEDGER.md has no hardware test), and it needs the
member's own USB interface and a Chromium browser. The line now says what
it takes, and drops "real" until the owner has run one cue list on a real
interface.

Distribution listed "Direct platform connections from Street Banker: Coming
soon". Nothing in the code plans it; delivery goes through the partner. The
row now says "Not offered", which is true whatever the owner decides about
the future (make-real brief, 2026-09-23).
"""
import re

import pytest

import app as appmod


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def test_the_light_designer_directory_line_says_what_it_needs():
    import command_center as cc

    blurb = cc.MODULE_BY_ROUTE["/lights"][2]
    assert "real DMX" not in blurb
    assert "bring your own USB interface" in blurb
    assert "Chrome or Edge" in blurb
    assert "—" not in blurb


def test_the_light_designer_sidebar_line_drops_real():
    import hubs

    lines = [desc for _hub, _name, _tag, items in hubs.HUBS
             for key, _href, _icon, _label, desc in items if key == "lights"]
    assert lines
    for desc in lines:
        assert "real DMX" not in desc
        assert "ENTTEC" in desc


def test_the_distribution_page_no_longer_says_coming_soon(flask_app):
    body = flask_app.test_client().get("/distribution").get_data(as_text=True)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    assert "Coming soon" not in text
    assert "Direct platform connections from Street Banker Not offered" in text
