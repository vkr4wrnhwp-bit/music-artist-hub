"""Two more tabs that were anchors to the foot of their own page.

The route walk of 2026-09-12 found the same shape the Calendar tab had:
"Track Passports" on /catalog and "Contracts & licences" on /vault each
pointed at #section at the end of the page they were already on. A tab
is a view; each now opens on its own section alone.
"""
import uuid

import pytest

import app as appmod
import db as store

PASSWORD = "views-pass-12345"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    email = "views-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Views", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    return client


def test_the_passports_tab_is_a_view(artist):
    body = artist.get("/catalog").get_data(as_text=True)
    assert 'href="/catalog?view=passports"' in body
    assert 'href="/catalog#passports"' not in body
    view = artist.get("/catalog?view=passports").get_data(as_text=True)
    assert 'id="passports"' in view
    assert 'id="identifiers"' not in view, "the catalog's own sections belong to the other view"
    assert 'aria-current="page"' in view.split('href="/catalog?view=passports"')[1][:120]


def test_the_contracts_tab_is_a_view(artist):
    body = artist.get("/vault").get_data(as_text=True)
    assert 'href="/vault?view=contracts"' in body
    assert 'href="/vault#contracts"' not in body
    view = artist.get("/vault?view=contracts").get_data(as_text=True)
    assert 'id="contracts"' in view
    assert "The Archive Drawer" not in view, "the files view belongs to the other tab"


def test_nothing_left_links_at_the_old_anchors():
    import glob
    import io as _io
    hits = []
    for path in glob.glob("templates/**/*.html", recursive=True) + ["app.py"]:
        text = _io.open(path, encoding="utf-8").read()
        for needle in ('"/catalog#passports"', '"/vault#contracts"', '"/releases/autopilot#calendar"'):
            if needle in text:
                hits.append((path, needle))
    assert hits == []
