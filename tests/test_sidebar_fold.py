"""The sidebar audit, held.

52 entries became 37 without losing a page: four parked off the sidebar
with their code kept (Capital, Benchmark, Funding, Conflicts - invented or
illustrative figures, waiting for a real provider), fifteen folded into
five tabbed fronts (Income by type, Royalty Lanes, Scores, Deals, Press),
and Reports - five real export routes - finally badged live.
"""
import io
import os
import re

import pytest

import app as appmod
import hubs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARKED = {"/capital": "Simulated demo", "/benchmark": "illustrative",
          "/funding": "illustrative", "/conflicts": "Disputes",
          "/fan-label": "placeholders", "/network": "sample profiles"}
FOLDED = {
    "/publishing": "income", "/mechanicals": "income", "/neighboring-rights": "income",
    "/territories": "income",
    "/money-queue": "royalty-lanes",
    "/trust-score": "scores", "/insights": "scores", "/qualification": "scores",
    "/sync/deal-simulator": "deals", "/sync/clearance-packs": "deals", "/deal-room": "deals",
    "/epk": "press-desk", "/artist-profile": "press-desk",
    # Tier C, folded the same day.
    "/releases": "autopilot", "/documents": "vault", "/tracks": "catalog",
    # Fans, one front (2026-09-06).
    "/fans": "fans", "/links/fans": "fans", "/fan-club": "fans",
    # Overview under the Command Center front (2026-09-07).
    "/overview": "command-center",
}


def _entries():
    return [it for _k, _l, _d, items in hubs.HUBS for it in items]


def test_the_sidebar_is_thirty_seven_entries():
    # HUBS only; the Community and Account groups are counted by hubs.py's
    # own group walk. Fans lost two entries there (Fan Label parked, Fan
    # Club folded into the Fans front) without touching this number.
    # 33 after Overview folded under Command Center; 34 with Stage Plot
    # back under the Live Stage Suite (owner, both 2026-09-07). 37 with the
    # owner's three outside apps - Noise Lab, The Room, REACH - each on its
    # own Render service and opened in a new tab (2026-09-08).
    assert len(_entries()) == 37


def test_nothing_parked_or_folded_is_a_sidebar_entry():
    hrefs = {it[1] for it in _entries()}
    for href in list(PARKED) + [h for h in FOLDED if h not in ("/publishing", "/qualification", "/deal-room", "/fans")]:
        if href in ("/releases",):
            continue          # /releases is the calendar's URL; the front is /releases/autopilot
        assert href not in hrefs, href
    keys = {it[0] for it in _entries()}
    for key in ("capital", "benchmark", "funding", "conflicts", "epk", "profile", "mechanicals",
                "neighboring", "territories", "money-queue", "trust-score", "insights",
                "connections", "deal-simulator", "sync-packs", "releases", "documents", "tracks",
                "fan-label", "fan-club-admin", "network", "overview"):
        assert key not in keys, key
    for key in ("income", "scores", "deals", "royalty-lanes", "press-desk", "reports"):
        assert key in keys, key
    community = {it[0] for it in hubs.COMMUNITY_GROUP[1]} | {it[0] for it in hubs.ACCOUNT_GROUP[1]}
    assert "fans" in community and "fan-label" not in community and "fan-club-admin" not in community
    assert "network" not in community


def test_the_fronts_are_live_and_reports_is_no_longer_a_sample():
    live = set(hubs.live_keys())
    for key in ("income", "scores", "deals", "royalty-lanes", "press-desk", "reports", "fans"):
        assert key in live, key
    for gone in ("capital", "benchmark", "funding", "conflicts", "fan-label", "fan-club-admin"):
        assert gone not in live


@pytest.fixture(scope="module")
def demo():
    client = appmod.app.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def test_every_parked_page_still_answers_and_says_it_is_parked(demo):
    for href, word in PARKED.items():
        body = demo.get(href).get_data(as_text=True)
        assert "Parked." in body and word in body, href
        assert 'href="%s"' % href not in body.split('id="main"')[0] if 'id="main"' in body else True


def test_every_folded_page_answers_and_carries_its_strip(demo):
    for href, front in FOLDED.items():
        r = demo.get(href)
        assert r.status_code == 200, href
        body = r.get_data(as_text=True)
        assert 'class="sb-subnav"' in body or 'class="pd-bar"' in body, href
        assert 'aria-current="page"' in body or "pd-btn" in body, href


def test_a_folded_page_lights_its_front_in_the_sidebar(demo):
    body = demo.get("/trust-score").get_data(as_text=True)
    assert 'href="/qualification"' in body
    on = re.search(r'href="/qualification"[^>]*class="[^"]*font-semibold', body)
    assert on, "Scores should be the highlighted entry while reading Trust"


def test_the_press_desk_strip_reaches_the_kit_and_the_one_sheet(demo):
    body = demo.get("/press-desk").get_data(as_text=True)
    assert 'href="/epk"' in body and 'href="/artist-profile"' in body
    kit = demo.get("/epk").get_data(as_text=True)
    assert 'href="/press-desk"' in kit and 'aria-current="page"' in kit


def test_the_strip_is_the_shared_control_and_clears_touch_targets():
    css = io.open(os.path.join(HERE, "static", "css", "app-chrome.css"), encoding="utf-8").read()
    assert ".sb-subnav-a.is-on" in css and ".sb-subnav-a:focus-visible" in css
    coarse = css[css.rindex("pointer: coarse"):]
    assert ".sb-subnav-a" in coarse and "44px" in coarse


def test_the_parked_pages_are_documented():
    doc = io.open(os.path.join(HERE, "docs", "PARKED_PAGES.md"), encoding="utf-8").read()
    for href in PARKED:
        assert href in doc, href
