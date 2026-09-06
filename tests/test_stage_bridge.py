"""Stage Control phase 5: the Stage Bridge, end to end on the simulator.

The wire format is the product: a signed body with a nonce and an expiry,
verified on the device, settled once on the server. These tests drive the
in-process bridge exactly the way a remote one would be driven, so the
acceptance criteria the brief lists - replays rejected, expired rejected,
revocation, lockout, no false success on a lost link - are each one test.
"""
from datetime import datetime, timedelta, timezone
import json
import uuid

import pytest

import advance_store as adv
import db as store
import passport_store as ps
import stage_adapters as sa
import stage_bridge as sb
import stage_safety as ss
import stage_store as st

USER = "bridge-tests"


@pytest.fixture(scope="module", autouse=True)
def schema():
    store.init_db()
    ps.init_passports()
    adv.init_advance()
    st.init_stage()
    sb.init_bridge()


@pytest.fixture
def show():
    """A show advanced against a published passport with one mix and two
    sources, and a registered, armed, heartbeating simulator device."""
    sid = "show-" + uuid.uuid4().hex[:10]
    pid = ps.create_passport(USER, artist_name="Prayers")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("inputs", pid, channel="2", source="Kick", sort=2)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
    ps.publish(pid, USER)
    adv.attach(sid, USER, pid)
    dev, token = sb.register(USER, sid, "Rack A")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    return {"id": sid, "device": sb.get_device(dev["id"]), "token": token}


def _approved(show, kind="more", step=2, source="Lead Vox"):
    rid = st.submit(show_id=show["id"], user_id=USER, performer="Leafar", mix="Mix 1",
                    kind=kind, source=source, step_db=step,
                    allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox", "Kick"])
    st.approve(rid, USER, actor="eng")
    return rid


# --- registration and credentials ----------------------------------------------

def test_the_token_is_shown_once_and_stored_only_as_a_hash(show):
    dev, token = show["device"], show["token"]
    assert token not in json.dumps(dev)
    assert sb.authenticate(token)["id"] == dev["id"]
    assert sb.authenticate("not-the-token") is None
    assert sb.authenticate("") is None


def test_rotating_changes_both_secrets_and_expires_what_was_queued(show):
    dev, old_token = show["device"], show["token"]
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    assert cmd["state"] == "queued"
    new_dev, new_token = sb.rotate(dev["id"], USER, actor="eng")
    assert new_token != old_token
    assert new_dev["signing_key"] != dev["signing_key"]
    assert sb.authenticate(old_token) is None and sb.authenticate(new_token)["id"] == dev["id"]
    assert sb.get_command(cmd["id"])["state"] == "expired"
    assert st.get(rid, USER)["state"] == "expired"


def test_revocation_is_immediate_and_final(show):
    dev = show["device"]
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.revoke(dev["id"], USER, actor="eng")
    assert sb.authenticate(show["token"]) is None
    assert sb.device_for_show(show["id"], USER) is None
    assert sb.mode(show["id"], USER)["code"] == "no_device"
    assert sb.get_command(cmd["id"])["state"] == "rejected"
    assert st.get(rid, USER)["state"] == "failed"
    assert sb.arm(dev["id"], USER) is None, "a revoked device cannot be armed again"
    assert sb.rotate(dev["id"], USER) == (None, None)


def test_the_mode_is_computed_never_flagged(show):
    dev = show["device"]
    assert sb.mode(show["id"], USER)["mode"] == "connected"
    sb.disarm(dev["id"], USER, actor="eng")
    m = sb.mode(show["id"], USER)
    assert m["mode"] == "request" and m["code"] == "disarmed"
    sb.arm(dev["id"], USER)
    stale = (datetime.now(timezone.utc) + timedelta(seconds=60))
    assert sb.mode(show["id"], USER, now=stale)["code"] == "device_stale"
    assert sb.mode(show["id"], USER)["simulated"] is True


# --- issuing ------------------------------------------------------------------------

def test_an_approved_request_becomes_a_signed_command(show):
    rid = _approved(show)
    cmd, decision = sb.issue(rid, USER, actor="eng")
    assert decision.allowed and cmd["state"] == "queued"
    assert st.get(rid, USER)["state"] == "queued_for_device"
    assert st.get(rid, USER)["command_id"] == cmd["id"]
    body = sb.wire(cmd)
    assert sb.verify_signature(body, show["device"]["signing_key"], body["signature"])
    assert body["command"] == "send_level_delta" and body["step_db"] == 2
    assert body["expires"] > body["issued"]


def test_a_tampered_body_does_not_verify(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    body = sb.wire(cmd)
    body["step_db"] = 12
    assert not sb.verify_signature(body, show["device"]["signing_key"], body["signature"])
    assert not sb.verify_signature(sb.wire(cmd), "not-the-key", cmd["signature"])


def test_a_refusal_is_audited_with_its_code(show):
    rid = _approved(show, kind="feedback", step=0)
    cmd, decision = sb.issue(rid, USER, actor="eng")
    assert cmd is None and decision.code == "not_a_command"
    def _payload(e):
        return e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"] or "{}")
    kinds = [(e["kind"], _payload(e).get("code")) for e in st.events_since(show["id"])]
    assert ("safety.refused", "not_a_command") in kinds
    assert st.get(rid, USER)["state"] == "approved", "a refused request is untouched"


def test_less_is_a_negative_delta(show):
    rid = _approved(show, kind="less", step=3)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    assert cmd["step_db"] == -3


def test_nonces_never_repeat(show):
    seen = set()
    for _ in range(3):
        cmd, _ = sb.issue(_approved(show), USER, actor="eng")
        seen.add(cmd["nonce"])
    assert len(seen) == 3


# --- the device side --------------------------------------------------------------

def test_pulling_marks_sent_and_hands_over_only_the_signed_body(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    handed = sb.pull(show["device"])
    assert [h["id"] for h in handed] == [cmd["id"]]
    assert set(handed[0]) == set(sb.BODY_FIELDS) | {"signature"}
    assert "signing_key" not in handed[0]
    assert sb.get_command(cmd["id"])["state"] == "sent"
    assert st.get(rid, USER)["state"] == "sent"
    assert sb.pull(show["device"]) == [], "a second pull hands over nothing"


def test_an_expired_command_is_never_handed_over(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert sb.pull(show["device"], now=later) == []
    assert sb.get_command(cmd["id"])["state"] == "expired"
    assert st.get(rid, USER)["state"] == "expired"


def test_the_device_verifies_what_a_bridge_must(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    cmd = sb.get_command(cmd["id"])
    assert sb.verify_for_device(cmd, show["device"]).allowed
    other = dict(show["device"], id="someone-else")
    assert sb.verify_for_device(cmd, other).code == "wrong_device"
    forged = dict(cmd, step_db=9)
    assert sb.verify_for_device(forged, show["device"]).code == "bad_signature"
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert sb.verify_for_device(cmd, show["device"], now=later).code == "expired"


# --- acknowledgement: what `applied` means ----------------------------------------

def test_a_confirmed_acknowledgement_reaches_applied(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    _c, d = sb.acknowledge(show["device"], cmd["id"], cmd["nonce"],
                           {"ok": True, "before": -20.0, "after": -18.0, "confirmed": True})
    assert d.code == "applied"
    req = st.get(rid, USER)
    assert req["state"] == "applied"
    assert json.loads(req["device_ack"])["after"] == -18.0
    assert sb.get_command(cmd["id"])["state"] == "applied"


def test_an_unconfirmed_acknowledgement_never_reads_as_done(show):
    """The console answered but could not read the value back. The
    performer sees 'console answered', never 'done'."""
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    _c, d = sb.acknowledge(show["device"], cmd["id"], cmd["nonce"], {"ok": True, "confirmed": False})
    assert d.code == "unconfirmed"
    assert st.get(rid, USER)["state"] == "device_acknowledged"
    assert st.PERFORMER_WORDING["device_acknowledged"] != "Done"
    kinds = [e["kind"] for e in st.events_since(show["id"])]
    assert "command.unconfirmed" in kinds


def test_a_failure_is_a_failure(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    _c, d = sb.acknowledge(show["device"], cmd["id"], cmd["nonce"],
                           {"ok": False, "failure": "Channel is locked on the desk."})
    assert d.code == "failed"
    req = st.get(rid, USER)
    assert req["state"] == "failed" and "locked on the desk" in req["failure"]


def test_a_replayed_acknowledgement_is_refused(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    sb.acknowledge(show["device"], cmd["id"], cmd["nonce"], {"ok": True, "confirmed": True})
    _c, again = sb.acknowledge(show["device"], cmd["id"], cmd["nonce"], {"ok": False, "failure": "x"})
    assert again.code == "replayed"
    assert st.get(rid, USER)["state"] == "applied", "the replay changed nothing"
    _c, wrong = sb.acknowledge(show["device"], cmd["id"], "not-the-nonce", {"ok": True})
    assert wrong.code == "unknown_command"


def test_a_late_acknowledgement_settles_as_expired_not_applied(show):
    """Internet loss must not report a change that may never have happened.
    An acknowledgement arriving after the command's expiry is recorded, but
    the request is expired, not applied."""
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    _c, d = sb.acknowledge(show["device"], cmd["id"], cmd["nonce"],
                           {"ok": True, "confirmed": True}, now=later)
    assert d.code == "expired"
    assert st.get(rid, USER)["state"] == "expired"


def test_reconcile_applies_each_entry_once(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    entry = {"command_id": cmd["id"], "nonce": cmd["nonce"],
             "result": {"ok": True, "confirmed": True}}
    first = sb.reconcile(show["device"], [entry, entry, {"command_id": "nope", "nonce": "n"}])
    assert [o["code"] for o in first] == ["applied", "replayed", "unknown_command"]
    assert st.get(rid, USER)["state"] == "applied"


# --- lockout ------------------------------------------------------------------------------

def test_emergency_lockout_stops_everything_in_flight(show):
    dev = show["device"]
    queued = _approved(show)
    sb.issue(queued, USER, actor="eng")
    sent = _approved(show)
    cmd_sent, _ = sb.issue(sent, USER, actor="eng")
    sb.pull(dev)
    sb.lockout(dev["id"], USER, actor="eng", reason="Feedback on stage")
    assert st.get(queued, USER)["state"] == "failed"
    assert st.get(sent, USER)["state"] == "failed"
    assert sb.get_command(cmd_sent["id"])["state"] == "rejected"
    m = sb.mode(show["id"], USER)
    assert m["mode"] == "request" and m["code"] == "lockout"
    # A late acknowledgement for the rejected command changes nothing.
    _c, d = sb.acknowledge(dev, cmd_sent["id"], cmd_sent["nonce"], {"ok": True, "confirmed": True})
    assert d.code == "replayed" and st.get(sent, USER)["state"] == "failed"
    # Releasing the lockout does not re-arm.
    sb.release_lockout(dev["id"], USER, actor="eng")
    assert sb.mode(show["id"], USER)["code"] == "disarmed"
    assert sb.arm(dev["id"], USER)["armed"] == 1


def test_nothing_can_be_issued_during_lockout(show):
    sb.lockout(show["device"]["id"], USER, actor="eng")
    cmd, d = sb.issue(_approved(show), USER, actor="eng")
    assert cmd is None and d.code == "lockout"


# --- the in-process bridge -------------------------------------------------------------------

def test_run_local_drives_the_simulator_to_applied_and_back(show):
    dev = show["device"]
    rid = _approved(show, step=2)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    out = sb.run_local(dev["id"], USER)
    assert out["outcomes"] == [{"command_id": cmd["id"], "code": "applied"}]
    assert st.get(rid, USER)["state"] == "applied"
    sim = sa.instance_for(dev["id"], "simulator")
    assert sim.read_send_level("Mix 1", "Lead Vox") == -18.0
    # Revert: the inverse delta, and the original request reads reverted.
    rcmd, d = sb.issue(rid, USER, actor="eng", is_revert=True)
    assert d.allowed and rcmd["revert_of"] == cmd["id"] and rcmd["step_db"] == -2
    sb.run_local(dev["id"], USER)
    assert st.get(rid, USER)["state"] == "reverted"
    assert sim.read_send_level("Mix 1", "Lead Vox") == -20.0


def test_run_local_reports_a_console_refusal_as_failed(show):
    dev = show["device"]
    sim = sa.instance_for(dev["id"], "simulator")
    sim.fail_next = "DCA is locked."
    rid = _approved(show)
    sb.issue(rid, USER, actor="eng")
    out = sb.run_local(dev["id"], USER)
    assert out["outcomes"][0]["code"] == "failed"
    assert "DCA is locked" in st.get(rid, USER)["failure"]


def test_run_local_refuses_to_drive_anything_but_the_simulator(show, monkeypatch):
    class Real(sa.SimulatorAdapter):
        SPEC = dict(sa.SimulatorAdapter.SPEC, key="real", simulated=False,
                    tested_model="a real desk")
    monkeypatch.setitem(sa.ADAPTERS, "real", Real)
    dev, _t = sb.register(USER, show["id"], "Real rack", adapter_key="real")
    assert "real bridge" in sb.run_local(dev["id"], USER)["error"]


def test_a_stale_sent_command_is_expired_by_the_desk_poll(show):
    rid = _approved(show)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.pull(show["device"])
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert sb.expire_stale(show["id"], USER, now=later) == 1
    assert st.get(rid, USER)["state"] == "expired"
    assert sb.expire_stale(show["id"], USER, now=later) == 0


def test_rate_limits_count_only_what_was_issued(show):
    for _ in range(3):
        sb.issue(_approved(show, step=1), USER, actor="eng")
    counts = sb.recent_counts(show["id"], "Leafar", "Mix 1", "Lead Vox")
    assert counts == {"performer": 3, "mix": 3, "source": 3}
    assert sb.recent_counts(show["id"], "Javon", "Mix 2", "Kick") == {"performer": 0, "mix": 0, "source": 0}
