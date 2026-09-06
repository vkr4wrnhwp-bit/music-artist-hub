"""Stage Control - the console-adapter contract, and the one adapter that ships.

Phase 5 of docs/STAGE_CONTROL_BRIEF.md. A console adapter is the only thing in
the system that touches a desk, and it has to say what it is before it is
allowed to: manufacturer, family, the model and firmware it was actually
tested on, the protocol, the commands it supports, whether it can confirm a
write by reading the value back, whether it can revert, its limits and its
known gaps. An adapter that has not been tested says so in its own fields.

THE COMMAND VOCABULARY IS THE FIRST SAFETY LIMIT. Everything the brief forbids
- preamp gain, phantom power, patching, routing, clocking, firmware, network,
output protection, system processing, the master output - is not "blocked"
here. It has no name. A request cannot ask for what the vocabulary cannot
say, so there is nothing for a bug to let through.

WHAT SHIPS: the simulator. It is labelled simulated in its spec, in its
health, and in every acknowledgement it returns, and it is the only adapter
the web process is allowed to drive directly (see stage_bridge.run_local).
Nothing here claims support for any real console. The owner's decision of
2026-09-04 (docs/STAGE_CONTROL_PHASE1_AUDIT.md) is that an X32 adapter may be
written later; the contract below is shaped so it drops in - `acknowledges`
is exactly the read-back the X32 can do - but until one has moved a fader on
a named model and firmware, none is listed.
"""
import threading

# --- the vocabulary ----------------------------------------------------------

READS = ("read_send_level", "read_mute", "read_health")
WRITES = ("send_level_delta", "mute_state")
COMMANDS = READS + WRITES

# Named so the refusal is a fact the tests can hold, not an absence they have
# to infer. None of these is a command; none can be requested.
NEVER = ("preamp_gain", "phantom_power", "patch", "routing", "clock",
         "firmware", "network", "output_protection", "system_processing",
         "master_output")

# Which request kind becomes which command. Reports never do.
COMMAND_FOR_KIND = {"more": "send_level_delta", "less": "send_level_delta",
                    "mute": "mute_state", "unmute": "mute_state"}


class AdapterError(Exception):
    """The adapter tried and the console said no, or nothing came back."""


class AdapterUnavailable(AdapterError):
    """The adapter cannot reach its console at all."""


# --- the contract ------------------------------------------------------------

class ConsoleAdapter:
    """What every adapter must provide. The SPEC is the declaration the brief
    asks for; the methods are the only operations the system can ask of a
    desk. A subclass that cannot do one raises AdapterError rather than
    pretending."""

    SPEC = {
        "key": "", "manufacturer": "", "product_family": "",
        "tested_model": "", "tested_firmware": "", "protocol": "",
        "version": "", "commands": (), "acknowledges": False,
        "can_revert": False, "connection": "", "limits": {},
        "known_limitations": (), "simulated": False,
    }

    @classmethod
    def spec(cls):
        out = dict(ConsoleAdapter.SPEC)
        out.update(cls.SPEC)
        out["commands"] = tuple(c for c in out["commands"] if c in COMMANDS)
        out["reads"] = tuple(c for c in out["commands"] if c in READS)
        out["writes"] = tuple(c for c in out["commands"] if c in WRITES)
        out["known_limitations"] = tuple(out["known_limitations"])
        return out

    @classmethod
    def supports(cls, command):
        return command in cls.spec()["commands"]

    def health(self):
        raise AdapterError("This adapter does not report health.")

    def read_send_level(self, mix, source):
        raise AdapterError("This adapter cannot read a send level.")

    def read_mute(self, mix, source):
        raise AdapterError("This adapter cannot read a mute state.")

    def apply_send_delta(self, mix, source, step_db):
        raise AdapterError("This adapter cannot change a send level.")

    def set_mute(self, mix, source, muted):
        raise AdapterError("This adapter cannot change a mute state.")


# --- the simulator -----------------------------------------------------------

class SimulatorAdapter(ConsoleAdapter):
    """A console that exists only in memory.

    It behaves like the desk the safety work was designed around: a send level
    per (mix, source) that a bounded delta moves, clamped to the console's own
    range, and a read-back after every write so a change can be CONFIRMED
    rather than assumed. Two switches exist for the tests and for rehearsing
    failure on the desk page: `offline` (the console is unreachable) and
    `fail_next` (the next write is refused with that reason). `confirms` can
    be turned off to model a desk that cannot read a value back, which is the
    case the brief's confirmation rule exists for.
    """

    DEFAULT_LEVEL_DB = -20.0
    MIN_DB = -60.0
    MAX_DB = 10.0

    SPEC = {
        "key": "simulator",
        "manufacturer": "Street Banker",
        "product_family": "Simulator",
        "tested_model": "none - simulated",
        "tested_firmware": "n/a",
        "protocol": "in-process",
        "version": "1.0",
        "commands": COMMANDS,
        "acknowledges": True,
        "can_revert": True,
        "connection": "None. Runs inside the web process; drives no hardware.",
        "limits": {"max_step_db": 3, "min_level_db": MIN_DB, "max_level_db": MAX_DB},
        "known_limitations": (
            "Simulated. No audio, no console, no network.",
            "Levels live in this process's memory; a second web worker has its own.",
        ),
        "simulated": True,
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.levels = {}
        self.mutes = {}
        self.offline = False
        self.fail_next = None
        self.confirms = True
        self.writes = 0

    def _key(self, mix, source):
        return ((mix or "").strip().lower(), (source or "").strip().lower())

    def health(self):
        return {"ok": not self.offline, "adapter": "simulator", "simulated": True,
                "detail": "Simulated console. Nothing here moves audio."
                if not self.offline else "Simulated console is offline."}

    def _guard(self):
        if self.offline:
            raise AdapterUnavailable("The simulated console is offline.")
        if self.fail_next:
            reason, self.fail_next = self.fail_next, None
            raise AdapterError(reason)

    def read_send_level(self, mix, source):
        if self.offline:
            raise AdapterUnavailable("The simulated console is offline.")
        return self.levels.get(self._key(mix, source), self.DEFAULT_LEVEL_DB)

    def read_mute(self, mix, source):
        if self.offline:
            raise AdapterUnavailable("The simulated console is offline.")
        return bool(self.mutes.get(self._key(mix, source), False))

    def apply_send_delta(self, mix, source, step_db):
        with self._lock:
            self._guard()
            key = self._key(mix, source)
            before = self.levels.get(key, self.DEFAULT_LEVEL_DB)
            wanted = before + float(step_db)
            after = max(self.MIN_DB, min(self.MAX_DB, wanted))
            self.levels[key] = after
            self.writes += 1
            confirmed = self.confirms and self.read_send_level(mix, source) == after
            return {"before": before, "after": after, "confirmed": confirmed,
                    "clamped": after != wanted, "simulated": True}

    def set_mute(self, mix, source, muted):
        with self._lock:
            self._guard()
            key = self._key(mix, source)
            before = bool(self.mutes.get(key, False))
            self.mutes[key] = bool(muted)
            self.writes += 1
            confirmed = self.confirms and self.read_mute(mix, source) == bool(muted)
            return {"before": before, "after": bool(muted), "confirmed": confirmed,
                    "clamped": False, "simulated": True}


# --- the registry ------------------------------------------------------------

# Every adapter the system knows. One entry, on purpose: see the module
# docstring. Adding a real console here is a code change that must come with
# the tested_model and tested_firmware it was proved on.
ADAPTERS = {"simulator": SimulatorAdapter}

_instances = {}
_instances_lock = threading.Lock()


def adapter_class(key):
    return ADAPTERS.get(key)


def spec(key):
    cls = adapter_class(key)
    return cls.spec() if cls else None


def instance_for(device_id, key):
    """One adapter object per registered device, for the life of the process.
    The simulator's levels have to persist between requests or a desk page
    could never show a change it just made."""
    with _instances_lock:
        inst = _instances.get(device_id)
        if inst is None or inst.spec()["key"] != key:
            cls = adapter_class(key)
            if cls is None:
                return None
            inst = cls()
            _instances[device_id] = inst
        return inst


def forget(device_id):
    with _instances_lock:
        _instances.pop(device_id, None)
