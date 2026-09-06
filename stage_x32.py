"""Stage Control - the Behringer X32 / Midas M32 adapter. UNTESTED.

The owner's desk (docs/STAGE_CONTROL_PHASE1_AUDIT.md): the X32 is the most
common console in the rooms they play, and on 2026-09-04 they lifted the
brief's rule against reverse-engineered protocols. This is the adapter that
override allows. It speaks the community-documented OSC remote protocol
("Unofficial X32/M32 OSC Remote Protocol") over UDP 10023.

THE TESTING GATE STANDS. Nothing here has moved a fader on a real desk. The
spec says so in its own fields - `tested_model` and `tested_firmware` are
"UNTESTED" and `verified` is False - and the adapter is NOT in the default
registry: it is a bench adapter, reachable only when the operator sets
STAGE_BENCH_ADAPTERS=1 on the machine running the bridge, and every screen
that names it says UNTESTED. It graduates to `stage_adapters.ADAPTERS`, with
the model and firmware it was proved on written into the spec, only after
tools/x32_bench.py has run against a real X32 and the read-backs matched.
That is a code change, made once, by a person who watched the fader move.

WHAT THIS DRIVES. One send level per (mix bus, channel):
/ch/NN/mix/MM/level - a float in the desk's own 0..1 fader law, which the
functions below convert to and from dB - and its mute, /ch/NN/mix/MM/on.
Nothing else. The desk has no authentication at all, so every bound in
stage_safety is the only bound; this adapter adds the read-back that makes a
write CONFIRMED rather than assumed: it asks for the value after writing it.

The X32's fader law is piecewise linear in dB:
  f >= 0.5     : dB = 40 f - 30      (0.75 -> 0 dB, 1.0 -> +10 dB)
  f >= 0.25    : dB = 80 f - 50
  f >= 0.0625  : dB = 160 f - 70
  f >= 0       : dB = 480 f - 90     (0 -> -90 dB, shown as -inf on the desk)
"""
import socket
import struct

import stage_adapters as base

PORT = 10023
MIN_DB = -90.0
MAX_DB = 10.0
# Where the desk quantises: 1024 steps on a send level. Read-backs are compared
# at this resolution, not to the float we sent.
FADER_STEPS = 1023.0


# --- the fader law -------------------------------------------------------------

def float_to_db(f):
    f = max(0.0, min(1.0, float(f)))
    if f >= 0.5:
        return 40.0 * f - 30.0
    if f >= 0.25:
        return 80.0 * f - 50.0
    if f >= 0.0625:
        return 160.0 * f - 70.0
    return 480.0 * f - 90.0


def db_to_float(db):
    db = max(MIN_DB, min(MAX_DB, float(db)))
    if db >= -10.0:
        f = (db + 30.0) / 40.0
    elif db >= -30.0:
        f = (db + 50.0) / 80.0
    elif db >= -60.0:
        f = (db + 70.0) / 160.0
    else:
        f = (db + 90.0) / 480.0
    return max(0.0, min(1.0, f))


def quantise(f):
    """The desk stores 1024 positions; a value sent between two of them comes
    back as the nearer one. Compare at the desk's resolution."""
    return round(float(f) * FADER_STEPS) / FADER_STEPS


# --- OSC ------------------------------------------------------------------------

def _pad(b):
    return b + b"\0" * (4 - len(b) % 4)


def osc_encode(address, *args):
    """An OSC message. Arguments may be int, float or str. A query is the
    address alone - the X32 answers a bare address with the current value."""
    out = _pad(address.encode("ascii"))
    if not args:
        return out
    tags = ","
    body = b""
    for a in args:
        if isinstance(a, bool):
            a = int(a)
        if isinstance(a, int):
            tags += "i"
            body += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            body += struct.pack(">f", a)
        elif isinstance(a, str):
            tags += "s"
            body += _pad(a.encode("utf-8"))
        else:
            raise TypeError("unsupported OSC argument: %r" % (a,))
    return out + _pad(tags.encode("ascii")) + body


def osc_decode(packet):
    """(address, [args]). Tolerates the desk's habit of answering a query
    with the same address it was asked."""
    i = packet.find(b"\0")
    if i < 0:
        raise ValueError("no address")
    address = packet[:i].decode("ascii", "replace")
    pos = (i // 4 + 1) * 4
    args = []
    if pos >= len(packet) or packet[pos:pos + 1] != b",":
        return address, args
    j = packet.find(b"\0", pos)
    tags = packet[pos + 1:j].decode("ascii", "replace")
    pos = (j // 4 + 1) * 4
    for t in tags:
        if t == "i":
            args.append(struct.unpack(">i", packet[pos:pos + 4])[0]); pos += 4
        elif t == "f":
            args.append(struct.unpack(">f", packet[pos:pos + 4])[0]); pos += 4
        elif t == "s":
            k = packet.find(b"\0", pos)
            args.append(packet[pos:k].decode("utf-8", "replace")); pos = (k // 4 + 1) * 4
        else:
            raise ValueError("unsupported OSC type: %s" % t)
    return address, args


# --- transport ------------------------------------------------------------------

class UdpTransport:
    """One UDP socket to the desk. `ask` sends and waits for the desk's
    answer to that address; the X32 replies from the same port."""

    def __init__(self, host, port=PORT, timeout=0.5):
        self.host, self.port, self.timeout = host, port, timeout
        self._sock = None

    def _s(self):
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(self.timeout)
        return self._sock

    def ask(self, packet, want_address):
        s = self._s()
        s.sendto(packet, (self.host, self.port))
        for _ in range(8):
            try:
                data, _addr = s.recvfrom(4096)
            except socket.timeout:
                raise base.AdapterUnavailable("No answer from the X32 at %s." % self.host)
            address, args = osc_decode(data)
            if address == want_address:
                return args
        raise base.AdapterError("The X32 answered, but not to %s." % want_address)

    def send(self, packet):
        self._s().sendto(packet, (self.host, self.port))

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None


# --- the adapter ------------------------------------------------------------------

class X32Adapter(base.ConsoleAdapter):
    """Send levels and mutes on an X32/M32, addressed by the patch map.

    `patch` is {"mixes": {"Mix 1": 7}, "sources": {"Lead Vox": 1}} - the mix
    bus number and channel number for each name on the passport version. A
    name with no entry is refused, never guessed: the wrong bus is somebody
    else's ears.
    """

    SPEC = {
        "key": "x32",
        "manufacturer": "Behringer / Midas",
        "product_family": "X32 / M32",
        "tested_model": "UNTESTED - not yet bench-tested on any X32",
        "tested_firmware": "UNTESTED",
        "protocol": "OSC over UDP 10023 (community-documented, unofficial)",
        "version": "0.1-bench",
        "commands": base.COMMANDS,
        "acknowledges": True,       # the desk answers a query, so a write is read back
        "can_revert": True,
        "connection": "Same production network as the desk. UDP 10023. The X32 "
                      "has no authentication; the bridge is the only gate.",
        "limits": {"max_step_db": 3, "min_level_db": MIN_DB, "max_level_db": MAX_DB},
        "known_limitations": (
            "UNTESTED on real hardware. Bench-test with tools/x32_bench.py first.",
            "Protocol is community-documented, not published by the manufacturer.",
            "Only /ch/NN/mix/MM/level and /on are driven; nothing else is addressable.",
            "Read-back compares at the desk's 1024-step fader resolution.",
        ),
        "simulated": False,
        "verified": False,
    }

    def __init__(self, transport=None, patch=None, host=""):
        self.transport = transport or UdpTransport(host) if (transport or host) else None
        self.patch = patch or {"mixes": {}, "sources": {}}

    # -- addressing --
    def _bus(self, mix):
        n = (self.patch.get("mixes") or {}).get(mix)
        if n is None:
            raise base.AdapterError("No mix bus is patched for %r." % mix)
        n = int(n)
        if not 1 <= n <= 16:
            raise base.AdapterError("Mix bus %d is outside 1-16." % n)
        return n

    def _channel(self, source):
        n = (self.patch.get("sources") or {}).get(source)
        if n is None:
            raise base.AdapterError("No channel is patched for %r." % source)
        n = int(n)
        if not 1 <= n <= 32:
            raise base.AdapterError("Channel %d is outside 1-32." % n)
        return n

    def _level_addr(self, mix, source):
        return "/ch/%02d/mix/%02d/level" % (self._channel(source), self._bus(mix))

    def _on_addr(self, mix, source):
        return "/ch/%02d/mix/%02d/on" % (self._channel(source), self._bus(mix))

    def _need(self):
        if self.transport is None:
            raise base.AdapterUnavailable("No X32 host configured.")
        return self.transport

    # -- the contract --
    def health(self):
        try:
            args = self._need().ask(osc_encode("/xinfo"), "/xinfo")
        except base.AdapterError as e:
            return {"ok": False, "adapter": "x32", "simulated": False, "verified": False,
                    "detail": str(e)}
        model = args[2] if len(args) > 2 else "?"
        firmware = args[3] if len(args) > 3 else "?"
        return {"ok": True, "adapter": "x32", "simulated": False, "verified": False,
                "model": model, "firmware": firmware, "name": args[1] if len(args) > 1 else "",
                "detail": "%s firmware %s answering. UNTESTED adapter." % (model, firmware)}

    def read_send_level(self, mix, source):
        addr = self._level_addr(mix, source)
        args = self._need().ask(osc_encode(addr), addr)
        if not args:
            raise base.AdapterError("The X32 answered %s with no value." % addr)
        return float_to_db(args[0])

    def read_mute(self, mix, source):
        addr = self._on_addr(mix, source)
        args = self._need().ask(osc_encode(addr), addr)
        if not args:
            raise base.AdapterError("The X32 answered %s with no value." % addr)
        return int(args[0]) == 0

    def apply_send_delta(self, mix, source, step_db):
        addr = self._level_addr(mix, source)
        before = self.read_send_level(mix, source)
        wanted_db = max(MIN_DB, min(MAX_DB, before + float(step_db)))
        target = quantise(db_to_float(wanted_db))
        t = self._need()
        t.send(osc_encode(addr, float(target)))
        # The read-back is the whole point: the value the desk holds now.
        args = t.ask(osc_encode(addr), addr)
        got = quantise(args[0]) if args else None
        confirmed = got is not None and abs(got - target) <= 1.0 / FADER_STEPS
        after = float_to_db(got) if got is not None else wanted_db
        return {"before": before, "after": after, "confirmed": confirmed,
                "clamped": abs(wanted_db - (before + float(step_db))) > 1e-9,
                "simulated": False}

    def set_mute(self, mix, source, muted):
        addr = self._on_addr(mix, source)
        before = self.read_mute(mix, source)
        t = self._need()
        t.send(osc_encode(addr, 0 if muted else 1))
        args = t.ask(osc_encode(addr), addr)
        got = (int(args[0]) == 0) if args else None
        return {"before": before, "after": bool(muted), "confirmed": got == bool(muted),
                "clamped": False, "simulated": False}
