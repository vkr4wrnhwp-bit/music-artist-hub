"""Stage Control phase 5: the console-adapter contract and the simulator.

Two things are load-bearing. The vocabulary has no word for anything the
brief forbids, so a forbidden operation cannot be requested; and the only
adapter that ships says "simulated" everywhere it speaks, so nothing it does
can be mistaken for a console.
"""
import pytest

import stage_adapters as sa


# --- the vocabulary is the first safety limit --------------------------------

def test_the_vocabulary_holds_only_bounded_monitor_operations():
    assert set(sa.WRITES) == {"send_level_delta", "mute_state"}
    assert set(sa.COMMANDS) == set(sa.READS) | set(sa.WRITES)


def test_nothing_the_brief_forbids_has_a_name():
    """Preamp gain, phantom, patching, routing, clocking, firmware, network,
    output protection, system processing, the master output: none is a
    command, and none can be reached from a request kind."""
    for never in sa.NEVER:
        assert never not in sa.COMMANDS
        assert never not in sa.COMMAND_FOR_KIND.values()
    assert set(sa.COMMAND_FOR_KIND) == {"more", "less", "mute", "unmute"}


def test_a_report_never_becomes_a_command():
    for report in ("feedback", "no_signal", "distortion", "too_loud", "equipment"):
        assert report not in sa.COMMAND_FOR_KIND


# --- the declaration ---------------------------------------------------------

def test_the_simulator_declares_every_field_the_brief_asks_for():
    spec = sa.spec("simulator")
    for field in ("manufacturer", "product_family", "tested_model", "tested_firmware",
                  "protocol", "commands", "reads", "writes", "acknowledges",
                  "can_revert", "connection", "limits", "known_limitations", "version"):
        assert field in spec, field
    assert spec["simulated"] is True
    assert "simulated" in spec["tested_model"]
    assert spec["limits"]["max_step_db"] == 3


def test_no_real_console_is_claimed():
    """The registry has one entry. Adding a real desk is a code change that
    must carry the model and firmware it was proved on."""
    assert list(sa.ADAPTERS) == ["simulator"]
    assert sa.spec("x32") is None and sa.adapter_class("x32") is None


def test_the_base_contract_refuses_rather_than_pretends():
    base = sa.ConsoleAdapter()
    with pytest.raises(sa.AdapterError):
        base.apply_send_delta("Mix 1", "Lead Vox", 2)
    with pytest.raises(sa.AdapterError):
        base.health()


# --- the simulator -----------------------------------------------------------

def test_a_delta_moves_the_level_and_is_confirmed_by_read_back():
    sim = sa.SimulatorAdapter()
    out = sim.apply_send_delta("Mix 1", "Lead Vox", 2)
    assert out == {"before": -20.0, "after": -18.0, "confirmed": True,
                   "clamped": False, "simulated": True}
    assert sim.read_send_level("mix 1", "LEAD VOX") == -18.0, "names are case-insensitive"


def test_the_level_is_clamped_to_the_consoles_range_and_says_so():
    sim = sa.SimulatorAdapter()
    sim.levels[sim._key("Mix 1", "Kick")] = 9.0
    out = sim.apply_send_delta("Mix 1", "Kick", 3)
    assert out["after"] == sim.MAX_DB and out["clamped"] is True


def test_a_console_that_cannot_read_back_does_not_confirm():
    """This is the case the brief's rule exists for: the send went, and that
    is all anyone knows."""
    sim = sa.SimulatorAdapter()
    sim.confirms = False
    assert sim.apply_send_delta("Mix 1", "Lead Vox", 1)["confirmed"] is False


def test_offline_and_refusal_are_errors_not_results():
    sim = sa.SimulatorAdapter()
    sim.offline = True
    with pytest.raises(sa.AdapterUnavailable):
        sim.apply_send_delta("Mix 1", "Lead Vox", 1)
    assert sim.health()["ok"] is False
    sim.offline = False
    sim.fail_next = "Channel is in a DCA the console refuses to bypass."
    with pytest.raises(sa.AdapterError):
        sim.set_mute("Mix 1", "Lead Vox", True)
    assert sim.fail_next is None, "the refusal is spent"
    assert sim.set_mute("Mix 1", "Lead Vox", True)["confirmed"] is True


def test_every_answer_is_labelled_simulated():
    sim = sa.SimulatorAdapter()
    assert sim.health()["simulated"] is True
    assert sim.apply_send_delta("Mix 1", "Lead Vox", 1)["simulated"] is True
    assert sim.set_mute("Mix 1", "Lead Vox", True)["simulated"] is True


def test_one_instance_per_device_for_the_life_of_the_process():
    a = sa.instance_for("dev-a", "simulator")
    a.apply_send_delta("Mix 1", "Lead Vox", 3)
    assert sa.instance_for("dev-a", "simulator") is a
    assert sa.instance_for("dev-b", "simulator") is not a
    sa.forget("dev-a")
    assert sa.instance_for("dev-a", "simulator") is not a
    assert sa.instance_for("dev-c", "nope") is None
