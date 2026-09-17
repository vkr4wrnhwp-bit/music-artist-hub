"""The owner's own apps on other services, listed in the sidebar.

Noise Lab, The Room, REACH and Tour are suites on their own services. They
no longer have their own login: each link goes through /suites/go/<key>,
where Street Banker, the account of record, hands the signed-in artist
across (sb_suite_sso). Motion is still a plain link. They join the hubs as entries whose href is
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
    "reach": ("launch", "/suites/go/reach"),
    "masterclip": ("studio", "/suites/go/motion"),
    "tour-suite": ("stage", "/suites/go/tour"),
}

# Two suites that are no longer hub entries at all: their own products with
# their own sign-in, on the suites strip only (owner, 2026-09-15: "remove
# noise lab and the room from studio").
STRIP_ONLY = {
    "noise-lab": "/suites/go/noise-lab",
    "the-room": "/suites/go/the-room",
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
        assert href.startswith(("https://", "/suites/go/"))
        assert icon and label and desc
        assert hubs.get_hub(hub)["modules"]
    # Neighbours: Motion after Audio Studio in Studio & Assets, REACH after
    # Press in Launch. The Room and Noise Lab are not hub entries at all.
    studio = [it[0] for it in hubs.get_hub("studio")["modules"]]
    launch = [it[0] for it in hubs.get_hub("launch")["modules"]]
    assert "noise-lab" not in studio and "the-room" not in studio
    assert studio[studio.index("audio-studio") + 1] == "masterclip"
    assert launch[launch.index("press-desk") + 1] == "reach"


def test_they_are_live_not_previews():
    for key in list(EXTERNAL) + list(STRIP_ONLY):
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


def test_the_tool_suites_strip_lists_every_off_site_app(artist):
    """The owner's model (2026-09-15): Street Banker is the desk, the
    off-site apps are its tool suites. They get a strip of their own under
    every signed-in page, read from the same entries the rooms read."""
    assert [k for k, *_ in hubs.tool_suites()] == ["noise-lab", "the-room", "masterclip", "reach", "tour-suite", "company", "artifacts"]
    body = artist.get("/vault").get_data(as_text=True)
    strip = body.split('id="sb-tool-suites"')[1].split("</footer>")[0]
    for key, (_hub, href) in EXTERNAL.items():
        assert 'href="%s"' % href in strip and 'target="_blank"' in strip, key
    for key, href in STRIP_ONLY.items():
        assert 'href="%s"' % href in strip, key
    assert "Tool suites" in strip and "(opens in a new tab)" in strip
    assert "Sample" not in strip
    # Company and Artifacts wait for their addresses: on the strip, marked
    # Soon, opening the Command Center in this tab (owner, 2026-09-15).
    for pending in ("Company", "Artifacts"):
        m = re.search(r'<a href="/command-center"[^>]*title="The %s[^"]*"([^>]*)>' % pending.lower(), strip)
        assert m and "_blank" not in m.group(1), pending
    assert strip.count(">Soon<") == 2


def test_the_strip_draws_every_suite_as_one_system(artist):
    """Owner, 2026-09-17: "fix the images in the footer to be the same size and
    look". Every suite is the same bracket frame and two-letter monogram in
    its own colour, with its name beside it; none is a differently built image."""
    assert set(hubs.SUITE_MARKS) == {"noise-lab", "the-room", "masterclip", "reach", "tour-suite", "company", "artifacts"}
    assert len({c for _m, c in hubs.SUITE_MARKS.values()}) == len(hubs.SUITE_MARKS)
    labels = {k: label for k, _h, _i, label, _d in hubs.tool_suites()}
    body = artist.get("/vault").get_data(as_text=True)
    strip = body.split('id="sb-tool-suites"')[1].split("</footer>")[0]
    assert "<img" not in strip
    frames = re.findall(r'<svg class="h-10 w-12 shrink-0" viewBox="0 0 48 40"[^>]*>\s*<path d="([^"]+)"/>', strip)
    assert len(frames) == len(hubs.SUITE_MARKS) and len(set(frames)) == 1
    for key, (letters, colour) in hubs.SUITE_MARKS.items():
        assert re.search(r'fill="%s" stroke="none">%s</text>\s*</svg>\s*%s' % (re.escape(colour), letters, re.escape(labels[key])), strip), key
