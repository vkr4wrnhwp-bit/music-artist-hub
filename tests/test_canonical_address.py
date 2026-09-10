"""The homepage told the world it lived at its hosting URL.

Live, 2026-09-10: the app is served at app.streetbankermusic.com, and
its homepage carried

    <link rel="canonical" href="https://street-banker.onrender.com/">

plus og:url and og:image on the same host. Written into the markup, so
no environment variable could correct it. Two costs, both on the front
door: search engines are told to index the hosting address rather than
the brand, and every share of the real domain previews as onrender.com.

The address is derived now. A host written into markup cannot follow the
site when it moves, and it moved.
"""
import io
import os

import pytest


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.streetbankermusic.com")
    import importlib

    import app as appmod
    importlib.reload(appmod)
    return appmod.app


def test_the_homepage_names_the_address_it_is_served_on(application):
    html = application.test_client().get("/").get_data(as_text=True)
    assert '<link rel="canonical" href="https://app.streetbankermusic.com/">' in html
    assert 'og:url" content="https://app.streetbankermusic.com/"' in html
    assert 'og:image" content="https://app.streetbankermusic.com/static/' in html


def test_no_host_is_written_into_the_markup():
    """The whole defect: a hardcoded host cannot be corrected by config."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with io.open(os.path.join(here, "templates/landing.html"),
                 encoding="utf-8") as f:
        markup = f.read()
    assert "onrender.com" not in markup, (
        "the homepage names a specific host again; it will be wrong the "
        "next time the site moves")


def test_the_address_follows_the_setting(monkeypatch):
    """Set it somewhere else and the page says somewhere else."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test")
    import importlib

    import app as appmod
    importlib.reload(appmod)
    html = appmod.app.test_client().get("/").get_data(as_text=True)
    assert 'canonical" href="https://example.test/"' in html
    assert "streetbankermusic" not in html


def test_every_public_link_is_built_from_the_same_setting():
    """Reset links, rider links, tour shares and Press Desk links are all
    pasted into messages and read later. They must not name a host the
    homepage has stopped naming."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with io.open(os.path.join(here, "app.py"), encoding="utf-8") as f:
        src = f.read()
    assert 'PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL")' in src, (
        "one setting decides the address everywhere, or they drift apart")
