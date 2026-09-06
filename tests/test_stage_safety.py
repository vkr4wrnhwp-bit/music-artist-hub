"""Stage Control phase 6: the safety engine.

Every bound here is the only bound - the console the owner tours with has no
authentication and no per-user limits, so nothing downstream catches a
mistake in this module. Each check is therefore tested on its own, with the
code the desk will show, in the order the engine applies them.
"""
from datetime import datetime, timedelta, timezone
import uuid

import pytest

import db as store
import stage_adapters as sa
import stage_safety as ss
import stage_store as st

USER = "safety-tests"
NOW = datetime(2030, 5, 2, 21, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def schema():
    store.init_db()
    st.init_stage()
    ss.init_policies()


def _device(**over):
    d = {"id": "dev-1", "user_id": USER, "show_id": "show-1", "adapter_key": "simulator",
         "armed": 1, "lockout": 0, "revoked_at": "", "health": '{"ok": true}',
         "last_heartbeat": (NOW - timedelta(seconds=3)).isoformat(timespec="seconds")}
    d.update(over)
    return d


def _req(**over):
    r = {"id": "req-1", "show_id": "show-1", "user_id": USER, "performer": "Leafar",
         "mix": "Mix 1", "source": "Lead Vox", "kind": "more", "step_db": 2,
         "approved_step_db": None, "state": "approved", "command_id": ""}
    r.update(over)
    return r


_DEFAULT = object()


def _eval(req=None, device=_DEFAULT, recent=None, show="show-1", user=USER, **kw):
    return ss.evaluate(show, req or _req(), _device() if device is _DEFAULT else device,
                       ["Mix 1", "Mix 2"], ["Lead Vox", "Kick"], recent or {}, user,
                       pol=dict(ss.POLICY_DEFAULTS), now=NOW, **kw)


# --- the device gate, in order -------------------------------------------------

def test_an_approved_request_on_a_ready_device_is_allowed():
    d = _eval()
    assert d.allowed and d.code == "ok"


@pytest.mark.parametrize("device, code", [
    (None, "no_device"),
    (_device(revoked_at="2030-05-02T20:00:00+00:00"), "device_revoked"),
    (_device(lockout=1), "lockout"),
    (_device(armed=0), "disarmed"),
    (_device(last_heartbeat=(NOW - timedelta(seconds=40)).isoformat(timespec="seconds")), "device_stale"),
    (_device(last_heartbeat=""), "device_stale"),
    (_device(health='{"ok": false, "detail": "Console link down"}'), "adapter_unhealthy"),
])
def test_the_device_must_be_present_armed_fresh_and_healthy(device, code):
    d = _eval(device=device)
    assert not d.allowed and d.code == code, (d.code, d.reason)


def test_the_broadest_refusal_wins():
    """Revoked AND locked out AND disarmed reads as revoked: the engineer is
    told the thing that needs fixing first."""
    d = _eval(device=_device(revoked_at="x", lockout=1, armed=0))
    assert d.code == "device_revoked"


# --- authorisation and locks -----------------------------------------------------

def test_only_the_owning_account_may_send():
    assert _eval(user="somebody-else").code == "not_authorised"
    assert _eval(req=_req(user_id="somebody-else")).code == "not_authorised"


def test_a_request_from_another_show_is_refused():
    assert _eval(req=_req(show_id="show-2")).code == "wrong_show"


def test_a_locked_mix_or_performer_or_show_refuses():
    show = "lock-" + uuid.uuid4().hex[:8]
    dev = _device(show_id=show)
    st.lock(show, "mix", target="Mix 1", reason="Wedge at the feedback point")
    d = _eval(req=_req(show_id=show), device=dev, show=show)
    assert d.code == "locked" and "feedback point" in d.reason
    st.unlock(show, "mix", target="Mix 1")
    st.lock(show, "show", reason="Doors are open.")
    assert _eval(req=_req(show_id=show), device=dev, show=show).code == "locked"


# --- what may become a command ------------------------------------------------------

def test_a_report_is_never_a_command():
    assert _eval(req=_req(kind="feedback")).code == "not_a_command"


def test_an_adapter_this_build_does_not_have_is_refused():
    assert _eval(device=_device(adapter_key="x32")).code == "no_adapter"


def test_a_command_the_adapter_cannot_do_is_refused(monkeypatch):
    class NoMute(sa.SimulatorAdapter):
        SPEC = dict(sa.SimulatorAdapter.SPEC, key="nomute",
                    commands=("send_level_delta", "read_send_level"))
    monkeypatch.setitem(sa.ADAPTERS, "nomute", NoMute)
    d = _eval(req=_req(kind="mute"), device=_device(adapter_key="nomute"))
    assert d.code == "unsupported"


def test_the_mix_and_the_source_must_be_on_the_attached_version():
    assert _eval(req=_req(mix="Mix 9")).code == "mix_unknown"
    assert _eval(req=_req(source="Cowbell")).code == "source_unknown"


# --- bounds -------------------------------------------------------------------------------

@pytest.mark.parametrize("step", [0, 4, -4, 10])
def test_the_delta_is_bounded(step):
    d = _eval(req=_req(step_db=step))
    assert d.code == "delta_out_of_bounds", step


def test_the_engineers_modified_amount_is_what_is_checked():
    assert _eval(req=_req(step_db=1, approved_step_db=3)).allowed
    assert _eval(req=_req(step_db=1, approved_step_db=4)).code == "delta_out_of_bounds"


def test_a_tighter_policy_lowers_the_ceiling_but_never_raises_it():
    pol = dict(ss.POLICY_DEFAULTS, max_step_db=1)
    d = ss.evaluate("show-1", _req(step_db=2), _device(), ["Mix 1"], ["Lead Vox"], {},
                    USER, pol=pol, now=NOW)
    assert d.code == "delta_out_of_bounds"


def test_mutes_carry_no_delta_and_are_allowed():
    assert _eval(req=_req(kind="mute", step_db=0)).allowed


# --- rate ---------------------------------------------------------------------------------

def test_rate_limits_per_performer_mix_and_source():
    assert _eval(recent={"performer": 6}).code == "rate_performer"
    assert _eval(recent={"mix": 10}).code == "rate_mix"
    assert _eval(recent={"source": 10}).code == "rate_source"
    assert _eval(recent={"performer": 5, "mix": 9, "source": 9}).allowed


# --- state ------------------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["pending", "acknowledged", "modified", "applied_manually",
                                   "queued_for_device", "sent", "applied"])
def test_only_an_approved_request_may_be_sent(state):
    assert _eval(req=_req(state=state)).code == "not_approved"


def test_a_revert_needs_an_applied_change_and_an_adapter_that_can():
    assert _eval(req=_req(state="applied", command_id="c1"), is_revert=True).allowed
    assert _eval(req=_req(state="approved"), is_revert=True).code == "not_applied"


def test_a_revert_on_an_adapter_without_revert_is_refused(monkeypatch):
    class Oneway(sa.SimulatorAdapter):
        SPEC = dict(sa.SimulatorAdapter.SPEC, key="oneway", can_revert=False)
    monkeypatch.setitem(sa.ADAPTERS, "oneway", Oneway)
    d = _eval(req=_req(state="applied"), device=_device(adapter_key="oneway"), is_revert=True)
    assert d.code == "no_revert"


# --- command age --------------------------------------------------------------------------------

def test_a_command_older_than_its_ttl_is_dead():
    fresh = {"issued": (NOW - timedelta(seconds=5)).isoformat(timespec="seconds")}
    old = {"issued": (NOW - timedelta(seconds=25)).isoformat(timespec="seconds")}
    assert ss.command_alive(fresh, now=NOW).allowed
    assert ss.command_alive(old, now=NOW).code == "expired"
    assert ss.command_alive({"issued": ""}, now=NOW).code == "expired"


# --- the policy -------------------------------------------------------------------------------

def test_the_policy_can_only_be_tightened_within_bounds():
    show = "pol-" + uuid.uuid4().hex[:8]
    current, refused = ss.set_policy(show, USER, max_step_db=2, per_performer_per_min=3,
                                     command_ttl_s=999, master_output="1", per_mix_per_min="x")
    assert current["max_step_db"] == 2 and current["per_performer_per_min"] == 3
    assert current["command_ttl_s"] == ss.POLICY_DEFAULTS["command_ttl_s"]
    assert set(refused) == {"command_ttl_s", "master_output", "per_mix_per_min"}
    assert ss.policy(show)["max_step_db"] == 2


def test_the_ceiling_cannot_be_raised_above_the_vocabulary():
    show = "pol-" + uuid.uuid4().hex[:8]
    current, refused = ss.set_policy(show, USER, max_step_db=6)
    assert current["max_step_db"] == 3 and refused == ["max_step_db"]
