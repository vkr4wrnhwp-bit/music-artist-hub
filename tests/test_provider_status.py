"""The Providers page (owner, 2026-09-23: "build the providers status page").

What it must never do, each held here:

  - open to anybody but an owner, or to a team seat working inside an
    artist's account
  - call a service on a page view
  - put a key's VALUE on the page, in a stored result or in a redirect -
    not even when the vendor echoes the key back in its error
  - spend money, a scarce quota or write a test file from "Check all"
  - call Ticketmaster while the owner's ruling keeps it off
  - POST to Stripe (setup_webhook_endpoint reads, then changes things)
  - read "we did not ask" as "failing"
  - wait on a dead vendor past its time limit

No test here reaches the network: every check runs against a fake wire
installed in urllib (urlopen and build_opener) and the ElevenLabs SDK
client, and anything that slips past the fake trips a socket guard.
"""
import email.message
import io
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pytest

import db as store
import provider_status as ps
import signal_providers as sp
from app import create_app

PW = "providers-pass-1"
DOMAIN = "sbtest.example"
FREE_SET = {"mlc", "discogs", "spotify", "youtube", "acr_console", "musicbrainz",
            "eventbrite", "ticketmaster", "stripe", "shopify_buy", "shopify_admin",
            "resend", "elevenlabs", "roex", "stemsplit", "itunes", "deezer", "odesli",
            "google_news"}
COSTED = {"soundcharts", "songstats", "google_places", "google_geocoding",
          "google_timezone", "google_routes", "r2"}


# --- the fake wire ------------------------------------------------------------------

class _Resp(object):
    def __init__(self, body, status=200):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.status = status
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "application/json"

    def read(self, n=-1):
        return self._body if n is None or n < 0 else self._body[:n]

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ok_body(url, method):
    """A well-formed answer from each service to the one question asked."""
    host = urllib.parse.urlsplit(url).hostname or ""
    path = urllib.parse.urlsplit(url).path
    if host == "accounts.spotify.com":
        return {"access_token": "tok", "token_type": "Bearer", "expires_in": 3600}
    if host == "account.soundcharts.com":
        return {"access_token": "tok", "expires_in": 3600}
    if host == "customer.api.soundcharts.com":
        return {"items": [{"uuid": "u", "name": "Radiohead"}], "page": {}}
    if host == "api.songstats.com":
        return {"artists": [{"songstats_artist_id": "a1", "name": "Radiohead"}]}
    if host == "public-api.themlc.com" and path == "/oauth/token":
        return {"accessToken": "a", "idToken": "i", "refreshToken": "r", "expiresIn": 3600}
    if host == "public-api.themlc.com":
        return [{"id": "1", "isrc": ps.KNOWN_ISRC, "title": "HUMBLE.", "mlcsongCode": "X"}]
    if host == "api.discogs.com":
        return {"id": 1, "username": "someone"}
    if host == "www.googleapis.com":
        return {"items": [{"id": ps.KNOWN_CHANNEL}]}
    if host == "api-v2.acrcloud.com":
        return {"data": [{"id": 1, "name": "b"}], "meta": {"total": 1, "last_page": 1}}
    if host == "musicbrainz.org":
        return {"artists": [{"id": "x", "name": "Radiohead"}]}
    if host == "www.eventbriteapi.com":
        return {"organizations": [{"id": "1"}], "pagination": {"has_more_items": False}}
    if host == "app.ticketmaster.com":
        return {"page": {"totalElements": 1, "size": 1}}
    if host == "places.googleapis.com":
        return {"places": [{"id": "p1"}]}
    if host == "maps.googleapis.com":
        return {"status": "OK", "results": [], "timeZoneId": "America/Chicago"}
    if host == "routes.googleapis.com":
        return {"routes": [{"distanceMeters": 340000, "duration": "11000s"}]}
    if host == "api.stripe.com" and path == "/v1/webhook_endpoints":
        return {"data": [{"id": "we_1", "url": "https://elsewhere.example/webhooks/stripe",
                          "status": "enabled", "enabled_events": ["*"]}]}
    if host == "api.stripe.com":
        return {"available": [], "pending": []}
    if host.endswith(".myshopify.com") and path == "/admin/oauth/access_token":
        return {"access_token": "granted", "expires_in": 86399, "scope": "read_customers"}
    if host.endswith(".myshopify.com") and path.startswith("/admin/api/"):
        return {"data": {"shop": {"name": "The Store"}}}
    if host.endswith(".myshopify.com"):
        return {"data": {"shop": {"name": "The Store", "primaryDomain": {"host": "h"}},
                         "collection": {"title": "Merch", "handle": "merch",
                                        "products": {"edges": [{"node": {"title": "Tee"}}]}}}}
    if host == "api.resend.com":
        return {"data": [{"id": "d1", "name": DOMAIN, "status": "verified"}]}
    if host == "stemsplit.io":
        return {"balance": 12}
    if host == "tonn.roexaudio.com":
        return {"status": "healthy"}
    if host == "itunes.apple.com":
        return {"resultCount": 1, "results": [{"trackName": "HUMBLE."}]}
    if host == "api.deezer.com":
        return {"id": 1, "title": "HUMBLE."}
    if host == "api.song.link":
        return {"entityUniqueId": "e", "linksByPlatform": {"spotify": {"url": "u"}, "deezer": {"url": "v"}}}
    if host == "news.google.com":
        return b"<rss><channel><item><title>A</title></item><item><title>B</title></item></channel></rss>"
    if host.endswith(".r2.cloudflarestorage.com"):
        return b"round trip" if method == "GET" else b""
    raise AssertionError("the fake wire has no answer for %s" % host)


class FakeNet(object):
    """Stands in for every outbound call. `mode` is how every service
    answers: "ok", an HTTP status (the body echoes the whole request back,
    keys included, the way a careless vendor might), "malformed" or
    "timeout". `overrides` maps a URL fragment to a mode of its own."""

    def __init__(self, mode="ok", overrides=None):
        self.mode = mode
        self.overrides = dict(overrides or {})
        self.calls = []
        self._lock = threading.Lock()

    def hosts(self):
        return {urllib.parse.urlsplit(c[1]).hostname for c in self.calls}

    def __call__(self, req, data=None, timeout=None, **kw):
        if isinstance(req, str):
            req = urllib.request.Request(req, data=data)
        url, method = req.full_url, req.get_method()
        headers = dict(req.header_items())
        with self._lock:
            self.calls.append((method, url, headers, req.data))
        mode = next((m for frag, m in self.overrides.items() if frag in url), self.mode)
        if mode == "timeout":
            raise socket.timeout("timed out")
        if isinstance(mode, int):
            echo = json.dumps({"message": "refused %s %s %s" % (url, headers, req.data)})
            raise urllib.error.HTTPError(url, mode, "refused", email.message.Message(),
                                         io.BytesIO(echo.encode("utf-8")))
        if mode == "malformed":
            return _Resp(b"<html>not json at all</html>")
        return _Resp(_ok_body(url, method))


class _Opener(object):
    def __init__(self, net):
        self.net = net

    def open(self, req, data=None, timeout=None):
        return self.net(req, data=data, timeout=timeout)


class _FakeModels(object):
    def __init__(self, net):
        self.net = net

    def list(self, request_options=None):
        from elevenlabs.core.api_error import ApiError
        assert request_options and request_options.get("max_retries") == 0, \
            "the SDK must not retry a dead vendor for minutes"
        with self.net._lock:
            self.net.calls.append(("GET", "https://api.elevenlabs.io/v1/models", {}, None))
        mode = self.net.mode
        if mode == "timeout":
            raise TimeoutError("timed out")
        if isinstance(mode, int):
            raise ApiError(status_code=mode, body={"detail": {
                "message": "bad key %s" % os.environ.get("ELEVENLABS_API_KEY")}})
        if mode == "malformed":
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return ["m1", "m2", "m3"]


class _FakeEleven(object):
    def __init__(self, net):
        self.models = _FakeModels(net)


def _no_real_network(*a, **kw):
    raise AssertionError("a real network connection was attempted")


@pytest.fixture
def net(monkeypatch):
    fake = FakeNet()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Opener(fake))
    monkeypatch.setattr(socket, "create_connection", _no_real_network)
    import audio_elevenlabs
    monkeypatch.setattr(audio_elevenlabs, "_client", lambda: _FakeEleven(fake))
    # Fresh process adapters, so a token or a rate window from another test
    # cannot answer for this one.
    monkeypatch.setattr(sp, "_mlc", None)
    monkeypatch.setattr(sp, "_discogs", None)
    # RoEx's own limiter is a shared table: another file in this worker may
    # have filled this minute, which would read (rightly) as "not asked".
    import roex_client
    roex_client.init()
    with store.get_db() as conn:
        conn.execute("DELETE FROM roex_rate")
    return fake


# --- keys ---------------------------------------------------------------------------

_SPECIAL = {
    "TICKETMASTER_ENABLED": "on",
    "AUDIO_INTELLIGENCE_ENABLED": "1",
    "EMAIL_FROM": "Street Banker <mail@%s>" % DOMAIN,
    "BACKUP_S3_REGION": "auto",
}


@pytest.fixture
def every_key(monkeypatch):
    """Every name any row reads, set to a value nobody could mistake for
    words, and every switch on."""
    monkeypatch.delenv("SANDBOX", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    tag = uuid.uuid4().hex[:10]
    values = {}
    for name in sorted(ps._all_names()):
        value = _SPECIAL.get(name) or ("sv%s%s" % (re.sub(r"[^a-z0-9]", "", name.lower()), tag))
        if name == "SHOPIFY_DOMAIN":
            value = "sv%s.myshopify.com" % tag
        monkeypatch.setenv(name, value)
        values[name] = value
    for p in ps.PROVIDERS:
        for flag in p.get("flags", ()):
            monkeypatch.setenv(flag, "1")
    return {n: v for n, v in values.items() if n not in _SPECIAL}


def _clear_results():
    for p in ps.PROVIDERS:
        store.set_kv(ps.KV_PREFIX + p["key"], "")


def _stored():
    return {p["key"]: store.get_kv(ps.KV_PREFIX + p["key"]) or "" for p in ps.PROVIDERS}


# --- accounts -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def app_obj():
    return create_app()


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SANDBOX", raising=False)


def _account(app_obj, name="Artist"):
    email_addr = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    client = app_obj.test_client()
    client.post("/signup", data={"name": name, "email": email_addr, "password": PW})
    client._email = email_addr
    return client


@pytest.fixture
def owner(app_obj, monkeypatch):
    client = _account(app_obj, "Owner")
    monkeypatch.setenv("OWNER_EMAILS", client._email)
    return client


# --- who reaches it -------------------------------------------------------------------

def test_only_an_owner_reaches_it(app_obj, owner, net):
    stranger = _account(app_obj, "Stranger")
    for method, path in (("get", "/admin/providers"), ("post", "/admin/providers/check"),
                         ("post", "/admin/providers/check/itunes")):
        assert getattr(stranger, method)(path).status_code == 404, path
    anon = app_obj.test_client()
    r = anon.get("/admin/providers")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert anon.post("/admin/providers/check").status_code == 302
    assert owner.get("/admin/providers").status_code == 200
    assert net.calls == [], "none of that asked anybody anything"


def test_a_team_seat_never_reaches_it(app_obj, monkeypatch, net):
    """An owner working inside an artist's account through a team seat is
    that artist's teammate, not the owner. The team gate answers /admin
    before the route's own 404 can - the same redirect every owner page
    gives a seat - and nothing is asked either way."""
    artist, member = _account(app_obj, "Artist"), _account(app_obj, "Member")
    artist_id = store.get_user_by_email(artist._email)["id"]
    store.set_user_plan(artist_id, "pro")
    r = artist.post("/team/invite", data={"email": member._email, "role": "manager",
                                          "access": "edit", "areas_sent": "1",
                                          "areas": ["fans"]})
    assert r.get_json().get("ok"), r.get_json()
    token = [m for m in store.list_team(artist_id) if m["email"] == member._email][0]["invite_token"]
    assert member.post("/team/join/" + token, data={}).status_code == 302
    monkeypatch.setenv("OWNER_EMAILS", member._email)
    assert member.get("/admin/providers").status_code == 200, "as themselves, the owner gets in"
    assert member.post("/portal/%s/open" % artist_id).status_code == 302
    for method, path in (("get", "/admin/providers"), ("post", "/admin/providers/check"),
                         ("post", "/admin/providers/check/itunes")):
        r = getattr(member, method)(path)
        assert r.status_code in (302, 404), (path, r.status_code)
        if r.status_code == 302:
            assert "team=" in r.headers["Location"], r.headers["Location"]
    assert net.calls == []


# --- a page view calls nobody ---------------------------------------------------------

def test_a_page_view_calls_nobody(app_obj, owner, every_key, monkeypatch):
    def refuse(*a, **kw):
        raise AssertionError("a page view made an outbound call")

    import http.client
    import requests
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request, "build_opener", refuse)
    monkeypatch.setattr(http.client.HTTPConnection, "request", refuse)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", refuse)
    monkeypatch.setattr(requests.sessions.Session, "request", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    import audio_elevenlabs
    monkeypatch.setattr(audio_elevenlabs, "_client", refuse)
    r = owner.get("/admin/providers")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Stripe" in body and "STRIPE_SECRET_KEY" in body
    assert owner.get("/admin/readiness").status_code == 200


# --- no value, anywhere -------------------------------------------------------------------

@pytest.mark.parametrize("mode", [401, 500, "ok"])
def test_no_value_reaches_the_page_the_store_or_a_redirect(owner, every_key, net, mode):
    """The fake vendor quotes the whole request back - URL, headers, body -
    in its error, so every key that rode in a query string, a header or a
    sign-in body is in the words a check gets back. None of it survives."""
    _clear_results()
    net.mode = mode
    locations = []
    r = owner.post("/admin/providers/check")
    locations.append(r.headers.get("Location", ""))
    for key in sorted(COSTED):
        r = owner.post("/admin/providers/check/%s" % key)
        assert r.status_code == 302, key
        locations.append(r.headers.get("Location", ""))
    body = owner.get("/admin/providers").get_data(as_text=True)
    stored = _stored()
    assert any(stored.values()), "the checks ran and were remembered"
    for name, value in every_key.items():
        assert value not in body, "%s's value is on the page" % name
        for key, raw in stored.items():
            assert value not in raw, "%s's value is in the stored result for %s" % (name, key)
        for loc in locations:
            assert value not in loc, "%s's value is in a redirect" % name
    assert "STRIPE_SECRET_KEY" in body, "the NAME is the useful part"


def test_scrub_catches_the_spellings_a_value_takes(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc/def+ghi=")
    text = ('url?key=sk_live_abc%2Fdef%2Bghi%3D json "sk_live_abc/def+ghi=" '
            'Bearer abcdefghijklmnop Invalid API Key provided: sk_test_****1234')
    out = ps.scrub(text)
    assert "abc" not in out and "1234" not in out and "abcdefghijklmnop" not in out, out


# --- Check all ------------------------------------------------------------------------

def test_check_all_is_exactly_the_free_read_only_set():
    assert set(ps.auto_keys()) == FREE_SET
    for p in ps.PROVIDERS:
        if p["key"] in COSTED:
            assert not p.get("auto") and p.get("cost_kind") in ("billed", "quota", "writes"), p["key"]
            assert p.get("cost"), "%s has its own button and must say what it costs" % p["key"]


def test_check_all_asks_the_free_set_and_nothing_that_costs(owner, every_key, net):
    _clear_results()
    r = owner.post("/admin/providers/check")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/providers?checked=all")
    stored = {k: json.loads(v) if v else None for k, v in _stored().items()}
    for key in FREE_SET:
        assert stored[key] and stored[key]["ok"] is True, (key, stored[key])
    for key in COSTED:
        assert stored[key] is None, "%s was asked by Check all" % key
    hosts = net.hosts()
    for banned in ("customer.api.soundcharts.com", "account.soundcharts.com", "api.songstats.com",
                   "places.googleapis.com", "maps.googleapis.com", "routes.googleapis.com"):
        assert banned not in hosts, banned
    assert not any(h.endswith(".r2.cloudflarestorage.com") for h in hosts), "R2 was written to"
    assert "app.ticketmaster.com" in hosts, "switched on, Ticketmaster is free and is asked"
    body = owner.get("/admin/providers?checked=all").get_data(as_text=True)
    assert "Working" in body and "Checked." in body


def test_check_all_leaves_ticketmaster_alone_while_it_is_off(owner, every_key, net, monkeypatch):
    monkeypatch.setenv("TICKETMASTER_ENABLED", "off")
    _clear_results()
    owner.post("/admin/providers/check")
    assert "app.ticketmaster.com" not in net.hosts()
    result = json.loads(store.get_kv(ps.KV_PREFIX + "ticketmaster"))
    assert result["ok"] is None and "owner ruling" in result["detail"]


def test_a_costed_check_runs_only_on_its_own_button(owner, every_key, net):
    _clear_results()
    r = owner.post("/admin/providers/check/google_geocoding")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/admin/providers?checked=google_geocoding#p-google_geocoding")
    assert net.hosts() == {"maps.googleapis.com"}
    assert json.loads(store.get_kv(ps.KV_PREFIX + "google_geocoding"))["ok"] is True
    assert owner.post("/admin/providers/check/no-such-service").status_code == 404


# --- every check, every kind of answer --------------------------------------------------------

CHECKED = sorted(p["key"] for p in ps.PROVIDERS if p.get("check"))
MODES = ["ok", 401, 403, 429, 500, 503, "malformed", "timeout"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("key", CHECKED)
def test_each_check_reads_every_kind_of_answer(key, mode, every_key, net):
    """Working only on a real, readable answer; failing, in words, on a
    refusal, a rate limit, a server error, a body it cannot read or no
    answer at all. RoEx's proof is the 200 from /health itself - the body
    is not read (release_ready.py health_ok) - so an unreadable 200 there is
    still an answer."""
    net.mode = mode
    result = ps.run(ps.by_key(key), timeout=5)
    expected = mode == "ok" or (mode == "malformed" and key == "roex")
    assert result["ok"] is expected, (key, mode, result)
    assert result["detail"].strip(), "a result always says something"
    assert net.calls, "%s asked nobody" % key
    if mode == 429 and key != "mlc":          # The MLC's sign-in error carries only its words
        assert "429" in result["detail"], (key, result["detail"])


def test_routes_not_enabled_is_a_known_state_not_a_failure(every_key, net):
    denied = json.dumps({"error": {"code": 403, "status": "PERMISSION_DENIED",
                                   "message": "Routes API has not been used in project"}})

    def wire(req, data=None, timeout=None, **kw):
        net.calls.append((req.get_method(), req.full_url, {}, req.data))
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", email.message.Message(),
                                     io.BytesIO(denied.encode("utf-8")))

    import venue_geo
    before = venue_geo.routes_available()
    import unittest.mock as mock
    with mock.patch.object(urllib.request, "urlopen", wire):
        result = ps.run(ps.by_key("google_routes"), timeout=5)
    assert result["ok"] is None and "Not enabled" in result["detail"]
    assert venue_geo.routes_available() == before, "the check never switches Routes off for the worker"


def test_ticketmaster_switched_off_makes_no_call(every_key, net, monkeypatch):
    monkeypatch.delenv("TICKETMASTER_ENABLED", raising=False)
    monkeypatch.setenv("RENDER", "1")        # a deployed service: off unless switched on
    p = ps.by_key("ticketmaster")
    result = ps.run(p)
    assert result["ok"] is None and "Off by owner ruling (2026-09-18)" in result["detail"]
    assert net.calls == []
    row = next(r for f in ps.rows(store) for r in f["providers"] if r["key"] == "ticketmaster")
    assert row["lamp"] == ("idle", "Off by owner ruling") and not row["can_check"]


def test_the_stripe_check_never_posts(every_key, net, monkeypatch):
    import stripe_provider

    def no(*a, **kw):
        raise AssertionError("the Stripe check wrote to Stripe")

    monkeypatch.setattr(stripe_provider, "_http", no)
    monkeypatch.setattr(stripe_provider, "_http_delete", no)
    monkeypatch.setattr(stripe_provider, "setup_webhook_endpoint", no)
    for overrides in ({}, {"/v1/webhook_endpoints": 403}):
        net.calls.clear()
        net.overrides = overrides
        result = ps.run(ps.by_key("stripe"), timeout=5)
        assert result["ok"] is True, result
        assert net.calls and all(c[0] == "GET" for c in net.calls), net.calls
    assert "restricted key" in result["detail"], "a 403 there is a working key without webhook read"


def test_a_disabled_stripe_webhook_is_a_failure(every_key, net, monkeypatch):
    import stripe_provider
    monkeypatch.setattr(stripe_provider, "_http_get", lambda path: {"data": [
        {"id": "we_1", "url": "https://x.example/webhooks/stripe", "status": "disabled",
         "enabled_events": ["*"]}]})
    result = ps.run(ps.by_key("stripe"), timeout=5)
    assert result["ok"] is False and "disabled" in result["detail"]


def test_the_shopify_checks_never_mint_or_forget_a_token(every_key, net, monkeypatch):
    """With the Admin credentials set and no Storefront token, reading the
    token MINTS one (a write to the store). The page and the checks read
    presence without it, and the Admin check never drops the kept tokens."""
    import shopify_buy
    import shopify_customers

    def no(*a, **kw):
        raise AssertionError("a Storefront token was minted or the grant forgotten")

    monkeypatch.setattr(shopify_customers, "mint_storefront_token", no)
    monkeypatch.setattr(shopify_customers, "forget_grant", no)
    monkeypatch.delenv("SHOPIFY_STOREFRONT_TOKEN")
    store.set_kv(shopify_buy.STOREFRONT_KEY, "")
    row = next(r for f in ps.rows(store) for r in f["providers"] if r["key"] == "shopify_buy")
    assert row["lamp"][1] == "Not configured"
    assert ps.run(ps.by_key("shopify_buy"))["ok"] is None
    assert ps.run(ps.by_key("shopify_admin"), timeout=5)["ok"] is True
    net.mode = 401
    assert ps.run(ps.by_key("shopify_admin"), timeout=5)["ok"] is False


def test_the_youtube_key_never_survives_its_own_url(every_key, net):
    net.mode = 403
    result = ps.run(ps.by_key("youtube"), timeout=5)
    assert result["ok"] is False
    assert every_key["YOUTUBE_API_KEY"] not in result["detail"]
    assert any("key=" in c[1] for c in net.calls), "the key did ride in the URL"


def test_not_configured_asks_nobody(net, monkeypatch):
    for name in ps._all_names():
        monkeypatch.delenv(name, raising=False)
    for p in ps.PROVIDERS:
        if p.get("check") and (p.get("env") or p.get("flags") or p.get("any_of")):
            result = ps.run(p)
            assert result["ok"] is None and "Not configured" in result["detail"], p["key"]
    assert net.calls == []


def test_a_sandbox_is_off_on_purpose_only_where_the_app_says_so(every_key, net, monkeypatch):
    monkeypatch.setenv("SANDBOX", "1")
    result = ps.run(ps.by_key("stripe"))
    assert result["ok"] is None and "sandbox" in result["detail"]
    assert net.calls == []
    # Spotify has no sandbox gate in the app, so it is still asked.
    assert ps.run(ps.by_key("spotify"), timeout=5)["ok"] is True


# --- three states, never two ---------------------------------------------------------------

def _row(key):
    return next(r for f in ps.rows(store) for r in f["providers"] if r["key"] == key)


def test_the_lamp_has_three_states_and_not_asked_is_not_failing(owner, every_key, monkeypatch):
    for ok, lamp in ((True, ("good", "Working")), (False, ("crit", "Failing"))):
        ps.save("itunes", {"ok": ok, "detail": "x", "ms": 1, "at": ps._now_iso()}, store)
        assert _row("itunes")["lamp"] == lamp
    ps.save("itunes", {"ok": None, "detail": "nothing asked", "ms": 0, "at": ps._now_iso()}, store)
    assert _row("itunes")["lamp"][0] == "idle"
    store.set_kv(ps.KV_PREFIX + "deezer", "")
    assert _row("deezer")["lamp"] == ("idle", "Not checked yet")
    # Rows with no safe check never read as failing.
    assert _row("acr_identify")["lamp"] == ("idle", "No live check")
    assert _row("suite_sso")["lamp"] == ("idle", "No live check")
    assert _row("bandsintown")["lamp"][1] == "Dormant"
    for stub in ("chartmetric", "soundexchange", "spotify_metadata"):
        row = _row(stub)
        assert row["lamp"] == ("idle", "Not built") and not row["env"], \
            "a stub shows no key that would read as a capability"
    monkeypatch.delenv("EVENTBRITE_TOKEN")
    assert _row("eventbrite")["lamp"] == ("off", "Not configured")
    assert "EVENTBRITE_TOKEN" in _row("eventbrite")["detail"]
    ps.save("itunes", {"ok": None, "detail": "nothing asked", "ms": 0, "at": ps._now_iso()}, store)
    ps.save("deezer", {"ok": False, "detail": "refused", "ms": 0, "at": ps._now_iso()}, store)
    body = owner.get("/admin/providers").get_data(as_text=True)
    assert "Not configured" in body and "Failing" in body and "Not built" in body

    def row_class(key):
        return re.search(r'<li class="pv-row is-(\w+)" id="p-%s">' % key, body).group(1)

    assert row_class("deezer") == "crit", "asked, and it failed"
    assert row_class("itunes") == "idle", "nothing was asked, so it is not red"
    assert row_class("acr_identify") == "idle" and row_class("chartmetric") == "idle"


def test_the_backup_row_reads_the_stored_run_and_flags_a_stale_one(every_key):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    store.set_kv("backup_last_run", json.dumps({"at": now.isoformat(), "ok": True, "bytes": 2e6}))
    assert _row("backup")["lamp"] == ("good", "Working")
    store.set_kv("backup_last_run", json.dumps({"at": (now - timedelta(hours=30)).isoformat(),
                                                "ok": True, "bytes": 2e6}))
    row = _row("backup")
    assert row["lamp"][0] == "crit" and "30 hours ago" in row["detail"]
    store.set_kv("backup_last_run", json.dumps({"at": now.isoformat(), "ok": False,
                                                "detail": "HTTP 403 AccessDenied"}))
    assert _row("backup")["lamp"][0] == "crit"
    store.set_kv("backup_last_run", "")
    assert _row("backup")["lamp"][0] == "idle"


# --- the time limit -------------------------------------------------------------------------

def test_a_check_that_hangs_is_cut_off_at_its_limit():
    slow = dict(key="slow", name="Slow", family="lookups", powers="p",
                check=lambda: time.sleep(3) or {"ok": True, "detail": "late"})
    started = time.monotonic()
    result = ps.run(slow, timeout=0.2)
    assert time.monotonic() - started < 1.5
    assert result["ok"] is False and "No answer within" in result["detail"]


def test_check_all_is_bounded_by_the_slowest_limit_not_the_sum(monkeypatch):
    slow = [dict(key="slow%d" % i, name="Slow", family="lookups", powers="p", auto=True,
                 timeout=0.3, check=lambda: time.sleep(3) or {"ok": True, "detail": "late"})
            for i in range(4)]
    monkeypatch.setattr(ps, "PROVIDERS", slow)
    started = time.monotonic()
    results = ps.check_all(store)
    assert time.monotonic() - started < 2.0, "four 0.3 s limits ran together"
    assert set(results) == {"slow0", "slow1", "slow2", "slow3"}
    assert all(r["ok"] is False for r in results.values())


# --- the page and its doors --------------------------------------------------------------------

def test_the_page_is_one_page_with_one_h1(owner):
    body = owner.get("/admin/providers").get_data(as_text=True)
    main = body.split("<main", 1)[1].split("</main>")[0]
    assert len(re.findall(r"<h1\b", main)) == 1
    assert re.search(r"<h([1-6])\b", main).group(1) == "1"
    assert "/static/css/providers.css" in body
    for fam in ("Music data and rights", "Touring and places", "Money, shop and mail",
                "Storage, backup and monitoring", "Audio tools", "Public music lookups"):
        assert fam in body
    assert 'href="/admin/readiness"' in body


def test_readiness_settings_and_the_owner_menu_lead_here(app_obj, owner):
    assert 'href="/admin/providers"' in owner.get("/admin/readiness").get_data(as_text=True)
    assert 'href="/admin/providers"' in owner.get("/settings").get_data(as_text=True)
    assert "/admin/providers" in owner.get("/overview").get_data(as_text=True)
    stranger = _account(app_obj, "Stranger")
    assert "/admin/providers" not in stranger.get("/overview").get_data(as_text=True)
    assert "/admin/providers" not in stranger.get("/settings").get_data(as_text=True)


def test_every_name_listed_is_one_the_app_actually_reads():
    """The readiness page's guard, for this page: a row that names a
    variable nothing reads sends the owner to type something with no
    effect. provider_status.py and readiness.py only list names, so neither
    counts as a reader."""
    repo = os.path.dirname(os.path.abspath(ps.__file__))
    blob = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "tests", "__pycache__", "tools",
                                                "node_modules", "static", "templates")]
        for name in files:
            if name.endswith(".py") and name not in ("provider_status.py", "readiness.py"):
                with open(os.path.join(root, name), encoding="utf-8", errors="ignore") as fh:
                    blob.append(fh.read())
    source = "\n".join(blob)
    names = set(ps._all_names())
    for p in ps.PROVIDERS:
        names.update(p.get("flags", ()))
    unknown = sorted(n for n in names if '"%s"' % n not in source and "'%s'" % n not in source)
    assert not unknown, "the page names variables the app never reads: %s" % unknown
