"""The owner's own apps on other services, listed in the sidebar.

Noise Lab and The Room live on the v2 workflows service, REACH on its own;
each has its own login. They join the hubs as entries whose href is
absolute, and everything that renders a hub entry - the sidebar, the hub
desk tiles, the command palette - opens one in a new tab and says so.
They are real apps, not previews, so they are never badged Sample.
"""
import io
import os
import re

import pytest

import app as appmod
import hubs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTERNAL = {
    "noise-lab": ("studio", "https://street-banker-v2-workflows.onrender.com/noise-lab/"),
    "the-room": ("studio", "https://street-banker-v2-workflows.onrender.com/song-builder"),
    "reach": ("launch", "https://reach-9ub6.onrender.com/reach/"),
}


def _items():
    return {it[0]: (hkey, it) for hkey, _l, _d, items in hubs.HUBS for it in items}


@pytest.fixture(scope="module")
def artist():
    client = appmod.app.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def test_the_three_apps_are_hub_entries_with_https_hrefs():
    items = _items()
    for key, (hub, href) in EXTERNAL.items():
        assert key in items, key
        got_hub, (_k, got_href, icon, label, desc) = items[key]
        assert got_hub == hub and got_href == href
        assert href.startswith("https://")
        assert icon and label and desc
        assert hubs.get_hub(hub)["modules"]
    # Neighbours: after Audio Studio in Studio & Assets, after Press in Launch.
    studio = [it[0] for it in hubs.get_hub("studio")["modules"]]
    launch = [it[0] for it in hubs.get_hub("launch")["modules"]]
    assert studio[studio.index("audio-studio") + 1:][:2] == ["noise-lab", "the-room"]
    assert launch[launch.index("press-desk") + 1] == "reach"


def test_they_are_live_not_previews():
    for key in EXTERNAL:
        assert key in hubs.LIVE_KEYS and key in hubs.live_keys(), key


def test_the_sidebar_opens_each_in_a_new_tab_and_says_so(artist):
    body = artist.get("/command-center").get_data(as_text=True)
    for key, (_hub, href) in EXTERNAL.items():
        m = re.search(r'<a href="%s"([^>]*)>' % re.escape(href), body)
        assert m, key
        attrs = m.group(1)
        assert 'target="_blank"' in attrs and 'rel="noopener"' in attrs, key
        anchor = body[m.start():body.index("</a>", m.end())]
        assert "(opens in a new tab)" in anchor and 'class="sr-only"' in anchor, key
        assert "Sample" not in anchor, "a real app is not badged as sample data"
    # Internal links are untouched.
    m = re.search(r'<a href="/audio-studio"([^>]*)>', body)
    assert m and "_blank" not in m.group(1)


def test_the_hub_desk_tiles_open_them_in_a_new_tab(artist):
    for hub in ("studio", "launch"):
        body = artist.get("/desk/%s" % hub).get_data(as_text=True)
        for key, (h, href) in EXTERNAL.items():
            if h != hub:
                continue
            # The sidebar renders the same href; the tile is the one with data-live.
            m = re.search(r'<a href="%s"([^>]*data-live="([01])"[^>]*)>' % re.escape(href), body)
            assert m, key
            assert 'target="_blank"' in m.group(1) and 'rel="noopener"' in m.group(1), key
            assert m.group(2) == "1", "a real app is Live on the desk, not Preview"
            tile = body[m.start():body.index("</a>", m.end())]
            assert "(opens in a new tab)" in tile, key


def test_the_command_palette_lists_them_and_opens_a_new_tab():
    idx = {e["key"]: e for e in hubs.command_index()}
    for key, (_hub, href) in EXTERNAL.items():
        assert idx[key]["href"] == href and idx[key]["live"] is True, key
    base = io.open(os.path.join(HERE, "templates", "base.html"), encoding="utf-8").read()
    go = base[base.index("function go(item)"):base.index("function open()")]
    assert 'window.open(item.href, "_blank", "noopener")' in go


def test_no_page_ever_lights_an_external_entry(artist):
    """active_page is a route's own key; an outside app has no page here."""
    body = artist.get("/audio-studio").get_data(as_text=True)
    for _key, (_hub, href) in EXTERNAL.items():
        m = re.search(r'<a href="%s"[^>]*class="([^"]*)"' % re.escape(href), body)
        assert m and "font-semibold" not in m.group(1)
