"""The external data providers tell the truth about what they did (audit,
2026-09-23, the providers group).

The owner's rulings these hold: a provider that is not configured or fails
says so plainly; nothing invented, sample or stale is shown as live; every
figure carries its source and when it was read; paid budgets are enforced.
No test here reaches a real service: every transport is a fake.
"""
import io
import json
import threading
import uuid
from datetime import date, timedelta
from urllib.parse import urlparse

import pytest

import db as store
import epk_config
import music_apis
import pulse_everything
import pulse_signals
import recovery_mlc
import signal_providers as providers
import soundcharts_budget
from app import create_app
from signal_providers import ProviderError, ProviderNoAnswer, ProviderNotAsked

PW = "provider-honesty-1"
A = "11e81bcc-9c1c-ce38-b96b-a0369fe50396"


@pytest.fixture
def app_obj():
    return create_app()


def _account(app_obj, monkeypatch=None, owner=False, plan="pro"):
    email = "ph-%s@example.net" % uuid.uuid4().hex[:10]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava Kane", "email": email, "password": PW})
    client.post("/login", data={"email": email, "password": PW})
    if plan:
        client.post("/plan/switch", data={"plan": plan})
    if owner:
        monkeypatch.setenv("OWNER_EMAILS", email)
    return client, store.get_user_by_email(email)


@pytest.fixture
def soundcharts(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "app")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    for k in ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET", "SOUNDCHARTS_ACCESS_TOKEN",
              "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    yield
    providers.reset_registry(None)


def _install(fetch):
    adapter = providers.SoundchartsAdapter(fetch=fetch)
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    return adapter


def _hang(calls):
    def fetch(url):
        calls.append(url)
        raise ProviderNoAnswer("Soundcharts did not answer in time", slow=True)
    return fetch


# --- providers-2: a page's time budget, and the circuit break ------------------

def test_a_slow_failure_stops_the_rest_of_the_page_asking(soundcharts):
    calls = []
    adapter = providers.SoundchartsAdapter(fetch=_hang(calls))
    with providers.time_budget(25):
        view = pulse_everything.build(adapter, A, today=date(2026, 9, 23))
    assert len(calls) == 1, "one hang, then nothing else is sent"
    assert "profile" in view["failed"]
    assert set(view["not_asked"]) == {"radio", "youtube_views"}
    states = {r["state"] for r in view["audience_rows"] + view["playlist_rows"] + view["report_rows"]}
    assert states == {"not_asked"}


def test_a_spent_budget_sends_nothing(soundcharts):
    calls = []
    adapter = providers.SoundchartsAdapter(fetch=lambda url: calls.append(url) or {})
    with providers.time_budget(0):
        with pytest.raises(ProviderNotAsked):
            adapter._get("/api/v2.9/artist/%s" % A)
    assert calls == []


def test_a_reload_right_after_a_hang_does_not_wait_again(soundcharts):
    calls = []
    adapter = providers.SoundchartsAdapter(fetch=_hang(calls))
    with pytest.raises(ProviderNoAnswer):
        adapter._get("/api/v2.9/artist/%s" % A)
    with pytest.raises(ProviderNotAsked):
        adapter._get("/api/v2.9/artist/%s" % A)
    assert len(calls) == 1


def test_pulse_with_soundcharts_hanging_asks_once(soundcharts, app_obj):
    calls = []
    _install(_hang(calls))
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    store.save_pulse_provider_artist(user["id"], "soundcharts", A)
    store.record_pulse_snapshot(user["id"], 100, None, None, provider="soundcharts",
                                day=(date.today() - timedelta(days=3)).isoformat(),
                                monthly_listeners=4400)
    body = client.get("/pulse").get_data(as_text=True)
    assert len(calls) == 1, calls
    assert "Soundcharts did not answer in time" in body
    assert "Not asked this time" in body


# --- providers-6: platform failures are named, refusals are the owner's --------

def _wire(fail=None, refuse=None):
    """Every section answers, except the platforms named."""
    calls = []

    def fetch(url):
        calls.append(url)
        p = urlparse(url).path
        if fail and fail in p:
            raise ProviderError("Soundcharts 500: upstream failure")
        if refuse and refuse in p:
            raise ProviderError("Soundcharts 403: Not in your plan.")
        if p.endswith("/streaming/spotify/listening"):
            return {"items": [{"date": "%sT00:00:00+00:00" % date.today().isoformat(),
                               "value": 5100}], "page": {"next": None}}
        if "/audience/" in p and not p.endswith("/latest"):
            return {"items": [{"date": "%sT00:00:00+00:00" % date.today().isoformat(),
                               "followerCount": 901}], "page": {"next": None}}
        return {"items": [], "page": {"next": None}}
    return fetch, calls


def _pulse_page(app_obj, monkeypatch, owner=False):
    client, user = _account(app_obj, monkeypatch, owner=owner)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    store.save_pulse_provider_artist(user["id"], "soundcharts", A)
    store.record_pulse_snapshot(user["id"], 100, None, None, provider="soundcharts",
                                day=date.today().isoformat(), monthly_listeners=5100)
    body = client.get("/pulse").get_data(as_text=True)
    return body.split('id="everything"')[1].split("</section>")[0]


def test_a_platform_that_did_not_answer_says_so_to_everyone(soundcharts, app_obj, monkeypatch):
    fetch, _calls = _wire(fail="/audience/facebook")
    _install(fetch)
    section = _pulse_page(app_obj, monkeypatch)
    grid = section.split("Audience by platform")[1].split("Playlists by platform")[0]
    assert "Facebook" in grid and "Did not answer just now" in grid
    assert "Not in the plan" not in section


def test_the_owner_sees_what_the_plan_refused(soundcharts, app_obj, monkeypatch):
    fetch, _calls = _wire(refuse="/audience/facebook")
    _install(fetch)
    section = _pulse_page(app_obj, monkeypatch, owner=True)
    grid = section.split("Audience by platform")[1].split("Playlists by platform")[0]
    assert "Facebook" in grid and "Not in the plan" in grid


def test_a_customer_does_not_see_the_plan_refusal(soundcharts, app_obj, monkeypatch):
    fetch, _calls = _wire(refuse="/audience/facebook")
    _install(fetch)
    section = _pulse_page(app_obj, monkeypatch, owner=False)
    assert "Not in the plan" not in section


def test_platform_failures_are_not_filed_as_refusals(soundcharts):
    fetch, _calls = _wire(fail="/audience/facebook", refuse="/audience/tiktok")
    adapter = providers.SoundchartsAdapter(fetch=fetch)
    got = adapter.get_audience_all(A, date(2026, 9, 1), date(2026, 9, 23))
    assert got["facebook"]["state"] == "failed"
    assert got["tiktok"]["state"] == "refused"


# --- providers-7: no snapshot on file still names why -------------------------

def test_a_refusal_with_nothing_on_file_is_named(soundcharts, app_obj):
    def refuse(url):
        raise ProviderError("Soundcharts 401: Unauthorized")
    _install(refuse)
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    body = client.get("/pulse").get_data(as_text=True)
    assert "Monthly listeners" in body
    assert "Soundcharts refused the request just now (Soundcharts 401: Unauthorized)" in body


def test_no_metrics_provider_is_named(monkeypatch, app_obj):
    monkeypatch.delenv("SOUNDCHARTS_ENABLED", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    providers.reset_registry(None)
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    body = client.get("/pulse").get_data(as_text=True)
    assert "No metrics provider is connected on this service" in body


# --- providers-10: Deezer that was never asked is not "no match" -------------

def test_deezer_never_asked_says_why():
    out = pulse_signals.build(None, None, None, None, [], today=date(2026, 9, 23),
                              deezer_state="no_spotify")
    deezer = [i for i in out if i["key"] == "deezer"][0]
    assert "No Deezer match" not in deezer["detail"]
    assert "Spotify is not connected" in deezer["detail"]


def test_pulse_without_spotify_does_not_claim_a_deezer_miss(monkeypatch, app_obj):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    body = client.get("/pulse").get_data(as_text=True)
    assert "No Deezer match found" not in body
    assert "Deezer was not asked" in body


# --- providers-9: Deezer error objects are not cached ------------------------

QUOTA = {"error": {"type": "Exception", "message": "Quota limit exceeded", "code": 4}}


def test_a_deezer_quota_error_is_asked_again_next_time(monkeypatch):
    calls = []
    answers = {"quota": True}

    def fetch(url):
        calls.append(url)
        if answers["quota"]:
            return QUOTA
        if "/track/isrc:" in url:
            return {"id": 9, "link": "https://www.deezer.com/track/9"}
        if "/search/artist" in url:
            return {"data": [{"id": 5, "name": "Probe Quota", "nb_fan": 77, "link": "x"}]}
        return {}
    monkeypatch.setattr(music_apis, "_fetch_json", fetch)
    isrc = "USPQ%08d" % (uuid.uuid4().int % 10 ** 8)
    name = "Probe Quota %s" % uuid.uuid4().hex[:6]
    assert music_apis.deezer_has_isrc(isrc)[0] is None
    assert music_apis.deezer_artist_fans(name) is None
    assert music_apis.deezer_artist_known_absent(name) is False, "a quota error is not 'no match'"
    answers["quota"] = False
    assert music_apis.deezer_has_isrc(isrc)[0] is True
    assert music_apis.deezer_artist_fans(name)["fans"] == 77


def test_deezers_no_data_is_still_an_answer(monkeypatch):
    monkeypatch.setattr(music_apis, "_fetch_json",
                        lambda url: {"error": {"code": 800, "message": "no data"}})
    isrc = "USND%08d" % (uuid.uuid4().int % 10 ** 8)
    assert music_apis.deezer_has_isrc(isrc)[0] is False
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: pytest.fail("cached"))
    assert music_apis.deezer_has_isrc(isrc)[0] is False


# --- providers-19: a keyword hit is not the artist's own identifiers ----------

def _deezer_catalog(url):
    if "api.deezer.com/search" in url:
        return {"data": [{"id": 1, "title": "Hello", "title_short": "Hello",
                          "artist": {"name": "Adele"}},
                         {"id": 2, "title": "Hello", "title_short": "Hello",
                          "artist": {"name": "Probe Artist"}}]}
    if "/track/1" in url:
        return {"id": 1, "isrc": "GBBKS1500214", "album": {"id": 10}}
    if "/track/2" in url:
        return {"id": 2, "isrc": "USPRB2600002", "album": {"id": 20}}
    if "/album/10" in url:
        return {"id": 10, "upc": "886445581159", "label": "XL Recordings"}
    if "/album/20" in url:
        return {"id": 20, "upc": "198000000002", "label": "Probe Records"}
    return {}


def test_only_a_hit_by_the_same_artist_is_accepted(monkeypatch):
    monkeypatch.setattr(music_apis, "_fetch_json", _deezer_catalog)
    meta = music_apis.deezer_track_metadata("Hello %s" % "", "Probe Artist")
    assert meta["isrc"] == "USPRB2600002" and meta["source"] == "Deezer"
    assert meta["lookup_codes"]["isrc"] == "USPRB2600002" and meta["read_on"]
    other = "Nobody %s" % uuid.uuid4().hex[:6]
    assert music_apis.deezer_track_metadata("Hello", other) is None
    assert music_apis.deezer_track_metadata("Hello", "") is None


def test_the_catalog_names_the_source_of_a_looked_up_code(monkeypatch, app_obj):
    monkeypatch.setattr(music_apis, "_fetch_json", _deezer_catalog)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("MLC not connected in this test")))
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    client, _user = _account(app_obj)
    client.post("/catalog/add", json={"title": "Hello", "artist": "Probe Artist"})
    body = client.get("/catalog").get_data(as_text=True)
    ids = body.split('id="identifiers"')[1].split("</section>")[0]
    assert "USPRB2600002" in ids and "GBBKS1500214" not in ids
    assert "from Deezer, matched by title and artist, not confirmed" in ids
    assert "come from your catalog records" not in ids


# --- providers-8 / providers-3: The MLC ------------------------------------------

def _mlc(monkeypatch, transport):
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "api-user@example.net")
    monkeypatch.setenv("MLC_PASSWORD", "right")
    adapter = providers.MLCAdapter(transport=transport)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: adapter)
    return adapter


def _mlc_transport(search_answer, calls=None):
    def transport(method, url, headers, body):
        if calls is not None:
            calls.append(url)
        if url.endswith("/oauth/token"):
            return 200, {"accessToken": "a", "idToken": "i", "refreshToken": "r", "expiresIn": 3600}
        return search_answer(body)
    return transport


@pytest.mark.parametrize("answer", [None, {}, {"message": "oops"}])
def test_an_unreadable_mlc_200_is_an_error_not_no_work(monkeypatch, app_obj, answer):
    _mlc(monkeypatch, _mlc_transport(lambda body: (200, answer)))
    client, user = _account(app_obj)
    client.post("/tracks/add", data={"title": "Night Drive"})
    t = [t for t in store.list_os_tracks(user["id"]) if t["title"] == "Night Drive"][0]
    store.update_os_track_passport(user["id"], t["id"], dict(t["passport"], isrc="USAIW2600123"))
    sweep_id = recovery_mlc.sweep(user["id"])
    latest = store.latest_recovery_mlc_sweep(user["id"])
    assert latest["id"] == sweep_id
    row = latest["rows"][0]
    assert row["result"] == "error" and "could not read" in row["message"]
    assert latest["summary"]["unmatched"] == 0


def test_a_hanging_mlc_stops_the_sweep_and_keeps_what_was_asked(monkeypatch, app_obj):
    calls = []

    def search(body):
        raise ProviderNoAnswer("The MLC did not answer in time", slow=True)
    _mlc(monkeypatch, _mlc_transport(search, calls))
    client, user = _account(app_obj)
    for n in range(4):
        client.post("/tracks/add", data={"title": "Song %d" % n})
    for n, t in enumerate(store.list_os_tracks(user["id"])):
        store.update_os_track_passport(user["id"], t["id"],
                                       dict(t["passport"], isrc="USAIW2690%03d" % n))
    recovery_mlc.sweep(user["id"])
    searches = [u for u in calls if u.endswith("/search/recordings")]
    assert len(searches) == 1, "one hang, then the rest are not asked"
    latest = store.latest_recovery_mlc_sweep(user["id"])
    results = sorted(r["result"] for r in latest["rows"])
    assert results.count("error") == 1 and results.count("not_asked") == len(results) - 1
    assert latest["summary"]["not_asked"] == len(results) - 1
    assert latest["summary"]["checked"] == 1 and latest["summary"]["unmatched"] == 0
    page = client.get("/recovery").get_data(as_text=True)
    assert "not asked" in page


def test_a_failed_mlc_check_is_not_called_never_checked():
    import artist_os
    ev = artist_os.mlc_evidence({"mlc_check": {"result": "error", "asked": "ISRC USAIW2600123",
                                               "message": "The MLC 500: upstream failure"}})
    assert ev["label"] == "check failed"
    assert "Nobody has asked" not in ev["detail"] and "The MLC 500" in ev["detail"]


# --- providers-12 / 18 / 20: YouTube and Discogs --------------------------------

@pytest.fixture
def youtube(monkeypatch):
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_CACHE_S", "0")


@pytest.mark.parametrize("failure", [
    ProviderNoAnswer("YouTube did not answer in time", slow=True),
    ProviderError("YouTube 500: backendError - Backend Error"),
    ProviderError("YouTube 429: rateLimitExceeded - Too many requests"),
])
def test_youtube_not_answering_is_not_a_no_match(youtube, failure):
    def fetch(url):
        raise failure
    adapter = providers.YouTubeAdapter(fetch=fetch)
    with pytest.raises(ProviderError):
        adapter.resolve_channel("@avakane")


def test_a_rejected_filter_is_still_a_no_match(youtube):
    def fetch(url):
        raise ProviderError("YouTube 400: invalidArgument - bad handle")
    assert providers.YouTubeAdapter(fetch=fetch)._by("forHandle", "@x") == ""


def test_a_string_error_body_is_quoted_not_crashed():
    assert providers.YouTubeAdapter.error_text({"error": "boom"}) == "boom"
    assert providers.YouTubeAdapter.error_text(["x"]) == ""


def test_an_empty_youtube_200_is_not_a_missing_channel(youtube, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CACHE_S", "3600")
    adapter = providers.YouTubeAdapter(fetch=lambda url: {})
    with pytest.raises(ProviderNoAnswer):
        adapter.get_social("UC" + "a" * 22)


def test_an_empty_discogs_200_is_not_a_missing_release(monkeypatch):
    monkeypatch.setenv("DISCOGS_ENABLED", "1")
    monkeypatch.setenv("DISCOGS_TOKEN", "t")
    monkeypatch.setenv("DISCOGS_CACHE_S", "3600")
    adapter = providers.DiscogsAdapter(transport=lambda m, u, h: (200, {}, {}),
                                       sleep=lambda s: None)
    with pytest.raises(ProviderNoAnswer):
        adapter._get("/database/search", q="Ava Kane Night Drive %s" % uuid.uuid4().hex)


def test_a_timeout_is_worded_for_a_person():
    import socket
    err = providers.transport_error("Discogs", socket.timeout("timed out"))
    assert str(err) == "Discogs did not answer in time" and err.slow
    err = providers.transport_error("The MLC", ValueError("Expecting property name"))
    assert str(err) == "The MLC sent a reply this app could not read" and not err.slow


def test_the_catalog_does_not_say_discogs_answered_when_it_did_not():
    text = open("templates/_catalog_passports.html", encoding="utf-8").read()
    assert "Discogs answered:" not in text


# --- providers-22: ?yt= is a code, not free text ------------------------------

def test_free_text_in_the_yt_link_is_not_printed(app_obj, youtube):
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    body = client.get("/pulse?yt=Your+account+is+suspended.+Call+555-0100").get_data(as_text=True)
    assert "Your account is suspended" not in body


def test_googles_reason_still_reaches_the_owner(app_obj, youtube, monkeypatch):
    def fetch(url):
        raise ProviderError("YouTube 403: quotaExceeded - The request cannot be completed")
    adapter = providers.YouTubeAdapter(fetch=fetch)
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    try:
        client, user = _account(app_obj)
        store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
        r = client.post("/pulse/youtube", data={"channel": "@avakane"})
        assert r.headers["Location"].endswith("/pulse?yt=failed#youtube")
        body = client.get("/pulse?yt=failed").get_data(as_text=True)
        assert "quotaExceeded" in body
    finally:
        providers.reset_registry(None)


# --- providers-13: Spotify refusals by kind -----------------------------------

class _Http(Exception):
    def __init__(self, code, body):
        Exception.__init__(self, "HTTP %s" % code)
        self.code, self._body = code, body

    def read(self):
        return json.dumps(self._body).encode()


def test_a_rejected_secret_is_not_usually_temporary(app_obj, monkeypatch):
    import spotify_provider as sp
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "wrong")

    def token():
        raise _Http(400, {"error": "invalid_client", "error_description": "Invalid client secret"})
    monkeypatch.setattr(sp, "app_token", token)
    client, user = _account(app_obj)
    store.save_pulse_profile(user["id"], "sp-%s" % uuid.uuid4().hex[:8], "Ava Kane")
    body = client.get("/pulse").get_data(as_text=True)
    assert "refused this service's app credentials (Invalid client secret)" in body
    assert "usually temporary" not in body


def test_a_search_timeout_is_not_called_a_credential_refusal(app_obj, monkeypatch):
    import socket
    import spotify_provider as sp
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "right")
    monkeypatch.setattr(sp, "app_token", lambda: "tok")

    def api(path, token):
        raise socket.timeout("timed out")
    monkeypatch.setattr(sp, "_api", api)
    client, _user = _account(app_obj)
    answer = client.get("/pulse/search?q=ava").get_json()
    assert answer["refused_kind"] == "noanswer"
    assert answer["refused"] == "Spotify did not answer in time"


# --- providers-14: demo access says sent only when Resend accepted -------------

def test_a_refused_demo_password_mail_is_not_sent(app_obj, monkeypatch):
    import email_provider
    monkeypatch.setenv("RESEND_API_KEY", "re_test")

    def refuse(url, payload, headers):
        raise _Http(403, {"message": "The domain is not verified."})
    monkeypatch.setattr(email_provider, "_http", refuse)
    email = "lead-%s@example.com" % uuid.uuid4().hex[:8]
    r = app_obj.test_client().post("/demo-access", data={"email": email, "workspace": "artist"},
                                   headers={"X-Forwarded-For": "203.0.113.%d" % (uuid.uuid4().int % 250)})
    assert "demo=pending" in r.headers["Location"]
    lead = [i for i in store.get_inbox() if i["kind"] == "demo-access"
            and i["payload"]["email"] == email][0]["payload"]
    assert lead["password_sent"] is False
    assert "not verified" in lead["send_error"]


# --- providers-15: diagnostics are the owner's -----------------------------------

DIAGS = ("/storage/diag", "/mail/diag?domains=1", "/rack/studio-split/diag?probe=1", "/presave/diag")


@pytest.mark.parametrize("path", DIAGS)
def test_a_customer_gets_404_from_every_diagnostic(app_obj, path):
    client, _user = _account(app_obj, plan="label")
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", DIAGS)
def test_the_owner_still_reads_every_diagnostic(app_obj, monkeypatch, path):
    for k in ("R2_ACCOUNT_ID", "RESEND_API_KEY", "STEMSPLIT_API_KEY",
              "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    import spotify_provider
    monkeypatch.setattr(spotify_provider, "_http",
                        lambda *a, **k: pytest.fail("no Spotify call in a test"))
    monkeypatch.setattr(spotify_provider, "app_token", lambda: None)
    client, _user = _account(app_obj, monkeypatch, owner=True, plan=None)
    assert client.get(path).status_code == 200


def test_the_r2_report_never_carries_the_raw_error_body(app_obj, monkeypatch):
    import blob_store

    class _S3(Exception):
        def read(self):
            return (b"<Error><Code>InvalidAccessKeyId</Code><Message>nope</Message>"
                    b"<AWSAccessKeyId>AKIASECRETSECRET</AWSAccessKeyId></Error>")
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: (_ for _ in ()).throw(_S3("403")))
    monkeypatch.setattr(blob_store, "diagnose", lambda: {})
    client, _user = _account(app_obj, monkeypatch, owner=True, plan=None)
    body = client.get("/storage/diag").get_json()
    assert body["s3_code"] == "InvalidAccessKeyId"
    assert "s3_error_body" not in body and "AKIASECRET" not in json.dumps(body)


# --- providers-1: the press kit dates its audience ------------------------------

def test_an_audience_figure_says_when_it_was_read():
    stats = epk_config.real_stats([], 0, metrics={
        "label": "Soundcharts", "monthly_listeners": 5, "followers": 6, "as_of": "2026-09-20"},
        today=date(2026, 9, 23))
    assert all(s["sub"] == "Measured by Soundcharts, as of 20 Sep 2026" for s in stats)


def test_an_old_audience_figure_is_called_the_last_on_file():
    stats = epk_config.real_stats([], 0, metrics={
        "label": "Soundcharts", "monthly_listeners": 98765, "as_of": "2026-03-07"},
        today=date(2026, 9, 23))
    assert stats[0]["sub"] == "Measured by Soundcharts; last figure on file, from 7 Mar 2026"


def test_the_public_kit_shows_the_date(soundcharts, app_obj):
    _install(lambda url: pytest.fail("a public kit must not fetch"))
    client, user = _account(app_obj)
    client.post("/epk/save", json={"tagline": "t", "bio": "b"})
    client.get("/epk")
    store.save_pulse_profile(user["id"], "sp-ava", "Ava Kane")
    store.save_pulse_provider_artist(user["id"], "soundcharts", A)
    store.record_pulse_snapshot(user["id"], 1234, None, None, provider="soundcharts",
                                day="2026-03-07", monthly_listeners=98765)
    slug = store.get_epk(user["id"])["slug"]
    body = app_obj.test_client().get("/epk/" + slug).get_data(as_text=True)
    assert "98,765" in body and "last figure on file, from 7 Mar 2026" in body


# --- providers-21: the allowance cannot be overspent by racing calls ----------

def test_racing_calls_cannot_pass_the_ceiling(monkeypatch):
    kv = {}
    lock = threading.Lock()

    def incr(key, by=1):
        with lock:
            kv[key] = str(int(kv.get(key) or 0) + by)
            return int(kv[key])
    monkeypatch.setattr(store, "get_kv", lambda key, default=None: kv.get(key, default))
    monkeypatch.setattr(store, "set_kv", lambda key, value: kv.__setitem__(key, value))
    monkeypatch.setattr(store, "kv_incr", incr)
    soundcharts_budget.set_budget(100)
    kv[soundcharts_budget._count_key("team")] = "99"
    gate = threading.Barrier(8)
    got = []

    def call():
        gate.wait()
        got.append(soundcharts_budget.reserve("team"))
    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert got.count(True) == 1
    assert soundcharts_budget.counts()["total"] == 100
