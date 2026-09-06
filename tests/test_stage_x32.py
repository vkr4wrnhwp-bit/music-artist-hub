"""The X32 adapter, against a fake desk.

Nothing here proves the adapter works on an X32 - only a bench test on real
hardware can, and until one has run the spec says UNTESTED and the adapter
stays out of the default registry. What these prove is everything that can
be proved without the desk: the OSC bytes are right, the fader law is the
documented one, a write is confirmed only by what comes back, and a name
with no patch entry is refused rather than guessed.
"""
import struct

import pytest

import stage_adapters as base
import stage_x32 as x32


# --- the fader law -------------------------------------------------------------

@pytest.mark.parametrize("f, db", [(1.0, 10.0), (0.75, 0.0), (0.5, -10.0),
                                   (0.25, -30.0), (0.0625, -60.0), (0.0, -90.0)])
def test_the_documented_breakpoints(f, db):
    assert x32.float_to_db(f) == pytest.approx(db)
    assert x32.db_to_float(db) == pytest.approx(f)


def test_the_law_round_trips_and_clamps():
    for db in (-72.5, -45.0, -20.0, -6.0, 0.0, 3.0, 9.9):
        assert x32.float_to_db(x32.db_to_float(db)) == pytest.approx(db, abs=1e-6)
    assert x32.db_to_float(40.0) == 1.0 and x32.db_to_float(-200.0) == 0.0
    assert x32.float_to_db(2.0) == 10.0


# --- OSC ---------------------------------------------------------------------------

def test_a_query_is_the_bare_address_padded_to_four():
    pkt = x32.osc_encode("/ch/01/mix/07/level")
    assert pkt == b"/ch/01/mix/07/level\0"
    assert len(pkt) % 4 == 0
    assert x32.osc_decode(pkt) == ("/ch/01/mix/07/level", [])


def test_a_set_carries_a_typed_float_and_decodes_back():
    pkt = x32.osc_encode("/ch/01/mix/07/level", 0.75)
    assert pkt[:20] == b"/ch/01/mix/07/level\0"
    assert b",f\0\0" in pkt
    assert pkt[-4:] == struct.pack(">f", 0.75)
    addr, args = x32.osc_decode(pkt)
    assert addr == "/ch/01/mix/07/level" and args == pytest.approx([0.75])


def test_ints_and_strings_encode_too():
    addr, args = x32.osc_decode(x32.osc_encode("/xinfo", 1, "X32", 2.5))
    assert addr == "/xinfo" and args[0] == 1 and args[1] == "X32" and args[2] == pytest.approx(2.5)
    with pytest.raises(TypeError):
        x32.osc_encode("/x", [1])


# --- a fake desk ------------------------------------------------------------------

class FakeDesk:
    """Answers like an X32: a query by address returns the stored value; a
    set stores it, quantised to the desk's fader steps."""

    def __init__(self):
        self.levels = {}
        self.on = {}
        self.sent = []
        self.answer_nothing = False
        self.offline = False

    def _reply(self, addr):
        if addr == "/xinfo":
            return ["192.168.1.10", "FOH X32", "X32", "4.06"]
        if addr.endswith("/level"):
            return [self.levels.get(addr, 0.75)]
        if addr.endswith("/on"):
            return [self.on.get(addr, 1)]
        return []

    def ask(self, packet, want):
        if self.offline:
            raise base.AdapterUnavailable("No answer from the X32.")
        addr, args = x32.osc_decode(packet)
        assert addr == want
        if self.answer_nothing:
            return []
        return self._reply(addr)

    def send(self, packet):
        addr, args = x32.osc_decode(packet)
        self.sent.append((addr, args))
        if addr.endswith("/level"):
            self.levels[addr] = x32.quantise(args[0])
        elif addr.endswith("/on"):
            self.on[addr] = int(args[0])


PATCH = {"mixes": {"Mix 1": 7, "Mix 2": 8}, "sources": {"Lead Vox": 1, "Kick": 2}}


def _adapter(desk=None):
    return x32.X32Adapter(transport=desk or FakeDesk(), patch=PATCH)


def test_the_spec_says_untested_everywhere_it_can():
    spec = x32.X32Adapter.spec()
    assert spec["verified"] is False and spec["simulated"] is False
    assert "UNTESTED" in spec["tested_model"] and "UNTESTED" in spec["tested_firmware"]
    assert spec["acknowledges"] is True, "the desk answers a query, so writes can be read back"
    assert any("UNTESTED" in k for k in spec["known_limitations"])


def test_addresses_come_from_the_patch_map_never_from_a_guess():
    a = _adapter()
    assert a._level_addr("Mix 1", "Lead Vox") == "/ch/01/mix/07/level"
    assert a._on_addr("Mix 2", "Kick") == "/ch/02/mix/08/on"
    with pytest.raises(base.AdapterError):
        a._level_addr("Mix 9", "Lead Vox")
    with pytest.raises(base.AdapterError):
        a._level_addr("Mix 1", "Cowbell")
    bad = x32.X32Adapter(transport=FakeDesk(), patch={"mixes": {"Mix 1": 17}, "sources": {"Kick": 0}})
    with pytest.raises(base.AdapterError):
        bad._bus("Mix 1")
    with pytest.raises(base.AdapterError):
        bad._channel("Kick")


def test_health_reads_the_desks_own_name_and_firmware():
    h = _adapter().health()
    assert h["ok"] and h["model"] == "X32" and h["firmware"] == "4.06"
    assert h["verified"] is False and "UNTESTED" in h["detail"]
    desk = FakeDesk(); desk.offline = True
    assert _adapter(desk)["ok"] is False if False else _adapter(desk).health()["ok"] is False


def test_a_delta_is_written_in_the_fader_law_and_confirmed_by_read_back():
    desk = FakeDesk()
    a = _adapter(desk)
    assert a.read_send_level("Mix 1", "Lead Vox") == pytest.approx(0.0)      # desk default 0.75
    out = a.apply_send_delta("Mix 1", "Lead Vox", 2)
    assert desk.sent[0][0] == "/ch/01/mix/07/level"
    assert desk.sent[0][1][0] == pytest.approx(x32.quantise(x32.db_to_float(2.0)), abs=1e-6)
    assert out["before"] == pytest.approx(0.0)
    assert out["after"] == pytest.approx(2.0, abs=0.05)
    assert out["confirmed"] is True and out["simulated"] is False


def test_an_unanswered_read_back_is_not_a_confirmation():
    desk = FakeDesk()
    a = _adapter(desk)
    out = a.apply_send_delta("Mix 1", "Lead Vox", 1)
    assert out["confirmed"] is True
    desk.answer_nothing = True
    with pytest.raises(base.AdapterError):
        a.read_send_level("Mix 1", "Lead Vox")


def test_the_top_of_the_fader_clamps_and_says_so():
    desk = FakeDesk()
    desk.levels["/ch/01/mix/07/level"] = 1.0
    out = _adapter(desk).apply_send_delta("Mix 1", "Lead Vox", 3)
    assert out["after"] == pytest.approx(10.0) and out["clamped"] is True


def test_mute_is_the_on_flag_inverted():
    desk = FakeDesk()
    a = _adapter(desk)
    assert a.read_mute("Mix 1", "Kick") is False
    out = a.set_mute("Mix 1", "Kick", True)
    assert desk.sent[-1] == ("/ch/02/mix/07/on", [0])
    assert out["confirmed"] is True and a.read_mute("Mix 1", "Kick") is True
    assert a.set_mute("Mix 1", "Kick", False)["confirmed"] is True


def test_no_host_means_unavailable_not_a_crash():
    a = x32.X32Adapter(patch=PATCH)
    with pytest.raises(base.AdapterUnavailable):
        a.read_send_level("Mix 1", "Lead Vox")
    assert a.health()["ok"] is False
