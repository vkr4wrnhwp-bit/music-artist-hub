"""Stage Bridge - the daemon that runs on the venue's production network.

The device half of docs/STAGE_CONTROL_BRIDGE.md. It holds one console
adapter, calls OUT to Street Banker with its device token, and does exactly
what a bridge must:

  heartbeat -> pull -> verify (signature, expiry, nonce) -> apply -> ack

Acknowledgements it cannot deliver are kept in a local JSON queue and
posted to /bridge/reconcile when the link returns, so internet loss never
reports a change that did not happen and never loses one that did.

Standard library only, so it runs on whatever laptop is at front of house.

    python tools/stage_bridge_daemon.py \
        --server https://street-banker.onrender.com \
        --token   <device token, shown once at registration> \
        --key     <signing key, shown with it> \
        --adapter simulator

    python tools/stage_bridge_daemon.py ... --adapter x32 --host 192.168.1.10 \
        --patch patch.json      # {"mixes": {"Mix 1": 7}, "sources": {"Lead Vox": 1}}

The X32 adapter is UNTESTED and reachable only with STAGE_BENCH_ADAPTERS=1
in the environment; the desk says so on every screen. Bench-test with
tools/x32_bench.py before trusting it in a room with an audience.
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

BODY_FIELDS = ("id", "nonce", "device_id", "show_id", "request_id", "command",
               "mix", "source", "step_db", "muted", "revert_of", "issued", "expires")


# --- the checks a bridge must make ---------------------------------------------------

def canonical(body):
    return json.dumps({k: body.get(k) for k in BODY_FIELDS}, sort_keys=True,
                      separators=(",", ":"))


def verify(body, key, seen_nonces, now=None):
    """(ok, reason). Signature, expiry, replay - in that order, and none of
    them optional. `seen_nonces` is the set this process has already handled."""
    want = hmac.new(key.encode("utf-8"), canonical(body).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, body.get("signature") or ""):
        return False, "bad_signature"
    now = now if now is not None else time.time()
    exp = _ts(body.get("expires"))
    if exp is None or now > exp:
        return False, "expired"
    if body.get("nonce") in seen_nonces:
        return False, "replayed"
    return True, "ok"


def _ts(iso):
    if not iso:
        return None
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def apply(adapter, body):
    """One command through the adapter. Returns the ack result; never raises.
    Anything the adapter cannot do is a failure the server records."""
    import stage_adapters as base
    try:
        if body["command"] == "send_level_delta":
            out = adapter.apply_send_delta(body["mix"], body["source"], body["step_db"])
        elif body["command"] == "mute_state":
            out = adapter.set_mute(body["mix"], body["source"], bool(body["muted"]))
        else:
            return {"ok": False, "failure": "Unknown command %r." % body["command"]}
        out["ok"] = True
        return out
    except base.AdapterError as e:
        return {"ok": False, "failure": str(e)}
    except Exception as e:  # a bug in the adapter is still a failed command, not a dead bridge
        return {"ok": False, "failure": "%s: %s" % (type(e).__name__, e)}


# --- the server ---------------------------------------------------------------------------

class Api:
    def __init__(self, server, token, timeout=8):
        self.server = server.rstrip("/")
        self.token = token
        self.timeout = timeout

    def post(self, path, body):
        req = urllib.request.Request(
            self.server + path, data=json.dumps(body or {}).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.token}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))


# --- the local queue --------------------------------------------------------------------------

class Queue:
    """Acknowledgements not yet delivered, on disk, so a crash mid-outage
    loses nothing."""

    def __init__(self, path):
        self.path = path
        self.entries = []
        self.seen = set()
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.entries = data.get("entries", [])
            self.seen = set(data.get("seen", []))

    def save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries, "seen": sorted(self.seen)[-5000:]}, f)
        os.replace(tmp, self.path)

    def add(self, entry):
        self.entries.append(entry)
        self.save()

    def drain(self, delivered):
        self.entries = [e for e in self.entries if e["command_id"] not in delivered]
        self.save()


# --- one cycle -----------------------------------------------------------------------------------

def cycle(api, adapter, key, queue, log=print, now=None):
    """Heartbeat, reconcile what is owed, pull, verify, apply, ack. Returns
    a summary. Never raises for a network failure: the queue keeps the acks
    and the next cycle tries again."""
    out = {"heartbeat": False, "pulled": 0, "acked": 0, "queued": 0, "stopped": False}
    try:
        health = adapter.health()
    except Exception as e:
        health = {"ok": False, "detail": str(e)}
    try:
        hb = api.post("/bridge/heartbeat", {"health": health, "software_version": "daemon-0.1"})
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("offline: %s" % e)
        return out
    out["heartbeat"] = True
    if hb.get("revoked") or not hb.get("ok"):
        log("revoked or refused by the server; stopping")
        out["stopped"] = True
        return out
    if hb.get("lockout"):
        log("LOCKOUT is on; nothing will be applied")

    if queue.entries:
        try:
            res = api.post("/bridge/reconcile", {"entries": queue.entries})
            delivered = {o["command_id"] for o in res.get("outcomes", [])}
            queue.drain(delivered)
            log("reconciled %d" % len(delivered))
        except (urllib.error.URLError, OSError, ValueError) as e:
            log("reconcile failed: %s" % e)

    try:
        pulled = api.post("/bridge/pull", {})
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("pull failed: %s" % e)
        return out
    if pulled.get("lockout") or not pulled.get("armed", True):
        # The server settles anything it handed us as rejected; do not apply.
        return out

    for body in pulled.get("commands", []):
        out["pulled"] += 1
        ok, reason = verify(body, key, queue.seen, now)
        if not ok:
            result = {"ok": False, "failure": "Bridge refused: " + reason}
            log("refused %s: %s" % (body.get("id"), reason))
        else:
            queue.seen.add(body["nonce"])
            result = apply(adapter, body)
            log("%s -> %s" % (body["command"], "ok" if result.get("ok") else result.get("failure")))
        entry = {"command_id": body.get("id"), "nonce": body.get("nonce"), "result": result}
        try:
            api.post("/bridge/ack", entry)
            out["acked"] += 1
        except (urllib.error.URLError, OSError, ValueError) as e:
            queue.add(entry)
            out["queued"] += 1
            log("ack kept for later: %s" % e)
    queue.save()
    return out


def build_adapter(key, host="", patch=None):
    import stage_adapters as base
    if key == "simulator":
        return base.SimulatorAdapter()
    if key == "x32":
        if os.environ.get("STAGE_BENCH_ADAPTERS", "").strip() != "1":
            raise SystemExit("The X32 adapter is UNTESTED and needs STAGE_BENCH_ADAPTERS=1 to run.")
        import stage_x32
        return stage_x32.X32Adapter(host=host, patch=patch)
    raise SystemExit("unknown adapter: %s" % key)


def main(argv=None):
    p = argparse.ArgumentParser(description="Street Banker Stage Bridge")
    p.add_argument("--server", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--key", required=True, help="the signing key shown at registration")
    p.add_argument("--adapter", default="simulator")
    p.add_argument("--host", default="", help="console IP (x32)")
    p.add_argument("--patch", default="", help="JSON file: mix bus and channel per passport name")
    p.add_argument("--queue", default=os.path.join(HERE, "instance", "stage-bridge-queue.json"))
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--once", action="store_true")
    a = p.parse_args(argv)
    patch = json.load(open(a.patch, encoding="utf-8")) if a.patch else None
    adapter = build_adapter(a.adapter, host=a.host, patch=patch)
    os.makedirs(os.path.dirname(a.queue), exist_ok=True)
    queue = Queue(a.queue)
    api = Api(a.server, a.token)
    print("Stage Bridge: %s adapter -> %s" % (a.adapter, a.server))
    while True:
        out = cycle(api, adapter, a.key, queue)
        if out["stopped"] or a.once:
            return 0 if not out["stopped"] else 2
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
