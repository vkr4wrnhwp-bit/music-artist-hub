"""Release-Ready, the RoEx back end (owner's brief, 2026-09-19).

An artist uploads a mix, or a vocal and a beat. RoEx writes a mix report,
makes free 30-second previews, and the full master once the artist has
paid through a one-time Stripe Checkout ($6.99 by default, the owner's
price, kept in Settings). RoEx charges the owner per credit, so:

  nothing here ever reaches the network: RoEx's two seams, Stripe's two
  seams and the bucket are replaced, and a real socket connect fails the
  test
  with no key there is nothing to call and the page says so
  the mix report on upload sits under the owner's monthly credit budget
  a paid final is requested once, and only for a claimed payment
  RoEx's webhook is a nudge: a wrong token is a 404, and a right one only
  makes the job read RoEx again
  a file RoEx would refuse is refused here first, before anything is
  stored or sent
  a read-only team seat starts nothing; one account never sees another's
"""
import email
import hashlib
import hmac
import html
import io
import json
import logging
import os
import socket
import sqlite3
import struct
import time
import urllib.error
import urllib.request
import urllib.response
import uuid
import wave
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import app as appmod
import audio_probe
import blob_store
import db as store
import release_ready as rr
import release_ready_settings as rrs
import release_ready_store as rstore
import roex_client as roex
import stripe_provider as sp

PW = "release-ready-1"
SENTINEL = "rk-SENTINEL-123"
SECRET = "whsec_release_ready"
J = {"Accept": "application/json"}
PAGE = rr.PAGE

PREVIEW_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 64


def _wav(seconds=12.0, rate=44100, width=2, channels=1):
    """A real WAV with different bytes every time (so no two uploads match)."""
    buf = io.BytesIO()
    frames = int(seconds * rate)
    seed = hashlib.sha256(uuid.uuid4().bytes).digest()
    size = frames * width * channels
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes((seed * (size // 32 + 1))[:size])
    return buf.getvalue()


MASTER_WAV = _wav(1.0)

REPORT = {
    "bit_depth": 0, "clipping": "MINOR", "if_master_drc": "OPTIMAL",
    "if_master_loudness": "LESS", "if_mix_drc": "LESS", "if_mix_loudness": "MORE",
    "mono_compatible": True, "phase_issues": False, "sample_rate": 44100,
    "peak_loudness_dbfs": -0.4, "stereo_field": "BALANCED",
    "tonal_profile": {"bass_frequency": "HIGH", "low_mid_frequency": "MEDIUM",
                      "high_mid_frequency": "LOW", "high_frequency": "MEDIUM"},
    "summary": {"intro": "A punchy mix.", "summary": "Bring the bass down a touch."},
}


def _analysis_ok(payload=None):
    return 200, {"error": False, "message": "", "info": "",
                 "mixDiagnosisResults": {"completion_time": "t", "error": False, "info": "",
                                         "payload": payload or REPORT}}


# --- the fakes ------------------------------------------------------------------------

class FakeRoex:
    """Stands in for roex_client._http. Every path must be scripted; an
    unscripted call fails the test. The last response for a path repeats."""

    def __init__(self):
        self.calls = []
        self.script = {}

    def on(self, path, *responses):
        self.script[path] = list(responses)

    def __call__(self, method, path, body=None, timeout=30):
        self.calls.append((method, path, json.loads(json.dumps(body)) if body else None))
        assert roex.allowed_path(path), path
        key = "/recombinestatus/" if path.startswith("/recombinestatus/") else path
        queue = self.script.get(key)
        if not queue:
            raise AssertionError("unscripted RoEx call: %s %s" % (method, path))
        resp = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(resp, BaseException):
            raise resp
        return resp

    def paths(self):
        return [p for _m, p, _b in self.calls]

    def bodies(self, path):
        return [b for _m, p, b in self.calls if p == path]

    def count(self, path):
        return self.paths().count(path)


class Env:
    pass


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    """Every test: no network, a fake RoEx, a fake bucket, a fake Stripe,
    background steps run inline, and a clean month of counters."""
    def refuse(*_a, **_k):
        raise RuntimeError("a test tried to open a real network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    e = Env()
    e.roex = FakeRoex()
    monkeypatch.setattr(roex, "_http", e.roex)
    e.files, e.downloads = {}, []

    def download(url, max_bytes=roex.MAX_MASTER_BYTES, timeout=120):
        e.downloads.append(url)
        if url not in e.files:
            raise roex.RoexDownloadError("no such file in the test")
        data = e.files[url]
        path = tmp_path / ("dl-%d" % len(e.downloads))
        path.write_bytes(data)
        return str(path), len(data), hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(roex, "_download", download)

    e.objects, e.puts = {}, []

    def put(key, data, content_type=None):
        e.puts.append(key)
        if e.__dict__.get("put_fails"):
            raise urllib.error.URLError("bucket down")
        e.objects[key] = bytes(data)
        return True
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "put", put)
    monkeypatch.setattr(blob_store, "delete", lambda key: e.objects.pop(key, None) is not None or True)
    monkeypatch.setattr(blob_store, "presigned_get",
                        lambda key, ttl=3600: "https://bucket.test/%s?X-Amz-Expires=%d&X-Amz-Signature=s"
                        % (key, ttl))
    monkeypatch.setattr(blob_store, "fetch",
                        lambda path, timeout=30: e.objects.get(blob_store.key_of(path)))

    e.stripe_calls, e.sessions = [], {}

    def stripe_http(path, fields):
        e.stripe_calls.append((path, dict(fields)))
        if path == "/v1/checkout/sessions":
            sid = "cs_rr_%s" % uuid.uuid4().hex[:8]
            # Stripe keeps the session, open, until it is paid or expired.
            e.sessions[sid] = {"id": sid, "object": "checkout.session", "status": "open",
                               "payment_status": "unpaid"}
            return {"id": sid, "url": "https://checkout.stripe.com/c/" + sid}
        if path.startswith("/v1/checkout/sessions/") and path.endswith("/expire"):
            sid = path.split("/")[4]
            if sid in e.sessions:
                e.sessions[sid]["status"] = "expired"
            return {"id": sid, "status": "expired"}
        return {"id": "x"}

    def stripe_get(path):
        if path.startswith("/v1/checkout/sessions/"):
            return dict(e.sessions.get(path.rsplit("/", 1)[1]) or {})
        return {}
    monkeypatch.setattr(sp, "_http", stripe_http)
    monkeypatch.setattr(sp, "_http_get", stripe_get)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_release_ready")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)

    monkeypatch.setattr(rr, "_spawn", lambda fn, *a: (fn(*a), True)[1])
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("ROEX_API_KEY", SENTINEL)
    for name in ("RENDER", "SANDBOX", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    e.owner_email = "owner-rr-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", e.owner_email)
    with store.get_db() as conn:
        conn.execute("DELETE FROM app_kv WHERE key LIKE 'rr\\_%' ESCAPE '\\'")
        conn.execute("DELETE FROM roex_rate")
    store.set_kv("rr_open", "1")
    return e


def _account(plan="artist", name="Artist", email=None):
    email = email or "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _owner(env):
    return _account("label", "Owner", env.owner_email)


def _upload_mix(c, data=None, name="mix.wav", style="POP", is_master="0", title="Night Drive",
                boxes=True, version=None):
    form = {"mode": "mix", "title": title, "analysis_style": style, "is_master": is_master,
            "consent_version": version or rr.CONSENT_VERSION,
            "file": (io.BytesIO(data if data is not None else _wav()), name)}
    if boxes:
        form.update(rights="1", licence="1")
    return c.post(PAGE + "/upload", data=form, content_type="multipart/form-data", headers=J)


def _upload_pair(c, title="Duet"):
    form = {"mode": "pair", "title": title, "consent_version": rr.CONSENT_VERSION,
            "rights": "1", "licence": "1",
            "vocal": (io.BytesIO(_wav()), "vocal.wav"), "beat": (io.BytesIO(_wav()), "beat.wav")}
    return c.post(PAGE + "/upload", data=form, content_type="multipart/form-data", headers=J)


def _jobs(source_id, jtype=None):
    return rstore.jobs_for_source(source_id, (jtype,) if jtype else None)


def _due(job_id):
    rstore.update_job(job_id, next_poll_at=rstore.iso(rstore.now() - timedelta(seconds=1)))


def _mix_with_report(c, env, **kw):
    env.roex.on("/mixanalysis", _analysis_ok())
    r = _upload_mix(c, **kw)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["source_id"]


def _preview_ready(c, env, sid, task="mt_1", start=72.0):
    """One master preview, made and fetched."""
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": task}))
    r = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["MEDIUM"]},
               headers=J)
    assert r.status_code == 200, r.get_json()
    jid = r.get_json()["jobs"][0]["id"]
    url = "https://roex.test/%s-preview.mp3" % task
    env.files[url] = PREVIEW_BYTES
    env.roex.on("/retrievepreviewmaster", (200, {"previewMasterTaskResults": {
        "download_url_mastered_preview": url, "preview_start_time": start}}))
    _due(jid)
    assert c.get(PAGE + "/jobs/%s.json" % jid).status_code == 200
    assert rstore.get_job(jid)["status"] == "preview_ready"
    return jid


def _sig(payload):
    t = str(int(time.time()))
    v1 = hmac.new(SECRET.encode(), ("%s.%s" % (t, payload)).encode(), hashlib.sha256).hexdigest()
    return {"Stripe-Signature": "t=%s,v1=%s" % (t, v1)}


def _stripe_hook(event_type, obj):
    payload = json.dumps({"type": event_type, "data": {"object": obj}})
    return appmod.app.test_client().post("/webhooks/stripe", data=payload, headers=_sig(payload),
                                         content_type="application/json")


def _paid_session(jid, uid, amount=699, status="paid"):
    return {"id": "cs_paid_%s" % uuid.uuid4().hex[:8], "object": "checkout.session",
            "status": "complete", "payment_status": status, "client_reference_id": uid,
            "amount_total": amount, "currency": "usd",
            "payment_intent": "pi_%s" % uuid.uuid4().hex[:10],
            "metadata": {"kind": "release_ready", "job_id": jid}}


def _owner_notes(env):
    owner = store.get_user_by_email(env.owner_email)
    return store.list_notifications(owner["id"]) if owner else []


# --- 1. no key: not connected, and nothing is called ---------------------------------------

def test_no_key_means_not_connected_and_no_call(env, monkeypatch):
    monkeypatch.delenv("ROEX_API_KEY")
    c = _account()
    state = c.get(PAGE + "/state.json").get_json()["state"]
    assert state["open"] is False and state["code"] == "not_connected"
    assert "isn't connected yet" in state["message"]
    page = c.get(PAGE)
    assert page.status_code == 200 and "isn't connected yet" in html.unescape(page.get_data(as_text=True))
    r = _upload_mix(c)
    assert r.status_code == 409 and "isn't connected yet" in r.get_json()["message"]
    for call in (lambda: roex.mix_analysis("https://x.test/a.wav", "POP", False),
                 lambda: roex.mastering_preview("https://x.test/a.wav", "POP", "MEDIUM"),
                 lambda: roex.retrieve_final_master("mt_1"),
                 lambda: roex.retrieve_recombine("rc_1"),
                 lambda: roex.health()):
        assert call().kind == "not_configured"
    assert env.roex.calls == [] and env.puts == []


def test_a_sandbox_never_spends_credits(monkeypatch):
    monkeypatch.setenv("SANDBOX", "1")
    assert not roex.configured()


def test_the_page_opens_soon_for_artists_and_opens_for_the_owner(env):
    store.set_kv("rr_open", "0")
    artist = _account()
    assert artist.get(PAGE + "/state.json").get_json()["state"]["code"] == "opens_soon"
    assert _upload_mix(artist).status_code == 409
    owner = _owner(env)
    state = owner.get(PAGE + "/state.json").get_json()["state"]
    assert state["open"] and state["code"] == "owner_only"


def test_a_fan_account_cannot_open_it():
    fan = _account("fan")
    assert fan.get(PAGE).status_code == 402


# --- 2. the seam is the only way out ---------------------------------------------------------

def test_the_real_seam_sends_only_the_header_to_roex(monkeypatch):
    seen = []

    class Resp:
        status = 200

        def read(self, n=-1):
            return b'{"mastering_task_id": "mt_9"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(self, req, data=None, timeout=None):
        seen.append((req, self))
        return Resp()
    monkeypatch.setattr(roex, "_http", _reload_http())
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    out = roex.mastering_preview("https://bucket.test/a.wav?X-Amz-Signature=s", "POP", "HIGH")
    assert out.ok and out.data == {"task_id": "mt_9"}
    req, opener = seen[0]
    # The opener that carried the key follows no redirect.
    assert any(type(h).__name__ == "_NoRedirect" for h in opener.handlers)
    assert not any(type(h) is urllib.request.HTTPRedirectHandler for h in opener.handlers)
    assert req.full_url == "https://tonn.roexaudio.com/masteringpreview"
    assert req.get_header("X-api-key") == SENTINEL
    assert "key=" not in req.full_url
    assert json.loads(req.data)["masteringData"]["desiredLoudness"] == "HIGH"


def _reload_http():
    """The module's own _http, read from its source, for the one test that
    drives it against a fake urlopen."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("roex_client_fresh", roex.__file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._http


def test_the_seam_refuses_any_endpoint_outside_the_allowlist(env):
    for path in ("/separate", "/retrievestems", "/upload", "/mixpreview", "/separatestatus/x"):
        assert not roex.allowed_path(path)
        with pytest.raises(ValueError):
            _reload_http()("POST", path, {})
        assert roex._call("POST", path, {}).kind == "bad_request"
    assert env.roex.calls == []
    assert not any(p in roex.ENDPOINTS for p in ("/separate", "/retrievestems", "/upload"))


def test_every_path_a_whole_flow_uses_is_on_the_allowlist(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/f.wav"}))
    env.files["https://roex.test/f.wav"] = MASTER_WAV
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, c._id)).status_code == 200
    assert env.roex.paths()
    for path in env.roex.paths():
        assert path in roex.ENDPOINTS
        assert not any(bad in path for bad in ("/separate", "/retrievestems", "/upload"))


# --- the key never leaves the server ---------------------------------------------------------

def test_the_key_is_scrubbed_from_every_message_and_log(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.roex.on("/retrievepreviewmaster",
                RuntimeError("boom %s https://tonn.roexaudio.com/x?key=%s" % (SENTINEL, SENTINEL)))
    out = roex.retrieve_preview_master("mt_1")
    assert out.kind == "unknown" and SENTINEL not in out.roex_message
    env.roex.on("/retrieverecombine", (500, {"message": "bad key %s at https://a.test/?key=%s"
                                              % (SENTINEL, SENTINEL)}))
    out = roex.retrieve_recombine("rc_1")
    assert out.kind == "server_error"
    assert SENTINEL not in out.roex_message and "key=" not in out.roex_message
    assert SENTINEL not in caplog.text


def test_the_key_is_never_on_a_page_or_in_json(env):
    owner = _owner(env)
    sid = _mix_with_report(owner, env)
    bodies = [owner.get(p).get_data(as_text=True) for p in (
        PAGE, PAGE + "/state.json", PAGE + "/sources/%s" % sid, PAGE + "/sources/%s.json" % sid,
        "/admin/release-ready", "/admin/release-ready.json", "/admin/readiness", "/settings")]
    for body in bodies:
        assert SENTINEL not in body
    job = _jobs(sid)[0]
    assert "roex_task_id" not in owner.get(PAGE + "/jobs/%s.json" % job["id"]).get_data(as_text=True)


# --- the rate limiter ------------------------------------------------------------------------------

def test_ninety_a_minute_then_busy_and_the_window_slides():
    t = datetime(2026, 9, 19, 12, 0, 5, tzinfo=timezone.utc)
    for _ in range(roex.RATE_LIMIT):
        roex._rate_take(t)
    with pytest.raises(roex.RoexBusy):
        roex._rate_take(t)
    assert roex.rate_counts(t)["this_minute"] == roex.RATE_LIMIT, "a refused slot is not counted"
    # Halfway through the next minute the previous one counts for half.
    later = t + timedelta(seconds=55)                 # 12:01:00
    half = later + timedelta(seconds=30)              # 12:01:30
    for _ in range(roex.RATE_LIMIT // 2):
        roex._rate_take(half)
    with pytest.raises(roex.RoexBusy):
        roex._rate_take(half)


def test_two_connections_share_one_count_and_old_rows_go():
    t = datetime(2026, 9, 19, 13, 0, 1, tzinfo=timezone.utc)
    conn = sqlite3.connect(store.db_path())
    conn.execute("INSERT INTO roex_rate (minute, n) VALUES (?, ?)", (roex._minute(t), 89))
    conn.execute("INSERT INTO roex_rate (minute, n) VALUES (?, ?)", ("2026-09-19T09:00", 5))
    conn.commit()
    conn.close()
    roex._rate_take(t)
    with pytest.raises(roex.RoexBusy):
        roex._rate_take(t)
    with store.get_db() as c2:
        assert c2.execute("SELECT COUNT(*) FROM roex_rate WHERE minute = '2026-09-19T09:00'").fetchone()[0] == 0


def test_a_limited_call_never_leaves(env):
    now = roex._now()
    with store.get_db() as conn:
        conn.execute("INSERT INTO roex_rate (minute, n) VALUES (?, ?)", (roex._minute(now), 500))
    out = roex.retrieve_preview_master("mt_1")
    assert out.kind == "busy" and out.sent is False and env.roex.calls == []


# --- 3. the report on upload, under the owner's budget ------------------------------------------

def test_an_upload_records_consent_and_runs_the_report(env):
    c = _account()
    data = _wav()
    env.roex.on("/mixanalysis", _analysis_ok())
    r = _upload_mix(c, data=data, style="TRAP")
    assert r.status_code == 200
    sid = r.get_json()["source_id"]
    consent = [x for x in rstore.consents_for(c._id)][-1]
    assert consent["user_id"] == c._id and consent["actor_id"] == c._id
    assert consent["file_sha256"] == hashlib.sha256(data).hexdigest()
    assert consent["text_version"] == "rr-consent-2" and consent["text_sha256"] == rr.CONSENT_SHA256
    assert consent["rights_attested"] == 1 and consent["licence_granted"] == 1
    src = rstore.get_source(sid)
    assert src["storage_key"] == "r2:release_ready/%s/%s.wav" % (c._id, sid)
    assert env.objects["release_ready/%s/%s.wav" % (c._id, sid)] == data
    body = env.roex.bodies("/mixanalysis")[0]
    assert body == {"mixDiagnosisData": {"audioFileLocation": body["mixDiagnosisData"]["audioFileLocation"],
                                         "musicalStyle": "TRAP", "isMaster": False}}
    assert "X-Amz-Expires=3600" in body["mixDiagnosisData"]["audioFileLocation"]
    job = _jobs(sid, "mix_analysis")[0]
    assert job["status"] == "reported" and job["credits_spent_estimate"] == 10
    view = c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]["report"]
    rep = view["report"]
    assert rep["title"] == "Mix report by RoEx" and view["chip"] == "Mix report ready"
    words = {v["label"]: v["value"] for v in rep["verdicts"]}
    assert words["Loudness"] == "Too quiet for mastering"          # if_mix_loudness MORE
    assert words["Dynamics"] == "Too much compression"             # if_mix_drc LESS
    figures = {f["label"]: f["value"] for f in rep["figures"]}
    assert figures["Integrated loudness"] == "Not measured"         # RoEx sent none
    assert figures["Bit depth"] == "Not measured"                   # RoEx sent 0
    assert figures["True peak"] == "-0.4 dBFS"
    assert "0 LUFS" not in json.dumps(view)
    assert rep["notes_label"] == "Written by RoEx's AI"
    assert not any(k in view for k in ("score", "readiness"))
    assert rrs.counts()["auto"] == 10


def test_a_master_reads_the_master_verdicts_the_right_way_round():
    rep = rr.report_view(REPORT, is_master=True)
    words = {v["label"]: v["value"] for v in rep["verdicts"]}
    assert words["Loudness"] == "Too loud for every major platform"   # LESS = too loud
    apple = rr.report_view(dict(REPORT, if_master_loudness="LESS_APPLE"), True)
    assert apple["verdicts"][0]["value"] == "Fine for Spotify and SoundCloud, too loud for Apple Music"


def test_the_budget_pauses_reports_at_the_cap(env):
    store.set_kv("rr_monthly_credit_budget", "10")
    c = _account()
    env.roex.on("/mixanalysis", _analysis_ok())
    first = _upload_mix(c).get_json()["source_id"]
    second = _upload_mix(c).get_json()["source_id"]
    assert env.roex.count("/mixanalysis") == 1, "the second report never left"
    assert _jobs(first)[0]["status"] == "reported"
    paused = _jobs(second)[0]
    assert paused["status"] == "paused_budget"
    assert rrs.counts()["auto"] == 10
    view = c.get(PAGE + "/sources/%s.json" % second).get_json()["source"]["report"]
    assert view["message"].startswith("Mix reports are paused for the rest of this month")
    # A button press still counts against the budget, so it waits too.
    r = c.post(PAGE + "/sources/%s/report" % second, headers=J)
    assert r.status_code == 409 and env.roex.count("/mixanalysis") == 1
    # The owner raises the budget; the queue picks the paused one up.
    store.set_kv("rr_monthly_credit_budget", "100")
    assert rr.run_due()["resumed"] == 1
    assert _jobs(second)[0]["status"] == "reported" and env.roex.count("/mixanalysis") == 2


def test_the_per_artist_cap_waits_for_a_button_press(env):
    store.set_kv("rr_artist_monthly_reports", "1")
    c = _account()
    env.roex.on("/mixanalysis", _analysis_ok())
    _upload_mix(c)
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid)[0]
    assert job["status"] == "on_request" and env.roex.count("/mixanalysis") == 1
    assert "Get the mix report" in rr.message_for(job)
    assert c.post(PAGE + "/sources/%s/report" % sid, headers=J).status_code == 200
    assert _jobs(sid)[0]["status"] == "reported" and env.roex.count("/mixanalysis") == 2


def test_with_auto_reports_off_nothing_runs_until_asked(env):
    store.set_kv("rr_auto_analysis", "0")
    c = _account()
    sid = _upload_mix(c).get_json()["source_id"]
    assert _jobs(sid)[0]["status"] == "on_request" and env.roex.calls == []


def test_the_same_file_again_reuses_its_report(env):
    c = _account()
    data = _wav()
    env.roex.on("/mixanalysis", _analysis_ok())
    first = _upload_mix(c, data=data).get_json()["source_id"]
    again = _upload_mix(c, data=data).get_json()
    assert again["source_id"] == first and again.get("reused")
    assert env.roex.count("/mixanalysis") == 1 and rrs.counts()["auto"] == 10


def test_a_report_roex_says_failed_keeps_its_credits_counted(env):
    # RoEx processed it and reported a failure. Nothing RoEx publishes says
    # a failed report is free, so the budget keeps it (review RR-4).
    c = _account()
    env.roex.on("/mixanalysis", (200, {"error": False, "mixDiagnosisResults": {
        "error": True, "info": "Audio is silent", "payload": {}}}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid)[0]
    assert job["status"] == "failed" and rrs.counts()["auto"] == 10
    assert job["credits_spent_estimate"] == 10
    assert rr.message_for(job) == ('RoEx couldn\'t process this file. RoEx said: "Audio is silent". '
                                   'Try again, or upload a different export.')


def test_a_report_that_never_answers_keeps_its_credits_counted(env):
    c = _account()
    env.roex.on("/mixanalysis", TimeoutError("read timed out"))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid)[0]
    assert job["status"] == "failed" and job["error_kind"] == "no_answer"
    assert rrs.counts()["auto"] == 10, "RoEx may have charged"


# --- 4. previews: the spec's fields, exactly ------------------------------------------------------

def test_previews_send_the_spec_fields_and_share_one_start(env):
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_a"}),
                (200, {"mastering_task_id": "mt_b"}))
    r = c.post(PAGE + "/sources/%s/previews" % sid,
               data={"style": "POP", "loudness": ["MEDIUM", "HIGH"]}, headers=J)
    assert r.status_code == 200
    first, second = [j["id"] for j in r.get_json()["jobs"]]
    sent = env.roex.bodies("/masteringpreview")
    assert len(sent) == 1, "the second waits to learn where the first starts"
    md = sent[0]["masteringData"]
    assert set(md) == {"trackData", "musicalStyle", "desiredLoudness", "sampleRate"}
    assert len(md["trackData"]) == 1 and set(md["trackData"][0]) == {"trackURL"}
    url = md["trackData"][0]["trackURL"]
    assert url.startswith("https://bucket.test/release_ready/%s/" % c._id)
    assert "X-Amz-Expires=604800" in url
    assert (md["musicalStyle"], md["desiredLoudness"], md["sampleRate"]) == ("POP", "MEDIUM", "44100")
    env.files["https://roex.test/a.mp3"] = PREVIEW_BYTES
    env.roex.on("/retrievepreviewmaster", (200, {"previewMasterTaskResults": {
        "download_url_mastered_preview": "https://roex.test/a.mp3", "preview_start_time": 72.0}}))
    _due(first)
    job = c.get(PAGE + "/jobs/%s.json" % first).get_json()["job"]
    assert job["status"] == "preview_ready" and job["preview"]["starts_at"] == "Starts at 1:12"
    assert job["settings"]["loudness_label"] == "Loudness setting: Medium"
    assert "LUFS" not in json.dumps(job), "a mastering preview has no measured loudness"
    _due(second)
    c.get(PAGE + "/jobs/%s.json" % second)
    md2 = env.roex.bodies("/masteringpreview")[1]["masteringData"]
    assert md2["desiredLoudness"] == "HIGH" and md2["previewStartTime"] == 72.0
    assert "webhookURL" not in md2, "never an empty webhook"
    # The preview is ours, served to its owner only.
    got = c.get(PAGE + "/jobs/%s/preview" % first)
    assert got.status_code == 302 and "X-Amz-Expires=300" in got.headers["Location"]
    assert _account().get(PAGE + "/jobs/%s/preview" % first).status_code == 404


def test_the_free_previews_have_a_cap_per_file(env):
    store.set_kv("rr_previews_per_file", "2")
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_c"}))
    assert c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW", "HIGH"]},
                  headers=J).status_code == 200
    r = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["MEDIUM"]},
               headers=J)
    assert r.status_code == 429 and r.get_json()["message"] == "You've used the free previews for this file."


def test_a_vocal_and_a_beat_recombine_with_both_links(env, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.test")
    c = _account()
    r = _upload_pair(c)
    assert r.status_code == 200 and env.roex.calls == [], "no report for a vocal and a beat"
    sid = r.get_json()["source_id"]
    vocal = rstore.get_source(sid)
    _v, beat = rstore.pair_sources(c._id, vocal["pair_id"])
    assert vocal["role"] == "vocal" and beat["role"] == "beat"
    assert vocal["consent_id"] != beat["consent_id"], "each file has its own consent"
    env.roex.on("/recombine", (200, {"recombineTaskId": "rc_1", "error": False, "message": ""}))
    r = c.post(PAGE + "/sources/%s/previews" % sid,
               data={"style": "TRAP", "loudness": ["MEDIUM"], "vocal_gain_db": "9"}, headers=J)
    jid = r.get_json()["jobs"][0]["id"]
    body = env.roex.bodies("/recombine")[0]["recombineData"]
    assert body["vocalStemURL"].startswith("https://bucket.test/release_ready/%s/%s" % (c._id, vocal["id"]))
    assert body["backingStemURL"].startswith("https://bucket.test/release_ready/%s/%s" % (c._id, beat["id"]))
    assert (body["musicalStyle"], body["desiredLoudness"], body["vocalGainDb"]) == ("TRAP", "MEDIUM", 6.0)
    assert body["webhookURL"].startswith("https://") and "/webhooks/roex/%s/" % jid in body["webhookURL"]
    env.roex.on("/recombinestatus/", (202, ""))
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert rstore.get_job(jid)["status"] == "processing"
    env.roex.on("/recombinestatus/", (200, {"recombineTaskId": "rc_1", "status": "complete"}))
    env.roex.on("/retrieverecombinepreview", (200, {"recombineTaskId": "rc_1", "preview": {
        "preview_url": "https://roex.test/rc.mp3", "preview_start_seconds": 40,
        "measured_lufs_full": -9.84}}))
    env.files["https://roex.test/rc.mp3"] = PREVIEW_BYTES
    _due(jid)
    job = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert job["status"] == "preview_ready"
    assert job["preview"]["measured"] == "Measured by RoEx: -9.8 LUFS (the whole master)"
    assert "/recombinestatus/rc_1" in env.roex.paths()


# --- 5 and 6. RoEx's webhook: a nudge, checked, once -------------------------------------------------

def test_the_webhook_is_refused_without_its_token_and_only_rereads_with_it(env, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.test")
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_w"}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["HIGH"]},
                 headers=J).get_json()["jobs"][0]["id"]
    hook = env.roex.bodies("/masteringpreview")[0]["masteringData"]["webhookURL"]
    token = hook.rsplit("/", 1)[1]
    assert len(token) >= 40 and token not in json.dumps(rstore.get_job(jid))
    anon = appmod.app.test_client()
    before = len(env.roex.calls)
    assert anon.post("/webhooks/roex/%s/%s" % (jid, "wrong-token")).status_code == 404
    assert anon.post("/webhooks/roex/%s/%s" % ("no-such-job", token)).status_code == 404
    assert len(env.roex.calls) == before, "a refused webhook calls nothing"
    # The right token makes the job read RoEx again; the body is not trusted.
    env.roex.on("/retrievepreviewmaster", (202, {"status": 202}))
    r = anon.post("/webhooks/roex/%s/%s" % (jid, token),
                  json={"status": "completed", "download_url": "https://evil.test/x.mp3"})
    assert r.status_code == 200
    assert env.roex.count("/retrievepreviewmaster") == 1
    assert rstore.get_job(jid)["status"] == "processing"
    assert "https://evil.test/x.mp3" not in env.downloads
    # A second update seconds later (RoEx sends several per job) is not
    # dropped: RoEx has finished, so it is read once more and stored.
    env.files["https://roex.test/w.mp3"] = PREVIEW_BYTES
    env.roex.on("/retrievepreviewmaster", (200, {"previewMasterTaskResults": {
        "download_url_mastered_preview": "https://roex.test/w.mp3", "preview_start_time": 10}}))
    assert anon.post("/webhooks/roex/%s/%s" % (jid, token)).status_code == 200
    assert rstore.get_job(jid)["webhook_count"] == 2
    assert rstore.get_job(jid)["status"] == "preview_ready"
    assert env.roex.count("/retrievepreviewmaster") == 2
    # A late delivery for a finished job changes nothing and calls nothing.
    anon.post("/webhooks/roex/%s/%s" % (jid, token))
    assert env.roex.count("/retrievepreviewmaster") == 2


# --- 7. the paid final: after a claimed payment, once ------------------------------------------------

def test_nothing_but_a_payment_starts_the_paid_retrieval(env, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.test")
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    token = env.roex.bodies("/masteringpreview")[0]["masteringData"]["webhookURL"].rsplit("/", 1)[1]
    appmod.app.test_client().post("/webhooks/roex/%s/%s" % (jid, token))
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    c.get(PAGE + "/sources/%s.json" % sid)
    rr.run_due()
    rr.advance(jid)
    assert env.roex.count("/retrievefinalmaster") == 0
    assert env.roex.count("/retrieverecombine") == 0
    assert rstore.get_job(jid)["status"] == "preview_ready"


def test_a_paid_checkout_retrieves_once_stores_and_attaches(env):
    c = _account()
    track = store.add_os_track(c._id, "Night Drive")
    sid = _mix_with_report(c, env, title="Night Drive")
    jid = _preview_ready(c, env, sid)
    r = c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert r.status_code == 200 and r.get_json()["checkout_url"].startswith("https://checkout.stripe.com/")
    fields = [f for p, f in env.stripe_calls if p == "/v1/checkout/sessions"][-1]
    assert fields["mode"] == "payment"
    assert fields["metadata[kind]"] == "release_ready" and fields["metadata[job_id]"] == jid
    assert fields["client_reference_id"] == c._id
    assert fields["line_items[0][price_data][unit_amount]"] == "699"
    assert fields[sp.IDEMPOTENCY_FIELD].startswith("rr-checkout:%s:699:" % jid)
    # The checkout closes by itself long before RoEx's link to the audio.
    left = int(fields["expires_at"]) - time.time()
    assert 2 * 3600 - 5 <= left <= 2.5 * 3600 + 5
    assert "/creative-studio/release-ready/jobs/%s/paid?session_id={CHECKOUT_SESSION_ID}" % jid \
        in fields["success_url"]
    assert env.roex.count("/retrievefinalmaster") == 0, "a checkout is not a payment"
    env.roex.on("/retrievefinalmaster",
                (200, {"finalMasterTaskResults": {"download_url_mastered": "https://roex.test/f.wav"}}))
    env.files["https://roex.test/f.wav"] = MASTER_WAV
    sess = _paid_session(jid, c._id)
    env.sessions[sess["id"]] = sess
    assert _stripe_hook("checkout.session.completed", sess).status_code == 200
    job = rstore.get_job(jid)
    assert env.roex.count("/retrievefinalmaster") == 1
    assert job["status"] == "stored" and job["paid_session_id"] == sess["id"]
    assert env.objects["release_ready/%s/%s-master.wav" % (c._id, jid)] == MASTER_WAV
    assert job["output_url"] == PAGE + "/jobs/%s/master.wav" % jid and job["roex_output_url"] is None
    assert job["os_track_id"] == track, "matched to the song's Track Passport by title"
    # The success redirect and a replayed webhook change nothing.
    assert c.get(PAGE + "/jobs/%s/paid?session_id=%s" % (jid, sess["id"])).status_code == 302
    assert _stripe_hook("checkout.session.completed", sess).status_code == 200
    assert env.roex.count("/retrievefinalmaster") == 1
    notes = [n for n in store.list_notifications(c._id) if n["title"] == "Your master is stored"]
    assert len(notes) == 1
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["chip"] == "Master stored" and view["master"]["url"] == job["output_url"]
    assert view["next"]["passport"] == "/tracks/%s" % track
    assert c.get(view["master"]["url"]).status_code == 302
    assert _account().get(view["master"]["url"]).status_code == 404
    assert rrs.counts() == {"auto": 10, "paid": 220, "total": 230}
    # The owner's desk: 10 credits for the report, 220 for the master.
    row = [a for a in rr.admin_data()["artists"] if a["id"] == c._id][0]
    assert (row["credits"], row["masters"], row["revenue"], row["cost"], row["margin"]) == \
        (230, 1, "6.99", "2.30", "4.69")
    assert rr.admin_data()["summary"]["cost_estimate_usd"] == "2.30"


def test_the_redirect_alone_claims_it_when_the_webhook_never_came(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/g.wav"}))
    env.files["https://roex.test/g.wav"] = MASTER_WAV
    sess = _paid_session(jid, c._id)
    env.sessions[sess["id"]] = sess
    c.get(PAGE + "/jobs/%s/paid?session_id=%s" % (jid, sess["id"]))
    assert rstore.get_job(jid)["status"] == "stored" and env.roex.count("/retrievefinalmaster") == 1


def test_an_unpaid_a_wrong_account_or_a_wrong_amount_retrieves_nothing(env):
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, c._id, status="unpaid")).status_code == 200
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, "someone-else")).status_code == 200
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, c._id, amount=100)).status_code == 200
    assert env.roex.count("/retrievefinalmaster") == 0
    assert rstore.get_job(jid)["status"] == "preview_ready"
    assert any("price" in n["title"] or "match" in n["title"] for n in _owner_notes(env))
    assert owner


def test_a_second_payment_for_the_same_master_is_caught(env):
    _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/h.wav"}))
    env.files["https://roex.test/h.wav"] = MASTER_WAV
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    second = _paid_session(jid, c._id)
    _stripe_hook("checkout.session.completed", second)
    assert env.roex.count("/retrievefinalmaster") == 1
    pay = [p for p in rstore.payments() if p["session_id"] == second["id"]][0]
    assert pay["duplicate"] == 1
    assert any(n["title"] == "A master was paid for twice" for n in _owner_notes(env))


def test_the_owner_sets_the_price_and_the_checkout_follows(env):
    owner = _owner(env)
    assert rrs.price_cents("master") == 699 and rrs.price_display("master") == "6.99"
    r = owner.post("/admin/release-ready/settings", data={"price_master": "7.49"}, headers=J)
    assert r.status_code == 200 and rrs.price_cents("master") == 749
    for bad in ("7,49", "0.10", "150", "abc"):
        r = owner.post("/admin/release-ready/settings", data={"price_master": bad}, headers=J)
        assert r.status_code == 400 and rrs.price_cents("master") == 749
    c = _account()
    assert c.post("/admin/release-ready/settings", data={"price_master": "1.00"}).status_code == 404
    assert rrs.price_cents("master") == 749
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    assert rr.public_job(rstore.get_job(jid))["buy"]["label"] == "Buy this master: $7.49"
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    fields = [f for p, f in env.stripe_calls if p == "/v1/checkout/sessions"][-1]
    assert fields["line_items[0][price_data][unit_amount]"] == "749"


def test_an_old_preview_asks_for_a_fresh_one(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    rstore.update_job(jid, submitted_at=rstore.iso(rstore.now() - timedelta(days=8)))
    r = c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert r.status_code == 409 and r.get_json()["message"] == "Make a fresh preview first, it's free."
    assert not [p for p, _f in env.stripe_calls if p == "/v1/checkout/sessions"]


def test_a_final_that_timed_out_waits_for_the_owner_and_is_tried_once_more(env):
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", TimeoutError("read timed out"))
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "needs_owner" and env.roex.count("/retrievefinalmaster") == 1
    rr.run_due()
    rr.advance(jid)
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert env.roex.count("/retrievefinalmaster") == 1, "never repeated on its own"
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["message"].startswith("Your payment went through.")
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/i.wav"}))
    env.files["https://roex.test/i.wav"] = MASTER_WAV
    assert owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J).status_code == 200
    assert env.roex.count("/retrievefinalmaster") == 2
    assert rstore.get_job(jid)["status"] == "stored"


@pytest.mark.parametrize("not_ready", [(202, {"status": 202}), (200, {"status": "202", "message": "x"})])
def test_a_final_roex_says_is_not_ready_waits_for_the_owner(env, not_ready):
    # Review RR-3: RoEx does not say whether a repeat /retrievefinalmaster
    # charges again, so "not ready" (an HTTP 202, or a 200 whose body says
    # 202) never makes the app ask again on its own. The owner decides.
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", not_ready,
                (200, {"finalMasterTaskResults": "https://roex.test/k.wav"}))
    env.files["https://roex.test/k.wav"] = MASTER_WAV
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "needs_owner" and env.roex.count("/retrievefinalmaster") == 1
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    c.get(PAGE + "/sources/%s.json" % sid)
    rr.run_due()
    rr.advance(jid)
    assert env.roex.count("/retrievefinalmaster") == 1, "never repeated without the owner"
    assert any(n["title"] == "A paid master needs you" for n in _owner_notes(env))
    assert owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J).status_code == 200
    assert rstore.get_job(jid)["status"] == "stored"
    assert env.roex.count("/retrievefinalmaster") == 2


def test_studio_points_at_release_ready_only_when_it_is_open(env):
    import studio_config

    def detail():
        return dict((k, d) for k, _ok, _h, d in studio_config.readiness())["processing"]
    assert "Release-Ready" in detail()
    store.set_kv("rr_open", "0")
    assert "Release-Ready" not in detail()


def test_a_master_the_bucket_refused_is_never_called_stored(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/j.wav"}))
    env.files["https://roex.test/j.wav"] = MASTER_WAV
    env.put_fails = True
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "retrieving" and not job.get("stored_at")
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["chip"] != "Master stored" and view["master"] is None
    assert "Master stored" not in html.unescape(c.get(PAGE + "/sources/%s" % sid).get_data(as_text=True))


# --- 8. out of RoEx credits: the owner is told, the artist gets a kind retry ----------------------

def test_a_report_short_of_credits_alerts_the_owner_and_offers_a_retry(env):
    _owner(env)
    c = _account()
    env.roex.on("/mixanalysis", (402, {"message": "Insufficient credits"}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid)[0]
    assert job["status"] == "credits_short" and rrs.counts()["auto"] == 0
    view = c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]["report"]
    assert view["chip"] == "Needs a retry"
    assert view["message"] == rr.COPY["our_side"]
    assert "credit" not in view["message"].lower(), "the owner's balance is not the artist's business"
    alerts = [n for n in _owner_notes(env) if n["title"] == "RoEx is out of credits"]
    assert len(alerts) == 1 and alerts[0]["link"] == "/admin/release-ready"
    # A second artist hitting the same wall in the same hour: no second alert.
    _upload_mix(_account())
    assert len([n for n in _owner_notes(env) if n["title"] == "RoEx is out of credits"]) == 1
    # Topped up: the artist's retry works.
    env.roex.on("/mixanalysis", _analysis_ok())
    assert c.post(PAGE + "/sources/%s/report" % sid, headers=J).status_code == 200
    assert _jobs(sid)[0]["status"] == "reported"


def test_a_paid_recombine_short_of_credits_tells_the_artist_their_payment_is_safe(env):
    owner = _owner(env)
    c = _account()
    sid = _upload_pair(c).get_json()["source_id"]
    env.roex.on("/recombine", (200, {"recombineTaskId": "rc_9"}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW"]},
                 headers=J).get_json()["jobs"][0]["id"]
    env.roex.on("/recombinestatus/", (200, {"status": "complete"}))
    env.roex.on("/retrieverecombinepreview", (200, {"preview": {"preview_url": "https://roex.test/r9.mp3",
                                                                "measured_lufs_full": -11.0}}))
    env.files["https://roex.test/r9.mp3"] = PREVIEW_BYTES
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert rstore.get_job(jid)["status"] == "preview_ready"
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    fields = [f for p, f in env.stripe_calls if p == "/v1/checkout/sessions"][-1]
    assert fields["metadata[product]"] == "recombine" and fields["line_items[0][price_data][unit_amount]"] == "699"
    env.roex.on("/retrieverecombine", (402, {"message": "Insufficient credits, and auto top-up is disabled"}))
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "credits_short" and env.roex.count("/retrieverecombine") == 1
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["chip"] == "Our side is fixing this"
    assert view["message"] == rr.COPY["paid_waiting"]
    assert len([n for n in _owner_notes(env) if n["title"] == "A paid master is waiting on RoEx credits"]) == 1
    # The owner tops up and presses Try the retrieval again.
    env.roex.on("/retrieverecombine", (200, {"result": {
        "master_url": "https://roex.test/r9.wav", "measured_lufs": -9.1, "peak_level": -1.0,
        "track_length_seconds": 12, "sample_rate": 44100, "bit_depth": 16, "channels": 2,
        "processing": {"musical_style": "POP", "desired_loudness": "LOW", "vocal_gain_db": 0}}}))
    env.files["https://roex.test/r9.wav"] = MASTER_WAV
    assert owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J).status_code == 200
    job = rstore.get_job(jid)
    assert job["status"] == "stored" and rrs.counts()["paid"] == 250
    master = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]["master"]
    assert master["measured"] == {"label": "Measured by RoEx", "loudness": "-9.1 LUFS",
                                  "true_peak": "-1.0 dBFS",
                                  "text": "-9.1 LUFS, true peak -1.0 dBFS"}


# --- 9. a file RoEx would refuse is refused here, before anything happens ---------------------------

@pytest.mark.parametrize("data,name,message", [
    (lambda: _wav(601, rate=8000, width=1), "long.wav",
     "This file is 10:01 long. Release-Ready takes up to 10 minutes per file."),
    (lambda: b"fLaC" + b"\x00" * 4000, "fake.wav",
     "Release-Ready takes WAV, FLAC or MP3. This file looks like something else."),
    (lambda: b"just some text, not audio" * 100, "notes.mp3",
     "Release-Ready takes WAV, FLAC or MP3. This file looks like something else."),
    (lambda: _wav(5), "short.wav", "This file is shorter than 10 seconds."),
    (lambda: _wav(12, rate=96000, width=1), "hires.wav",
     "Export at 44.1 kHz or 48 kHz. This file is 96 kHz."),
])
def test_a_file_roex_would_refuse_is_refused_before_anything(env, data, name, message):
    c = _account()
    r = _upload_mix(c, data=data(), name=name)
    assert r.status_code == 400 and r.get_json()["message"] == message
    assert env.roex.calls == [] and env.puts == []
    assert rstore.consents_for(c._id) == [] and rstore.list_sources(c._id) == []


def test_without_both_boxes_nothing_is_stored_or_sent(env):
    c = _account()
    r = _upload_mix(c, boxes=False)
    assert r.status_code == 400 and r.get_json()["message"] == "Tick both boxes to send this file."
    form = {"mode": "mix", "title": "x", "analysis_style": "POP", "rights": "1",
            "consent_version": rr.CONSENT_VERSION, "file": (io.BytesIO(_wav()), "a.wav")}
    r = c.post(PAGE + "/upload", data=form, content_type="multipart/form-data", headers=J)
    assert r.status_code == 400
    assert env.roex.calls == [] and env.puts == [] and rstore.consents_for(c._id) == []


# --- 10. team seats ---------------------------------------------------------------------------------

def _invite(owner, member, access):
    import team_areas
    r = owner.post("/team/invite", data={"email": member._email, "role": "manager",
                                         "access": access, "areas": list(team_areas.keys())})
    assert r.get_json().get("ok"), r.get_json()
    token = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]["invite_token"]
    assert member.post("/team/join/" + token, data={}).status_code == 302
    assert member.post("/portal/%s/open" % owner._id).status_code == 302


def test_a_read_only_seat_cannot_start_anything(env):
    artist, reader = _account("pro"), _account("artist", "Reader")
    sid = _mix_with_report(artist, env)
    jid = _preview_ready(artist, env, sid)
    _invite(artist, reader, "read")
    calls, puts = len(env.roex.calls), len(env.puts)
    assert reader.get(PAGE + "/sources/%s.json" % sid).status_code == 200, "a reader can look"
    for path, data in ((PAGE + "/upload", {}), (PAGE + "/sources/%s/previews" % sid, {"style": "POP"}),
                       (PAGE + "/sources/%s/report" % sid, {}), (PAGE + "/jobs/%s/buy" % jid, {}),
                       (PAGE + "/sources/%s/delete" % sid, {})):
        assert reader.post(path, data=data, headers=J).status_code == 403, path
    r = _upload_mix(reader)
    assert r.status_code == 403
    assert len(env.roex.calls) == calls and len(env.puts) == puts
    assert not [p for p, _f in env.stripe_calls if p == "/v1/checkout/sessions"]


def test_an_editor_works_in_the_artists_account_but_cannot_pay(env):
    artist, editor = _account("pro"), _account("artist", "Editor")
    _invite(artist, editor, "edit")
    env.roex.on("/mixanalysis", _analysis_ok())
    r = _upload_mix(editor, version=rr.CONSENT_VERSION_SEAT)
    assert r.status_code == 200
    sid = r.get_json()["source_id"]
    src = rstore.get_source(sid)
    assert src["user_id"] == artist._id and src["uploaded_by"] == editor._id
    consent = rstore.get_consent(src["consent_id"])
    assert consent["user_id"] == artist._id and consent["actor_id"] == editor._id
    assert consent["text_version"] == rr.CONSENT_VERSION_SEAT
    jid = _preview_ready(editor, env, sid)
    r = editor.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert r.status_code == 403 and r.get_json()["message"] == "Only the account holder can buy a master."
    assert rr.public_job(rstore.get_job(jid), seat=True)["buy"]["reason"] == \
        "Only the account holder can buy a master."


# --- 11. one account never sees another's -----------------------------------------------------------

def test_one_account_cannot_see_or_touch_anothers_jobs(env):
    a, b = _account(), _account()
    sid = _mix_with_report(a, env)
    jid = _preview_ready(a, env, sid)
    report = _jobs(sid, "mix_analysis")[0]["id"]
    for path in (PAGE + "/sources/%s" % sid, PAGE + "/sources/%s.json" % sid,
                 PAGE + "/jobs/%s.json" % jid, PAGE + "/jobs/%s.json" % report,
                 PAGE + "/jobs/%s/preview" % jid, PAGE + "/jobs/%s/master.wav" % jid,
                 PAGE + "/jobs/%s/paid?session_id=cs_x" % jid):
        assert b.get(path).status_code == 404, path
    for path in (PAGE + "/jobs/%s/buy" % jid, PAGE + "/sources/%s/previews" % sid,
                 PAGE + "/sources/%s/report" % sid, PAGE + "/sources/%s/delete" % sid):
        assert b.post(path, data={"style": "POP", "loudness": ["LOW"]}, headers=J).status_code == 404, path
    assert b.get(PAGE + "/state.json").get_json()["sources"] == []
    assert rstore.get_source(sid)["deleted_at"] is None


def test_a_label_sees_its_roster_artists_status_and_no_audio(env):
    label, artist = _account("label", "Label"), _account("artist", "Signed")
    sid = _mix_with_report(artist, env, title="Roster Song")
    with store.get_db() as conn:
        conn.execute("INSERT INTO roster_members (id, label_id, email, artist_user_id, status,"
                     " invite_token, created) VALUES (?,?,?,?,?,?,?)",
                     (uuid.uuid4().hex, label._id, artist._email, artist._id, "active",
                      uuid.uuid4().hex, rstore.iso()))
    rows = rstore.status_rows(artist._id)
    assert rows and rows[0]["song"] == "Roster Song" and rows[0]["status"] == "Mix report ready"
    assert set(rows[0]) == {"song", "what", "status", "date"}
    assert label.get("/roster/artist/%s" % artist._id).status_code == 200
    assert label.get(PAGE + "/sources/%s.json" % sid).status_code == 404


def test_the_owner_desk_is_the_owners_alone(env):
    owner, other = _owner(env), _account("label")
    assert owner.get("/admin/release-ready").status_code == 200
    assert owner.get("/admin/release-ready.json").get_json()["ok"]
    for path in ("/admin/release-ready", "/admin/release-ready.json"):
        assert other.get(path).status_code == 404
    for path in ("/admin/release-ready/run", "/admin/release-ready/resume",
                 "/admin/release-ready/health", "/admin/release-ready/settings"):
        assert other.post(path, headers=J).status_code == 404
    env.roex.on("/health", (200, "OK"))
    r = owner.post("/admin/release-ready/health", headers=J)
    assert r.get_json()["kind"] == "ok" and env.roex.paths() == ["/health"]


# --- the words -----------------------------------------------------------------------------------------

def test_the_copy_has_no_em_dash_and_no_monospace():
    words = list(rr.COPY.values()) + list(rr.CHIPS.values()) + list(rr.consent_text().values())
    words += [rr.report_view(REPORT, False), rr.report_view({}, True)]
    for w in words:
        assert "\u2014" not in json.dumps(w, ensure_ascii=False)
    for name in ("release_ready.html", "release_ready_source.html", "_rr_report.html",
                 "release_ready_admin.html"):
        text = open(os.path.join(os.path.dirname(rr.__file__), "templates", name),
                    encoding="utf-8").read()
        assert "\u2014" not in text and "monospace" not in text


def test_an_empty_report_is_not_measured_not_zero():
    rep = rr.report_view({}, False)
    assert all(v["value"] == "Not measured" for v in rep["verdicts"])
    assert all(f["value"] == "Not measured" for f in rep["figures"])


# --- the audio header reader -------------------------------------------------------------------------

def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


@pytest.mark.parametrize("width,bits", [(2, 16), (3, 24)])
def test_wav_headers_give_length_rate_and_depth(tmp_path, width, bits):
    p = _write(tmp_path, "a.wav", _wav(12, rate=48000, width=width, channels=2))
    got = audio_probe.probe(p, "a.wav")
    assert got["ok"] and got["sample_rate"] == 48000 and got["bit_depth"] == bits
    assert got["channels"] == 2 and abs(got["duration_s"] - 12) < 0.01


def test_an_extensible_wav_is_read(tmp_path):
    rate, ch, bits, secs = 44100, 2, 24, 11
    block = ch * bits // 8
    data_len = rate * secs * block
    guid = struct.pack("<H", 1) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
    fmt = struct.pack("<HHIIHH", 0xFFFE, ch, rate, rate * block, block, 32) \
        + struct.pack("<HHI", 22, bits, 3) + guid
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", data_len)
    p = tmp_path / "ext.wav"
    with open(p, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", 4 + len(body) - 4 + data_len) + body)
        fh.truncate(fh.tell() + data_len)
    got = audio_probe.probe(str(p), "ext.wav")
    assert got["ok"] and got["bit_depth"] == 24 and abs(got["duration_s"] - secs) < 0.01


def test_a_header_promising_audio_the_file_lacks_is_unreadable(tmp_path):
    data = bytearray(_wav(12))
    # claim eleven minutes of data in a file that holds twelve seconds
    idx = bytes(data).index(b"data")
    struct.pack_into("<I", data, idx + 4, 44100 * 2 * 660)
    got = audio_probe.probe(_write(tmp_path, "lie.wav", bytes(data)), "lie.wav")
    assert not got["ok"] and got["reason"] == "unreadable"


def test_flac_streaminfo_is_read(tmp_path):
    rate, ch, bits, total = 44100, 2, 16, 44100 * 30
    packed = (rate << 44) | ((ch - 1) << 41) | ((bits - 1) << 36) | total
    info = struct.pack(">HH", 4096, 4096) + b"\x00" * 6 + packed.to_bytes(8, "big") + b"\x00" * 16
    data = b"fLaC" + bytes([0x80]) + len(info).to_bytes(3, "big") + info + b"\x00" * 64
    got = audio_probe.probe(_write(tmp_path, "a.flac", data), "a.flac")
    assert got["ok"] and got["sample_rate"] == 44100 and got["bit_depth"] == 16
    assert abs(got["duration_s"] - 30) < 0.01


def test_an_mp3_with_an_info_header_is_read_and_one_without_is_not_guessed(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_probe, "_ffmpeg_path", lambda: None)
    frame = b"\xff\xfb\x90\x64"                      # MPEG1 L3 128 kbps 44.1 kHz stereo
    side = b"\x00" * 32
    info = b"Info" + struct.pack(">I", 1) + struct.pack(">I", 1149)   # 1149 frames = 30 s
    good = frame + side + info + b"\x00" * 400
    got = audio_probe.probe(_write(tmp_path, "a.mp3", good), "a.mp3")
    assert got["ok"] and abs(got["duration_s"] - 1149 * 1152 / 44100) < 0.01
    bare = frame + b"\x00" * 4000
    got = audio_probe.probe(_write(tmp_path, "b.mp3", bare), "b.mp3")
    assert not got["ok"] and got["reason"] == "unreadable"


# --- the pages (the UI half) ---------------------------------------------------------------
# What the artist, a team seat, a label and the owner actually see. Every
# page is read the way a browser gets it; the words are checked, not
# assumed: RoEx's words labelled as RoEx's, "Not measured" never 0, the
# owner's price rather than a number in a template, nothing offered that
# the server would refuse, and nothing of RoEx's (a task id, a link, the
# key) on any page.

def _page(c, path):
    r = c.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return html.unescape(r.get_data(as_text=True))


def _ours(body):
    """The page's own content: from the Release-Ready root to the end of
    the page's main column, without the shell around it (the sidebar, the
    tool-suites footer, the product tour)."""
    start = body.find('data-no-collapse class="rr')
    if start < 0:
        return ""
    ends = [i for i in (body.find("<footer", start), body.find("</main>", start)) if i > 0]
    return body[start:min(ends) if ends else len(body)]


def test_the_upload_page_opens_with_the_plate_and_asks_for_both_boxes(env):
    c = _account()
    body = _page(c, PAGE)
    ours = _ours(body)
    assert 'class="sb-plate"' in ours and "Release-Ready" in ours
    # Both kinds of upload, both boxes, the exact words and their version.
    assert 'value="mix"' in ours and 'value="pair"' in ours
    assert 'name="file"' in ours and 'name="vocal"' in ours and 'name="beat"' in ours
    for words in (rr.CONSENT_NOTE, rr.CONSENT_RIGHTS, rr.CONSENT_LICENCE):
        assert words in ours
    assert '<input type="checkbox" name="rights" value="1" required>' in ours
    assert '<input type="checkbox" name="licence" value="1" required>' in ours
    assert 'name="consent_version" value="rr-consent-2"' in ours
    assert "WAV, FLAC or MP3, up to 10 minutes, 44.1 or 48 kHz." in ours
    # Open, connected, payments on: the form is live and nothing says otherwise.
    assert "<fieldset disabled" not in ours and "<fieldset>" in ours
    assert "Payments aren't switched on yet." not in ours
    assert "$6.99" in ours
    assert "/static/css/release_ready.css" in body and "/static/js/release_ready.js" in body
    # Genre choices are RoEx's analysis list, without DANCE.
    assert 'value="HIP_HOP_GRIME"' in ours and 'value="DANCE"' not in ours


def test_the_price_on_the_page_is_the_owners_setting(env):
    owner = _owner(env)
    assert owner.post("/admin/release-ready/settings", data={"price_master": "7.49",
                                                            "price_recombine": "8.25"},
                      headers=J).status_code == 200
    ours = _ours(_page(_account(), PAGE))
    assert "$7.49" in ours and "$8.25" in ours and "$6.99" not in ours


def test_every_closed_state_disables_the_form_and_says_why(env, monkeypatch):
    artist = _account()
    store.set_kv("rr_open", "0")
    ours = _ours(_page(artist, PAGE))
    assert "Release-Ready opens soon." in ours and "<fieldset disabled" in ours
    owner = _owner(env)
    ours = _ours(_page(owner, PAGE))
    assert "Only owner logins can use this until you open it in Settings." in ours
    assert "<fieldset disabled" not in ours, "the owner can try it while it is closed"
    store.set_kv("rr_open", "1")
    monkeypatch.delenv("ROEX_API_KEY")
    ours = _ours(_page(artist, PAGE))
    assert "Release-Ready isn't connected yet. Nothing can be uploaded until it is." in ours
    assert "<fieldset disabled" in ours
    assert env.roex.calls == []


def test_without_stripe_the_page_says_payments_are_not_on(env, monkeypatch):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    monkeypatch.delenv("STRIPE_SECRET_KEY")
    assert "Payments aren't switched on yet." in _ours(_page(c, PAGE))
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "Payments aren't switched on yet." in ours
    assert 'action="%s/jobs/%s/buy"' % (PAGE, jid) not in ours, "no form that would be refused"
    assert "disabled title=\"Payments aren't switched on yet.\"" in ours


def test_the_report_card_is_roexs_words_and_never_a_zero(env):
    c = _account()
    env.roex.on("/mixanalysis", _analysis_ok())
    sid = _upload_mix(c, style="TRAP").get_json()["source_id"]
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "Mix report by RoEx" in ours and "Measured by RoEx" in ours
    assert "RoEx's notes" in ours and "Written by RoEx's AI" in ours
    assert "Too quiet for mastering" in ours and "Too much compression" in ours
    assert "Some minor clipping" in ours and "-0.4 dBFS" in ours and "44.1 kHz" in ours
    # RoEx sent no LUFS figure and a bit depth of 0: both read Not measured.
    assert ours.count("Not measured") >= 2
    assert "0 LUFS" not in ours and "0-bit" not in ours
    # No score, no count of problems, and not the other pages' "readiness".
    assert "Release Readiness" not in ours and "/100" not in ours
    assert "There's no score: RoEx doesn't give one." in ours
    # The dots only repeat RoEx's words: MINOR clipping and LESS dynamics warn.
    assert "rr-dot--warn" in ours and "rr-dot--good" in ours
    # Nothing of RoEx's plumbing reaches the page.
    assert "bucket.test" not in ours and "X-Amz" not in ours and SENTINEL not in ours


def test_the_previews_offer_the_specs_choices_and_the_owners_price(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid, task="mt_ui")
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "Free 30-second previews" in ours
    assert 'src="%s/jobs/%s/preview"' % (PAGE, jid) in ours
    assert "Loudness setting: Medium" in ours and "Starts at 1:12 in the song." in ours
    previews = ours.split("Free 30-second previews")[1].split("data-rr-make")[0]
    assert "LUFS" not in previews.replace("LUFS targets", ""), \
        "a mastering preview carries no loudness figure"
    assert 'action="%s/jobs/%s/buy"' % (PAGE, jid) in ours and "Buy this master: $6.99" in ours
    assert "One payment. The full master is stored in your catalog when it's ready." in ours
    # The spec's mastering styles and the three presets, nothing else.
    for code in ("POP", "HIPHOP_GRIME", "ROCK_INDIE", "REGGAE_DUB", "OTHER"):
        assert 'value="%s"' % code in ours
    for code in ("LOW", "MEDIUM", "HIGH"):
        assert 'name="loudness" value="%s"' % code in ours
    assert "5 of 6 free previews left" in ours
    assert "mt_ui" not in ours and "roex.test" not in ours


def test_a_vocal_and_a_beat_get_the_recombine_styles_and_the_vocal_level(env):
    c = _account()
    sid = _upload_pair(c).get_json()["source_id"]
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "A vocal and a beat" in ours and "Mix report by RoEx" not in ours
    assert 'name="vocal_gain_db" type="range" min="-6" max="6"' in ours
    assert "Moves the vocal against RoEx's automatic balance." in ours
    for code in ("TRAP", "K_POP", "REGGAETON", "CINEMATIC"):
        assert 'value="%s"' % code in ours


def test_a_stored_master_shows_where_it_goes_next_and_nothing_before(env):
    c = _account()
    track = store.add_os_track(c._id, "Night Drive")
    sid = _mix_with_report(c, env, title="Night Drive")
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/ui.wav"}))
    env.files["https://roex.test/ui.wav"] = MASTER_WAV
    env.put_fails = True
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    ours = _ours(_page(c, PAGE + "/sources/%s?paid=1" % sid))
    assert "Payment received. We're getting your full master from RoEx." in ours
    assert "Your master is stored." not in ours and "Download the WAV" not in ours
    assert "Master stored on" not in _page(c, "/tracks/%s" % track)
    env.put_fails = False
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert rstore.get_job(jid)["status"] == "stored"
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "Your master is stored." in ours
    assert 'href="%s/jobs/%s/master.wav"' % (PAGE, jid) in ours
    assert 'href="/tracks/%s"' % track in ours and "Open its Track Passport" in ours
    assert 'href="/links/new?title=Night+Drive"' in ours and 'href="/rollout-studio/new"' in ours
    assert "WAV, 44.1 kHz 16-bit" in ours and "RoEx, through Release-Ready" in ours
    # The Track Passport and the Metadata Passport say so; the score does not move.
    passport = _page(c, "/tracks/%s" % track)
    assert 'id="master"' in passport and "Master stored on" in passport
    assert 'href="%s/jobs/%s/master.wav"' % (PAGE, jid) in passport
    assert "Not counted in the passport's score." in passport
    assert "Master stored" in _page(c, "/metadata-passport")


def test_team_seats_see_the_work_but_not_the_controls_they_lack(env):
    artist, editor, reader = _account("pro"), _account("artist", "Editor"), _account("artist", "Reader")
    sid = _mix_with_report(artist, env)
    jid = _preview_ready(artist, env, sid)
    _invite(artist, editor, "edit")
    _invite(artist, reader, "read")
    ours = _ours(_page(editor, PAGE + "/sources/%s" % sid))
    assert "Only the account holder can buy a master." in ours
    assert 'action="%s/jobs/%s/buy"' % (PAGE, jid) not in ours
    assert "data-rr-make" in ours, "an editor can still make previews"
    ours = _ours(_page(reader, PAGE + "/sources/%s" % sid))
    assert rr.READ_ONLY in ours
    for action in ("/previews", "/delete", "/report"):
        assert 'action="%s/sources/%s%s"' % (PAGE, sid, action) not in ours, action
    assert 'action="%s/jobs/%s/buy"' % (PAGE, jid) not in ours
    listing = _ours(_page(reader, PAGE))
    assert "<fieldset disabled" in listing and rr.READ_ONLY in listing


def test_the_owner_settings_card_and_desk_are_the_owners_alone(env):
    owner, artist = _owner(env), _account("label")
    body = _page(owner, "/settings")
    card = body.split('id="release-ready"')[1].split("</section>")[0]
    assert 'action="/admin/release-ready/settings"' in card
    assert 'name="price_master" inputmode="decimal" value="6.99"' in card
    assert 'name="price_recombine" inputmode="decimal" value="6.99"' in card
    assert 'name="budget" inputmode="numeric" value="1000"' in card
    assert 'name="switches" value="1"' in card and 'name="open"' in card and 'name="auto_analysis"' in card
    assert "RoEx key: set" in card and SENTINEL not in body
    assert 'href="/admin/release-ready"' in card
    assert "—" not in card and "monospace" not in card
    other = _page(artist, "/settings")
    assert 'id="release-ready"' not in other and "/admin/release-ready/settings" not in other
    # Saving comes back to the card and says what happened.
    r = owner.post("/admin/release-ready/settings", data={"price_master": "7,49"})
    assert r.status_code == 302 and r.headers["Location"].endswith("#release-ready")
    assert "Not saved: price per master." in _page(owner, r.headers["Location"])
    r = owner.post("/admin/release-ready/settings", data={"price_master": "7.49"})
    card = _page(owner, r.headers["Location"]).split('id="release-ready"')[1].split("</section>")[0]
    assert "Saved." in card and 'value="7.49"' in card
    desk = _ours(_page(owner, "/admin/release-ready"))
    assert "Release-Ready desk" in desk and "Credits used this month" in desk
    assert "Estimated from RoEx's price list." in desk
    for button in ("Run the queue now", "Check the RoEx connection", "Resume paused reports"):
        assert button in desk
    assert "RoEx key: set" in desk and SENTINEL not in desk
    assert "Retrieve without payment" not in _ours(_page(artist, PAGE))


def test_the_studio_room_and_the_palette_find_it(env, monkeypatch):
    import re

    import hubs
    import rooms
    entry = [e for e in hubs.command_index() if e["key"] == "release-ready"][0]
    assert entry["href"] == PAGE and entry["label"] == "Release-Ready" and entry["live"] is True
    for word in ("master", "mastering", "release ready"):
        assert word in entry["aka"], word
    assert rooms.room_for_key("release-ready") == "studio"
    base = open(os.path.join(os.path.dirname(rr.__file__), "templates", "base.html"),
                encoding="utf-8").read()
    assert "item.aka" in base, "the palette reads the extra words"
    monkeypatch.setenv("NAV_ROOMS", "1")
    store.set_kv("nav_layout", "")
    c = _account()
    room = _page(c, "/room/studio")
    assert 'data-room-card="release-ready"' in room and 'href="%s"' % PAGE in room
    body = _page(c, PAGE)
    assert 'id="sb-room-back"' in body and "Back to Studio" in body
    assert re.search(r'"key":\s*"release-ready"', body), "in the palette's index"


def test_a_label_reads_status_only_on_its_roster_page(env):
    label, artist = _account("label", "Label"), _account("artist", "Signed")
    sid = _mix_with_report(artist, env, title="Roster Tune")
    _preview_ready(artist, env, sid)
    with store.get_db() as conn:
        conn.execute("INSERT INTO roster_members (id, label_id, email, artist_user_id, status,"
                     " invite_token, created) VALUES (?,?,?,?,?,?,?)",
                     (uuid.uuid4().hex, label._id, artist._email, artist._id, "active",
                      uuid.uuid4().hex, rstore.iso()))
    body = _page(label, "/roster/artist/%s" % artist._id)
    section = body.split('id="release-ready"')[1].split("</section>")[0]
    assert "Roster Tune" in section and "Mix report ready" in section and "Preview ready" in section
    assert PAGE not in section and "<audio" not in section and "/buy" not in section


def test_the_pages_keep_the_house_rules():
    import re
    here = os.path.dirname(rr.__file__)
    for name in ("templates/release_ready.html", "templates/release_ready_source.html",
                 "templates/_rr_report.html", "templates/release_ready_admin.html",
                 "static/js/release_ready.js", "static/css/release_ready.css"):
        text = open(os.path.join(here, *name.split("/")), encoding="utf-8").read()
        assert "—" not in text and "&mdash;" not in text, name
        assert "monospace" not in text.lower(), name
    css = open(os.path.join(here, "static", "css", "release_ready.css"), encoding="utf-8").read()
    sizes = [float(x) for x in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css)]
    assert sizes and min(sizes) >= 12
    for value in re.findall(r"border-radius:\s*([^;]+);", css):
        assert value.strip() in ("var(--sb-r-control)", "var(--sb-r-panel)", "var(--sb-r-pill)", "50%"), value
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css), "colours are tokens"


def test_a_rendered_page_carries_no_em_dash(env):
    c = _account()
    sid = _mix_with_report(c, env)
    _preview_ready(c, env, sid)
    owner = _owner(env)
    for client, path in ((c, PAGE), (c, PAGE + "/sources/%s" % sid), (owner, "/admin/release-ready")):
        ours = _ours(_page(client, path))
        assert ours and "—" not in ours, path


# --- review fixes, 2026-09-19 (money and security) ----------------------------------------------

def _final_ok(env, url="https://roex.test/final.wav"):
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": url}))
    env.files[url] = MASTER_WAV


def test_rr1_a_payment_after_the_upload_is_deleted_retrieves_nothing(env):
    """RR-1: deleting the upload closes the open checkout first, and a
    payment that still lands on the cancelled job is recorded as stale:
    no paid retrieval, the owner is told to refund."""
    _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    assert c.post(PAGE + "/jobs/%s/buy" % jid, headers=J).status_code == 200
    opened = rstore.get_job(jid)["checkout_session_id"]
    r = c.post(PAGE + "/sources/%s/delete" % sid, headers=J)
    assert r.status_code == 200 and rstore.get_job(jid)["status"] == "cancelled"
    assert ("/v1/checkout/sessions/%s/expire" % opened) in [p for p, _f in env.stripe_calls]
    _final_ok(env)
    sess = _paid_session(jid, c._id)
    assert _stripe_hook("checkout.session.completed", sess).status_code == 200
    job = rstore.get_job(jid)
    assert env.roex.count("/retrievefinalmaster") == 0
    assert job["status"] == "cancelled" and not job["paid_at"]
    pay = [p for p in rstore.payments() if p["session_id"] == sess["id"]][0]
    assert pay["mismatch"] == "stale"
    assert any(n["title"] == "A Release-Ready payment came in too late" for n in _owner_notes(env))
    # The artist's return from Stripe lands on a page that says so, not a 404.
    back = c.get(PAGE + "/jobs/%s/paid?session_id=%s" % (jid, sess["id"]))
    assert back.status_code == 302 and back.headers["Location"].endswith(PAGE + "?msg=stale_payment")
    assert rr.COPY["stale_payment"] in html.unescape(c.get(back.headers["Location"]).get_data(as_text=True))
    assert "paid after the preview could no longer be used" in json.dumps(rr.admin_data()["payment_problems"])


def test_rr1_a_checkout_paid_before_the_delete_is_claimed_and_the_upload_stays(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    opened = rstore.get_job(jid)["checkout_session_id"]
    env.sessions[opened] = dict(_paid_session(jid, c._id), id=opened)
    _final_ok(env)
    r = c.post(PAGE + "/sources/%s/delete" % sid, headers=J)
    assert r.status_code == 409 and r.get_json()["message"] == rr.COPY["delete_wait"]
    assert rstore.get_job(jid)["status"] == "stored" and rstore.get_source(sid)["deleted_at"] is None
    assert env.roex.count("/retrievefinalmaster") == 1


def test_rr1_a_payment_after_the_owner_released_the_master_is_not_retrieved_again(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    assert c.post(PAGE + "/jobs/%s/buy" % jid, headers=J).status_code == 200
    _final_ok(env)
    owner = _owner(env)
    r = owner.post("/admin/release-ready/jobs/%s/retry" % jid,
                   data={"action": "retrieve", "unpaid_ok": "1"}, headers=J)
    assert r.status_code == 200 and rstore.get_job(jid)["status"] == "stored"
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, c._id)).status_code == 200
    assert rstore.get_job(jid)["status"] == "stored"
    assert env.roex.count("/retrievefinalmaster") == 1
    assert [p["mismatch"] for p in rstore.payment_problems() if p["job_id"] == jid] == ["stale"]


def test_rr2_the_owners_retry_uses_the_link_roex_already_gave(env):
    """RR-2: RoEx handed over the master link but our download failed. The
    owner's retry fetches from that link; RoEx is not asked (or paid) twice."""
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/held.wav"}))
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "retrieving" and job["roex_output_url"]
    rstore.update_job(jid, paid_at=rstore.iso(rstore.now() - timedelta(hours=1)))
    need = [n for n in rr.admin_data()["needs"] if n["id"] == jid][0]
    assert need["link_held"]
    assert "Fetch the master again from RoEx's link" in _ours(_page(owner, "/admin/release-ready"))
    env.files["https://roex.test/held.wav"] = MASTER_WAV
    r = owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J)
    assert r.status_code == 200 and r.get_json()["message"] == rr.DESK_COPY["refetch_started"]
    assert rstore.get_job(jid)["status"] == "stored"
    assert env.roex.count("/retrievefinalmaster") == 1


def test_rr2_an_expired_link_is_dropped_and_the_owner_asks_roex_again(env):
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": "https://roex.test/old.wav"}))
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    rstore.update_job(jid, status="needs_owner",
                      roex_output_expires=rstore.iso(rstore.now() - timedelta(minutes=1)))
    _final_ok(env, "https://roex.test/new.wav")
    assert owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J).status_code == 200
    assert env.roex.count("/retrievefinalmaster") == 2
    assert rstore.get_job(jid)["status"] == "stored"


def test_rr4_a_gateway_timeout_keeps_the_credits_and_is_not_retried(env):
    """RR-4: a 5xx after the request went out may have been charged: one
    call, the reservation stays counted, and button re-runs are capped."""
    c = _account()
    env.roex.on("/mixanalysis", (504, {"message": "Endpoint request timed out"}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid, "mix_analysis")[0]
    for _ in range(3):
        _due(job["id"])
        c.get(PAGE + "/sources/%s.json" % sid)
    job = rstore.get_job(job["id"])
    assert env.roex.count("/mixanalysis") == 1
    assert job["status"] == "failed" and job["error_kind"] == "roex_error"
    assert rrs.counts()["auto"] == 10 and job["credits_spent_estimate"] == 10
    assert rr.message_for(job) == rr.COPY["roex_error"]
    for n in range(rrs.MANUAL_REPORTS_PER_FILE):
        assert c.post(PAGE + "/sources/%s/report" % sid, headers=J).status_code == 200
    assert env.roex.count("/mixanalysis") == 1 + rrs.MANUAL_REPORTS_PER_FILE
    r = c.post(PAGE + "/sources/%s/report" % sid, headers=J)
    assert r.status_code == 429 and r.get_json()["message"] == rr.COPY["report_runs"]
    assert env.roex.count("/mixanalysis") == 1 + rrs.MANUAL_REPORTS_PER_FILE
    view = c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]
    assert view["report_can_run"] is False and view["report_budget_note"] == rr.COPY["report_runs"]
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert 'action="%s/sources/%s/report"' % (PAGE, sid) not in ours


def test_rr4_a_429_from_roex_is_tried_again_and_nothing_is_counted_as_spent(env):
    c = _account()
    env.roex.on("/mixanalysis", (429, {"message": "Too many requests"}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid, "mix_analysis")[0]
    assert job["status"] == "queued" and job["credits_spent_estimate"] == 0
    for _ in range(3):
        _due(job["id"])
        c.get(PAGE + "/sources/%s.json" % sid)
    job = rstore.get_job(job["id"])
    assert job["status"] == "failed" and job["error_kind"] == "unreachable"
    assert rrs.counts()["auto"] == 0, "refused at the door: given back"


def test_rr5_the_buy_window_is_six_days_and_a_late_claim_retrieves_nothing(env):
    _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    rstore.update_job(jid, submitted_at=rstore.iso(rstore.now() - timedelta(days=6, hours=1)))
    r = c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    assert r.status_code == 409 and r.get_json()["message"] == rr.COPY["fresh_preview"]
    rstore.update_job(jid, submitted_at=rstore.iso(rstore.now() - timedelta(days=5, hours=23)))
    assert c.post(PAGE + "/jobs/%s/buy" % jid, headers=J).status_code == 200
    fields = [f for p, f in env.stripe_calls if p == "/v1/checkout/sessions"][-1]
    assert "expires_at" in fields
    # Paid, but the claim comes after RoEx's link to the audio ran out.
    rstore.update_job(jid, submitted_at=rstore.iso(rstore.now() - timedelta(days=7)))
    _final_ok(env)
    assert _stripe_hook("checkout.session.completed", _paid_session(jid, c._id)).status_code == 200
    assert env.roex.count("/retrievefinalmaster") == 0
    job = rstore.get_job(jid)
    assert job["status"] == "preview_ready" and not job["paid_at"]
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["payment_note"] == rr.COPY["stale_payment"]
    assert any(n["title"] == "A Release-Ready payment came in too late" for n in _owner_notes(env))


def _fake_https(answers):
    """Stands in for urllib's https_open: a scripted answer per URL, and a
    record of every request with the key header it carried. Returns the
    method to patch onto the handler class, and the record."""
    seen = []

    def https_open(handler, req):
        seen.append((req.full_url, req.get_header("X-api-key")))
        code, location, body = answers.get(req.full_url, (200, None, b"{}"))
        headers = email.message_from_string(("Location: %s\n\n" % location) if location else "\n")
        resp = urllib.response.addinfourl(io.BytesIO(body), headers, req.full_url, code)
        resp.msg = "Found" if location else "OK"
        return resp
    return https_open, seen


def _fresh_roex():
    import importlib.util
    spec = importlib.util.spec_from_file_location("roex_client_redirects", roex.__file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rr6_a_redirect_from_roex_never_carries_the_key_anywhere(monkeypatch):
    fake, seen = _fake_https({"https://tonn.roexaudio.com/masteringpreview":
                              (302, "https://elsewhere.example/steal", b"")})
    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", fake)
    mod = _fresh_roex()
    status, _body = mod._http("POST", "/masteringpreview", {"masteringData": {}})
    assert status == 302
    assert seen == [("https://tonn.roexaudio.com/masteringpreview", SENTINEL)], \
        "one request, to RoEx only: the redirect was never followed"
    assert mod._classify(302, {}).kind == "unknown"


def test_rr6_a_file_link_may_only_lead_to_a_public_https_address(monkeypatch):
    good = "https://93.184.216.34/f.wav"
    fake, seen = _fake_https({
        good: (200, None, b"RIFF...."),
        "https://93.184.216.34/to-http": (302, "http://93.184.216.34/f.wav", b""),
        "https://93.184.216.34/to-private": (302, "https://10.0.0.5/f.wav", b""),
        "https://93.184.216.34/to-loopback": (302, "https://127.0.0.1/f.wav", b""),
        "https://93.184.216.34/to-cdn": (302, good, b""),
    })
    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", fake)
    monkeypatch.setattr(urllib.request.HTTPHandler, "http_open", fake)
    mod = _fresh_roex()
    path, n, _sha = mod._download("https://93.184.216.34/to-cdn")
    with open(path, "rb") as fh:
        assert n == 8 and fh.read() == b"RIFF...."
    os.remove(path)
    for bad in ("to-http", "to-private", "to-loopback"):
        with pytest.raises(mod.RoexDownloadError):
            mod._download("https://93.184.216.34/" + bad)
    before = len(seen)
    for url in ("https://192.168.1.4/f.wav", "https://127.0.0.1/f.wav", "http://93.184.216.34/f.wav"):
        with pytest.raises(mod.RoexDownloadError):
            mod._download(url)
    assert len(seen) == before, "a private or plain-http link is never requested"
    assert not any(u.startswith(("http://", "https://10.", "https://127.")) for u, _k in seen)
    assert all(k is None for _u, k in seen), "no key on a file download"


def test_rr7_a_stuck_free_preview_is_made_again_for_free(env):
    """RR-7 / RR-14 (second list): the owner's action for an unpaid preview
    that stopped on RoEx credits reads the free preview again. The paid
    final is a separate, clearly named control."""
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_x"}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["MEDIUM"]},
                 headers=J).get_json()["jobs"][0]["id"]
    env.roex.on("/retrievepreviewmaster", (402, {"message": "Insufficient credits"}))
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert rstore.get_job(jid)["status"] == "credits_short"
    desk = _ours(_page(owner, "/admin/release-ready"))
    block = [b for b in desk.split('class="rr-need"')
             if "/admin/release-ready/jobs/%s/retry" % jid in b][0]
    assert "Make this preview again (free)" in block
    assert "Release the full master without payment" in block and "Try the retrieval again" not in block
    env.files["https://roex.test/x.mp3"] = PREVIEW_BYTES
    env.roex.on("/retrievepreviewmaster", (200, {"previewMasterTaskResults": {
        "download_url_mastered_preview": "https://roex.test/x.mp3", "preview_start_time": 30}}))
    r = owner.post("/admin/release-ready/jobs/%s/retry" % jid, data={"action": "preview"}, headers=J)
    assert r.status_code == 200 and r.get_json()["message"] == rr.DESK_COPY["preview_polled"]
    job = rstore.get_job(jid)
    assert job["status"] == "preview_ready" and not job["owner_release_by"]
    assert env.roex.count("/retrievefinalmaster") == 0


def test_rr7_a_preview_roex_never_started_is_asked_for_again(env):
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (402, {"message": "Insufficient credits"}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW"]},
                 headers=J).get_json()["jobs"][0]["id"]
    assert rstore.get_job(jid)["status"] == "credits_short"
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_again"}))
    env.roex.on("/retrievepreviewmaster", (202, {"status": 202}))
    assert owner.post("/admin/release-ready/jobs/%s/retry" % jid, headers=J).status_code == 200
    job = rstore.get_job(jid)
    assert job["status"] == "processing" and job["roex_task_id"] == "mt_again"
    assert env.roex.count("/retrievefinalmaster") == 0


def test_rr8_a_team_seat_cannot_delete_a_paid_master(env):
    artist, editor = _account("pro"), _account("artist", "Editor")
    sid = _mix_with_report(artist, env)
    jid = _preview_ready(artist, env, sid)
    artist.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    _final_ok(env)
    _stripe_hook("checkout.session.completed", _paid_session(jid, artist._id))
    assert rstore.get_job(jid)["status"] == "stored"
    _invite(artist, editor, "edit")
    r = editor.post(PAGE + "/jobs/%s/master/delete" % jid, headers=J)
    assert r.status_code == 403 and r.get_json()["message"] == rr.COPY["seat_delete"]
    assert rstore.get_job(jid)["status"] == "stored"
    assert "Delete this master" not in _ours(_page(editor, PAGE + "/sources/%s" % sid))


def test_rr9_a_refund_or_a_dispute_stops_counting_as_revenue(env):
    owner = _owner(env)
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    _final_ok(env)
    sess = _paid_session(jid, c._id)
    _stripe_hook("checkout.session.completed", sess)
    before = rr.admin_data()
    row = [a for a in before["artists"] if a["id"] == c._id][0]
    assert (row["masters"], row["revenue"]) == (1, "6.99")
    assert _stripe_hook("charge.refunded", {"id": "ch_1", "object": "charge",
                                            "payment_intent": sess["payment_intent"],
                                            "amount_refunded": 699}).status_code == 200
    data = rr.admin_data()
    row = [a for a in data["artists"] if a["id"] == c._id][0]
    assert (row["masters"], row["revenue"], row["margin"]) == (0, "0.00", "-2.30")
    # The month's tiles are for the whole desk: this master comes off them.
    assert data["masters_sold_month"] == before["masters_sold_month"] - 1
    assert Decimal(data["revenue_month"]) == Decimal(before["revenue_month"]) - Decimal("6.99")
    assert any(n["title"] == "A Release-Ready payment was refunded" for n in _owner_notes(env))
    # A second master, disputed: out of revenue and on the owner's list.
    sid2 = _mix_with_report(c, env)
    jid2 = _preview_ready(c, env, sid2, task="mt_2")
    c.post(PAGE + "/jobs/%s/buy" % jid2, headers=J)
    sess2 = _paid_session(jid2, c._id)
    _stripe_hook("checkout.session.completed", sess2)
    assert rr.admin_data()["masters_sold_month"] == data["masters_sold_month"] + 1
    assert _stripe_hook("charge.dispute.created", {"id": "dp_1", "object": "dispute", "charge": "ch_2",
                                                   "payment_intent": sess2["payment_intent"],
                                                   "amount": 699}).status_code == 200
    after = rr.admin_data()
    assert after["masters_sold_month"] == data["masters_sold_month"]
    assert any(p["job_id"] == jid2 and "disputed" in p["text"] for p in after["payment_problems"])
    assert "disputed by the card holder" in _ours(_page(owner, "/admin/release-ready"))


def test_rr10_the_alert_band_only_shows_our_own_sentences(env):
    c = _account()
    body = html.unescape(c.get(PAGE + "?msg=Your+payment+failed.+Email+refunds%40evil.example")
                         .get_data(as_text=True))
    assert "refunds@evil.example" not in body and "Your payment failed" not in body
    assert rr.COPY["no_file"] in html.unescape(c.get(PAGE + "?msg=no_file").get_data(as_text=True))
    # A form sent back to a page carries a code, never the sentence.
    sid = _mix_with_report(c, env)
    r = c.post(PAGE + "/sources/%s/delete" % sid)
    assert r.status_code == 302 and r.headers["Location"].endswith(PAGE + "?msg=deleted")
    owner = _owner(env)
    r = owner.post("/admin/release-ready/run")
    assert "msg=queue_ran" in r.headers["Location"] and "The+queue" not in r.headers["Location"]
    assert "The queue ran: " in _page(owner, r.headers["Location"])
    assert "The queue ran: 7 step(s) started." in _page(owner, "/admin/release-ready?msg=queue_ran&n=7")
    assert "evil" not in _page(owner, "/admin/release-ready?msg=evil&n=3")
    assert "evil" not in _page(owner, "/admin/release-ready?msg=queue_ran&n=evil")


def test_rr11_a_master_is_never_streamed_through_the_app(env, monkeypatch):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    _final_ok(env)
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))

    def no_fetch(*_a, **_k):
        raise AssertionError("the master was read into memory")
    monkeypatch.setattr(blob_store, "fetch", no_fetch)
    r = c.get(PAGE + "/jobs/%s/master.wav?via=app" % jid)
    assert r.status_code == 302 and "X-Amz-Expires=300" in r.headers["Location"]


# --- review fixes, 2026-09-19 (checked against RoEx's spec) ---------------------------------------

def test_spec1_a_top_level_master_link_is_kept(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"download_url_mastered": "https://roex.test/top.wav"}))
    env.files["https://roex.test/top.wav"] = MASTER_WAV
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    assert rstore.get_job(jid)["status"] == "stored"
    assert env.roex.count("/retrievefinalmaster") == 1


def test_spec1_an_answer_without_a_link_keeps_what_it_carried_for_the_owner(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (200, {"finalMasterTaskResults": {}, "taskStatus": "done"}))
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "needs_owner" and job["error_kind"] == "unknown"
    assert "finalMasterTaskResults, taskStatus" in job["error_text"]


def test_spec2_a_refused_key_answered_as_400_alerts_the_owner(env):
    owner = _owner(env)
    c = _account()
    env.roex.on("/mixanalysis", (400, {"code": 400,
                                       "message": "API key not valid. Please pass a valid API key."}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid, "mix_analysis")[0]
    assert job["status"] == "needs_owner" and job["error_kind"] == "auth"
    assert rr.message_for(job) == rr.COPY["our_side"]
    assert rrs.counts()["auto"] == 0
    assert any(n["title"] == "RoEx refused the API key" for n in _owner_notes(env))
    env.roex.on("/health", (400, {"message": "API key not valid. Please pass a valid API key."}))
    r = owner.post("/admin/release-ready/health", headers=J)
    assert r.get_json()["kind"] == "auth" and r.get_json()["message"] == "RoEx refused the key."


def test_spec3_a_webhook_during_a_running_step_is_not_lost(env, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://app.test")
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_l"}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["HIGH"]},
                 headers=J).get_json()["jobs"][0]["id"]
    token = env.roex.bodies("/masteringpreview")[0]["masteringData"]["webhookURL"].rsplit("/", 1)[1]
    env.files["https://roex.test/l.mp3"] = PREVIEW_BYTES
    ready = (200, {"previewMasterTaskResults": {
        "download_url_mastered_preview": "https://roex.test/l.mp3", "preview_start_time": 5}})
    inner = env.roex
    reads = []

    def http(method, path, body=None, timeout=30):
        if path == "/retrievepreviewmaster":
            reads.append(path)
            if len(reads) == 1:
                # RoEx finishes and calls the webhook while this step holds
                # the lease; the step itself still read "not ready".
                hook = appmod.app.test_client().post("/webhooks/roex/%s/%s" % (jid, token))
                assert hook.status_code == 200
                return 202, {"status": 202}
            return ready
        return inner(method, path, body, timeout)
    monkeypatch.setattr(roex, "_http", http)
    _due(jid)
    rr.advance(jid)
    assert len(reads) == 2, "the delivery made during the step was acted on"
    assert rstore.get_job(jid)["status"] == "preview_ready"


def test_spec4_our_own_words_are_never_quoted_as_roexs(env):
    c = _account()
    env.roex.on("/mixanalysis", (200, {"error": False, "message": "", "info": ""}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid, "mix_analysis")[0]
    assert job["status"] == "failed" and job["error_kind"] == "bad_answer"
    msg = rr.message_for(job)
    assert msg == rr.COPY["bad_answer"] and "RoEx said" not in msg
    assert job["error_text"] == "RoEx's answer carried no report", "kept for the owner"
    env.roex.on("/masteringpreview", (200, {"message": ""}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW"]},
                 headers=J).get_json()["jobs"][0]["id"]
    job = rstore.get_job(jid)
    assert job["error_kind"] == "bad_answer" and "RoEx said" not in rr.message_for(job)


def test_spec5_a_flat_mix_report_is_read(env):
    c = _account()
    env.roex.on("/mixanalysis", (200, {"error": False, "info": "", "payload": REPORT}))
    sid = _upload_mix(c).get_json()["source_id"]
    job = _jobs(sid, "mix_analysis")[0]
    assert job["status"] == "reported" and job["result"]["clipping"] == "MINOR"


def _recombine_ready(c, env, task="rc_f"):
    sid = _upload_pair(c).get_json()["source_id"]
    env.roex.on("/recombine", (200, {"recombineTaskId": task}))
    jid = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW"]},
                 headers=J).get_json()["jobs"][0]["id"]
    env.roex.on("/recombinestatus/", (200, {"status": "complete"}))
    env.roex.on("/retrieverecombinepreview", (200, {"preview": {"preview_url": "https://roex.test/%s.mp3" % task}}))
    env.files["https://roex.test/%s.mp3" % task] = PREVIEW_BYTES
    _due(jid)
    c.get(PAGE + "/jobs/%s.json" % jid)
    assert rstore.get_job(jid)["status"] == "preview_ready"
    return sid, jid


def test_spec6_the_master_format_is_read_off_the_stored_file(env):
    c = _account()
    track = store.add_os_track(c._id, "Duet")
    sid, jid = _recombine_ready(c, env)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrieverecombine", (200, {"result": {
        "master_url": "https://roex.test/rf.wav", "sample_rate": 44100, "bit_depth": 16}}))
    env.files["https://roex.test/rf.wav"] = _wav(1.0, rate=48000, width=3, channels=2)
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    job = rstore.get_job(jid)
    assert job["status"] == "stored" and job["os_track_id"] == track
    master = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]["master"]
    assert master["format"] == "WAV, 48 kHz 24-bit", "what the file holds, not what was expected"
    assert master["measured"]["text"] == "Not measured", "one Not measured, not two"
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "WAV, 48 kHz 24-bit" in ours and "44.1 kHz 16-bit" not in ours
    assert "Not measured, true peak" not in ours
    assert "WAV, 48 kHz 24-bit" in _page(c, "/tracks/%s" % track)
    assert rr.master_format({"result": {"master": {"sample_rate": 44100, "bit_depth": 16}}}) == \
        "WAV, 44.1 kHz 16-bit"
    assert rr.master_format({"result": {}}) == "WAV"


# --- review fixes, 2026-09-19 (second list: the artist's side) -----------------------------------

def test_second_rr1_a_paid_master_alert_is_never_silenced_by_another(env):
    _owner(env)
    a, b = _account(), _account()
    sid_a = _mix_with_report(a, env)
    env.roex.on("/masteringpreview", (402, {"message": "Insufficient credits"}))
    a.post(PAGE + "/sources/%s/previews" % sid_a, data={"style": "POP", "loudness": ["LOW"]}, headers=J)
    assert [n for n in _owner_notes(env) if n["title"] == "RoEx is out of credits"]
    sid_b = _mix_with_report(b, env)
    jid = _preview_ready(b, env, sid_b)
    b.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    env.roex.on("/retrievefinalmaster", (402, {"message": "Insufficient credits"}))
    _stripe_hook("checkout.session.completed", _paid_session(jid, b._id))
    assert rstore.get_job(jid)["status"] == "credits_short"
    assert [n for n in _owner_notes(env) if n["title"] == "A paid master is waiting on RoEx credits"]
    rstore.update_job(jid, paid_at=rstore.iso(rstore.now() - timedelta(hours=5)))
    assert rr.run_due()["stuck_paid"] >= 1
    assert [n for n in _owner_notes(env) if n["title"] == "A paid master is taking too long"]
    ours = _ours(_page(b, PAGE + "/sources/%s?paid=1" % sid_b))
    assert "This page updates by itself" not in ours
    assert "You won't be charged again" in ours


def test_second_rr2_our_side_failures_do_not_use_up_free_previews(env):
    c = _account()
    sid = _mix_with_report(c, env)
    env.roex.on("/masteringpreview", (402, {"message": "Insufficient credits"}))
    for _ in range(4):
        r = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["LOW", "HIGH"]},
                   headers=J)
        assert r.status_code == 200
    view = c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]
    assert view["previews_used"] == 0 and view["previews_left"] == rrs.previews_per_file()
    assert rstore.previews_today(c._id) == 0


def test_second_rr3_no_refund_is_promised(env):
    assert "refund" not in rr.COPY["paid_waiting"].lower()
    assert "You won't be charged again" in rr.COPY["paid_waiting"]


def test_second_rr4_the_licence_says_what_roexs_terms_take():
    words = rr.consent_text()
    assert words["version"] == "rr-consent-2"
    assert "this service only" not in words["licence"]
    for part in ("RoEx and its service providers", "host", "listen to", "improve RoEx's service"):
        assert part in words["licence"], part
    assert rr.CONSENT_SHA256 == rr._consent_hash(words)


def test_second_rr5_a_stereo_field_roex_calls_too_wide_or_narrow_says_so():
    for code, word, tone in (("WIDE", "Too wide", "warn"), ("NARROW", "Too narrow", "warn"),
                             ("BALANCED", "Balanced", "good"), ("MONO", "Mono", "idle")):
        v = [x for x in rr.report_view(dict(REPORT, stereo_field=code), False)["verdicts"]
             if x["label"] == "Stereo field"][0]
        assert (v["value"], v["tone"]) == (word, tone), code


def test_second_rr6_old_previews_free_the_allowance_for_a_fresh_one(env):
    store.set_kv("rr_previews_per_file", "2")
    c = _account()
    sid = _mix_with_report(c, env)
    first = _preview_ready(c, env, sid, task="mt_o1")
    second = _preview_ready(c, env, sid, task="mt_o2")
    assert c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]["previews_left"] == 0
    for jid in (first, second):
        rstore.update_job(jid, submitted_at=rstore.iso(rstore.now() - timedelta(days=7)))
    view = c.get(PAGE + "/sources/%s.json" % sid).get_json()["source"]
    assert view["previews_left"] == 2
    assert view["previews"][0]["buy"]["reason"] == rr.COPY["fresh_preview"]
    env.roex.on("/masteringpreview", (200, {"mastering_task_id": "mt_o3"}))
    r = c.post(PAGE + "/sources/%s/previews" % sid, data={"style": "POP", "loudness": ["MEDIUM"]},
               headers=J)
    assert r.status_code == 200


def test_second_rr7_a_master_outlives_its_upload_and_is_deleted_from_its_passport(env):
    c = _account()
    track = store.add_os_track(c._id, "Night Drive")
    sid = _mix_with_report(c, env, title="Night Drive")
    jid = _preview_ready(c, env, sid)
    c.post(PAGE + "/jobs/%s/buy" % jid, headers=J)
    _final_ok(env)
    _stripe_hook("checkout.session.completed", _paid_session(jid, c._id))
    assert rstore.get_job(jid)["status"] == "stored"
    r = c.post(PAGE + "/sources/%s/delete" % sid, headers=J)
    assert r.status_code == 200 and "Track Passport" in r.get_json()["message"]
    passport = _page(c, "/tracks/%s" % track)
    assert "Master stored on" in passport and "Open in Release-Ready" not in passport
    assert 'action="%s/jobs/%s/master/delete"' % (PAGE, jid) in passport
    r = c.post(PAGE + "/jobs/%s/master/delete" % jid, data={"from": "passport"})
    assert r.status_code == 302 and ("/tracks/%s?" % track) in r.headers["Location"]
    assert rstore.get_job(jid)["status"] == "master_deleted"
    assert "Master stored on" not in _page(c, "/tracks/%s" % track)


def test_second_rr8_the_upload_page_only_promises_a_report_that_will_run(env):
    store.set_kv("rr_monthly_credit_budget", "0")
    c = _account()
    ours = _ours(_page(c, PAGE))
    assert "as soon as it lands" not in ours and "Mix reports are paused" in ours
    store.set_kv("rr_monthly_credit_budget", "1000")
    assert "as soon as it lands" in _ours(_page(c, PAGE))
    # The artist's cap is used, then the budget runs out: one sentence, no
    # pointer to a button that isn't there.
    store.set_kv("rr_artist_monthly_reports", "1")
    env.roex.on("/mixanalysis", _analysis_ok())
    _upload_mix(c)
    assert "runs when you ask for it" in _ours(_page(c, PAGE))
    sid = _upload_mix(c).get_json()["source_id"]
    assert _jobs(sid)[0]["status"] == "on_request"
    store.set_kv("rr_monthly_credit_budget", "10")
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "Get the mix report" not in ours
    assert ours.count("Mix reports are paused for the rest of this month") == 1


def test_second_rr9_the_same_30_seconds_is_only_said_when_it_is_true(env):
    c = _account()
    sid, _jid = _recombine_ready(c, env, task="rc_s")
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "same 30 seconds" not in ours and "loudest part" in ours
    sid = _mix_with_report(c, env)
    _preview_ready(c, env, sid, task="mt_s1", start=72.0)
    _preview_ready(c, env, sid, task="mt_s2", start=72.0)
    assert "the same 30 seconds" in _ours(_page(c, PAGE + "/sources/%s" % sid))
    _preview_ready(c, env, sid, task="mt_s3", start=40.0)
    ours = _ours(_page(c, PAGE + "/sources/%s" % sid))
    assert "the same 30 seconds" not in ours and "don't all start at the same place" in ours
    assert "The same 30 seconds" not in _ours(_page(c, PAGE))


def test_second_rr11_a_master_the_owner_released_does_not_say_payment_received(env):
    c = _account()
    sid = _mix_with_report(c, env)
    jid = _preview_ready(c, env, sid)
    _final_ok(env)
    env.put_fails = True
    owner = _owner(env)
    owner.post("/admin/release-ready/jobs/%s/retry" % jid, data={"action": "retrieve", "unpaid_ok": "1"},
               headers=J)
    job = rstore.get_job(jid)
    assert job["status"] == "retrieving" and not job["paid_at"]
    view = c.get(PAGE + "/jobs/%s.json" % jid).get_json()["job"]
    assert view["chip"] == "Getting your master"
    assert view["message"] == rr.COPY["release_working"] and "Payment" not in view["message"]


def test_second_rr12_a_team_seat_confirms_on_the_artists_behalf(env):
    artist, editor = _account("pro", "Mara"), _account("artist", "Editor")
    _invite(artist, editor, "edit")
    ours = _ours(_page(editor, PAGE))
    seat = rr.consent_text("Mara")
    assert seat["rights"] in ours and seat["licence"] in ours
    assert "On behalf of Mara" in ours and rr.CONSENT_RIGHTS not in ours
    assert 'name="consent_version" value="rr-consent-2-seat"' in ours
    r = _upload_mix(editor)                       # the account holder's wording
    assert r.status_code == 400 and r.get_json()["message"] == rr.COPY["consent_changed"]
    env.roex.on("/mixanalysis", _analysis_ok())
    sid = _upload_mix(editor, version=rr.CONSENT_VERSION_SEAT).get_json()["source_id"]
    consent = rstore.get_consent(rstore.get_source(sid)["consent_id"])
    assert consent["text_version"] == "rr-consent-2-seat"
    assert consent["text_sha256"] == rr._consent_hash(seat)
    # The account holder still makes their own statement.
    assert "On behalf of" not in _ours(_page(artist, PAGE))


def test_second_rr13_the_room_card_is_live_only_when_release_ready_is(env, monkeypatch):
    import hubs

    def entry():
        return [e for e in hubs.command_index() if e["key"] == "release-ready"][0]
    assert "release-ready" in hubs.live_keys() and entry()["live"] is True
    store.set_kv("rr_open", "0")
    assert "release-ready" not in hubs.live_keys() and entry()["live"] is False
    store.set_kv("rr_open", "1")
    monkeypatch.delenv("ROEX_API_KEY")
    assert "release-ready" not in hubs.live_keys()
