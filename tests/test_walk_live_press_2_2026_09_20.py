"""Three things the 2026-09-20 live and press walk found, pinned.

A month or day that has the right shape but does not exist (2027-13,
2027-02-30) was a 500 on the calendar pages; a JSON body that is a number
or a string reached `.get` and was a 500 on every JSON endpoint, including
the anonymous pitch play counter; and /stage/<anything> opened an empty
Engineer Desk for any signed-in account, other accounts' dates included.
"""
import uuid
from datetime import date, timedelta

import pytest

import advance_store as adv
import app as appmod
import db as store
import epk_config
import passport_store as ps
import stage_bridge as sb
import tour_engine as eng

PW = "walk-lp2-pw-1234"
TZ = "America/New_York"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(name="Walk Artist", plan="label"):
    email = "lp2-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _tour_with_a_date(c):
    r = c.post("/tours/new", data={
        "name": "Walk Run", "artist_name": "Walk", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": TZ, "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = c.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "Walk Hall",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    return tid, sid


def _post_json(c, path, raw, **kw):
    return c.post(path, data=raw, content_type="application/json", **kw)


# --- 1. a month or day that does not exist ---------------------------------

def test_a_month_that_does_not_exist_shows_this_month_instead():
    c, _uid = _account()
    tid, _sid = _tour_with_a_date(c)
    this_month = date.today().strftime("%B %Y")
    for q in ("2027-13", "2027-00", "2027-99"):
        r = c.get("/tours?month=" + q)
        assert r.status_code == 200, q
        assert 'aria-label="%s"' % this_month in r.get_data(as_text=True), q
    tour_month = date.fromisoformat(eng.today_in(TZ)).strftime("%B %Y")
    for q in ("2027-13", "2027-00"):
        r = c.get("/tours/%s/calendar?month=%s" % (tid, q))
        assert r.status_code == 200, q
        assert tour_month in r.get_data(as_text=True), q
    # A real month is still honoured.
    body = c.get("/tours/%s/calendar?month=2030-05" % tid).get_data(as_text=True)
    assert "May 2030" in body and "Nashville, TN" in body


def test_a_day_that_does_not_exist_shows_today_instead():
    c, _uid = _account()
    tid, _sid = _tour_with_a_date(c)
    today = date.fromisoformat(eng.today_in(TZ))
    for q in ("2027-02-30", "2027-13-01", "2027-00-10"):
        r = c.get("/tours/%s/my-day?date=%s" % (tid, q))
        assert r.status_code == 200, q
        body = r.get_data(as_text=True)
        assert "?date=%s" % (today + timedelta(days=1)).isoformat() in body, q
    r = c.get("/tours/%s/my-day?date=2030-05-02" % tid)
    assert r.status_code == 200 and "?date=2030-05-03" in r.get_data(as_text=True)


# --- 2. a JSON body that is not an object -----------------------------------

def test_the_anonymous_pitch_play_counter_survives_a_scalar_body():
    _c, uid = _account()
    token = "tok" + uuid.uuid4().hex[:12]
    store.upsert_epk_share(uid, token, "", "", [{"label": "Song", "url": "/x.mp3"}])
    anon = appmod.app.test_client()
    for raw in ("42", '"x"', "[]", "null", "true"):
        r = _post_json(anon, "/pitch/%s/play" % token, raw)
        assert r.status_code == 400, raw
    # A real play still counts.
    assert _post_json(anon, "/pitch/%s/play" % token, '{"label": "Song"}').status_code == 200


def test_signed_in_json_endpoints_survive_a_scalar_body():
    c, uid = _account()
    paths = ("/epk/save", "/epk/asset/photo/visibility", "/epk/asset/photo/from-vault",
             "/lights/library/save", "/lights/rigs/save", "/lights/setlists/save",
             "/lights/library/%s/share" % uuid.uuid4().hex,
             "/lights/library/%s/comment" % uuid.uuid4().hex,
             "/lights/remote/%s/cmd" % uuid.uuid4().hex[:8],
             "/support/ask", "/catalog/add", "/artwork/save", "/links/create",
             "/funding/request")
    for path in paths:
        for raw in ("42", '"x"'):
            r = _post_json(c, path, raw)
            assert r.status_code < 500, (path, raw, r.status_code)
    # A body that was not a form saved nothing to the EPK.
    assert (store.get_epk(uid) or {}).get("data") in (None, {})
    assert epk_config.normalize_epk_overrides(42) == {}
    assert epk_config.normalize_epk_overrides("x") == {}


def test_a_signed_vendor_webhook_survives_a_scalar_body(monkeypatch):
    """The audio vendors' door checks the signature first, then read the
    body with `.get`; a signed scalar was the one way past it to a 500."""
    import hashlib
    import hmac
    monkeypatch.setenv("AUDIO_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MOCK_WEBHOOK_SECRET", "walk-lp2-secret")
    vendor = appmod.app.test_client()
    for raw in (b"42", b'"x"'):
        sig = hmac.new(b"walk-lp2-secret", raw, hashlib.sha256).hexdigest()
        r = vendor.post("/webhooks/audio/mock", data=raw, content_type="application/json",
                        headers={"X-Signature": sig, "X-Event-Id": uuid.uuid4().hex})
        assert r.status_code == 200, (raw, r.status_code)
        assert r.get_json()["ok"] is True


def test_a_studio_measurement_with_a_scalar_body_is_a_404_not_a_500():
    c, _uid = _account()
    r = c.post("/studio/new", data={"title": "Walk Fire", "artist_name": "Walk",
                                    "project_type": "master_single"})
    pid = r.headers["Location"].rstrip("/").split("/")[-1].split("?")[0]
    for raw in ("42", '"x"'):
        r = _post_json(c, "/studio/session/%s/measure" % pid, raw)
        assert r.status_code == 404, (raw, r.status_code)


def test_the_device_door_survives_a_scalar_body():
    _c, uid = _account()
    sid = "show-" + uuid.uuid4().hex[:10]
    pid = ps.create_passport(uid, artist_name="Walk")
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Walk", sort=1)
    ps.publish(pid, uid)
    adv.attach(sid, uid, pid)
    _dev, token = sb.register(uid, sid, "Rack A")
    machine = appmod.app.test_client()
    hdr = {"Authorization": "Bearer " + token}
    for path in ("/bridge/heartbeat", "/bridge/ack", "/bridge/reconcile"):
        r = _post_json(machine, path, "42", headers=hdr)
        assert r.status_code == 200, path


# --- 3. /stage/<id> is a door only onto a stage the caller may open ----------

STAGE_READS = ("", "/bridge", "/me", "/events?since=0", "/bridge/diagnostics.json")


def test_an_id_no_tour_or_passport_holds_is_a_404():
    c, _uid = _account()
    for sid in ("not-a-show", uuid.uuid4().hex):
        for sub in STAGE_READS:
            assert c.get("/stage/%s%s" % (sid, sub)).status_code == 404, (sid, sub)
        assert c.post("/stage/%s/lock" % sid, data={}).status_code == 404
        assert c.post("/stage/%s/ask" % sid, data={}).status_code == 404


def test_another_accounts_unadvanced_date_is_a_404():
    owner, _uid = _account("Owner")
    _tid, sid = _tour_with_a_date(owner)
    other, _uid2 = _account("Other")
    for sub in STAGE_READS:
        assert other.get("/stage/%s%s" % (sid, sub)).status_code == 404, sub
    assert other.post("/stage/%s/lock" % sid, data={}).status_code == 404
    assert other.post("/stage/%s/bridge/lockout" % sid, data={}).status_code == 404
    # The stranger's session never sees the show's page nor its name.
    assert "Walk Hall" not in other.get("/stage/%s" % sid).get_data(as_text=True)


def test_the_owners_own_unadvanced_date_still_opens_the_desk():
    owner, _uid = _account("Owner")
    _tid, sid = _tour_with_a_date(owner)
    r = owner.get("/stage/%s" % sid)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "no passport attached" in body.lower()
    assert owner.get("/stage/%s/bridge" % sid).status_code == 200
    assert owner.get("/stage/%s/events?since=0" % sid).status_code == 200


def test_a_passport_attachment_still_opens_the_desk_without_a_tour_row():
    """Every stage test builds its show this way: an id that lives only in
    the attachment. That door stays open, for the owner alone."""
    owner, uid = _account("Owner")
    sid = "show-" + uuid.uuid4().hex[:10]
    pid = ps.create_passport(uid, artist_name="Walk")
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Walk", sort=1)
    ps.publish(pid, uid)
    adv.attach(sid, uid, pid)
    assert owner.get("/stage/%s" % sid).status_code == 200
    other, _uid2 = _account("Other")
    assert other.get("/stage/%s" % sid).status_code == 404
