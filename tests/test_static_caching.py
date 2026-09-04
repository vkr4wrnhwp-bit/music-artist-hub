"""Static assets are cacheable, and the share links are not crawlable.

The app was re-sending every byte of every asset on every visit. Flask
touches the session on nearly every request, so it stamped "Vary: Cookie",
and no shared cache stores a response carrying that header; with Werkzeug's
default "Cache-Control: no-cache" on top, Cloudflare reported
cf-cache-status: DYNAMIC for all of /static/ and the origin paid for the
lot - roughly one full cold page load a minute, around the clock, mostly
crawlers. These tests pin the fix and, just as importantly, pin the things
the fix must NOT change.
"""
import pytest

import app as appmod


@pytest.fixture(scope="module")
def client():
    return appmod.create_app().test_client()


def _vary(response):
    return [v.strip().lower() for v in
            ",".join(response.headers.getlist("Vary")).split(",") if v.strip()]


def test_a_cache_busted_asset_is_frozen_for_a_year(client):
    """A "?v=" in the URL means a new file arrives at a new address, so the
    old one can be kept indefinitely."""
    r = client.get("/static/css/tailwind.css?v=27")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_a_bare_asset_gets_a_day_not_a_year(client):
    """70-odd references carry no cache-buster - mostly images. Freezing
    those for a year would make replacing one a year-long mistake."""
    r = client.get("/static/img/streetbanker-logo.svg")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=86400"


def test_cookie_is_gone_from_vary_on_static(client):
    """The whole point: while "Cookie" is in Vary, no shared cache will
    store the response and every byte stays an origin fetch."""
    r = client.get("/static/css/tailwind.css?v=27")
    assert "cookie" not in _vary(r)
    assert _vary(r) == ["accept-encoding"]


def test_html_still_varies_on_cookie(client):
    """The guard on the fix. Pages genuinely differ per session - a signed-in
    visitor must never be served a cached signed-out page, or vice versa."""
    r = client.get("/login")
    assert r.status_code == 200
    assert "cookie" in _vary(r)
    assert "immutable" not in (r.headers.get("Cache-Control") or "")


def test_a_missing_asset_is_not_cached(client):
    """A 404 frozen at the edge for a year is a bug nobody can clear."""
    r = client.get("/static/css/does-not-exist.css?v=1")
    assert r.status_code == 404
    assert "immutable" not in (r.headers.get("Cache-Control") or "")


def test_a_revalidation_still_carries_the_lifetime(client):
    """A 304 that answers without Cache-Control leaves the browser's copy
    stale by default, so it asks again on the very next page load and the
    round trip never stops."""
    first = client.get("/static/css/tailwind.css?v=27")
    etag = first.headers.get("ETag")
    assert etag, "asset should carry an ETag to revalidate against"
    again = client.get("/static/css/tailwind.css?v=27",
                       headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "cookie" not in _vary(again)


def test_the_service_worker_is_still_never_cached(client):
    """/sw.js is served from the root by its own route, outside /static/, and
    it must keep revalidating or a bad worker would be unshiftable."""
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-cache"


def test_robots_answers_a_stranger(client):
    """A crawler bounced to /login never reads the rules."""
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.mimetype == "text/plain"


def test_robots_hides_every_share_link(client):
    """Each of these is public so a recipient without an account can open it;
    the unguessable token is the authorisation. Indexing one would publish a
    private link to the world."""
    body = client.get("/robots.txt").get_data(as_text=True)
    for prefix in ("/uploads/", "/epk/", "/press/", "/beat/", "/licence/",
                   "/tour-share/", "/lights/remote/", "/sign/", "/s/", "/l/"):
        assert "Disallow: %s" % prefix in body, prefix


def test_robots_still_lets_the_marketing_pages_be_found(client):
    """The public pages exist to be found; only the share links are hidden.
    /static/ is allowed because a crawler that cannot fetch the CSS renders
    the page wrongly and judges it on that."""
    body = client.get("/robots.txt").get_data(as_text=True)
    assert "Allow: /static/" in body
    for public_page in ("/about", "/pricing", "/ai", "/lanes", "/rollout"):
        assert "Disallow: %s\n" % public_page not in body
