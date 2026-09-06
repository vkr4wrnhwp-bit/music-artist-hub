"""The Stage Bridge daemon, with a fake server and the simulator.

What a bridge must do is small and must not bend: verify the signature,
refuse the expired and the replayed, apply through the adapter, acknowledge
once, and keep what it could not deliver until the link is back.
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))

import stage_adapters as base
import stage_bridge_daemon as d

KEY = "k" * 64


def _signed(**over):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    body = {"id": "c1", "nonce": "n1", "device_id": "dev", "show_id": "s", "request_id": "r",
            "command": "send_level_delta", "mix": "Mix 1", "source": "Lead Vox", "step_db": 2,
            "muted": None, "revert_of": "", "issued": now.isoformat(timespec="seconds"),
            "expires": (now + timedelta(seconds=20)).isoformat(timespec="seconds")}
    body.update(over)
    body["signature"] = hmac.new(KEY.encode(), d.canonical(body).encode(), hashlib.sha256).hexdigest()
    return body


# --- verify --------------------------------------------------------------------

def test_a_good_command_verifies():
    assert d.verify(_signed(), KEY, set()) == (True, "ok")


def test_a_tampered_or_forged_command_does_not():
    body = _signed()
    body["step_db"] = 9
    assert d.verify(body, KEY, set())[1] == "bad_signature"
    assert d.verify(_signed(), "not-the-key", set())[1] == "bad_signature"


def test_expired_and_replayed_are_refused():
    late = _signed(expires="2020-01-01T00:00:00+00:00")
    assert d.verify(late, KEY, set())[1] == "expired"
    assert d.verify(_signed(), KEY, {"n1"})[1] == "replayed"


# --- apply ---------------------------------------------------------------------

def test_apply_goes_through_the_adapter_and_never_raises():
    sim = base.SimulatorAdapter()
    out = d.apply(sim, _signed())
    assert out["ok"] and out["confirmed"] and out["after"] == -18.0
    sim.fail_next = "DCA locked."
    assert d.apply(sim, _signed())["failure"] == "DCA locked."
    assert d.apply(sim, _signed(command="nonsense"))["ok"] is False


# --- a cycle against a fake server ---------------------------------------------

class FakeApi:
    def __init__(self, commands=None):
        self.commands = commands or []
        self.calls = []
        self.fail = set()
        self.flags = {"ok": True, "armed": True, "lockout": False, "revoked": False}

    def post(self, path, body):
        self.calls.append((path, body))
        if path in self.fail:
            raise urllib.error.URLError("down")
        if path == "/bridge/heartbeat":
            return dict(self.flags)
        if path == "/bridge/pull":
            cmds, self.commands = self.commands, []
            return {"ok": True, "commands": cmds, "armed": self.flags["armed"],
                    "lockout": self.flags["lockout"]}
        if path == "/bridge/ack":
            return {"ok": True, "code": "applied"}
        if path == "/bridge/reconcile":
            return {"ok": True, "outcomes": [{"command_id": e["command_id"], "code": "applied"}
                                             for e in body["entries"]]}
        raise AssertionError(path)


def test_one_cycle_heartbeats_pulls_applies_and_acks(tmp_path):
    api = FakeApi([_signed()])
    q = d.Queue(str(tmp_path / "q.json"))
    out = d.cycle(api, base.SimulatorAdapter(), KEY, q, log=lambda *_a: None)
    assert out == {"heartbeat": True, "pulled": 1, "acked": 1, "queued": 0, "stopped": False}
    paths = [p for p, _b in api.calls]
    assert paths == ["/bridge/heartbeat", "/bridge/pull", "/bridge/ack"]
    ack = api.calls[-1][1]
    assert ack["command_id"] == "c1" and ack["result"]["confirmed"] is True
    assert "n1" in q.seen, "the nonce is remembered so a replay is refused"


def test_a_replayed_command_is_refused_and_still_acked_as_refused(tmp_path):
    api = FakeApi([_signed(), _signed()])
    q = d.Queue(str(tmp_path / "q.json"))
    d.cycle(api, base.SimulatorAdapter(), KEY, q, log=lambda *_a: None)
    acks = [b for p, b in api.calls if p == "/bridge/ack"]
    assert acks[0]["result"]["ok"] is True
    assert acks[1]["result"]["ok"] is False and "replayed" in acks[1]["result"]["failure"]


def test_an_ack_that_cannot_be_delivered_waits_on_disk_and_reconciles(tmp_path):
    api = FakeApi([_signed()])
    api.fail.add("/bridge/ack")
    path = str(tmp_path / "q.json")
    q = d.Queue(path)
    out = d.cycle(api, base.SimulatorAdapter(), KEY, q, log=lambda *_a: None)
    assert out["queued"] == 1 and out["acked"] == 0
    assert json.load(open(path))["entries"][0]["command_id"] == "c1"
    # A new process, the link back: the queue is reconciled first.
    api.fail.clear()
    q2 = d.Queue(path)
    assert q2.entries and "n1" in q2.seen
    d.cycle(api, base.SimulatorAdapter(), KEY, q2, log=lambda *_a: None)
    assert any(p == "/bridge/reconcile" for p, _b in api.calls)
    assert q2.entries == []


def test_offline_is_not_an_error(tmp_path):
    api = FakeApi([_signed()])
    api.fail.add("/bridge/heartbeat")
    out = d.cycle(api, base.SimulatorAdapter(), KEY, d.Queue(str(tmp_path / "q.json")),
                  log=lambda *_a: None)
    assert out["heartbeat"] is False and out["pulled"] == 0


def test_revocation_stops_the_daemon_and_lockout_applies_nothing(tmp_path):
    api = FakeApi([_signed()])
    api.flags["revoked"] = True
    out = d.cycle(api, base.SimulatorAdapter(), KEY, d.Queue(str(tmp_path / "q.json")),
                  log=lambda *_a: None)
    assert out["stopped"] is True
    api = FakeApi([_signed()])
    api.flags["lockout"] = True
    sim = base.SimulatorAdapter()
    out = d.cycle(api, sim, KEY, d.Queue(str(tmp_path / "q2.json")), log=lambda *_a: None)
    assert out["pulled"] == 0 and sim.writes == 0


def test_the_x32_needs_the_bench_flag(monkeypatch):
    monkeypatch.delenv("STAGE_BENCH_ADAPTERS", raising=False)
    with pytest.raises(SystemExit):
        d.build_adapter("x32", host="192.0.2.1")
    monkeypatch.setenv("STAGE_BENCH_ADAPTERS", "1")
    a = d.build_adapter("x32", host="192.0.2.1", patch={"mixes": {}, "sources": {}})
    assert a.spec()["verified"] is False
    with pytest.raises(SystemExit):
        d.build_adapter("nope")
