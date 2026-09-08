"""Stage Control phase 7: the brief's ACCEPTANCE CRITERIA, one test each.

docs/STAGE_CONTROL_BRIEF.md ends with sixteen bullets under "The build is
complete only when". Each is a test here, in the brief's order and with the
brief's words in the test name, so a reader can tick the list against a test
run. Where an earlier module already proves a bullet in depth, the test here
is short and its docstring names the deeper one; where a bullet FAILED while
this file was written, the product was fixed and the fix is recorded in
docs/STAGE_CONTROL_PHASE7.md.

Everything runs against the simulator. The bullets that need a real console
- "the simulator adapter can process supported bounded commands" is the only
console bullet, and it names the simulator on purpose - are covered; the X32
adapter's bench run on real hardware is an open item, not an acceptance
criterion.
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
import stage_safety as ss
import stage_store as st
import tour_store as ts

PASSWORD = "accept-rooms-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


def _account(application, label="acc"):
    email = "%s-%s@example.net" % (label, uuid.uuid4().hex[:10])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        user = store.get_user_by_email(email)
    return client, user


def _passport(user, sources=("Lead Vox",)):
    pid = ps.create_passport(user["id"], artist_name="Prayers", production_name="No Tengo Calma")
    for i, s in enumerate(sources):
        ps.add_row("inputs", pid, channel=str(i + 1), source=s, sort=i + 1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
    ps.publish(pid, user["id"])
    return pid


@pytest.fixture
def show(application):
    """An owner, a published passport, and a show advanced against it."""
    client, user = _account(application, "owner")
    with application.app_context():
        pid = _passport(user)
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
    return {"client": client, "user": user, "show": sid, "passport": pid}


@pytest.fixture
def tour_show(application):
    """The same, as a TOUR date with a live Stage Control share link, so a
    performer with no account can open the page from a QR code."""
    client, user = _account(application, "tourowner")
    r = client.post("/tours/new", data={
        "name": "Accept Run", "artist_name": "Prayers", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "The Basement East",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    with application.app_context():
        pid = _passport(user, sources=("Lead Vox", "Kick"))
        adv.attach(sid, user["id"], pid)
    client.post("/tours/%s/share/new" % tid, data={"scope": "stage", "show_id": sid})
    with application.app_context():
        link = [l for l in ts.list_share_links(tid) if l["scope"] == "stage"][0]
    return {"client": client, "user": user, "tour": tid, "show": sid, "token": link["token"]}


def _token_from(page):
    return re.search(r'<p class="sc-token">([^<]+)</p>', page).group(1)


def _register_and_arm(show):
    c = show["client"]
    r = c.post("/stage/%s/bridge/register" % show["show"], data={"name": "Rack A", "adapter": "simulator"})
    token = _token_from(c.get(r.headers["Location"]).get_data(as_text=True))
    c.post("/stage/%s/bridge/arm" % show["show"])
    c.post("/stage/%s/bridge/heartbeat" % show["show"])
    return token


def _ask(show, kind="more", step="2", source="Lead Vox"):
    show["client"].post("/stage/%s/ask" % show["show"], data={
        "performer": "Leafar", "mix": "Mix 1", "kind": kind, "source": source, "step_db": step})
    with show["client"].application.app_context():
        rows = st.for_show(show["show"], show["user"]["id"], open_only=True)
    return rows[-1]["id"]


def _state(show, rid):
    with show["client"].application.app_context():
        return st.get(rid, show["user"]["id"])["state"]


# 1 ---------------------------------------------------------------------------

def test_a_production_team_can_create_and_publish_a_versioned_show_passport(application):
    """Deeper: tests/test_passport_store.py, tests/test_passport_routes.py."""
    client, user = _account(application, "team")
    r = client.post("/passports/new", data={"artist_name": "Prayers", "production_name": "Calma"})
    pid = r.headers["Location"].rstrip("/").split("/")[-1]
    client.post("/passports/%s/inputs/add" % pid, data={"channel": "1", "source": "Lead Vox"})
    r = client.post("/passports/%s/publish" % pid, data={"change_note": "First"})
    assert r.status_code in (302, 303)
    with application.app_context():
        head = ps.get_passport(pid, user["id"])
        v1 = ps.get_version(head["current_version_id"], user["id"])
    assert v1 and v1["number"] == 1
    r = client.post("/passports/%s/publish" % pid, data={"change_note": "Second"})
    with application.app_context():
        head = ps.get_passport(pid, user["id"])
        v2 = ps.get_version(head["current_version_id"], user["id"])
        both = ps.versions(pid)
    assert v2["number"] == 2 and v2["id"] != v1["id"]
    assert [v["number"] for v in both] == [2, 1] or [v["number"] for v in both] == [1, 2]
    page = client.get("/passports/%s/versions" % pid).get_data(as_text=True)
    assert "v2" in page and "v1" in page


# 2 ---------------------------------------------------------------------------

def test_a_show_retains_its_assigned_passport_version(show):
    """Deeper: tests/test_tour_stage_link.py::test_a_newer_version_is_a_notice_never_a_swap."""
    with show["client"].application.app_context():
        first = adv.get_attachment(show["show"], show["user"]["id"])["version_id"]
        ps.add_row("inputs", show["passport"], channel="2", source="Kick", sort=2)
        ps.publish(show["passport"], show["user"]["id"])
        assert adv.get_attachment(show["show"], show["user"]["id"])["version_id"] == first
        snap = adv.snapshot_for(show["show"], show["user"]["id"])
    assert [i["source"] for i in snap["inputs"]] == ["Lead Vox"], "the desk reads the frozen version"


# 3 ---------------------------------------------------------------------------

def test_a_performer_can_submit_a_request_from_a_mobile_device(tour_show, application):
    """A phone with no account, through the QR share link. Deeper:
    tests/test_stage_guest.py."""
    phone = application.test_client()
    page = phone.get("/stage/guest/%s?as=Leafar" % tour_show["token"])
    assert page.status_code == 200 and "Mix 1" in page.get_data(as_text=True)
    r = phone.post("/stage/guest/%s/ask" % tour_show["token"], data={
        "performer": "Leafar", "mix": "Mix 1", "kind": "more", "source": "Kick", "step_db": "1"})
    assert r.status_code in (302, 303) and "refused" not in r.headers["Location"]
    with application.app_context():
        queue = st.for_show(tour_show["show"], tour_show["user"]["id"], open_only=True)
    assert len(queue) == 1 and queue[0]["source"] == "Kick" and queue[0]["state"] == "pending"


# 4 ---------------------------------------------------------------------------

def test_the_request_appears_in_realtime_at_the_engineer_desk(tour_show, application):
    """Realtime is the event cursor (phase 1 audit: no sockets, by decision).
    The desk polls /events?since=N and the new request is in the answer."""
    before = tour_show["client"].get("/stage/%s/events?since=0" % tour_show["show"]).get_json()["cursor"]
    phone = application.test_client()
    phone.post("/stage/guest/%s/ask" % tour_show["token"], data={
        "performer": "Leafar", "mix": "Mix 1", "kind": "feedback"})
    poll = tour_show["client"].get("/stage/%s/events?since=%d" % (tour_show["show"], before)).get_json()
    kinds = [(e["kind"], e["actor"]) for e in poll["events"]]
    assert ("request.new", "Leafar") in kinds
    assert poll["cursor"] > before and poll["summary"]["urgent"] == 1
    desk = tour_show["client"].get("/stage/%s" % tour_show["show"]).get_data(as_text=True)
    assert "Feedback" in desk and "Leafar" in desk


# 5 ---------------------------------------------------------------------------

def test_the_engineer_can_acknowledge_modify_apply_manually_reject_or_approve(show):
    c, sid = show["client"], show["show"]
    a, b, d, e = _ask(show), _ask(show), _ask(show), _ask(show)
    c.post("/stage/%s/request/%s/acknowledge" % (sid, a))
    assert _state(show, a) == "acknowledged"
    c.post("/stage/%s/request/%s/modify" % (sid, a), data={"step_db": "1"})
    assert _state(show, a) == "modified"
    c.post("/stage/%s/request/%s/applied" % (sid, b), data={"note": "Pushed it a touch"})
    assert _state(show, b) == "applied_manually"
    c.post("/stage/%s/request/%s/reject" % (sid, d), data={"reason": "Wedge is at the edge"})
    assert _state(show, d) == "rejected"
    c.post("/stage/%s/request/%s/approve" % (sid, e))
    assert _state(show, e) == "approved"
    with c.application.app_context():
        assert st.get(a, show["user"]["id"])["approved_step_db"] == 1
        assert st.get(d, show["user"]["id"])["engineer_note"] == "Wedge is at the edge"


# 6 ---------------------------------------------------------------------------

def test_request_states_remain_accurate(show):
    """Every transition the log records is one TRANSITIONS allows, and the
    state a request ends in is the state its last event says. Deeper:
    tests/test_stage_store.py."""
    c, sid = show["client"], show["show"]
    rid = _ask(show)
    c.post("/stage/%s/request/%s/acknowledge" % (sid, rid))
    c.post("/stage/%s/request/%s/modify" % (sid, rid), data={"step_db": "3"})
    c.post("/stage/%s/request/%s/approve" % (sid, rid))
    c.post("/stage/%s/request/%s/applied" % (sid, rid))
    c.post("/stage/%s/request/%s/approve" % (sid, rid))   # refused: terminal-ish state
    with c.application.app_context():
        events = [e for e in st.events_since(sid, 0) if e["request_id"] == rid
                  and e["kind"].startswith("request.") and e["kind"] != "request.new"]
        final = st.get(rid, show["user"]["id"])["state"]
    hops = [(e["payload"]["from"], e["payload"]["to"]) for e in events]
    assert hops == [("pending", "acknowledged"), ("acknowledged", "modified"),
                    ("modified", "approved"), ("approved", "applied_manually")]
    for a, b in hops:
        assert st.can_move(a, b), (a, b)
    assert final == hops[-1][1] == "applied_manually"
    assert set(st.STATES) == set(st.TRANSITIONS) == set(st.PERFORMER_WORDING)


# 7 ---------------------------------------------------------------------------

def test_the_simulator_adapter_can_process_supported_bounded_commands(show):
    _register_and_arm(show)
    rid = _ask(show, step="3")
    show["client"].post("/stage/%s/request/%s/approve" % (show["show"], rid))
    r = show["client"].post("/stage/%s/request/%s/send" % (show["show"], rid))
    assert "refused" not in r.headers["Location"]
    with show["client"].application.app_context():
        req = st.get(rid, show["user"]["id"])
        cmd = sb.get_command(req["command_id"])
    assert req["state"] == "applied" and cmd["state"] == "applied"
    ack = json.loads(req["device_ack"])
    assert ack == {"ok": True, "before": -20.0, "after": -17.0, "confirmed": True,
                   "failure": None, "simulated": True}
    assert abs(cmd["step_db"]) <= sa.spec("simulator")["limits"]["max_step_db"]


# 8 ---------------------------------------------------------------------------

def test_unsupported_commands_are_rejected(show, monkeypatch):
    """At every layer: a report never becomes a command; an adapter without
    the command refuses it; a bridge refuses a signed body naming anything
    outside the vocabulary."""
    _register_and_arm(show)
    with show["client"].application.app_context():
        uid = show["user"]["id"]
        rid = st.submit(show["show"], uid, "Leafar", "Mix 1", "feedback", allowed_mixes=["Mix 1"])
        st.approve(rid, uid)
        cmd, d = sb.issue(rid, uid, actor="eng")
        assert cmd is None and d.code == "not_a_command"

        class NoMute(sa.SimulatorAdapter):
            SPEC = dict(sa.SimulatorAdapter.SPEC, key="nomute",
                        commands=("send_level_delta", "read_send_level"))
        monkeypatch.setitem(sa.ADAPTERS, "nomute", NoMute)
        dev = sb.device_for_show(show["show"], uid)
        d = ss.evaluate(show["show"], {"id": "r", "show_id": show["show"], "user_id": uid,
                                       "performer": "Leafar", "mix": "Mix 1", "source": "Lead Vox",
                                       "kind": "mute", "state": "approved", "step_db": 0},
                        dict(dev, adapter_key="nomute"), ["Mix 1"], ["Lead Vox"], {}, uid)
        assert d.code == "unsupported"

        rid = _ask(show)
        st.approve(rid, uid)
        cmd, _ = sb.issue(rid, uid, actor="eng")
        sb.pull(dev)
        forged = dict(sb.get_command(cmd["id"]), command="preamp_gain")
        forged["signature"] = sb.sign(forged, dev["signing_key"])
        assert sb.verify_for_device(forged, dev).code == "not_allowed"
        for never in sa.NEVER:
            assert never not in sa.COMMANDS


# 9 ---------------------------------------------------------------------------

def test_replayed_and_expired_commands_are_rejected(show, application):
    """Over the device's own door. Deeper: tests/test_stage_bridge.py."""
    token = _register_and_arm(show)
    dev = application.test_client()
    auth = {"Authorization": "Bearer " + token}
    with application.app_context():
        uid = show["user"]["id"]
        rid = _ask(show)
        st.approve(rid, uid)
        cmd, _ = sb.issue(rid, uid, actor="eng")
    pulled = dev.post("/bridge/pull", json={}, headers=auth).get_json()["commands"]
    assert [p["id"] for p in pulled] == [cmd["id"]]
    body = {"command_id": cmd["id"], "nonce": cmd["nonce"], "result": {"ok": True, "confirmed": True}}
    assert dev.post("/bridge/ack", json=body, headers=auth).get_json()["code"] == "applied"
    assert dev.post("/bridge/ack", json=body, headers=auth).get_json()["code"] == "replayed"
    assert _state(show, rid) == "applied"
    with application.app_context():
        rid2 = _ask(show)
        st.approve(rid2, uid)
        cmd2, _ = sb.issue(rid2, uid, actor="eng")
        device = sb.device_for_show(show["show"], uid)
        sb.pull(device)
        late = datetime.now(timezone.utc) + timedelta(seconds=90)
        _c, d = sb.acknowledge(device, cmd2["id"], cmd2["nonce"], {"ok": True, "confirmed": True}, now=late)
    assert d.code == "expired" and _state(show, rid2) == "expired"


# 10 --------------------------------------------------------------------------

def test_stage_bridge_can_be_revoked(show, application):
    token = _register_and_arm(show)
    dev = application.test_client()
    auth = {"Authorization": "Bearer " + token}
    assert dev.post("/bridge/heartbeat", json={}, headers=auth).status_code == 200
    show["client"].post("/stage/%s/bridge/revoke" % show["show"])
    assert dev.post("/bridge/heartbeat", json={}, headers=auth).status_code == 401
    assert dev.post("/bridge/pull", json={}, headers=auth).status_code == 401
    with application.app_context():
        m = sb.mode(show["show"], show["user"]["id"])
    assert m["mode"] == "request" and m["code"] == "no_device"
    page = show["client"].get("/stage/%s/bridge" % show["show"]).get_data(as_text=True)
    assert "No Stage Bridge yet" in page, "a revoked device is gone; register another"


# 11 --------------------------------------------------------------------------

def test_emergency_lockout_immediately_prevents_connected_commands(show, application):
    token = _register_and_arm(show)
    dev = application.test_client()
    auth = {"Authorization": "Bearer " + token}
    with application.app_context():
        uid = show["user"]["id"]
        queued = _ask(show); st.approve(queued, uid); sb.issue(queued, uid, actor="eng")
        sent = _ask(show); st.approve(sent, uid); c_sent, dsent = sb.issue(sent, uid, actor="eng"); assert c_sent is not None, (dsent.code, dsent.reason if hasattr(dsent, "reason") else dsent)
        sb.pull(sb.device_for_show(show["show"], uid))
    # Every seat may press it; here the owner does, from the desk.
    r = show["client"].post("/stage/%s/bridge/lockout" % show["show"], data={"reason": "Feedback"})
    assert r.status_code in (302, 303)
    assert _state(show, queued) == "failed" and _state(show, sent) == "failed"
    pulled = dev.post("/bridge/pull", json={}, headers=auth).get_json()
    assert pulled["lockout"] is True and pulled["commands"] == []
    late = dev.post("/bridge/ack", json={"command_id": c_sent["id"], "nonce": c_sent["nonce"],
                                         "result": {"ok": True, "confirmed": True}}, headers=auth).get_json()
    assert late["code"] == "replayed" and _state(show, sent) == "failed"
    with application.app_context():
        fresh = _ask(show); st.approve(fresh, uid)
        cmd, d = sb.issue(fresh, uid, actor="eng")
    assert cmd is None and d.code == "lockout"
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert 'data-mode="request"' in desk and "lockout" in desk.lower()


# 12 --------------------------------------------------------------------------

def test_internet_loss_does_not_falsely_report_successful_changes(show, application):
    """Three ways a link can die, none of which may read `applied`: the
    bridge never answers (the desk poll expires it); the answer arrives
    after expiry; the answer arrives without confirmation."""
    _register_and_arm(show)
    with application.app_context():
        uid = show["user"]["id"]
        device = sb.device_for_show(show["show"], uid)
        silent = _ask(show); st.approve(silent, uid); sb.issue(silent, uid, actor="eng")
        sb.pull(device)
        assert st.get(silent, uid)["state"] == "sent"
        later = datetime.now(timezone.utc) + timedelta(seconds=90)
        sb.expire_stale(show["show"], uid, now=later)
        assert st.get(silent, uid)["state"] == "expired"

        late = _ask(show); st.approve(late, uid); c_late, _ = sb.issue(late, uid, actor="eng")
        sb.pull(device)
        sb.acknowledge(device, c_late["id"], c_late["nonce"], {"ok": True, "confirmed": True}, now=later)
        assert st.get(late, uid)["state"] == "expired"

        unsure = _ask(show); st.approve(unsure, uid); c_un, _ = sb.issue(unsure, uid, actor="eng")
        sb.pull(device)
        sb.acknowledge(device, c_un["id"], c_un["nonce"], {"ok": True, "confirmed": False})
        assert st.get(unsure, uid)["state"] == "device_acknowledged"
        # Only the bridge's CONFIRMED acknowledgement takes the last hop, and
        # the command is settled, so a second answer is a replay.
        assert sb.acknowledge(device, c_un["id"], c_un["nonce"], {"ok": True, "confirmed": True})[1].code == "replayed"
        assert st.get(unsure, uid)["state"] == "device_acknowledged"
        assert st.can_move("sent", "applied") is False and st.can_move("pending", "applied") is False
    for state in ("sent", "expired", "device_acknowledged"):
        assert st.PERFORMER_WORDING[state] != "Done"
    phone = show["client"].get("/stage/%s/me?as=Leafar" % show["show"]).get_data(as_text=True)
    assert "Console answered" in phone and "Timed out" in phone


# 13 --------------------------------------------------------------------------

def test_request_mode_remains_usable_without_console_integration(show):
    c, sid = show["client"], show["show"]
    desk = c.get("/stage/%s" % sid).get_data(as_text=True)
    assert 'data-mode="request"' in desk and "No console is connected" in desk
    rid = _ask(show)
    c.post("/stage/%s/request/%s/acknowledge" % (sid, rid))
    c.post("/stage/%s/request/%s/applied" % (sid, rid))
    assert _state(show, rid) == "applied_manually"
    phone = c.get("/stage/%s/me?as=Leafar" % sid).get_data(as_text=True)
    assert "Done" in phone and "Request Mode" in phone
    with c.application.app_context():
        assert sb.device_for_show(sid, show["user"]["id"]) is None


# 14 --------------------------------------------------------------------------

def test_tenant_isolation_is_tested(show, application):
    """Another account: 404 everywhere, never 403 - a stranger must not learn
    a show exists from the shape of the refusal. Deeper:
    tests/test_stage_partner_roles.py."""
    other, _u = _account(application, "other")
    rid = _ask(show)
    sid = show["show"]
    for path in ("/stage/%s" % sid, "/stage/%s/bridge" % sid, "/stage/%s/events?since=0" % sid,
                 "/stage/%s/me" % sid, "/stage/%s/bridge/diagnostics.json" % sid):
        assert other.get(path).status_code == 404, path
    for path in ("/stage/%s/request/%s/approve" % (sid, rid), "/stage/%s/bridge/lockout" % sid,
                 "/stage/%s/lock" % sid):
        assert other.post(path, data={}).status_code == 404, path
    assert _state(show, rid) == "pending"
    with application.app_context():
        assert st.get(rid, _u["id"]) is None


def test_role_authorization_is_tested(show, application):
    """A seat at the owning partner opens what its role carries; without the
    permission it is a 403. Deeper: tests/test_stage_partner_roles.py."""
    import partner_store as pstore
    with application.app_context():
        partner = pstore.create_partner("Accept %s" % uuid.uuid4().hex[:6])
        assert pstore.attach_user(partner, show["user"]["id"])
    seats = {}
    for role in ("viewer", "support", "manager"):
        client, user = _account(application, role)
        with application.app_context():
            pstore.add_member(partner, user["email"], name=user["name"], role=role, user_id=user["id"])
        seats[role] = client
    sid = show["show"]
    assert seats["viewer"].get("/stage/%s" % sid).status_code == 403
    assert seats["support"].get("/stage/%s" % sid).status_code == 200
    _register_and_arm(show)
    rid = _ask(show)
    show["client"].post("/stage/%s/request/%s/approve" % (sid, rid))
    assert seats["support"].post("/stage/%s/request/%s/send" % (sid, rid)).status_code == 403
    assert seats["manager"].get("/stage/%s/bridge" % sid).status_code == 403
    assert seats["manager"].get("/stage/%s/bridge/diagnostics.json" % sid).status_code == 403
    assert _state(show, rid) == "approved"


# 15 --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/login", "/about", "/plan", "/press"])
def test_existing_street_banker_features_continue_working_public(application, path):
    r = application.test_client().get(path)
    assert r.status_code == 200, (path, r.status_code)


def test_existing_street_banker_features_continue_working_signed_in(show):
    for path in ("/passports/", "/tours", "/passports/%s" % show["passport"]):
        r = show["client"].get(path)
        assert r.status_code == 200, (path, r.status_code)


# 16 --------------------------------------------------------------------------

def test_setup_security_deployment_and_operating_documentation_are_complete():
    import io
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bridge = io.open(os.path.join(here, "docs", "STAGE_CONTROL_BRIDGE.md"), encoding="utf-8").read()
    for heading in ("## Operating runbook", "## Deployment validation", "## Device endpoints",
                    "## Registering a device", "## The safety engine", "## Running the bridge daemon"):
        assert heading in bridge, heading
    for word in ("lamp", "stale", "offline", "rotate", "revoke", "x32_bench", "graduat", "--diagnostics"):
        assert word.lower() in bridge.lower(), word
    phase7 = io.open(os.path.join(here, "docs", "STAGE_CONTROL_PHASE7.md"), encoding="utf-8").read()
    for word in ("bench", "hardware", "Stage Rack", "open"):
        assert word in phase7, word
