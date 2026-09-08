"""Stage Control - the Stage Rack status surface.

The STAGE RACK section of docs/STAGE_CONTROL_BRIEF.md asks the software to
expose, for the edge device that will one day be an appliance: identity,
ownership, network health, console connection, adapter status, software
version, last update, last heartbeat, armed state, emergency lockout,
remote-revocation state and a diagnostic export. This module computes all
of that from what the server already holds - the device row, its last
heartbeat, the show's policy and the event log - and nothing else.

NOTHING HERE IS A FLAG. Network health is the age of the last heartbeat
against the thresholds the safety engine defines (stage_safety.heartbeat_state);
the mode is stage_bridge.mode(); the console connection is what the daemon
last reported, or "Not reported" when it never said. A value the server has
not measured is shown as not measured, never as a guess.

NO SECRET LEAVES. The device's token is stored only as a hash and the rack
shows the first eight hex characters of that HASH as a fingerprint - enough
to tell two devices apart in a runbook, useless to anybody else. The signing
key and every command signature are stripped from the export by name, and
tests/test_stage_security.py holds that no token, key or HMAC appears in it.

The Stage Rack appliance itself does not exist. This is the status surface
the brief says its software must expose; the hardware is a separate
validation, recorded as open in docs/STAGE_CONTROL_PHASE7.md.
"""
import json

import stage_adapters as adapters
import stage_bridge as sb
import stage_safety as safety
import stage_store as st

NOT_MEASURED = "Not measured"
NOT_REPORTED = "Not reported"

# Column names that must never appear in an export, whatever table they are on.
SECRET_COLUMNS = ("token_hash", "signing_key", "signature")

# The lamps the panel may light. A lamp is for a state that needs a person to
# act; a healthy value is a reading on an LCD, not a lamp.
LAMPS = ("offline", "stale", "lockout", "revoked", "unverified_adapter", "disarmed",
         "console_unreachable")


def fingerprint(device):
    """First eight hex of the stored SHA-256 of the token. Not the token; not
    enough of the hash to matter."""
    return (device.get("token_hash") or "")[:8] if device else ""


def _health(device):
    try:
        return json.loads((device or {}).get("health") or "{}")
    except ValueError:
        return {}


def status(show_id, user_id, now=None):
    """Everything the STAGE RACK list asks for, as one dict. `device` is None
    when the show has never registered one, and every reading says so."""
    import db as store
    import tour_store as ts

    pol = safety.policy(show_id)
    m = sb.mode(show_id, user_id, now=now)
    dev = m["device"]
    spec = m["spec"]
    owner = store.get_user(user_id) or {}
    tour_id = ts.tour_id_for_show(show_id)

    out = {
        "show_id": show_id,
        "ownership": {"tour_id": tour_id, "owner_id": user_id,
                      "owner": owner.get("name") or owner.get("email") or ""},
        "mode": {"mode": m["mode"], "code": m["code"], "reason": m["reason"]},
        "policy": {"heartbeat_stale_s": pol["heartbeat_stale_s"],
                   "offline_after_s": safety.offline_after_s(pol),
                   "command_ttl_s": pol["command_ttl_s"]},
        "device": None,
        "lamps": [],
    }
    if dev is None:
        out["network"] = {"state": None, "label": NOT_MEASURED, "heartbeat_age_s": None,
                          "last_heartbeat": ""}
        out["console"] = {"connected": None, "label": NOT_REPORTED, "detail": ""}
        out["adapter"] = None
        out["software_version"] = NOT_REPORTED
        out["last_update"] = NOT_REPORTED
        out["armed"] = False
        out["lockout"] = {"on": False, "reason": ""}
        out["revoked"] = {"on": False, "at": ""}
        return out

    age = safety.age_seconds(dev.get("last_heartbeat"), now)
    net_state = safety.heartbeat_state(dev.get("last_heartbeat"), pol, now)
    health = _health(dev)
    rep = sb.report(dev)
    connected = rep.get("console_connected") if "console_connected" in rep else None
    if connected is None and health:
        # An old daemon sends only health; its ok flag is the console link.
        connected = bool(health.get("ok")) if "ok" in health else None

    out["device"] = {
        "id": dev["id"], "name": dev["name"], "fingerprint": fingerprint(dev),
        "adapter_key": dev["adapter_key"], "created": dev["created"],
        "rotated_at": dev.get("rotated_at") or "",
    }
    out["network"] = {
        "state": net_state,
        "label": NOT_MEASURED if net_state is None else net_state,
        "heartbeat_age_s": None if age is None else int(age),
        "last_heartbeat": dev.get("last_heartbeat") or "",
    }
    out["console"] = {
        "connected": connected,
        "label": NOT_REPORTED if connected is None else ("connected" if connected else "unreachable"),
        "detail": (rep.get("probe") or {}).get("detail") or health.get("detail") or "",
    }
    reported = rep.get("adapter_status") or {}
    out["adapter"] = {
        "key": dev["adapter_key"],
        "name": ("%s %s" % (spec["manufacturer"], spec["product_family"])).strip() if spec else dev["adapter_key"],
        "verified": bool(spec and spec.get("verified")),
        "simulated": bool(spec and spec.get("simulated")),
        "tested_model": spec["tested_model"] if spec else NOT_REPORTED,
        "reported": reported or None,
        "healthy": bool(health.get("ok", True)) if health else None,
    }
    out["software_version"] = dev.get("software_version") or NOT_REPORTED
    out["last_update"] = rep.get("last_update") or NOT_REPORTED
    out["armed"] = bool(dev.get("armed"))
    out["lockout"] = {"on": bool(dev.get("lockout")), "reason": dev.get("lockout_reason") or ""}
    out["revoked"] = {"on": bool(dev.get("revoked_at")), "at": dev.get("revoked_at") or ""}

    lamps = []
    if out["revoked"]["on"]:
        lamps.append("revoked")
    if out["lockout"]["on"]:
        lamps.append("lockout")
    if net_state == "offline":
        lamps.append("offline")
    elif net_state == "stale":
        lamps.append("stale")
    if connected is False:
        lamps.append("console_unreachable")
    if spec and not spec.get("verified"):
        lamps.append("unverified_adapter")
    if not out["armed"] and not out["lockout"]["on"] and not out["revoked"]["on"]:
        lamps.append("disarmed")
    out["lamps"] = lamps
    return out


LAMP_WORDS = {
    "revoked": ("Revoked", "crit"),
    "lockout": ("Emergency lockout", "crit"),
    "offline": ("Offline", "crit"),
    "stale": ("Heartbeat stale", "warn"),
    "console_unreachable": ("Console unreachable", "crit"),
    "unverified_adapter": ("Adapter UNTESTED", "crit"),
    "disarmed": ("Disarmed", ""),
}


def redact(row):
    """A copy of a row with every secret column gone. Used on every record
    the export carries, so a new column named like a secret is caught by the
    test rather than shipped."""
    return {k: v for k, v in dict(row).items() if k not in SECRET_COLUMNS}


def diagnostics(show_id, user_id, now=None, events=50, commands=20):
    """The diagnostic export: the status above plus the last N events and
    commands, redacted. JSON-safe."""
    out = status(show_id, user_id, now=now)
    out["events"] = st.events_recent(show_id, limit=events)
    out["commands"] = [redact(c) for c in sb.commands_for_show(show_id, user_id, limit=commands)]
    for c in out["commands"]:
        try:
            c["ack"] = json.loads(c.get("ack") or "{}")
        except (TypeError, ValueError):
            c["ack"] = {}
    out["adapters_available"] = sorted(adapters.available())
    out["bench_adapters_enabled"] = adapters.bench_enabled()
    return out
