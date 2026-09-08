"""The Stage Rack status surface (STAGE RACK in the brief).

What the software must expose for the edge device that will one day be an
appliance, computed from what the device last said and never from a flag.
The hardware does not exist; these hold the surface the brief lists, field
by field, and that a value nobody measured is shown as not measured.
"""
from datetime import datetime, timedelta, timezone
import json
import re
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps
import stage_adapters as sa
import stage_bridge as sb
import stage_rack as rack
import stage_safety as ss
import stage_store as st

USER = "rack-tests"
PASSWORD = "rack-rooms-123"


@pytest.fixture(scope="module", autouse=True)
def schema():
    store.init_db()
    ps.init_passports()
    adv.init_advance()
    st.init_stage()
    sb.init_bridge()


def _show():
    sid = "show-" + uuid.uuid4().hex[:10]
    pid = ps.create_passport(USER, artist_name="Prayers")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", sort=1)
    ps.publish(pid, USER)
    adv.attach(sid, USER, pid)
    return sid


# --- the fields the brief lists -------------------------------------------------------

def test_a_show_with_no_device_reports_every_field_as_absent():
    sid = _show()
    s = rack.status(sid, USER)
    assert s["device"] is None and s["adapter"] is None and s["lamps"] == []
    assert s["network"]["label"] == rack.NOT_MEASURED
    assert s["console"]["label"] == s["software_version"] == s["last_update"] == rack.NOT_REPORTED
    assert s["mode"] == {"mode": "request", "code": "no_device",
                         "reason": "No Stage Bridge is registered for this show."}
    assert s["armed"] is False and s["lockout"]["on"] is False and s["revoked"]["on"] is False


def test_the_brief_fields_are_all_present_and_computed():
    sid = _show()
    dev, token = sb.register(USER, sid, "Rack A")
    s = rack.status(sid, USER)
    for field in ("device", "ownership", "network", "console", "adapter", "software_version",
                  "last_update", "armed", "lockout", "revoked", "mode", "lamps", "policy"):
        assert field in s, field
    assert s["device"]["fingerprint"] == dev["token_hash"][:8] and token not in json.dumps(s)
    assert s["ownership"]["owner_id"] == USER
    assert s["network"]["label"] == rack.NOT_MEASURED, "no heartbeat yet is not offline"
    assert s["software_version"] == rack.NOT_REPORTED and s["last_update"] == rack.NOT_REPORTED
    assert s["console"]["label"] == rack.NOT_REPORTED
    assert s["adapter"]["key"] == "simulator" and s["adapter"]["verified"] is True
    assert s["armed"] is False and "disarmed" in s["lamps"]
    assert s["policy"]["offline_after_s"] == ss.offline_after_s(ss.policy(sid))


def test_a_heartbeat_from_an_old_daemon_reads_not_reported_for_the_rack_fields():
    sid = _show()
    dev, _t = sb.register(USER, sid, "Old")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True, "detail": "fine"}, software_version="daemon-0.1")
    s = rack.status(sid, USER)
    assert s["network"]["state"] == "online" and s["network"]["heartbeat_age_s"] == 0
    assert s["software_version"] == "daemon-0.1" and s["last_update"] == rack.NOT_REPORTED
    assert s["console"]["connected"] is True, "an old daemon's health ok is its console link"
    assert s["armed"] is True and s["lamps"] == []
    assert s["mode"]["mode"] == "connected"


def test_a_heartbeat_with_the_rack_fields_is_stored_clipped_and_shown():
    sid = _show()
    dev, _t = sb.register(USER, sid, "New")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True}, software_version="daemon-0.2",
                 report={"adapter_status": {"name": "simulator", "verified": True, "tested_model": "x" * 500},
                         "console_connected": False, "last_update": "2030-05-02T20:00:00+00:00",
                         "probe": {"reachable": False, "detail": "no answer"},
                         "token": "smuggled", "signing_key": "smuggled"})
    d = sb.get_device(dev["id"])
    rep = sb.report(d)
    assert set(rep) <= set(sb.REPORT_FIELDS) and "token" not in rep
    assert len(rep["adapter_status"]["tested_model"]) == 200
    s = rack.status(sid, USER)
    assert s["console"] == {"connected": False, "label": "unreachable", "detail": "no answer"}
    assert s["last_update"] == "2030-05-02T20:00:00+00:00" and s["software_version"] == "daemon-0.2"
    assert "console_unreachable" in s["lamps"]
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    assert rack.status(sid, USER)["last_update"] == "2030-05-02T20:00:00+00:00", \
        "a heartbeat without a report keeps the last one"


def test_lamps_light_only_for_states_that_need_a_person(monkeypatch):
    sid = _show()
    dev, _t = sb.register(USER, sid, "Lamps")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    assert rack.status(sid, USER)["lamps"] == []
    later = datetime.now(timezone.utc) + timedelta(seconds=ss.policy(sid)["heartbeat_stale_s"] + 5)
    assert rack.status(sid, USER, now=later)["lamps"] == ["stale"]
    gone = datetime.now(timezone.utc) + timedelta(seconds=ss.offline_after_s(ss.policy(sid)) + 5)
    assert rack.status(sid, USER, now=gone)["lamps"] == ["offline"]
    sb.lockout(dev["id"], USER, reason="Feedback")
    s = rack.status(sid, USER)
    assert s["lamps"] == ["lockout"] and s["lockout"] == {"on": True, "reason": "Feedback"}
    sb.release_lockout(dev["id"], USER)
    assert rack.status(sid, USER)["lamps"] == ["disarmed"]
    sb.revoke(dev["id"], USER)
    assert rack.status(sid, USER)["device"] is None, "a revoked device is no device for this show"
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    bench, _t = sb.register(USER, sid, "Bench", adapter_key="x32")
    sb.arm(bench["id"], USER)
    sb.heartbeat(sb.get_device(bench["id"]), {"ok": True})
    s = rack.status(sid, USER)
    assert "unverified_adapter" in s["lamps"] and s["adapter"]["verified"] is False
    for lamp in rack.LAMPS:
        assert lamp in rack.LAMP_WORDS


# --- the diagnostic export --------------------------------------------------------------

def test_the_export_carries_the_last_events_and_commands_redacted():
    sid = _show()
    dev, token = sb.register(USER, sid, "Diag")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    # The rate limits are the point elsewhere; here they would cap the run at
    # six commands a minute, so widen them to their bounds for the export.
    ss.set_policy(sid, USER, per_performer_per_min=30, per_mix_per_min=60, per_source_per_min=60)
    cmds = []
    for _ in range(25):
        rid = st.submit(sid, USER, "Leafar", "Mix 1", "more", source="Lead Vox", step_db=1,
                        allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"], rate_limit=0)
        st.approve(rid, USER)
        cmd, d = sb.issue(rid, USER, actor="eng")
        if cmd:
            cmds.append(cmd)
        sb.run_local(dev["id"], USER)
    body = rack.diagnostics(sid, USER)
    assert len(body["events"]) == 50 and len(body["commands"]) == 20
    seqs = [e["seq"] for e in body["events"]]
    assert seqs == sorted(seqs) and seqs[-1] == st.cursor(sid)
    text = json.dumps(body)
    assert token not in text and dev["signing_key"] not in text and dev["token_hash"] not in text
    for c in body["commands"]:
        assert "signature" not in c and isinstance(c["ack"], dict)
    assert body["adapters_available"] == ["simulator"] or "x32" in body["adapters_available"]


# --- the page and the route ----------------------------------------------------------------

@pytest.fixture
def room():
    application = appmod.app
    email = "rack-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Rack Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", sort=1)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
    return {"client": client, "user": user, "show": sid, "app": application}


def test_the_bridge_page_draws_the_rack_as_instruments(room):
    c, sid = room["client"], room["show"]
    c.post("/stage/%s/bridge/register" % sid, data={"name": "Rack A", "adapter": "simulator"})
    page = c.get("/stage/%s/bridge" % sid).get_data(as_text=True)
    assert "Stage Rack" in page and 'class="sc-rack' in page
    assert page.count('class="sb-lcd') >= 12, "one LCD per field the brief lists"
    assert "Not measured" in page and "Not reported" in page
    assert "Disarmed" in page
    assert "/stage/%s/bridge/diagnostics.json" % sid in page
    with room["app"].app_context():
        dev = sb.device_for_show(sid, room["user"]["id"])
    assert dev["token_hash"][:8] in page and dev["token_hash"] not in page
    c.post("/stage/%s/bridge/arm" % sid)
    c.post("/stage/%s/bridge/heartbeat" % sid)
    page = c.get("/stage/%s/bridge" % sid).get_data(as_text=True)
    assert "online" in page and "local-1.0" in page and "Not reported" not in page
    assert re.search(r'<span class="sb-lcd-v">(Armed|Connected)</span>', page)


def test_the_diagnostics_route_is_json_for_the_owner_and_404_for_a_stranger(room):
    c, sid = room["client"], room["show"]
    c.post("/stage/%s/bridge/register" % sid, data={"name": "Rack A", "adapter": "simulator"})
    r = c.get("/stage/%s/bridge/diagnostics.json" % sid)
    assert r.status_code == 200 and r.mimetype == "application/json"
    body = r.get_json()
    assert body["show_id"] == sid and body["device"]["name"] == "Rack A"
    assert "events" in body and "commands" in body
    stranger = room["app"].test_client()
    assert stranger.get("/stage/%s/bridge/diagnostics.json" % sid).status_code in (302, 401)
    other = room["app"].test_client()
    email = "rack-x-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "X", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    assert other.get("/stage/%s/bridge/diagnostics.json" % sid).status_code == 404


def test_the_device_heartbeat_endpoint_takes_the_rack_fields_over_http(room):
    c, sid = room["client"], room["show"]
    r = c.post("/stage/%s/bridge/register" % sid, data={"name": "Rack A", "adapter": "simulator"})
    page = c.get(r.headers["Location"]).get_data(as_text=True)
    token = re.search(r'<p class="sc-token">([^<]+)</p>', page).group(1)
    dev = room["app"].test_client()
    hb = dev.post("/bridge/heartbeat", headers={"Authorization": "Bearer " + token}, json={
        "health": {"ok": True}, "software_version": "daemon-0.2",
        "adapter_status": {"name": "simulator", "verified": True}, "console_connected": True,
        "last_update": "2030-01-01T00:00:00+00:00"}).get_json()
    assert hb["ok"] and "heartbeat_stale_s" in hb
    with room["app"].app_context():
        s = rack.status(sid, room["user"]["id"])
    assert s["software_version"] == "daemon-0.2" and s["console"]["connected"] is True
    assert s["last_update"] == "2030-01-01T00:00:00+00:00"
