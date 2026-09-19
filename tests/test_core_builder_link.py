"""Core, the template builder new suites are made from, sits in the
owner's Internal tools and nowhere else.

Owner, 2026-09-17: "add this into the street banker back side owner
account, it's a template for making new suites".
"""
import re
import uuid

import pytest

import app as appmod

PASSWORD = "core-link-pass-1"


def _signed_client(email, name):
    client = appmod.app.test_client()
    client.post("/signup", data={"name": name, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def _internal_footer(client):
    body = client.get("/vault").get_data(as_text=True)
    if ">Internal<" not in body:
        return ""
    return body.split(">Internal<", 1)[1].split("</nav>", 1)[0]


def test_the_owner_sees_the_core_builder_in_a_new_tab(monkeypatch):
    email = "core-owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    monkeypatch.delenv("CORE_BUILDER_URL", raising=False)
    footer = _internal_footer(_signed_client(email, "Core Owner"))
    m = re.search(r'<a href="(https://street-banker-core-builder\.onrender\.com/)"([^>]*)>', footer)
    assert m, "the owner's Internal tools carry the Core builder"
    assert 'target="_blank"' in m.group(2) and 'rel="noopener"' in m.group(2)
    anchor = footer[m.start():footer.index("</a>", m.end())]
    assert "Core builder" in anchor and "(opens in a new tab)" in anchor


def test_the_address_comes_from_the_environment(monkeypatch):
    email = "core-owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    monkeypatch.setenv("CORE_BUILDER_URL", "https://core.streetbankermusic.com/")
    footer = _internal_footer(_signed_client(email, "Core Owner"))
    assert 'href="https://core.streetbankermusic.com/"' in footer


def test_an_artist_never_sees_it(monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", "somebody-else@example.net")
    email = "core-artist-%s@example.net" % uuid.uuid4().hex[:8]
    client = _signed_client(email, "Plain Artist")
    body = client.get("/vault").get_data(as_text=True)
    assert "Core builder" not in body and "street-banker-core-builder" not in body
