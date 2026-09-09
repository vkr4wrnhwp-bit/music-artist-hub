# -*- coding: utf-8 -*-
"""YouTube as a public read: the adapter, the Pulse windows, and the honesty.

The canned bodies below are the shapes the YouTube Data API v3 reference
describes (developers.google.com/youtube/v3): `channels.list` filtered by
`id`, `forHandle` or `forUsername` at 1 quota unit each, `search.list` for
`type=channel` returning `items[].id.channelId` from its own constrained
quota bucket, `statistics` carrying subscriberCount / viewCount /
videoCount / hiddenSubscriberCount, and errors as
`error.errors[].reason`.

The honesty points held here:

  * a hidden subscriber count is None, never the 0 YouTube sends with it;
  * quotaExceeded and keyInvalid reach the caller as Google's own word,
    because "403" does not tell an owner whether to wait or fix the key;
  * search runs at most once, and only when no 1-unit lookup could answer;
  * a non-200 is never cached, so an error cannot outlive itself;
  * with no key configured nothing is called at all and the page names the
    variable that is missing;
  * no channel is ever derived from the artist's name.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

import app as appmod
import signal_providers as providers

CHANNEL = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
OTHER = "UCabcdefghijklmnopqrstuv"
PASSWORD = "yt-tests-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.app


def _channel_body(channel_id=CHANNEL, subs="184000", views="35211870",
                  videos="6041", hidden=False, title="Devora",
                  custom="@devora"):
    return {"kind": "youtube#channelListResponse",
            "items": [{"kind": "youtube#channel", "id": channel_id,
                       "snippet": {"title": title, "customUrl": custom,
                                   "description": "The band's channel"},
                       "statistics": {"viewCount": views,
                                      "subscriberCount": subs,
                                      "hiddenSubscriberCount": hidden,
                                      "videoCount": videos}}]}


def _error_body(reason, message, code=403):
    return {"error": {"code": code, "message": message,
                      "errors": [{"domain": "youtube.quota", "reason": reason,
                                  "message": message}]}}


class Wire(object):
    """A canned transport. Records every URL, so the quota a resolution
    would have spent is visible to the test rather than inferred."""

    def __init__(self, handles=None, usernames=None, ids=None, search=None,
                 raise_on=None):
        self.calls = []
        self.handles = handles if handles is not None else {"@devora": CHANNEL}
        self.usernames = usernames or {}
        self.ids = ids if ids is not None else {CHANNEL: CHANNEL}
        self.search = search if search is not None else {}
        self.raise_on = raise_on or {}

    @property
    def paths(self):
        return [urlparse(u).path for u in self.calls]

    @property
    def searches(self):
        return [p for p in self.paths if p.endswith("/search")]

    def __call__(self, url):
        self.calls.append(url)
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        assert q.get("key"), "the API key travels on every call"
        for needle, err in self.raise_on.items():
            if needle in url:
                raise err
        if u.path.endswith("/search"):
            hit = self.search.get(q.get("q"))
            return {"items": ([{"id": {"kind": "youtube#channel", "channelId": hit},
                                "snippet": {"title": q.get("q")}}] if hit else [])}
        if "forHandle" in q:
            cid = self.handles.get(q["forHandle"])
        elif "forUsername" in q:
            cid = self.usernames.get(q["forUsername"])
        else:
            cid = self.ids.get(q.get("id"))
        if not cid:
            return {"items": []}
        if q.get("part") == "id":
            return {"items": [{"id": cid}]}
        return _channel_body(cid)


@pytest.fixture
def yt(monkeypatch):
    """A configured adapter with a canned wire and no cache, so each test
    counts the calls its own behaviour makes."""
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_CACHE_S", "0")

    def make(**kw):
        wire = Wire(**kw)
        return providers.YouTubeAdapter(fetch=wire), wire
    return make


# --- the endpoints and their quota ------------------------------------------

def test_the_base_url_and_filters_are_the_documented_ones(yt):
    """channels.list by id, forHandle and forUsername; search.list by q."""
    adapter, wire = yt(handles={"@devora": CHANNEL},
                       usernames={"OldName": OTHER},
                       search={"Devora The Band": OTHER})
    assert adapter.resolve_channel("@devora") == CHANNEL
    assert adapter.resolve_channel("https://www.youtube.com/user/OldName") == OTHER
    assert adapter.resolve_channel("Devora The Band") == OTHER
    bases = {urlparse(u).scheme + "://" + urlparse(u).netloc for u in wire.calls}
    assert bases == {"https://www.googleapis.com"}
    assert wire.paths[0] == "/youtube/v3/channels"
    assert wire.paths[-1] == "/youtube/v3/search"
    q = {k: v[0] for k, v in parse_qs(urlparse(wire.calls[0]).query).items()}
    assert q["forHandle"] == "@devora"
    s = {k: v[0] for k, v in parse_qs(urlparse(wire.calls[-1]).query).items()}
    assert s["type"] == "channel" and s["part"] == "snippet"
    assert s["q"] == "Devora The Band"


@pytest.mark.parametrize("typed, expected_kind", [
    ("https://www.youtube.com/channel/" + CHANNEL, "id"),
    (CHANNEL, "id"),
    ("https://www.youtube.com/@devora", "handle"),
    ("youtube.com/@devora", "handle"),
    ("@devora", "handle"),
    ("https://www.youtube.com/user/OldName", "username"),
    ("https://www.youtube.com/c/DevoraMusic", "name"),
    ("Devora The Band", "name"),
])
def test_a_url_a_handle_and_a_name_are_told_apart(typed, expected_kind):
    kind, _ = providers.YouTubeAdapter.parse_channel_input(typed)
    assert kind == expected_kind


def test_a_channel_id_and_a_handle_never_spend_a_search(yt):
    adapter, wire = yt()
    assert adapter.resolve_channel(CHANNEL) == CHANNEL
    assert adapter.resolve_channel("https://www.youtube.com/channel/" + CHANNEL) == CHANNEL
    assert adapter.resolve_channel("@devora") == CHANNEL
    assert adapter.resolve_channel("https://www.youtube.com/@devora") == CHANNEL
    assert wire.searches == [], "four resolutions, all at 1 unit each"
    assert adapter.searches == 0


def test_search_is_the_last_resort_and_runs_once(yt):
    """A bare word is tried as a handle and as a username first - both 1
    unit - and only then searched, exactly once."""
    adapter, wire = yt(handles={}, usernames={}, search={"devora": CHANNEL})
    assert adapter.resolve_channel("devora") == CHANNEL
    assert len(wire.searches) == 1
    assert wire.paths == ["/youtube/v3/channels", "/youtube/v3/channels",
                          "/youtube/v3/search"]
    assert adapter.searches == 1


def test_a_name_that_matches_nothing_searches_once_and_answers_empty(yt):
    adapter, wire = yt(handles={}, usernames={}, search={})
    assert adapter.resolve_channel("Nobody At All") == ""
    assert len(wire.searches) == 1, "one search, not a retry loop"


def test_a_handle_that_does_not_exist_is_not_widened_into_a_search(yt):
    """Searching for a handle the owner typed exactly would hand back
    somebody else's channel under their own name."""
    adapter, wire = yt(handles={}, search={"@devora": OTHER})
    assert adapter.resolve_channel("@devora") == ""
    assert wire.searches == []


# --- the statistics ---------------------------------------------------------

def test_the_statistics_are_parsed_as_numbers_with_the_channel_identity(yt):
    adapter, _ = yt()
    got = adapter.get_social(CHANNEL)
    assert got["subscribers"] == 184000
    assert got["views"] == 35211870
    assert got["videos"] == 6041
    assert got["hidden"] is False
    assert got["channel_title"] == "Devora"
    assert got["channel_url"] == "https://www.youtube.com/@devora"
    assert got["measured_at"].tzinfo is not None


def test_a_hidden_subscriber_count_is_none_and_not_the_nought_youtube_sends(yt):
    """YouTube sends subscriberCount 0 beside hiddenSubscriberCount true.
    Printing that would say the artist has no subscribers."""
    adapter, _ = yt()
    adapter._fetch = lambda url: _channel_body(subs="0", hidden=True)
    got = adapter.get_social(CHANNEL)
    assert got["hidden"] is True
    assert got["subscribers"] is None, "hidden is not zero"
    assert got["views"] == 35211870, "the views are still real"


def test_a_channel_youtube_does_not_have_answers_none(yt):
    adapter, _ = yt(ids={})
    assert adapter.get_social("UCnotarealchannelid00000") is None


# --- errors, in Google's own words ------------------------------------------

@pytest.mark.parametrize("reason, message, code", [
    ("quotaExceeded", "The request cannot be completed because you have "
     "exceeded your quota.", 403),
    ("keyInvalid", "Bad Request", 400),
    ("accessNotConfigured", "YouTube Data API has not been used in project "
     "123 before or it is disabled.", 403),
])
def test_googles_own_reason_reaches_the_caller(yt, reason, message, code):
    adapter, _ = yt()
    text = providers.YouTubeAdapter.error_text(_error_body(reason, message, code))
    assert reason in text and message in text

    def boom(url):
        raise providers.ProviderError("YouTube %d: %s" % (code, text))
    adapter._fetch = boom
    with pytest.raises(providers.ProviderError) as e:
        adapter.get_social(CHANNEL)
    assert reason in str(e.value)
    assert str(code) in str(e.value)


def test_a_quota_error_during_resolution_is_not_swallowed_as_no_match(yt):
    """A 400 on one filter is a no-match on that filter. A quota or key
    failure is the account's answer and has to surface."""
    err = providers.ProviderError(
        "YouTube 403: quotaExceeded - The request cannot be completed "
        "because you have exceeded your quota.")
    adapter, _ = yt(raise_on={"forHandle": err})
    with pytest.raises(providers.ProviderError) as e:
        adapter.resolve_channel("@devora")
    assert "quotaExceeded" in str(e.value)


# --- the cache --------------------------------------------------------------

def test_the_answer_holds_for_six_hours_then_is_read_again(monkeypatch, flask_app):
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.delenv("YOUTUBE_CACHE_S", raising=False)
    assert providers.YouTubeAdapter.cache_ttl() == 6 * 3600
    wire = Wire()
    adapter = providers.YouTubeAdapter(fetch=wire)
    with flask_app.app_context():
        assert adapter.get_social(CHANNEL)["subscribers"] == 184000
        assert len(wire.calls) == 1
        assert adapter.get_social(CHANNEL)["subscribers"] == 184000
        assert len(wire.calls) == 1, "inside six hours, the store answered"
        at = adapter.social_cached_at(CHANNEL)
        assert at is not None

        # Five hours on it still holds; seven hours on it does not.
        real = providers._utcnow()
        monkeypatch.setattr(providers, "_utcnow",
                            lambda: real + timedelta(hours=5))
        adapter.get_social(CHANNEL)
        assert len(wire.calls) == 1
        monkeypatch.setattr(providers, "_utcnow",
                            lambda: real + timedelta(hours=7))
        adapter.get_social(CHANNEL)
        assert len(wire.calls) == 2
        assert adapter.social_cached_at(CHANNEL) is not None


def test_a_non_200_is_never_cached(monkeypatch, flask_app):
    """A quota error kept for six hours would outlast the quota itself."""
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.delenv("YOUTUBE_CACHE_S", raising=False)
    calls = []

    def boom(url):
        calls.append(url)
        raise providers.ProviderError(
            "YouTube 403: quotaExceeded - you have exceeded your quota.")
    adapter = providers.YouTubeAdapter(fetch=boom)
    with flask_app.app_context():
        for _ in range(2):
            with pytest.raises(providers.ProviderError):
                adapter.get_social(OTHER)
        assert len(calls) == 2, "the failure was asked again, not served from a store"
        assert adapter.social_cached_at(OTHER) is None


def test_the_api_key_never_reaches_a_message_a_viewer_could_see(monkeypatch,
                                                              flask_app):
    """The key travels in the query string, so a transport failure that
    quoted the URL would print it on the page."""
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "super-secret-key")
    monkeypatch.setenv("YOUTUBE_CACHE_S", "0")
    redacted = providers.YouTubeAdapter.redact(
        "YouTube: <urlopen error> for /channels?key=super-secret-key")
    assert redacted == "YouTube: <urlopen error> for /channels?key=[key]"

    def leaky(url):
        raise providers.ProviderError(
            providers.YouTubeAdapter.redact("YouTube: timed out on " + url))
    adapter = providers.YouTubeAdapter(fetch=leaky)
    with pytest.raises(providers.ProviderError) as e:
        adapter.get_social(CHANNEL)
    assert "super-secret-key" not in str(e.value)
    assert "[key]" in str(e.value)


def test_the_cache_key_carries_no_api_key(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "super-secret-key")
    key = providers.YouTubeAdapter.cache_key(
        "/channels", {"part": "snippet,statistics", "id": CHANNEL})
    assert key.startswith("youtube:") and "super-secret-key" not in key


# --- not configured ---------------------------------------------------------

def test_with_no_key_nothing_is_called_and_the_missing_var_is_named(monkeypatch):
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    wire = Wire()
    adapter = providers.YouTubeAdapter(fetch=wire)
    assert adapter.configured() is False
    assert adapter.missing_env() == ["YOUTUBE_API_KEY"]
    assert "YOUTUBE_API_KEY" in adapter.health_check()["detail"]
    with pytest.raises(providers.ProviderError):
        adapter.get_social(CHANNEL)
    assert wire.calls == [], "not one request left the process"


def test_the_flag_alone_disables_it_the_house_way(monkeypatch):
    monkeypatch.delenv("YOUTUBE_ENABLED", raising=False)
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    adapter = providers.YouTubeAdapter()
    assert adapter.configured() is False
    assert "YOUTUBE_ENABLED" in adapter.health_check()["detail"]


def test_it_claims_social_only_and_says_why(monkeypatch):
    """CAP_METRICS would need a series. The public API has none."""
    assert providers.YouTubeAdapter.capabilities == (providers.CAP_SOCIAL,)
    assert providers.CAP_METRICS not in providers.YouTubeAdapter.capabilities
    doc = providers.YouTubeAdapter.__doc__
    assert "CAP_SOCIAL only" in doc and "NOT CAP_METRICS" in doc
    with pytest.raises(NotImplementedError):
        providers.YouTubeAdapter().get_social_activity("x", None, None)


def test_it_is_registered_after_the_providers_that_already_serve_a_capability():
    """Adding it must not move CAP_SOCIAL away from Soundcharts."""
    real = providers._REAL_ADAPTERS
    assert providers.YouTubeAdapter in real
    assert real.index(providers.YouTubeAdapter) > real.index(providers.SoundchartsAdapter)


# --- the Signal admin screen ------------------------------------------------

def _owner(flask_app, label="YT Admin"):
    """An owner of the Signal org, the way the Signal admin tests make one."""
    import db as store
    import signal_store as sstore
    email = "yt-adm-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    org = sstore.default_org()
    sstore.upsert_member(org["id"], email, label, "owner", user_id=user["id"])
    return client


def _adapter_row(body, key):
    rows = [r for r in body.split("<tr>") if "<b>%s</b>" % key in r]
    assert rows, "%s has no row in the adapters table" % key
    return rows[0]


def test_the_data_sources_page_lists_it_under_social_with_its_health(flask_app,
                                                                     monkeypatch):
    monkeypatch.delenv("YOUTUBE_ENABLED", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    providers.reset_registry(None)
    client = _owner(flask_app)
    try:
        body = client.get("/signal/admin/data-sources").get_data(as_text=True)
    finally:
        providers.reset_registry(None)
    row = _adapter_row(body, "youtube")
    assert "social" in row, "it is listed under CAP_SOCIAL"
    assert "not configured" in row
    assert "disabled (YOUTUBE_ENABLED is not set)" in row, "the health line names the flag"


def test_enabling_youtube_does_not_take_social_away_from_soundcharts(flask_app,
                                                                     monkeypatch):
    """Registering a new adapter must not move a capability that was
    already served."""
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_CLIENT_ID", "c")
    monkeypatch.setenv("SOUNDCHARTS_CLIENT_SECRET", "s")
    providers.reset_registry(None)
    try:
        reg = providers.registry()
        assert reg.for_capability(providers.CAP_SOCIAL).key == "soundcharts"
        client = _owner(flask_app)
        row = _adapter_row(
            client.get("/signal/admin/data-sources").get_data(as_text=True),
            "youtube")
        assert "configured" in row and "not configured" not in row
    finally:
        providers.reset_registry(None)


# --- Artist Pulse -----------------------------------------------------------

@pytest.fixture
def artist(flask_app):
    import db as store
    email = "ytp-%s@example.net" % uuid.uuid4().hex[:10]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "YT Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with flask_app.app_context():
        uid = store.get_user_by_email(email)["id"]
        store.save_pulse_profile(uid, "spotify-artist-yt", "YT Tester")
    return {"client": client, "uid": uid}


@pytest.fixture
def live_youtube(monkeypatch):
    """A configured YouTube adapter installed in the registry, so /pulse
    reads it the way it reads the real one."""
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_CACHE_S", "0")
    wire = Wire()
    adapter = providers.YouTubeAdapter(fetch=wire)
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    yield adapter, wire
    providers.reset_registry(None)


def _yt_section(body):
    assert 'id="youtube"' in body, "the YouTube panel is on the page"
    return body.split('id="youtube"')[1].split("</section>")[0]


def test_before_a_channel_is_named_the_windows_read_not_measured(artist,
                                                                 live_youtube):
    _, wire = live_youtube
    body = artist["client"].get("/pulse").get_data(as_text=True)
    section = _yt_section(body)
    assert section.count('<span class="sb-lcd-v">Not measured</span>') == 2
    assert "subscribers" in section and "total views" in section
    assert "Name your channel below" in section
    assert wire.calls == [], "nothing is fetched until the owner names one"


def test_the_page_never_guesses_a_channel_from_the_artist_name(artist,
                                                               live_youtube):
    _, wire = live_youtube
    artist["client"].get("/pulse")
    assert wire.searches == []
    assert "YT Tester" not in "".join(wire.calls)


def test_naming_a_channel_stores_youtubes_own_id_and_the_numbers_appear(artist,
                                                                        live_youtube):
    import db as store
    adapter, wire = live_youtube
    client = artist["client"]
    r = client.post("/pulse/youtube", data={"channel": "@devora"})
    assert r.status_code in (302, 303)
    with appmod.app.app_context():
        assert store.get_pulse_profile(artist["uid"])["youtube_channel_id"] == CHANNEL
    section = _yt_section(client.get("/pulse").get_data(as_text=True))
    assert '<span class="sb-lcd-v">184,000</span>' in section
    assert '<span class="sb-lcd-v">35,211,870</span>' in section
    assert "Measured by YouTube, less than an hour ago." in section
    assert "Not measured" not in section
    assert "Devora" in section


def test_the_measured_caption_carries_the_age_of_the_reading(artist, monkeypatch,
                                                             live_youtube):
    adapter, _ = live_youtube
    client = artist["client"]
    client.post("/pulse/youtube", data={"channel": "@devora"})
    monkeypatch.setattr(
        adapter, "social_cached_at",
        lambda cid: datetime.now(timezone.utc) - timedelta(hours=4))
    section = _yt_section(client.get("/pulse").get_data(as_text=True))
    assert "Measured by YouTube, 4 hours ago." in section


def test_a_hidden_count_reads_not_measured_on_the_page_and_says_why(artist,
                                                                    live_youtube):
    adapter, _ = live_youtube
    client = artist["client"]
    client.post("/pulse/youtube", data={"channel": "@devora"})
    adapter._fetch = lambda url: _channel_body(subs="0", hidden=True)
    section = _yt_section(client.get("/pulse").get_data(as_text=True))
    assert '<span class="sb-lcd-v">Not measured</span>' in section
    assert "hides its subscriber count" in section
    assert '<span class="sb-lcd-v">35,211,870</span>' in section


def test_a_channel_nobody_can_resolve_says_so_and_stores_nothing(artist,
                                                                 live_youtube):
    import db as store
    _, wire = live_youtube
    client = artist["client"]
    r = client.post("/pulse/youtube", data={"channel": "@nobody-at-all"})
    assert "yt=notfound" in r.headers["Location"]
    with appmod.app.app_context():
        assert store.get_pulse_profile(artist["uid"])["youtube_channel_id"] == ""
    section = _yt_section(client.get("/pulse?yt=notfound").get_data(as_text=True))
    assert "No YouTube channel matched that" in section


def test_clearing_the_field_forgets_the_channel(artist, live_youtube):
    import db as store
    client = artist["client"]
    client.post("/pulse/youtube", data={"channel": "@devora"})
    client.post("/pulse/youtube", data={"channel": "  "})
    with appmod.app.app_context():
        assert store.get_pulse_profile(artist["uid"])["youtube_channel_id"] == ""


def test_a_new_artist_drops_the_old_channel(artist, live_youtube):
    import db as store
    client = artist["client"]
    client.post("/pulse/youtube", data={"channel": "@devora"})
    with appmod.app.app_context():
        store.save_pulse_profile(artist["uid"], "spotify-artist-other", "Someone Else")
        assert store.get_pulse_profile(artist["uid"])["youtube_channel_id"] == ""


def test_with_no_key_the_panel_names_the_variable_and_calls_nothing(artist,
                                                                    monkeypatch):
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    wire = Wire()
    adapter = providers.YouTubeAdapter(fetch=wire)
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    try:
        section = _yt_section(artist["client"].get("/pulse").get_data(as_text=True))
    finally:
        providers.reset_registry(None)
    assert "YOUTUBE_API_KEY" in section
    assert section.count('<span class="sb-lcd-v">Not measured</span>') == 2
    assert wire.calls == []
    assert 'action="/pulse/youtube"' not in section, \
        "no field to fill in until the server has a key"


def test_the_graph_caption_no_longer_claims_youtube_has_no_public_api():
    """It has one - it just has no history, which is why there is still no
    line, only the two windows."""
    import io as _io
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    page = _io.open(_os.path.join(here, "templates", "pulse.html"),
                    encoding="utf-8").read()
    assert "TikTok / Apple / YouTube lines aren't shown" not in page
    assert "YouTube's public API reports current totals with no history" in page
