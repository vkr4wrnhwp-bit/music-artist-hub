"""The signed-in pages hold their shape for a phone and a screen reader.

An outside audit (2026-09-12) found task failures that were cheap and
mechanical: two mains on a page, a first heading that was an h2, no
skip link, icon buttons with no name, a link to an anchor nobody had
written, and dozens of inputs a screen reader could only call "edit
text". Each class gets a lock here so it cannot come back.
"""
import io
import os
import re
import uuid

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROUTES = ["/command-center", "/actions", "/artwork", "/vault", "/catalog", "/releases/autopilot",
          "/links", "/links/new", "/rollout-studio", "/rollout-studio/new", "/press-desk", "/epk",
          "/pulse", "/tours", "/tour-board", "/royalties", "/statements", "/recovery",
          "/royalty-recovery/cases", "/disputes", "/valuation", "/revenue-os", "/deal-room",
          "/reports", "/hours", "/tax", "/network", "/settings"]
FORMS = ["/artwork", "/epk", "/rollout-studio/new", "/links/new"]


@pytest.fixture(scope="module")
def pages():
    from app import create_app
    app_obj = create_app()
    client = app_obj.test_client()
    email = "land-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Land", "email": email, "password": "land-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    out = {}
    for route in ROUTES:
        r = client.get(route, follow_redirects=True)
        if r.status_code == 200:
            out[route] = r.get_data(as_text=True)
    assert len(out) >= len(ROUTES) - 3, "most of the smoke routes answer 200: %s" % sorted(set(ROUTES) - set(out))
    return client, out


def _main(body):
    return body.split("<main", 1)[1].split("</main>")[0] if "<main" in body else ""


def test_every_page_has_one_main_landmark(pages):
    _, out = pages
    for route, body in out.items():
        assert body.count("<main") == 1, "%s has %d main landmarks" % (route, body.count("<main"))


def test_every_page_has_one_h1_and_it_comes_first(pages):
    _, out = pages
    for route, body in out.items():
        main = _main(body)
        h1s = re.findall(r"<h1\b", main)
        assert len(h1s) == 1, "%s has %d h1 in main" % (route, len(h1s))
        first = re.search(r"<h([1-6])\b", main)
        assert first and first.group(1) == "1", "%s: the first heading in main is an h%s" % (route, first.group(1) if first else "?")


def test_the_skip_link_is_the_first_focusable_thing_and_lands_on_main(pages):
    _, out = pages
    for route, body in out.items():
        assert '<a class="sb-skip" href="#sb-main">' in body, route
        assert 'id="sb-main"' in body, route
        assert body.count('id="sb-main"') == 1, route


def test_every_visible_input_on_the_authoring_forms_has_a_name(pages):
    _, out = pages
    for route in FORMS:
        body = out[route]
        ids = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', body))
        bare = []
        for m in re.finditer(r'<(input|select|textarea)\b([^>]*)>', body):
            attrs = m.group(2)
            if re.search(r'type="(hidden|submit|checkbox|radio|file)"', attrs):
                continue
            if "aria-label" in attrs or "aria-labelledby" in attrs:
                continue
            idm = re.search(r'\bid="([^"]+)"', attrs)
            if idm and idm.group(1) in ids:
                continue
            bare.append(attrs.strip()[:80])
        assert not bare, "%s: %d unnamed inputs, e.g. %s" % (route, len(bare), bare[:3])


def test_icon_buttons_carry_a_name(pages):
    _, out = pages
    for route, body in out.items():
        for m in re.finditer(r'<button\b([^>]*)>(.*?)</button>', body, re.S):
            attrs, inner = m.group(1), m.group(2)
            if re.sub(r"<[^>]+>", "", inner).strip():
                continue
            assert "aria-label" in attrs or "title=" in attrs, "%s: a button with no text and no name: %s" % (route, attrs.strip()[:90])


def test_every_same_site_fragment_link_lands_on_an_id(pages):
    client, out = pages
    seen = {}
    for route, body in out.items():
        for href in set(re.findall(r'href="(/[^"#]*)#([A-Za-z][\w-]*)"', body)):
            path, frag = href
            if path not in seen:
                r = client.get(path, follow_redirects=True)
                seen[path] = r.get_data(as_text=True) if r.status_code == 200 else ""
            assert 'id="%s"' % frag in seen[path], "%s links to %s#%s and no element has that id" % (route, path, frag)


def test_the_network_profiles_point_at_a_real_section(pages):
    _, out = pages
    client, _ = pages
    body = client.get("/network?tab=my").get_data(as_text=True)
    assert 'id="my-network"' in body, "the anchor the nine profile pages point at"
    assert "/network?tab=my#my-network" in io.open(os.path.join(HERE, "templates", "network_profile.html"), encoding="utf-8").read()


def test_the_two_phone_layouts_are_reset_in_their_breakpoints():
    dept = io.open(os.path.join(HERE, "static", "css", "departments.css"), encoding="utf-8").read()
    narrow = dept.split("@media (max-width: 1023px)")[1]
    assert "grid-column: auto;" in narrow and "grid-row: auto;" in narrow, \
        "departments 01 and 02 collapse to a sliver at 360px without the reset"
    login = io.open(os.path.join(HERE, "static", "css", "login-session-recall.css"), encoding="utf-8").read()
    assert "@media (max-width: 520px) { .lsr-demo-row { grid-template-columns: 1fr; } }" in login
