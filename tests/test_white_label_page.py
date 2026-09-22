"""Somewhere to read about white label.

Owner, 2026-09-22: "where is white label section located for someone to
view or read about?" The answer was nowhere. /resellers is the owner's own
admin screen and /partners is about the distribution partnership, so a
label wondering whether they could run this under their own name had
nothing to read at all.

The thing the page must not do is oversell it. Two pages keep naming the
operating entity however white the label is, and a buyer should read that
here rather than discover it after signing.
"""
import pytest

import hubs
import public_pages_config as pages


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    import app as appmod
    a = appmod.create_app()
    a.config.update(TESTING=True)
    return a, a.test_client()


def test_a_stranger_can_read_it(app_client):
    """The person who needs this has not signed up yet, so a login wall
    would hide it from exactly the people it is for."""
    _a, c = app_client
    r = c.get("/white-label")
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    assert "White label" in page
    assert "Run it as yours." in page


def test_it_says_up_front_what_stays_named_after_us(app_client):
    """Terms and privacy keep naming the operating entity. A buyer finding
    that out after signing would be a fair complaint."""
    _a, c = app_client
    page = c.get("/white-label").get_data(as_text=True)
    assert "What stays named after us" in page
    assert "terms" in page.lower() and "privacy" in page.lower()
    assert "rather tell you this up front" in page


def test_it_does_not_promise_what_is_not_built(app_client):
    """Every row says Live or Talk to us. A row claiming something that
    only happens by hand would be the page selling a settings screen that
    does not exist."""
    _a, c = app_client
    page = c.get("/white-label").get_data(as_text=True)
    assert "Your own domain" in page and "Talk to us" in page
    for _title, status, _body in pages.get_white_label()["current"]:
        assert status in ("Live", "Talk to us"), status


def test_it_quotes_no_price(app_client):
    """White label is sold as a conversation, and a price on a public page
    is a promise the checkout cannot keep yet."""
    page = c_page = c_text = None
    _a, c = app_client
    page = c.get("/white-label").get_data(as_text=True)
    import re
    assert not re.search(r"\$\s?\d", page), "no figure until the owner sets one"
    assert "what it costs" in page.lower()


def test_the_footer_carries_it_for_everyone(app_client):
    keys = {k for k, _h, _l in hubs.footer_links("artist")}
    assert "white-label" in keys
    assert "white-label" in {k for k, _h, _l in hubs.footer_links("")}


def test_the_link_in_the_footer_actually_opens(app_client):
    _a, c = app_client
    href = dict((k, h) for k, h, _l in hubs.footer_links("artist"))["white-label"]
    assert c.get(href).status_code == 200


def test_it_is_not_the_owners_admin_screen(app_client):
    """/resellers manages tenants and is owner-only; this one only explains."""
    _a, c = app_client
    assert c.get("/resellers").status_code in (302, 404)
    assert c.get("/white-label").status_code == 200
