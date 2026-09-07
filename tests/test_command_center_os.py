"""Overview and the Command Center in one window; the windows on the board.

The owner, 2026-09-07: "overview and command center need to be in the
same window as overview isnt in the navigation. the operating system
windows that show in command center need to be designed better."

So Overview is a tab of the Command Center front - same URL, one strip,
the sidebar lights Command Center while you read it - and the board's
windows are grouped the way the sidebar is, with one lamp and a dashed
edge only where a window is still a preview, the note clamped to two
lines and carried in full on hover, and each window's own caveat small
beneath it.
"""
import re

import command_center as cc
import hubs
from tests.test_app import _demo


def test_overview_is_a_tab_of_the_command_center_front():
    client = _demo()
    for path in ("/command-center", "/overview"):
        body = client.get(path).get_data(as_text=True)
        strip = body.split('class="sb-subnav"')[1].split("</nav>")[0] if 'class="sb-subnav"' in body else ""
        assert 'href="/command-center"' in strip and 'href="/overview"' in strip, path
    # While reading Overview, the sidebar lights Command Center, not a missing entry.
    body = client.get("/overview").get_data(as_text=True)
    assert re.search(r'href="/command-center"[^>]*class="[^"]*font-semibold', body)
    keys = {it[0] for _k, _l, _d, items in hubs.HUBS for it in items}
    assert "overview" not in keys and "command-center" in keys


def test_the_windows_are_grouped_like_the_sidebar_with_a_lamp_only_for_previews():
    client = _demo()
    body = client.get("/command-center").get_data(as_text=True)
    os_ = body.split('id="os"')[1]
    groups = cc.module_groups()
    names = [g for g, _ in groups]
    assert "Launch Engine" in names and "Royalty Sweep & Banking" in names
    assert names.index("Launch Engine") < names.index("Royalty Sweep & Banking"), "sidebar order"
    import html as _html
    heads = [_html.unescape(h) for h in re.findall(r'<h3 class="sb-label[^"]*" id="os-\d+">([^<]+)</h3>', os_)]
    assert heads == names, "the headings are the sidebar's groups, in the sidebar's order"
    # Every window, once, and nothing invented.
    routes = [m[0] for m in cc.MODULES]
    assert sorted(m[0] for _g, ms in groups for m in ms) == sorted(routes)
    for route in routes:
        assert os_.count('href="%s"' % route) == 1, route
    previews = [m for m in cc.MODULES if m[3] == "preview"]
    assert os_.count('sb-lamp sb-lamp--warn">preview</span>') == len(previews)
    assert os_.count("sb-mod--preview") == len(previews)
    assert "Preview — not wired up yet" not in body, "the sentence became a lamp"
    # The caveat is the window's own, small, beneath the note.
    assert '<p class="sb-mod-disc">Estimates only' in os_ and "not legal advice" in os_
    # The note rides on hover in full.
    assert 'title="Campaigns, pre-saves, fan capture, variants, QR, attribution."' in os_


def test_unlisted_routes_are_still_on_the_board():
    groups = dict(cc.module_groups([("/nowhere", "Nowhere", "A window no hub lists.", "live", None)]))
    assert groups == {cc.OTHER_GROUP: [("/nowhere", "Nowhere", "A window no hub lists.", "live", None)]}
    folded = dict(cc.module_groups([("/links/fans", "Fan CRM", "x", "live", None)]))
    assert "Community" in folded, "a folded route groups with its front"


def test_the_chrome_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "app-chrome.css"), encoding="utf-8").read()
    assert ".sb-mod--preview" in css and ".sb-mod-disc" in css and "-webkit-line-clamp: 2" in css
    base = open(os.path.join(here, "templates", "base.html"), encoding="utf-8").read()
    assert int(re.search(r"app-chrome\.css\?v=(\d+)", base).group(1)) >= 6
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 193
