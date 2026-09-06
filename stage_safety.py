"""Stage Control - the safety engine.

Phase 6 of docs/STAGE_CONTROL_BRIEF.md: one place that decides whether a
connected command may be issued. Every check the brief lists is here, in
order, and the first refusal wins. Nothing else in the system may send a
command without a Decision from evaluate(), and every refusal is audited by
the caller with the code this returns, so the engineer sees it on the desk.

WHY THIS IS ITS OWN MODULE. The console the owner tours with (an X32) has no
authentication and no per-user limits - see the phase 1 audit. Every bound
here is the ONLY bound: a bug in this file has nothing downstream to catch it.
So the checks are data and small functions, tested one at a time, rather than
conditions scattered through request handlers.

The policy is per show and stored; the defaults are deliberately tight. A
performer can ask for three decibels at most in one step, six times a minute,
and only while the show is armed and a device is answering heartbeats.
"""
import json
from datetime import datetime, timezone

from db import get_db, _now
import stage_adapters as adapters
import stage_store as st

# --- policy ------------------------------------------------------------------

POLICY_DEFAULTS = {
    "max_step_db": 3,            # never above the request vocabulary's own ceiling
    "per_performer_per_min": 6,
    "per_mix_per_min": 10,
    "per_source_per_min": 10,
    "command_ttl_s": 20,         # a command older than this is dead, not late
    "heartbeat_stale_s": 20,     # a device quieter than this is not there
}

# What each policy value may be set to. Wider is not allowed from a form.
POLICY_BOUNDS = {
    "max_step_db": (1, 3),
    "per_performer_per_min": (1, 30),
    "per_mix_per_min": (1, 60),
    "per_source_per_min": (1, 60),
    "command_ttl_s": (5, 120),
    "heartbeat_stale_s": (5, 300),
}


def init_policies():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS stage_policies (
                show_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                policy TEXT NOT NULL DEFAULT '{}',
                updated TEXT NOT NULL
            );
        """)


def policy(show_id):
    out = dict(POLICY_DEFAULTS)
    with get_db() as db:
        row = db.execute("SELECT policy FROM stage_policies WHERE show_id = ?",
                         (show_id,)).fetchone()
    if row:
        try:
            stored = json.loads(row["policy"] or "{}")
        except ValueError:
            stored = {}
        for key, value in stored.items():
            if key in out:
                out[key] = value
    return out


def set_policy(show_id, user_id, **changes):
    """Store the values that are in bounds; ignore the rest. Returns the
    policy now in force and the keys that were refused."""
    current = policy(show_id)
    refused = []
    for key, value in changes.items():
        if key not in POLICY_BOUNDS:
            refused.append(key)
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            refused.append(key)
            continue
        low, high = POLICY_BOUNDS[key]
        if not low <= value <= high:
            refused.append(key)
            continue
        current[key] = value
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_policies (show_id, user_id, policy, updated) VALUES (?,?,?,?) "
            "ON CONFLICT(show_id) DO UPDATE SET policy = excluded.policy, updated = excluded.updated",
            (show_id, user_id, json.dumps(current), _now()))
    return current, refused


# --- time --------------------------------------------------------------------

def parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_seconds(ts, now=None):
    then = parse(ts)
    if then is None:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - then).total_seconds()


# --- the decision ------------------------------------------------------------

class Decision:
    def __init__(self, allowed, code="ok", reason=""):
        self.allowed = allowed
        self.code = code
        self.reason = reason

    def __bool__(self):
        return self.allowed

    def as_dict(self):
        return {"allowed": self.allowed, "code": self.code, "reason": self.reason}


def _refuse(code, reason):
    return Decision(False, code, reason)


def device_ready(device, pol=None, now=None):
    """Is this device in a state that may take a command? A Decision, so the
    desk can show WHY the show is in Request Mode."""
    if device is None:
        return _refuse("no_device", "No Stage Bridge is registered for this show.")
    if device.get("revoked_at"):
        return _refuse("device_revoked", "The Stage Bridge for this show has been revoked.")
    if device.get("lockout"):
        return _refuse("lockout", "Emergency lockout is on. Release it before sending.")
    if not device.get("armed"):
        return _refuse("disarmed", "The show is not armed.")
    pol = pol or POLICY_DEFAULTS
    age = age_seconds(device.get("last_heartbeat"), now)
    if age is None or age > pol["heartbeat_stale_s"]:
        return _refuse("device_stale", "The Stage Bridge has not answered a heartbeat "
                       "in the last %d seconds." % pol["heartbeat_stale_s"])
    try:
        health = json.loads(device.get("health") or "{}")
    except ValueError:
        health = {}
    if health and not health.get("ok", True):
        return _refuse("adapter_unhealthy",
                       health.get("detail") or "The console adapter reports a fault.")
    return Decision(True)


def evaluate(show_id, req, device, mixes, sources, recent, user_id, pol=None,
             is_revert=False, now=None):
    """May THIS request become a connected command right now?

    `req` is the stage request row; `device` the Stage Bridge row or None;
    `mixes` and `sources` the attached passport version's own lists; `recent`
    a dict of commands issued in the last minute keyed performer / mix /
    source; `user_id` who is asking. Read top to bottom: the order is the
    brief's, broadest refusal first, so the engineer is told the real reason.
    """
    pol = pol or policy(show_id)

    ready = device_ready(device, pol, now)
    if not ready:
        return ready
    if device.get("user_id") != user_id or req.get("user_id") != user_id:
        return _refuse("not_authorised", "Only the account that owns this show may send.")
    if req.get("show_id") != show_id or device.get("show_id") != show_id:
        return _refuse("wrong_show", "That request does not belong to this show.")

    locked = st.locked_reason(show_id, req.get("performer"), req.get("mix"))
    if locked:
        return _refuse("locked", locked)

    command = adapters.COMMAND_FOR_KIND.get(req.get("kind"))
    if command is None:
        return _refuse("not_a_command", "A report is a person telling you something; "
                       "it never becomes a console command.")
    spec = adapters.spec(device.get("adapter_key"))
    if spec is None:
        return _refuse("no_adapter", "The device names an adapter this build does not have.")
    if command not in spec["commands"]:
        return _refuse("unsupported", "The %s adapter cannot %s."
                       % (spec["key"], command.replace("_", " ")))
    if is_revert and not spec["can_revert"]:
        return _refuse("no_revert", "The %s adapter cannot revert a change." % spec["key"])

    if (req.get("mix") or "") not in (mixes or []):
        return _refuse("mix_unknown", "That mix is not on the attached passport version.")
    if command == "send_level_delta" and (req.get("source") or "") not in (sources or []):
        return _refuse("source_unknown", "That source is not on the attached input list.")

    if command == "send_level_delta":
        step = req.get("approved_step_db")
        if step is None:
            step = req.get("step_db")
        try:
            step = int(step)
        except (TypeError, ValueError):
            step = 0
        ceiling = min(int(pol["max_step_db"]), int(spec["limits"].get("max_step_db", 0) or 0))
        if step == 0 or abs(step) > ceiling:
            return _refuse("delta_out_of_bounds",
                           "Steps are limited to %d dB at a time." % ceiling)

    recent = recent or {}
    if recent.get("performer", 0) >= pol["per_performer_per_min"]:
        return _refuse("rate_performer", "%s has had %d changes in the last minute; wait."
                       % (req.get("performer") or "This performer", recent["performer"]))
    if recent.get("mix", 0) >= pol["per_mix_per_min"]:
        return _refuse("rate_mix", "%s has had %d changes in the last minute; wait."
                       % (req.get("mix") or "This mix", recent["mix"]))
    if command == "send_level_delta" and recent.get("source", 0) >= pol["per_source_per_min"]:
        return _refuse("rate_source", "%s has been moved %d times in the last minute; wait."
                       % (req.get("source") or "This source", recent["source"]))

    wanted_state = "applied" if is_revert else "approved"
    if req.get("state") != wanted_state:
        return _refuse("not_approved" if not is_revert else "not_applied",
                       "Only an approved request can be sent to the console."
                       if not is_revert else "Only an applied change can be reverted.")
    return Decision(True)


def command_alive(command, pol=None, now=None):
    """A queued or sent command past its expiry is dead. Nothing may apply it."""
    age = age_seconds(command.get("issued"), now)
    ttl = (pol or POLICY_DEFAULTS)["command_ttl_s"]
    if age is None:
        return _refuse("expired", "The command carries no issue time.")
    if age > ttl:
        return _refuse("expired", "The command is %d seconds old; the limit is %d."
                       % (int(age), ttl))
    return Decision(True)
