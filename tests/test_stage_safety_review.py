"""Stage Control phase 7: the live-audio safety review, as tests.

The console the owner tours with has no authentication and no per-user
limits (phase 1 audit), so every bound is ours and a bug in one layer has
nothing downstream to catch it. The review therefore asks for THREE layers
on the one thing that can hurt somebody - a level change - and for each of
the brief's protections to hold at the layer where it lives.

Two gaps were found while writing this and fixed in the same commit:

  * the adapters had no bound of their own - a delta that reached
    SimulatorAdapter.apply_send_delta or X32Adapter.apply_send_delta was
    applied whatever its size, so the store and the safety engine were the
    only two layers. ConsoleAdapter.bound_step is the third.
  * a revert used the REQUESTED step, not the read-back. A +3 clamped at the
    top of the fader to +1 was reverted by -3, landing 2 dB under where it
    started - a jump. issue(is_revert=True) now restores the acknowledged
    `before`, computed from the desk's own before/after.
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
import stage_rack as rack
import stage_safety as ss
import stage_store as st
import stage_x32 as x32

USER = "safety-review"


@pytest.fixture(scope="module", autouse=True)
def schema():
    store.init_db()
    ps.init_passports()
    adv.init_advance()
    st.init_stage()
    sb.init_bridge()


@pytest.fixture
def show():
    sid = "show-" + uuid.uuid4().hex[:10]
    pid = ps.create_passport(USER, artist_name="Prayers")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
    ps.publish(pid, USER)
    adv.attach(sid, USER, pid)
    dev, token = sb.register(USER, sid, "Rack A")
    sb.arm(dev["id"], USER)
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    return {"id": sid, "device": sb.get_device(dev["id"]), "token": token,
            "sim": sa.instance_for(dev["id"], "simulator")}


def _approved(show, kind="more", step=2):
    rid = st.submit(show["id"], USER, "Leafar", "Mix 1", kind, source="Lead Vox", step_db=step,
                    allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
    st.approve(rid, USER, actor="eng")
    return rid


def _req(**over):
    r = {"id": "r", "show_id": "s", "user_id": USER, "performer": "Leafar", "mix": "Mix 1",
         "source": "Lead Vox", "kind": "more", "step_db": 2, "approved_step_db": None,
         "state": "approved", "command_id": ""}
    r.update(over)
    return r


# --- three layers on a level change -----------------------------------------------

@pytest.mark.parametrize("step", [4, 6, 12, -4, 99, 0])
def test_a_step_is_bounded_at_the_store_the_safety_engine_and_the_adapter(show, step):
    # Layer 1: the request vocabulary.
    with pytest.raises(st.Refused):
        st.submit(show["id"], USER, "Leafar", "Mix 1", "more", source="Lead Vox", step_db=step,
                  allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
    # Layer 2: the safety engine, on the requested and on the engineer's amount.
    dev = show["device"]
    for req in (_req(show_id=show["id"], step_db=step), _req(show_id=show["id"], step_db=1, approved_step_db=step)):
        d = ss.evaluate(show["id"], req, dev, ["Mix 1"], ["Lead Vox"], {}, USER)
        assert d.code == "delta_out_of_bounds", (step, d.code)
    # Layer 3: the adapter itself, even if both above were bypassed.
    if step != 0:
        sim = sa.SimulatorAdapter()
        with pytest.raises(sa.AdapterError):
            sim.apply_send_delta("Mix 1", "Lead Vox", step)
        assert sim.read_send_level("Mix 1", "Lead Vox") == sim.DEFAULT_LEVEL_DB and sim.writes == 0


def test_the_x32_adapter_refuses_an_oversized_step_before_touching_the_desk():
    from tests.test_stage_x32 import FakeDesk, PATCH
    desk = FakeDesk()
    a = x32.X32Adapter(transport=desk, patch=PATCH)
    with pytest.raises(sa.AdapterError):
        a.apply_send_delta("Mix 1", "Lead Vox", 4)
    assert desk.sent == [], "nothing was written"
    for cls in (sa.SimulatorAdapter, x32.X32Adapter):
        assert cls.spec()["limits"]["max_step_db"] <= max(st.STEPS_DB)
        with pytest.raises(sa.AdapterError):
            cls.bound_step("nine")


def test_a_level_can_never_jump_even_with_a_tampered_row(show):
    """The store row is edited behind the vocabulary's back; the engine
    refuses. A signed command is forged with a big step; the adapter
    refuses and the level does not move."""
    rid = _approved(show, step=2)
    with store.get_db() as db:
        db.execute("UPDATE stage_requests SET step_db = 9 WHERE id = ?", (rid,))
    cmd, d = sb.issue(rid, USER, actor="eng")
    assert cmd is None and d.code == "delta_out_of_bounds"
    with store.get_db() as db:
        db.execute("UPDATE stage_requests SET step_db = 2 WHERE id = ?", (rid,))
    cmd, d = sb.issue(rid, USER, actor="eng")
    assert d.allowed
    dev = show["device"]
    with store.get_db() as db:
        db.execute("UPDATE stage_commands SET step_db = 9, signature = ? WHERE id = ?",
                   (sb.sign(dict(cmd, step_db=9), dev["signing_key"]), cmd["id"]))
    before = show["sim"].read_send_level("Mix 1", "Lead Vox")
    out = sb.run_local(dev["id"], USER)
    assert out["outcomes"][0]["code"] == "failed"
    assert show["sim"].read_send_level("Mix 1", "Lead Vox") == before
    assert "at most 3" in st.get(rid, USER)["failure"]


# --- mutes ----------------------------------------------------------------------------

def test_mutes_and_unmutes_only_where_the_vocabulary_allows(show, monkeypatch):
    assert sa.COMMAND_FOR_KIND["mute"] == sa.COMMAND_FOR_KIND["unmute"] == "mute_state"
    for report in st.REPORTS:
        assert report not in sa.COMMAND_FOR_KIND
    rid = _approved(show, kind="mute", step=0)
    cmd, d = sb.issue(rid, USER, actor="eng")
    assert d.allowed and cmd["command"] == "mute_state" and cmd["muted"] == 1 and cmd["step_db"] == 0
    assert cmd["source"] == "Lead Vox", "a mute names its source; the X32 addresses it by channel"

    class NoMute(sa.SimulatorAdapter):
        SPEC = dict(sa.SimulatorAdapter.SPEC, key="nomute",
                    commands=("send_level_delta", "read_send_level", "read_health"))
    monkeypatch.setitem(sa.ADAPTERS, "nomute", NoMute)
    d = ss.evaluate(show["id"], _req(show_id=show["id"], kind="unmute", step_db=0),
                    dict(show["device"], adapter_key="nomute"), ["Mix 1"], ["Lead Vox"], {}, USER)
    assert d.code == "unsupported"
    # A mute is never a level: the adapter's mute path carries no dB at all.
    sim = sa.SimulatorAdapter()
    out = sim.set_mute("Mix 1", "Lead Vox", True)
    assert out["after"] is True and sim.read_send_level("Mix 1", "Lead Vox") == sim.DEFAULT_LEVEL_DB


# --- revert restores the read-back --------------------------------------------------------

def test_a_revert_restores_the_read_back_value_not_the_requested_step(show):
    """+3 asked at 9.0 dB clamps to 10.0; the desk read back +1. The revert
    is -1, back to 9.0 - not -3, which would land at 7.0 and be a jump."""
    sim, dev = show["sim"], show["device"]
    sim.levels[sim._key("Mix 1", "Lead Vox")] = 9.0
    rid = _approved(show, step=3)
    cmd, _ = sb.issue(rid, USER, actor="eng")
    sb.run_local(dev["id"], USER)
    req = st.get(rid, USER)
    ack = json.loads(req["device_ack"])
    assert req["state"] == "applied" and ack["before"] == 9.0 and ack["after"] == 10.0
    rcmd, d = sb.issue(rid, USER, actor="eng", is_revert=True)
    assert d.allowed and rcmd["step_db"] == -1 and rcmd["revert_of"] == cmd["id"]
    sb.run_local(dev["id"], USER)
    assert st.get(rid, USER)["state"] == "reverted"
    assert sim.read_send_level("Mix 1", "Lead Vox") == 9.0


def test_a_revert_of_a_mute_restores_the_read_back_state(show):
    sim, dev = show["sim"], show["device"]
    sim.mutes[sim._key("Mix 1", "Lead Vox")] = True
    rid = _approved(show, kind="unmute", step=0)
    sb.issue(rid, USER, actor="eng")
    sb.run_local(dev["id"], USER)
    assert st.get(rid, USER)["state"] == "applied" and sim.read_mute("Mix 1", "Lead Vox") is False
    rcmd, d = sb.issue(rid, USER, actor="eng", is_revert=True)
    assert d.allowed and rcmd["muted"] == 1
    sb.run_local(dev["id"], USER)
    assert sim.read_mute("Mix 1", "Lead Vox") is True
    assert st.get(rid, USER)["state"] == "reverted"


def test_a_revert_without_read_back_numbers_falls_back_to_the_inverse_step():
    step, muted = sb._revert_target({"device_ack": '{"ok": true, "confirmed": true}'}, 2, None)
    assert (step, muted) == (-2, None)
    step, muted = sb._revert_target({"device_ack": "not json"}, -3, None)
    assert (step, muted) == (3, None)
    step, muted = sb._revert_target({"device_ack": '{"before": -20.0, "after": -18.0}'}, 2, None)
    assert (step, muted) == (-2, None)
    step, muted = sb._revert_target({"device_ack": '{"before": -20.0, "after": -20.0}'}, 2, None)
    assert (step, muted) == (-2, None), "a change the desk did not register reverts by the step"
    assert sb._revert_target({"device_ack": '{"before": -20.0, "after": 5.0}'}, 3, None)[0] == -3, \
        "the measured change can never exceed the bounded step"


def test_a_revert_needs_an_applied_change_and_an_adapter_that_can_revert(show):
    """Deeper: tests/test_stage_safety.py."""
    rid = _approved(show)
    assert sb.issue(rid, USER, actor="eng", is_revert=True)[1].code == "not_applied"


# --- lockout ------------------------------------------------------------------------------------

def test_lockout_refuses_in_flight_commands_and_releasing_does_not_re_arm(show):
    """Deeper: tests/test_stage_bridge.py::test_emergency_lockout_stops_everything_in_flight."""
    dev, sim = show["device"], show["sim"]
    a = _approved(show); sb.issue(a, USER, actor="eng")
    b = _approved(show); sb.issue(b, USER, actor="eng"); sb.pull(sb.get_device(dev["id"]))
    sb.lockout(dev["id"], USER, actor="eng", reason="Feedback")
    out = sb.run_local(dev["id"], USER)
    assert out["outcomes"] == [] and sim.writes == 0
    assert st.get(a, USER)["state"] == st.get(b, USER)["state"] == "failed"
    assert sb.issue(_approved(show), USER, actor="eng")[1].code == "lockout"
    sb.release_lockout(dev["id"], USER, actor="eng")
    d = sb.get_device(dev["id"])
    assert d["lockout"] == 0 and d["armed"] == 0
    assert sb.mode(show["id"], USER)["code"] == "disarmed"
    assert rack.status(show["id"], USER)["lamps"] == ["disarmed"]


# --- stale means Request Mode -----------------------------------------------------------------

def test_stale_is_defined_once_and_falls_the_show_back_to_request_mode(show):
    pol = ss.policy(show["id"])
    stale, offline = pol["heartbeat_stale_s"], ss.offline_after_s(pol)
    assert offline > stale
    # Heartbeats are stored to the second, so the boundaries are tested a
    # second either side rather than on the line.
    now = datetime.now(timezone.utc)
    for age, state, code in ((0, "online", "ok"), (stale - 1, "online", "ok"),
                             (stale + 2, "stale", "device_stale"),
                             (offline - 1, "stale", "device_stale"),
                             (offline + 2, "offline", "device_stale")):
        at = now + timedelta(seconds=age)
        assert ss.heartbeat_state(show["device"]["last_heartbeat"], pol, at) == state, age
        m = sb.mode(show["id"], USER, now=at)
        assert m["code"] == code and m["mode"] == ("connected" if code == "ok" else "request"), age
        r = rack.status(show["id"], USER, now=at)
        assert r["network"]["state"] == state and r["mode"]["mode"] == m["mode"], age
        assert ("stale" in r["lamps"]) == (state == "stale") and ("offline" in r["lamps"]) == (state == "offline")
        req = _req(show_id=show["id"])
        d = ss.evaluate(show["id"], req, show["device"], ["Mix 1"], ["Lead Vox"], {}, USER, pol=pol, now=at)
        assert d.code == code, age
    # Tightening the policy moves both thresholds together.
    ss.set_policy(show["id"], USER, heartbeat_stale_s=5)
    tight = ss.policy(show["id"])
    assert ss.heartbeat_state(show["device"]["last_heartbeat"], tight, now + timedelta(seconds=6)) == "stale"
    assert ss.offline_after_s(tight) == ss.OFFLINE_FLOOR_S
    assert rack.status(show["id"], USER, now=now + timedelta(seconds=6))["network"]["state"] == "stale"


def test_before_any_heartbeat_the_rack_says_not_measured_and_the_engine_refuses():
    sid = "show-" + uuid.uuid4().hex[:10]
    dev, _t = sb.register(USER, sid, "Quiet")
    sb.arm(dev["id"], USER)
    assert ss.heartbeat_state(sb.get_device(dev["id"])["last_heartbeat"]) is None
    assert sb.mode(sid, USER)["code"] == "device_stale"
    r = rack.status(sid, USER)
    assert r["network"]["label"] == rack.NOT_MEASURED and r["network"]["state"] is None
    assert "offline" not in r["lamps"] and "stale" not in r["lamps"]
