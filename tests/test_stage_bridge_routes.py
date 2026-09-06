"""Stage Control phases 5-6: the bridge page, the desk in Connected Control,
and the device's own door.

The store is tested in test_stage_bridge.py. This is about the rooms: the
mode banner is computed, the send button exists only when the mode says so,
a refusal is shown in words, and a device without a token gets nothing.
"""
import json
import uuid

import pytest

import advance_store as adv
import app as appmod
import passport_store as ps
import stage_bridge as sb
import stage_store as st

PASSWORD = "bridge-rooms-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def show(application):
    email = "br-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Bridge Tester", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        import db as store
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
    return {"client": client, "user": user, "show": sid}


def _ask(show, kind="more", step="2"):
    show["client"].post("/stage/%s/ask" % show["show"], data={
        "performer": "Leafar", "mix": "Mix 1", "kind": kind, "source": "Lead Vox", "step_db": step})
    with_ctx = st.for_show(show["show"], show["user"]["id"], open_only=True)
    return with_ctx[0]["id"]


def _register_and_arm(show):
    c = show["client"]
    r = c.post("/stage/%s/bridge/register" % show["show"], data={"name": "Rack A", "adapter": "simulator"})
    token = r.headers["Location"].split("token=")[1]
    c.post("/stage/%s/bridge/arm" % show["show"])
    c.post("/stage/%s/bridge/heartbeat" % show["show"])
    return token


# --- the page ------------------------------------------------------------------

def test_a_show_without_a_device_says_request_mode_and_offers_registration(show):
    body = show["client"].get("/stage/%s/bridge" % show["show"]).get_data(as_text=True)
    assert 'data-mode="request"' in body and "No Stage Bridge yet" in body
    assert "simulated" in body.lower()
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert 'data-mode="request"' in desk and "Send to the console" not in desk


def test_registering_shows_the_token_once(show):
    r = show["client"].post("/stage/%s/bridge/register" % show["show"],
                            data={"name": "Rack A", "adapter": "simulator"})
    assert r.status_code in (302, 303) and "token=" in r.headers["Location"]
    once = show["client"].get(r.headers["Location"]).get_data(as_text=True)
    assert "shown once" in once
    again = show["client"].get("/stage/%s/bridge" % show["show"]).get_data(as_text=True)
    assert "shown once" not in again
    assert "Rack A" in again and "Disarmed" in again


def test_a_second_registration_is_refused_while_one_stands(show):
    _register_and_arm(show)
    r = show["client"].post("/stage/%s/bridge/register" % show["show"], data={"name": "Rack B"})
    assert "Revoke" in r.headers["Location"]


def test_an_unknown_adapter_cannot_be_registered(show):
    r = show["client"].post("/stage/%s/bridge/register" % show["show"],
                            data={"name": "X", "adapter": "x32"})
    assert "unknown" in r.headers["Location"]


def test_arming_and_a_heartbeat_switch_the_desk_to_connected_control(show):
    _register_and_arm(show)
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert 'data-mode="connected"' in desk and "SIMULATED" in desk
    poll = show["client"].get("/stage/%s/events?since=0" % show["show"]).get_json()
    assert poll["mode"]["mode"] == "connected" and poll["mode"]["simulated"] is True


def test_the_send_button_appears_only_on_an_approved_request(show):
    _register_and_arm(show)
    rid = _ask(show)
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Send to the console" not in desk and "Approve for the console" in desk
    show["client"].post("/stage/%s/request/%s/approve" % (show["show"], rid))
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Send to the console" in desk


def test_sending_drives_the_simulator_to_applied(show):
    _register_and_arm(show)
    rid = _ask(show)
    show["client"].post("/stage/%s/request/%s/approve" % (show["show"], rid))
    r = show["client"].post("/stage/%s/request/%s/send" % (show["show"], rid))
    assert "refused" not in r.headers["Location"]
    with show["client"].application.app_context():
        req = st.get(rid, show["user"]["id"])
    assert req["state"] == "applied"
    assert json.loads(req["device_ack"])["confirmed"] is True
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Revert on the console" in desk
    show["client"].post("/stage/%s/request/%s/revert" % (show["show"], rid))
    with show["client"].application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "reverted"


def test_a_refusal_is_shown_in_words(show):
    _register_and_arm(show)
    rid = _ask(show)
    r = show["client"].post("/stage/%s/request/%s/send" % (show["show"], rid))
    assert "refused=" in r.headers["Location"]
    body = show["client"].get(r.headers["Location"]).get_data(as_text=True)
    assert "Only an approved request" in body


def test_lockout_from_the_page_ends_connected_control(show):
    _register_and_arm(show)
    show["client"].post("/stage/%s/bridge/lockout" % show["show"], data={"reason": "Feedback"})
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert 'data-mode="request"' in desk and "lockout" in desk.lower()
    page = show["client"].get("/stage/%s/bridge" % show["show"]).get_data(as_text=True)
    assert "Release lockout" in page and "Feedback" in page
    r = show["client"].post("/stage/%s/bridge/arm" % show["show"])
    assert "Release" in r.headers["Location"], "arming during lockout is refused"


def test_the_policy_form_only_tightens(show):
    c = show["client"]
    c.post("/stage/%s/bridge/policy" % show["show"], data={"max_step_db": "2", "per_mix_per_min": "4"})
    page = c.get("/stage/%s/bridge" % show["show"]).get_data(as_text=True)
    assert 'name="max_step_db" value="2"' in page and 'name="per_mix_per_min" value="4"' in page
    r = c.post("/stage/%s/bridge/policy" % show["show"], data={"max_step_db": "9"})
    assert "Out+of+bounds" in r.headers["Location"]


def test_the_simulator_switches_rehearse_failure(show):
    _register_and_arm(show)
    c = show["client"]
    c.post("/stage/%s/bridge/simulate" % show["show"], data={"what": "fail_next"})
    rid = _ask(show)
    c.post("/stage/%s/request/%s/approve" % (show["show"], rid))
    c.post("/stage/%s/request/%s/send" % (show["show"], rid))
    with c.application.app_context():
        req = st.get(rid, show["user"]["id"])
    assert req["state"] == "failed" and "Simulated" in req["failure"]
    c.post("/stage/%s/bridge/simulate" % show["show"], data={"what": "offline"})
    assert 'data-mode="request"' in c.get("/stage/%s" % show["show"]).get_data(as_text=True)


def test_a_stranger_cannot_see_or_work_the_bridge(show, application):
    other = application.test_client()
    r = other.get("/stage/%s/bridge" % show["show"])
    assert r.status_code in (302, 401)


# --- the device's door -----------------------------------------------------------

def test_the_device_endpoints_need_a_token(show, application):
    anon = application.test_client()
    for path in ("/bridge/heartbeat", "/bridge/pull", "/bridge/ack", "/bridge/reconcile"):
        r = anon.post(path, json={})
        assert r.status_code == 401, path
        r = anon.post(path, json={}, headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401, path


def test_a_real_bridge_could_drive_the_whole_path_over_http(show, application):
    """What a Stage Bridge on a venue network does: heartbeat, pull, apply,
    ack - with only its token. The same door reconcile uses after an
    outage."""
    token = _register_and_arm(show)
    dev = application.test_client()
    auth = {"Authorization": "Bearer " + token}
    hb = dev.post("/bridge/heartbeat", json={"health": {"ok": True}, "software_version": "bridge-0.1"},
                  headers=auth).get_json()
    assert hb["ok"] and hb["armed"] is True
    rid = _ask(show)
    show["client"].post("/stage/%s/request/%s/approve" % (show["show"], rid))
    with application.app_context():
        cmd, decision = sb.issue(rid, show["user"]["id"], actor="eng")
    assert decision.allowed
    pulled = dev.post("/bridge/pull", json={}, headers=auth).get_json()
    assert [c["id"] for c in pulled["commands"]] == [cmd["id"]]
    assert "signature" in pulled["commands"][0] and "signing_key" not in pulled["commands"][0]
    ack = dev.post("/bridge/ack", json={"command_id": cmd["id"], "nonce": cmd["nonce"],
                                        "result": {"ok": True, "before": -20, "after": -18, "confirmed": True}},
                   headers=auth).get_json()
    assert ack["code"] == "applied"
    with application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "applied"
    again = dev.post("/bridge/reconcile", json={"entries": [
        {"command_id": cmd["id"], "nonce": cmd["nonce"], "result": {"ok": True, "confirmed": True}}]},
        headers=auth).get_json()
    assert again["outcomes"][0]["code"] == "replayed"
    # Revoke, and the same token is nobody.
    show["client"].post("/stage/%s/bridge/revoke" % show["show"])
    assert dev.post("/bridge/heartbeat", json={}, headers=auth).status_code == 401
