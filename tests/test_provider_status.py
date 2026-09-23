"""The Providers page (owner, 2026-09-23: "build the providers status page").

What it must never do, each held here:

  - open to anybody but an owner, or to a team seat working inside an
    artist's account, or to a partner's staff acting as an owner's account
  - call a service on a page view
  - put a key's VALUE on the page, in a stored result or in a redirect -
    not even when the vendor echoes the key back in its error, not even
    part of one cut short, and not a secret the app holds outside the
    environment
  - spend money, a scarce quota or write a test file from "Check all"
  - spend twice on a double-click, a second press inside a minute, or a
    press from another site
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

# The time limit a test gives a check that is not about time. The fake wire
# answers at once, so a limit only bites when the machine is too busy to
# run the check's thread: with a dozen other test runs sharing the CPU, a
# check that answers the fake well inside 5 seconds on a quiet machine read
# "No answer within 5 seconds" (fixer, 2026-09-23). The time limit itself
# is held by its own tests below, each with a short limit of its own.
ROOMY = 60


@pytest.fixture(autouse=True)
def _roomy_default_limit(monkeypatch):
    """The same, for the checks a route runs at the row's default limit."""
    monkeypatch.setattr(ps, "CHECK_TIMEOUT_S", ROOMY)


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
        return {"kind": "youtube#channelListResponse", "pageInfo": {"totalResults": 1},
                "items": [{"id": ps.KNOWN_CHANNEL}]}
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
        # This deployment's endpoint (the test client is http://localhost)
        # beside another deployment's on the same key.
        return {"data": [{"id": "we_0", "url": "https://elsewhere.example/webhooks/stripe",
                          "status": "enabled", "enabled_events": ["*"]},
                         {"id": "we_1", "url": "http://localhost/webhooks/stripe",
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


WRONG_SHAPE = {"error": "upstream said no", "result": "error"}


class FakeNet(object):
    """Stands in for every outbound call. `mode` is how every service
    answers: "ok", an HTTP status (the body echoes the whole request back,
    keys included, the way a careless vendor might), "malformed" (not
    JSON), "wrong-shape" (a 200 whose JSON is an error, not the answer) or
    "timeout". `overrides` maps a URL fragment to a mode of its own;
    `answer(req, method, url)` may answer a call itself (None passes);
    `delay` makes every answer that slow."""

    def __init__(self, mode="ok", overrides=None):
        self.mode = mode
        self.overrides = dict(overrides or {})
        self.answer = None
        self.delay = 0.0
        self.calls = []
        self.times = []
        self._lock = threading.Lock()

    def hosts(self):
        return {urllib.parse.urlsplit(c[1]).hostname for c in self.calls}

    def to(self, host):
        return [c for c in self.calls if urllib.parse.urlsplit(c[1]).hostname == host]

    def __call__(self, req, data=None, timeout=None, **kw):
        if isinstance(req, str):
            req = urllib.request.Request(req, data=data)
        url, method = req.full_url, req.get_method()
        headers = dict(req.header_items())
        with self._lock:
            self.calls.append((method, url, headers, req.data))
            self.times.append((time.monotonic(), url))
        if self.delay:
            time.sleep(self.delay)
        if self.answer is not None:
            got = self.answer(req, method, url)
            if got is not None:
                return got
        mode = next((m for frag, m in self.overrides.items() if frag in url), self.mode)
        if mode == "timeout":
            raise socket.timeout("timed out")
        if isinstance(mode, int):
            echo = json.dumps({"message": "refused %s %s %s" % (url, headers, req.data)})
            raise urllib.error.HTTPError(url, mode, "refused", email.message.Message(),
                                         io.BytesIO(echo.encode("utf-8")))
        if mode == "malformed":
            return _Resp(b"<html>not json at all</html>")
        if mode == "wrong-shape":
            return _Resp(WRONG_SHAPE)
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
        if mode in ("malformed", "wrong-shape"):     # the SDK cannot parse either
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
    yield fake
    # A check past its time limit is abandoned, not stopped. Let any such
    # thread finish against the fake before the real urllib comes back.
    for t in threading.enumerate():
        if t.name.startswith("provider-check-"):
            t.join(ROOMY)


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
    # This deployment is the test client's own host, where the fake Stripe
    # account has a webhook endpoint.
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
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
        if ps._SECRET_NAME.search(name):
            # An adapter that cuts a vendor's words keeps the START of a key.
            head = value[:10]
            assert head not in body and not any(head in raw for raw in stored.values()), \
                "the first characters of %s survived" % name
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
    """Changed 2026-09-23 (providers review): this used to pin that the
    ruling was STORED as Ticketmaster's result. A stored "off by ruling"
    outlived the ruling - switched back on, the row still said off - so a
    gated answer is now read live from the ruling and never stored."""
    monkeypatch.setenv("TICKETMASTER_ENABLED", "off")
    _clear_results()
    owner.post("/admin/providers/check")
    assert "app.ticketmaster.com" not in net.hosts()
    assert not store.get_kv(ps.KV_PREFIX + "ticketmaster"), "a gated answer is not stored"
    row = _row("ticketmaster")
    assert row["lamp"] == ("idle", "Off by owner ruling") and "owner ruling" in row["detail"]


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
MODES = ["ok", 401, 403, 429, 500, 503, "malformed", "wrong-shape", "timeout"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("key", CHECKED)
def test_each_check_reads_every_kind_of_answer(key, mode, every_key, net):
    """Working only on a real, readable answer; failing, in words, on a
    refusal, a rate limit, a server error, a body it cannot read, a 200
    whose JSON is an error rather than the answer, or no answer at all.
    RoEx's proof is the 200 from /health itself - the body is not read
    (release_ready.py health_ok) - so an unreadable 200 there is still an
    answer."""
    net.mode = mode
    result = ps.run(ps.by_key(key), timeout=ROOMY)
    expected = mode == "ok" or (mode in ("malformed", "wrong-shape") and key == "roex")
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
        result = ps.run(ps.by_key("google_routes"), timeout=ROOMY)
    assert result["ok"] is None and "Not enabled" in result["detail"]
    assert venue_geo.routes_available() == before, "the check never switches Routes off for the worker"
    # A call went out, so the lamp names the state; "Not asked" would be untrue.
    assert result["label"] == "Not enabled"
    ps.save("google_routes", result, store)
    try:
        assert _row("google_routes")["lamp"] == ("idle", "Not enabled")
    finally:
        store.set_kv(ps.KV_PREFIX + "google_routes", "")


@pytest.mark.parametrize("reason,label,ok", [
    ("API_KEY_SERVICE_BLOCKED", "Blocked by the key", None),
    ("SERVICE_DISABLED", "Not enabled", None),
    ("SOMETHING_ELSE", None, False),
])
def test_routes_reads_googles_reason_for_a_403(reason, label, ok, every_key, net):
    """PERMISSION_DENIED alone does not say "not enabled": the key's own API
    restrictions give the same status. Google's reason decides the words."""
    body = json.dumps({"error": {"code": 403, "status": "PERMISSION_DENIED",
                                 "message": "Requests to this API are blocked.",
                                 "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                                              "reason": reason}]}}).encode("utf-8")

    def answer(req, method, url):
        raise urllib.error.HTTPError(url, 403, "Forbidden", email.message.Message(), io.BytesIO(body))

    net.answer = answer
    result = ps.run(ps.by_key("google_routes"), timeout=ROOMY)
    assert result["ok"] is ok, result
    assert result.get("label") == label
    if reason == "API_KEY_SERVICE_BLOCKED":
        assert "restrictions" in result["detail"] and "Not enabled on this Google project" not in result["detail"]


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
        result = ps.run(ps.by_key("stripe"), timeout=ROOMY)
        assert result["ok"] is True, result
        assert net.calls and all(c[0] == "GET" for c in net.calls), net.calls
    assert "restricted key" in result["detail"], "a 403 there is a working key without webhook read"


STAGING, LIVE = "https://staging.example", "https://live.example"


def _endpoint(base, status="enabled"):
    return {"id": "we_" + uuid.uuid4().hex[:6], "url": base + "/webhooks/stripe", "status": status,
            "enabled_events": ["*"]}


@pytest.mark.parametrize("case,endpoints,secret,ok,words", [
    # Another deployment's endpoint on the same key delivers nothing here.
    ("other-host", [_endpoint(LIVE)], "env", False, "live.example"),
    ("none", [], "env", False, "no webhook endpoint"),
    ("disabled", [_endpoint(STAGING, "disabled")], "env", False, "disabled"),
    ("no-secret", [_endpoint(STAGING)], None, False, "no signing secret"),
    ("legacy", [_endpoint(STAGING)], "legacy", True, "from before per-mode setup"),
    ("app", [_endpoint(LIVE), _endpoint(STAGING)], "app", True, "is enabled"),
    ("env", [_endpoint(STAGING)], "env", True, "is enabled"),
])
def test_the_stripe_webhook_is_this_deployments_and_delivers(case, endpoints, secret, ok, words,
                                                             every_key, net, monkeypatch):
    """Only an endpoint on this deployment's host counts, and every state in
    which no delivery lands - no endpoint here, a disabled one, one whose
    secret the app does not hold - is failing, alike. A legacy secret the
    route still accepts (webhook_accepts) is not "no secret"."""
    import stripe_provider
    monkeypatch.setenv("PUBLIC_BASE_URL", STAGING)
    monkeypatch.setattr(stripe_provider, "_http_get", lambda path: {"data": endpoints})
    kv = {"app": "stripe_test_webhook_secret", "legacy": "stripe_webhook_secret"}
    if secret != "env":
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    for key in kv.values():
        store.set_kv(key, "")
    if secret in kv:
        store.set_kv(kv[secret], "whsec_" + uuid.uuid4().hex)
    try:
        result = ps.run(ps.by_key("stripe"), timeout=ROOMY)
        assert result["ok"] is ok, (case, result)
        assert words in result["detail"], (case, result["detail"])
        if case == "other-host":
            assert STAGING + "/webhooks/stripe" in result["detail"]
        if secret == "legacy":
            assert stripe_provider.webhook_accepts() and not stripe_provider.webhook_configured()
            chip = next(c for c in _row("stripe")["optional"] if c["name"] == "STRIPE_WEBHOOK_SECRET")
            assert chip["app"] and chip["legacy"] and not chip["set"]
            assert "legacy secret held" in _row("webhooks")["detail"]
            assert "no signing secret" not in _row("webhooks")["detail"]
    finally:
        for key in kv.values():
            store.set_kv(key, "")


def test_the_press_decides_which_deployment_the_webhook_belongs_to(owner, every_key, net, monkeypatch):
    """Pressed on this host, the check reads this host's endpoint - the one
    Billing's one-click setup (request.url_root) would have made."""
    monkeypatch.setenv("PUBLIC_BASE_URL", STAGING)       # not where the press came from
    _clear_results()
    owner.post("/admin/providers/check/stripe")
    result = json.loads(store.get_kv(ps.KV_PREFIX + "stripe"))
    assert result["ok"] is True and "http://localhost/webhooks/stripe" in result["detail"]


def test_the_shopify_checks_never_mint_or_forget_a_token(every_key, net, monkeypatch):
    """With the Admin credentials set and no Storefront token, reading the
    token MINTS one (a write to the store). The page and the checks read
    presence without it, and the Admin check never drops the kept tokens.

    Changed 2026-09-23 (providers review): this used to pin the row as "Not
    configured: set SHOPIFY_STOREFRONT_TOKEN". With the Admin credentials
    set the app mints that token itself on the first Apparel visit, so the
    variable is not needed; the row now says so instead."""
    import shopify_buy
    import shopify_customers

    def no(*a, **kw):
        raise AssertionError("a Storefront token was minted or the grant forgotten")

    monkeypatch.setattr(shopify_customers, "mint_storefront_token", no)
    monkeypatch.setattr(shopify_customers, "forget_grant", no)
    monkeypatch.delenv("SHOPIFY_STOREFRONT_TOKEN")
    store.set_kv(shopify_buy.STOREFRONT_KEY, "")
    store.set_kv(shopify_buy.STOREFRONT_ERROR_KEY, "")
    row = _row("shopify_buy")
    assert row["lamp"] == ("idle", "Not minted yet")
    assert "first Apparel visit" in row["detail"] and not row["can_check"]
    chip = next(c for c in row["env"] if c["name"] == "SHOPIFY_STOREFRONT_TOKEN")
    assert chip["pending"] and not chip["set"]
    result = ps.run(ps.by_key("shopify_buy"))
    assert result["ok"] is None and "first Apparel visit" in result["detail"]
    # A mint that was already refused is said, in Shopify's words.
    store.set_kv(shopify_buy.STOREFRONT_ERROR_KEY, json.dumps({"status": 403, "why": "Access denied"}))
    try:
        assert "Access denied" in _row("shopify_buy")["detail"]
    finally:
        store.set_kv(shopify_buy.STOREFRONT_ERROR_KEY, "")
    # Without the Admin credentials nothing would mint it: then it IS missing.
    monkeypatch.delenv("SHOPIFY_CLIENT_ID")
    assert _row("shopify_buy")["lamp"] == ("off", "Not configured")
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", every_key["SHOPIFY_CLIENT_ID"])
    assert ps.run(ps.by_key("shopify_admin"), timeout=ROOMY)["ok"] is True
    net.mode = 401
    assert ps.run(ps.by_key("shopify_admin"), timeout=ROOMY)["ok"] is False


def test_the_youtube_key_never_survives_its_own_url(every_key, net):
    net.mode = 403
    result = ps.run(ps.by_key("youtube"), timeout=ROOMY)
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
    assert ps.run(ps.by_key("spotify"), timeout=ROOMY)["ok"] is True


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
    """Changed 2026-09-23 (fixer): this timed the whole call against 1.5 s.
    After the check, run() reads the secrets it scrubs with - now including
    the ones the app keeps in app_kv - and on a slow disk that read alone
    took longer than the check's limit. What the limit promises is that
    nobody waits on the vendor: the wait (ms) stops at the limit, and the
    call returns long before the hanging check would have."""
    slow = dict(key="slow", name="Slow", family="lookups", powers="p",
                check=lambda: time.sleep(10) or {"ok": True, "detail": "late"})
    started = time.monotonic()
    result = ps.run(slow, timeout=0.2)
    assert time.monotonic() - started < 6, "it did not wait for the 10 s check"
    assert result["ms"] < 1000, "the wait stopped at the 0.2 s limit"
    assert result["ok"] is False and "No answer within" in result["detail"]


def test_check_all_is_bounded_by_the_slowest_limit_not_the_sum(monkeypatch):
    """Changed 2026-09-23 (fixer): this timed the whole press against 2 s,
    which the leases, the stored results and the secrets read (a handful of
    database round trips, each slow on a slow disk) could pass on their
    own. The promise is read directly instead: every check starts before
    the first one's limit is up - one after another, each would wait out
    the 2 s limit before the next began - and each wait stops at its own
    limit."""
    starts = []

    def hang():
        starts.append(time.monotonic())
        time.sleep(20)
        return {"ok": True, "detail": "late"}

    slow = [dict(key="slow%d" % i, name="Slow", family="lookups", powers="p", auto=True,
                 timeout=2.0, check=hang) for i in range(4)]
    monkeypatch.setattr(ps, "PROVIDERS", slow)
    started = time.monotonic()
    results = ps.check_all(store)
    assert time.monotonic() - started < 16, "nobody waited for a 20 s check"
    assert set(results) == {"slow0", "slow1", "slow2", "slow3"}
    assert all(r["ok"] is False for r in results.values())
    assert len(starts) == 4 and max(starts) - min(starts) < 2.0,         "all four were under way inside the first one's limit (in a row: 6 s or more)"
    assert all(r["ms"] < 5000 for r in results.values()), "each wait stopped at its own limit"


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


# =====================================================================================
# The providers review (2026-09-23): each test below failed against fb9f99c4.
# =====================================================================================

def _partial_hits(text, values, min_len=8):
    """(name, run) for every run of min_len or more characters of a value
    found in text - a key cut short is still the key."""
    hits = []
    for name, value in values.items():
        for i in range(len(value) - min_len + 1):
            if value[i:i + min_len] in text:
                hits.append((name, value[i:i + min_len]))
                break
    return hits


def _random_secrets(monkeypatch, *names):
    """Random values for these names, so a run of 8 characters found in
    the words can only have come from the value."""
    out = {}
    for name in names:
        out[name] = "Q" + uuid.uuid4().hex + uuid.uuid4().hex[:7]
        monkeypatch.setenv(name, out[name])
    return out


# --- security-1: the cut came before the scrub -------------------------------------------

def test_a_key_quoted_past_the_cut_leaves_no_part_behind(owner, every_key, net, monkeypatch):
    """Eventbrite quotes the token after ~215 characters of words. The old
    _words() cut at 240 went through the middle of it, and scrub() - which
    blanked only the whole value - found nothing to hide."""
    secrets = _random_secrets(monkeypatch, "EVENTBRITE_TOKEN")
    token = secrets["EVENTBRITE_TOKEN"]
    said = ("The OAuth token you provided is invalid, has expired or has been revoked by the user "
            "who made it. Create a new private token in Account Settings > Developer Links. "
            "Send it in the Authorization header. Token received: " + token)
    assert said.index(token) < 240 < said.index(token) + len(token), "the old cut went through it"

    def answer(req, method, url):
        body = json.dumps({"error": "INVALID_AUTH", "error_description": said}).encode("utf-8")
        raise urllib.error.HTTPError(url, 401, "Unauthorized", email.message.Message(), io.BytesIO(body))

    net.answer = answer
    _clear_results()
    assert owner.post("/admin/providers/check/eventbrite").status_code == 302
    stored = store.get_kv(ps.KV_PREFIX + "eventbrite")
    page = owner.get("/admin/providers").get_data(as_text=True)
    assert "Token received" in stored, "the vendor's words are kept"
    assert not _partial_hits(stored, secrets) and not _partial_hits(page, secrets)


def test_scrub_blanks_a_key_an_adapter_already_cut(monkeypatch):
    """Upstream adapters cut before the words reach this module (Shopify
    body[:200], Resend [:200], The MLC raw[:200]): the start of a key is
    blanked however soon it stops. A value that is not a credential is
    blanked whole only, or a sender address would eat the words it starts
    with."""
    secrets = _random_secrets(monkeypatch, "RESEND_API_KEY", "SENTRY_DSN")
    key = secrets["RESEND_API_KEY"]
    monkeypatch.setenv("SENTRY_DSN", "https://%s@o1.ingest.sentry.io/2" % key[::-1])
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <mail@sbtest.example>")
    out = ps.scrub("HTTP Error 401: Unauthorized {\"message\": \"bad key " + key[:17])
    assert not _partial_hits(out, {"k": key}), out
    out = ps.scrub("dsn rejected: " + key[::-1][:12])
    assert not _partial_hits(out, {"k": key[::-1]}), out
    assert ps.scrub("Street Banker never calls the suites.") == "Street Banker never calls the suites."


# --- security-2: secrets the app holds outside the environment ---------------------------------

def test_a_secret_the_app_holds_is_hidden_too(owner, every_key, net):
    """The 24-hour Admin token from the client credentials grant lives in
    app_kv, not the environment. The echoing vendor quoted it back in a
    header dict, where no pattern matched it, and it was stored and shown
    whole."""
    import shopify_customers as sc
    granted = uuid.uuid4().hex
    store.set_kv(sc.GRANT_KEY, json.dumps({"token": granted, "client_id": sc.client_id(),
                                           "expires_at": time.time() + 86000,
                                           "scope": "read_customers"}))
    try:
        net.mode = 401
        _clear_results()
        owner.post("/admin/providers/check/shopify_admin")
        assert any(granted in c[2].values() for c in net.calls), "the token rode in a header"
        stored = store.get_kv(ps.KV_PREFIX + "shopify_admin")
        page = owner.get("/admin/providers").get_data(as_text=True)
        assert "401" in stored
        assert not _partial_hits(stored, {"granted": granted})
        assert not _partial_hits(page, {"granted": granted})
    finally:
        store.set_kv(sc.GRANT_KEY, "")


def test_every_secret_the_app_keeps_is_known_to_scrub(every_key):
    import shopify_buy
    kept = {"shopify_buy": shopify_buy.STOREFRONT_KEY, "live": "stripe_live_webhook_secret",
            "test": "stripe_test_webhook_secret", "legacy": "stripe_webhook_secret"}
    values = {k: uuid.uuid4().hex for k in kept}
    try:
        for k, kv in kept.items():
            store.set_kv(kv, values[k])
        text = " ".join("%s: '%s'" % (k, v) for k, v in values.items())
        assert not _partial_hits(ps.scrub(text), values)
        assert ps.scrub("{'X-shopify-access-token': 'abcdef0123456789'}").count("abcdef") == 0
    finally:
        for kv in kept.values():
            store.set_kv(kv, "")


# --- security-3: acting on an owner's behalf is not being the owner ----------------------------

def test_staff_acting_as_an_owner_account_is_not_the_owner(app_obj, owner, net):
    import partner_store as pstore
    staff = _account(app_obj, "Staff")
    staff_user = store.get_user_by_email(staff._email)
    owner_user = store.get_user_by_email(owner._email)
    pid = pstore.create_partner("Reseller %s" % uuid.uuid4().hex[:6], slug="r-" + uuid.uuid4().hex[:8])
    pstore.add_member(pid, staff_user["email"], name="Staff", role="admin", user_id=staff_user["id"])
    # The owner's account cannot go on a roster through the page any more ...
    owner.post("/resellers/%s/artists" % pid, data={"email": owner._email})
    assert store.get_user(owner_user["id"]).get("partner_id") != pid
    # ... and one put there before that still gives the staff nothing.
    assert pstore.attach_user(pid, owner_user["id"])
    staff.post("/partner/act/%s" % owner_user["id"])
    with staff.session_transaction() as s:
        assert s.get("acting_as") == owner_user["id"], "the staff is acting as the owner's account"
    for method, path in (("get", "/admin/providers"), ("post", "/admin/providers/check"),
                         ("post", "/admin/providers/check/soundcharts"),
                         ("get", "/admin/readiness"), ("get", "/resellers")):
        assert getattr(staff, method)(path).status_code == 404, path
    assert net.calls == [], "nothing was asked"
    with staff.session_transaction() as s:
        assert not s.get("acting_as"), "the act-on-behalf of an owner's account is dropped"


# --- security-4: a press from elsewhere, and a paid press repeated --------------------------------

@pytest.mark.parametrize("headers", [
    {"Origin": "https://shop.example.com"},
    {"Referer": "https://shop.example.com/products/tee"},
    {"Origin": "http://localhost", "Sec-Fetch-Site": "same-site"},
    {"Origin": "null"},
])
def test_a_press_from_another_site_asks_nobody(owner, every_key, net, headers):
    for path in ("/admin/providers/check", "/admin/providers/check/soundcharts",
                 "/admin/providers/check/r2", "/admin/providers/check/google_places"):
        assert owner.post(path, headers=headers).status_code == 403, path
    assert net.calls == []


def test_a_press_from_the_page_itself_goes_through_and_the_page_is_never_framed(owner, every_key, net):
    r = owner.post("/admin/providers/check/itunes",
                   headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin",
                            "Referer": "http://localhost/admin/providers"})
    assert r.status_code == 302 and net.to("itunes.apple.com")
    assert owner.get("/admin/providers").headers.get("X-Frame-Options") == "DENY"


def test_a_costed_check_is_asked_at_most_once_a_minute(owner, every_key, net):
    for key in COSTED:
        assert (ps.by_key(key).get("min_interval_s") or 0) >= 60, key
    _clear_results()
    owner.post("/admin/providers/check/google_places")
    r = owner.post("/admin/providers/check/google_places")
    assert len(net.to("places.googleapis.com")) == 1, "the second press spent nothing"
    assert "skipped=google_places" in r.headers["Location"]
    body = owner.get(r.headers["Location"]).get_data(as_text=True)
    assert "Not asked again" in body


# --- cost-1: a paid check past its limit ------------------------------------------------------------

def test_a_paid_check_past_its_limit_says_what_it_spent(every_key, net):
    """soundcharts_budget.record() runs before the call, and the time limit
    stops the waiting, not the call. The old words ("No answer within 12
    seconds") invited a second paid press."""
    import soundcharts_budget
    assert ps.by_key("soundcharts")["timeout"] > 30, "above a mint (15 s) plus a call (15 s)"
    assert ps.by_key("songstats")["timeout"] > 12, "above the adapter's own 12 s"
    before = soundcharts_budget.counts()["team"]
    net.delay = 1.0
    result = ps.run(ps.by_key("soundcharts"), timeout=0.3)
    assert result["ok"] is False and "No answer within" in result["detail"]
    assert soundcharts_budget.counts()["team"] == before + 1, "the call was counted"
    assert "paid call" in result["detail"]
    assert "{:,}".format(soundcharts_budget.summary()["total"]) in result["detail"]


# --- cost-2: a double-click -----------------------------------------------------------------------

def _twice(clients, path):
    barrier, codes = threading.Barrier(len(clients)), []

    def press(c):
        barrier.wait()
        codes.append(c.post(path).status_code)

    threads = [threading.Thread(target=press, args=(c,)) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    return codes


def test_two_presses_at_once_ask_once(app_obj, owner, every_key, net):
    second = app_obj.test_client()
    second.post("/login", data={"email": owner._email, "password": PW})
    assert second.get("/admin/providers").status_code == 200
    net.delay = 0.4
    _clear_results()
    assert _twice((owner, second), "/admin/providers/check/soundcharts") == [302, 302]
    assert len(net.to("customer.api.soundcharts.com")) == 1, "one paid call, not two"
    net.calls.clear()
    assert _twice((owner, second), "/admin/providers/check") == [302, 302]
    assert len(net.to("api.song.link")) == 1
    assert len(net.to("musicbrainz.org")) == 1
    for name in ("all", "soundcharts", "odesli"):
        assert not (store.get_kv(ps.LEASE_PREFIX + name) or ""), "the lease was let go: %s" % name


# --- cost-3 / cost-4: the process's own pacing ------------------------------------------------------

def test_the_musicbrainz_check_waits_its_turn_behind_a_lookup(every_key, net):
    adapter = ps._registry_adapter("musicbrainz")
    assert isinstance(adapter, sp.MusicBrainzAdapter)
    adapter.search_artists("radiohead", limit=1)          # Signal's own lookup
    assert ps.run(ps.by_key("musicbrainz"), timeout=ROOMY)["ok"] is True
    times = [t for t, url in net.times if "musicbrainz.org" in url]
    assert len(times) == 2 and times[1] - times[0] >= 1.0, times


def test_the_discogs_check_keeps_the_last_of_the_window_for_lookups(every_key, net):
    adapter = sp.discogs_adapter()
    adapter._remaining = 1
    result = ps.run(ps.by_key("discogs"), timeout=ROOMY)
    assert result["ok"] is None and "nearly spent" in result["detail"]
    assert net.calls == []
    adapter._remaining, stamp = None, adapter._last
    assert ps.run(ps.by_key("discogs"), timeout=ROOMY)["ok"] is True
    assert len(net.to("api.discogs.com")) == 1 and adapter._last > stamp, "paced and stamped"


# --- cost-5: the R2 test object -----------------------------------------------------------------------

@pytest.mark.parametrize("delete_works", [True, False])
def test_a_lost_reply_to_the_test_write_still_deletes_it(every_key, net, delete_works):
    bucket = {}

    def answer(req, method, url):
        path = urllib.parse.urlsplit(url).path
        if method == "PUT":
            bucket[path] = req.data               # stored, then the reply is lost
            raise socket.timeout("timed out")
        if method == "DELETE":
            if not delete_works:
                raise socket.timeout("timed out")
            bucket.pop(path, None)
            return _Resp(b"", 204)
        return None

    net.answer = answer
    result = ps.run(ps.by_key("r2"), timeout=ROOMY)
    assert [c[0] for c in net.calls] == ["PUT", "DELETE"]
    assert result["ok"] is False
    assert "no reply came back from the write" in result["detail"]
    assert "refused a write" not in result["detail"]
    if delete_works:
        assert bucket == {}
    else:
        assert "diagnostics/round-trip-" in result["detail"] and "could not be deleted" in result["detail"]


# --- correctness-4: a stored "not configured" outliving the setting --------------------------------------

def test_a_not_configured_answer_does_not_outlive_the_setting(owner, every_key, net, monkeypatch):
    monkeypatch.delenv("DISCOGS_TOKEN")
    monkeypatch.setenv("TICKETMASTER_ENABLED", "off")
    _clear_results()
    owner.post("/admin/providers/check")
    for key in ("discogs", "ticketmaster"):
        assert not store.get_kv(ps.KV_PREFIX + key), "%s: nothing asked, nothing stored" % key
    # One stored by the first build is ignored once the setting changes.
    ps.save("discogs", {"ok": None, "detail": "Not configured: set DISCOGS_TOKEN. Nothing was asked.",
                        "ms": 0, "at": ps._now_iso(), "reason": "unconfigured"}, store)
    monkeypatch.setenv("DISCOGS_TOKEN", every_key["DISCOGS_TOKEN"])
    monkeypatch.setenv("TICKETMASTER_ENABLED", "on")
    for key in ("discogs", "ticketmaster"):
        row = _row(key)
        assert row["lamp"] == ("idle", "Not checked yet") and row["can_check"], (key, row["lamp"])
        assert "Not configured" not in row["detail"] and "owner ruling" not in row["detail"]


# --- correctness-5: StemSplit's firewall ---------------------------------------------------------------

@pytest.mark.parametrize("body,firewall", [
    (b"error code: 1010", True),
    (b'{"message": "Invalid API key"}', False),
])
def test_a_cloudflare_1010_is_the_firewall_not_the_key(every_key, net, body, firewall):
    def answer(req, method, url):
        raise urllib.error.HTTPError(url, 403, "Forbidden", email.message.Message(), io.BytesIO(body))

    net.answer = answer
    result = ps.run(ps.by_key("stemsplit"), timeout=ROOMY)
    assert result["ok"] is False
    assert ("Cloudflare" in result["detail"]) is firewall
    assert ("refused the credentials" in result["detail"]) is (not firewall)


# --- correctness-6: a grant outage is not a refused secret ------------------------------------------------

@pytest.mark.parametrize("mode,words", [
    (503, "server error"),
    (429, "rate-limiting"),
    ("timeout", "did not answer in time"),
    (401, "refused the app's credentials"),
])
def test_the_grant_failure_is_read_by_what_it_answered(every_key, net, mode, words):
    import shopify_customers as sc
    store.set_kv(sc.GRANT_KEY, "")
    store.set_kv(sc.GRANT_ERROR_KEY, "")
    net.overrides = {"/admin/oauth/access_token": mode}
    result = ps.run(ps.by_key("shopify_admin"), timeout=ROOMY)
    assert result["ok"] is False and words in result["detail"], result
    if mode != 401:
        assert "refused the app's credentials" not in result["detail"]
    store.set_kv(sc.GRANT_ERROR_KEY, "")


# --- correctness-7 / correctness-8: The MLC is proved by its search -----------------------------------------

@pytest.mark.parametrize("status,body,ok", [
    (200, b"", False),
    (200, {"message": "Internal gateway error"}, False),
    (200, {"unexpected": "shape"}, False),
    (204, b"", True),
    (200, [], True),
])
def test_the_mlc_is_working_only_on_a_list_or_a_204(every_key, net, status, body, ok):
    def answer(req, method, url):
        if url.endswith("/search/recordings"):
            return _Resp(body, status)
        return None

    net.answer = answer
    result = ps.run(ps.by_key("mlc"), timeout=ROOMY)
    assert result["ok"] is ok, result


def test_the_mlc_is_proved_by_its_search_not_its_sign_in(every_key, net):
    """September 2026: sign-in worked while search answered 401."""
    net.overrides = {"/search/recordings": 401}
    result = ps.run(ps.by_key("mlc"), timeout=ROOMY)
    assert result["ok"] is False and "refused with both tokens" in result["detail"], result
    assert net.to("public-api.themlc.com") and any(c[1].endswith("/oauth/token") for c in net.calls)
    searches = [c for c in net.calls if c[1].endswith("/search/recordings")]
    assert searches and all(c[0] == "POST" and json.loads(c[3])["isrc"] == ps.KNOWN_ISRC
                            for c in searches)


def test_soundcharts_is_asked_only_through_the_budget(every_key, net, monkeypatch):
    import soundcharts_budget
    before = soundcharts_budget.counts()["team"]
    assert ps.run(ps.by_key("soundcharts"), timeout=ROOMY)["ok"] is True
    assert soundcharts_budget.counts()["team"] == before + 1, "counted like any other call"
    assert len(net.to("customer.api.soundcharts.com")) == 1
    monkeypatch.setattr(soundcharts_budget, "budget", lambda: 0)
    net.calls.clear()
    result = ps.run(ps.by_key("soundcharts"), timeout=ROOMY)
    assert result["ok"] is None and "Nothing was asked" in result["detail"]
    assert net.calls == [], "a spent allowance asks nobody"


def test_youtube_is_one_channel_lookup_never_a_search(every_key, net):
    assert ps.run(ps.by_key("youtube"), timeout=ROOMY)["ok"] is True
    assert len(net.calls) == 1
    parts = urllib.parse.urlsplit(net.calls[0][1])
    query = urllib.parse.parse_qs(parts.query)
    assert parts.path == "/youtube/v3/channels"
    assert query["part"] == ["id"] and query["id"] == [ps.KNOWN_CHANNEL]


# --- correctness-11: every link is a page ------------------------------------------------------------------

def test_every_open_the_page_link_is_a_page_the_owner_can_open(owner, net):
    for p in ps.PROVIDERS:
        if p.get("where"):
            r = owner.get(p["where"])
            assert r.status_code in (200, 301, 302, 308), (p["key"], p["where"], r.status_code)


# --- correctness-12: the toast says what was not asked ---------------------------------------------------

def test_odesli_inside_its_minute_is_not_asked_and_the_page_says_so(owner, every_key, net):
    _clear_results()
    owner.post("/admin/providers/check/odesli")
    r = owner.post("/admin/providers/check/odesli")
    assert len(net.to("api.song.link")) == 1
    assert "skipped=odesli" in r.headers["Location"]
    body = owner.get(r.headers["Location"]).get_data(as_text=True)
    assert "Not asked again" in body and "The result is on its row below" not in body
    r = owner.post("/admin/providers/check")
    assert len(net.to("api.song.link")) == 1
    assert "skipped=odesli" in r.headers["Location"]
    body = owner.get(r.headers["Location"]).get_data(as_text=True)
    assert "Odesli (song.link)</b> was not asked again" in body


# --- the fixer (2026-09-23): a named state came from a real call ---------------------------------------

def test_a_known_state_a_service_named_counts_as_asked_for_its_interval():
    """Google Routes' "Not enabled" (ok None, with a label) came back from a
    real, billable-once-enabled call, so a second press inside the minute
    shows it instead of asking again. A plain "nothing was asked" does not
    hold the button."""
    p = ps.by_key("google_routes")
    asked = {"ok": None, "label": "Not enabled", "detail": "x", "ms": 80, "at": ps._now_iso()}
    assert ps._too_soon(p, asked)
    assert not ps._too_soon(p, dict(asked, label=None))
    assert ps._too_soon(p, dict(asked, ok=False, label=None))
    assert not ps._too_soon(ps.by_key("itunes"), dict(asked, ok=True)), "no interval, never too soon"


def test_a_page_view_reads_the_stored_results_in_one_go(owner, every_key, monkeypatch):
    """One database read for every row's last result, not one per row: on
    a slow disk the page took seconds opening a connection per service."""
    reads = []
    real = store.get_kv

    def counting(key, default=None):
        if key.startswith(ps.KV_PREFIX):
            reads.append(key)
        return real(key, default)

    monkeypatch.setattr(store, "get_kv", counting)
    assert owner.get("/admin/providers").status_code == 200
    assert reads == [], reads
