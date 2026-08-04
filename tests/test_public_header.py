"""The public header: brand first, and no login wall in front of the
product story.

The old one led with "ARTIST INFRASTRUCTURE" over a small dark wordmark,
pointed Platform at /overview and the free-scan CTA at /recovery - both
of which bounce a signed-out visitor into a password field for asking
what the product is. These hold the replacement.
"""

import os
import re

from app import create_app


def _anon():
    return create_app().test_client()


def _home():
    return _anon().get("/").get_data(as_text=True)


def test_the_lockup_is_the_vector_logo_plus_live_text():
    body = _home()
    assert "streetbanker-logo-light.svg" in body
    # The descriptor is text, not baked into the image.
    assert "The Artist<br>Operating System" in body
    assert os.path.exists("static/img/streetbanker-logo-light.svg")
    # The originals are untouched.
    for original in ("static/img/streetbanker-logo.svg",
                     "static/img/streetbanker-logo-dark.svg"):
        assert os.path.exists(original), original


def test_the_light_logo_keeps_the_original_geometry():
    """Same brackets, same wordmark, same spacing - only the fill differs.
    A redrawn logo is a different logo."""
    light = open("static/img/streetbanker-logo-light.svg", encoding="utf-8").read()
    dark = open("static/img/streetbanker-logo-dark.svg", encoding="utf-8").read()
    paths = lambda svg: re.findall(r'd="([^"]+)"', svg)
    assert paths(light) == paths(dark)
    assert 'viewBox="0 0 920 250"' in light
    assert ".street banker" in light          # the period is part of it
    assert 'font-size="104"' in light and 'letter-spacing="-2"' in light
    assert 'stroke-width="18"' in light


def test_navigation_reaches_real_places():
    body = _home()
    for label in ("Platform", "AI Artist Twin", "Creative + Rollout",
                  "Royalty Sweep", "For Labels"):
        assert label in body, label
    # Every same-page target exists in the document.
    for anchor in ("platform", "artist-twin", "creative-rollout", "royalty-sweep"):
        assert 'id="%s"' % anchor in body, anchor


def test_no_navigation_item_bounces_a_visitor_to_login():
    """A public visitor asking what the product is must not be handed a
    password field. Every non-anchor destination in the header answers
    for itself, signed out."""
    app_obj = create_app()
    body = app_obj.test_client().get("/").get_data(as_text=True)
    header = body[body.index('<header class="sbh"'):body.index("</header>")]
    hrefs = set(re.findall(r'href="([^"]+)"', header))
    client = app_obj.test_client()
    for href in hrefs:
        if href.startswith("#") or href == "/login":
            continue
        response = client.get(href)
        assert response.status_code == 200, (href, response.status_code)


def test_the_cta_says_what_it_does():
    body = _home()
    assert "Run a Free Catalog Sweep" in body
    assert 'href="/catalog-sweep"' in body
    assert "Free Sweep" in body                     # the phone's short form
    for vague in ("Start Free", "Get Started", "Learn More", "Explore Now"):
        assert vague not in body, vague


def test_the_sweep_entry_is_open_to_a_stranger():
    client = _anon()
    page = client.get("/catalog-sweep")
    assert page.status_code == 200                  # not a redirect to login
    body = page.get_data(as_text=True)
    assert "Tell us what to look at" in body
    for field in ('name="catalog"', 'name="url"', 'name="role"'):
        assert field in body, field
    for role in ("artist", "songwriter", "producer", "manager", "label"):
        assert 'value="%s"' % role in body, role


def test_the_sweep_result_never_claims_a_scan_ran():
    client = _anon()
    body = client.post("/catalog-sweep", data={
        "catalog": "Synthwave Surfer", "role": "producer",
        "url": "https://open.spotify.com/artist/x"}).get_data(as_text=True)
    assert "Preliminary catalog coverage check" in body
    assert "No scan has run" in body
    assert "read a platform" in body                # says what it did not do
    # An account is offered after the explanation, never demanded before it.
    assert "/signup" in body
    for lie in ("we found", "we scanned", "issues detected", "uncollected royalties found"):
        assert lie.lower() not in body.lower(), lie


def test_the_header_is_one_component_used_by_both_public_pages():
    for path in ("/", "/catalog-sweep"):
        body = _anon().get(path).get_data(as_text=True)
        assert 'id="sb-header"' in body, path
        assert 'id="sb-header-drawer"' in body, path


def test_accessibility_scaffolding():
    body = _home()
    assert 'class="sbh-skip" href="#main"' in body   # skip link
    assert 'id="main"' in body                       # ...with a target
    assert '<header class="sbh"' in body
    assert 'aria-label="Product"' in body            # the nav is named
    assert 'aria-expanded="false"' in body           # accurate at rest
    assert 'aria-controls="sb-header-drawer"' in body
    assert 'role="dialog"' in body and 'aria-modal="true"' in body
    assert 'aria-label="Street Banker menu"' in body


def test_the_header_assets_exist_and_are_versioned():
    body = _home()
    for asset in ("/static/css/public-header.css", "/static/js/public-header.js"):
        assert asset in body, asset
        assert os.path.exists(asset.lstrip("/")), asset
    # The service worker caches /static first, so a changed asset needs a
    # new cache version or returning visitors keep the old header.
    sw = open("static/js/sw.js", encoding="utf-8").read()
    assert 'VERSION = "sb-v83"' in sw


def test_the_header_holds_its_own_space():
    """Sticky, and sized in CSS rather than by whatever is inside it - a
    bar that measures itself is a bar that shifts the page."""
    css = open("static/css/public-header.css", encoding="utf-8").read()
    assert "position: sticky" in css
    assert "--sbh-height: 86px" in css
    assert "--sbh-height-mobile: 70px" in css
    assert "prefers-reduced-motion" in css
    assert "env(safe-area-inset" in css
