"""Stage Control - the Stage Bridge, as the server sees it.

Phase 5 of docs/STAGE_CONTROL_BRIEF.md. A Stage Bridge is a device on the
venue's production network that holds the only connection to a console. This
module is the server's half of that relationship: registering a device,
rotating and revoking its credentials, taking its heartbeats, issuing it
signed commands, and recording what it says back. The console is never
exposed to the internet: the bridge calls out, pulls what is queued for it,
and posts acknowledgements.

THE WIRE FORMAT IS THE PRODUCT. A command is a small JSON body signed with
the device's key (HMAC-SHA256 over the canonical body), carrying a nonce and
an expiry. A bridge verifies the signature, refuses anything expired, and
refuses any nonce it has already seen; the server refuses any acknowledgement
for a nonce it has already settled. That is the replay protection, and it is
the same on both ends.

THE IN-PROCESS BRIDGE IS FOR THE SIMULATOR ONLY. run_local() pulls, verifies
and acknowledges exactly the way a remote bridge would, so the whole path -
safety decision, signing, delivery, confirmation, the request reaching
`applied` - is exercised end to end without hardware. It refuses to drive
anything whose adapter is not simulated: a real console is reached from a
real bridge on the venue network, never from the web process.

WHAT `applied` MEANS. A request reaches `applied` only when the device's
acknowledgement says the change was CONFIRMED - read back from the console,
not assumed from the send. An acknowledgement without confirmation leaves the
request at `device_acknowledged`, which the performer reads as "console
answered" and never as "done".
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from db import get_db, _now
import advance_store as adv
import stage_adapters as adapters
import stage_safety as safety
import stage_store as st

COMMAND_STATES = ("queued", "sent", "acked", "applied", "failed", "expired", "rejected")
OPEN_COMMAND_STATES = ("queued", "sent")


def _uid():
    return secrets.token_hex(16)


def _row(r):
    return dict(r) if r else None


# --- schema ------------------------------------------------------------------

def init_bridge():
    safety.init_policies()
    with get_db() as db:
        db.executescript("""
            /* A device. token_hash is what authenticates its calls; the
               signing key is what it verifies commands with. Both rotate
               together, and revocation is a timestamp so the record stays. */
            CREATE TABLE IF NOT EXISTS stage_devices (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                show_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                adapter_key TEXT NOT NULL DEFAULT 'simulator',
                token_hash TEXT NOT NULL,
                signing_key TEXT NOT NULL,
                armed INTEGER NOT NULL DEFAULT 0,
                lockout INTEGER NOT NULL DEFAULT 0,
                lockout_reason TEXT NOT NULL DEFAULT '',
                last_heartbeat TEXT NOT NULL DEFAULT '',
                health TEXT NOT NULL DEFAULT '{}',
                software_version TEXT NOT NULL DEFAULT '',
                revoked_at TEXT NOT NULL DEFAULT '',
                rotated_at TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sdev_show ON stage_devices(show_id, created);

            /* A command. The nonce is UNIQUE: that is the replay protection on
               the server side, as a constraint rather than a check. */
            CREATE TABLE IF NOT EXISTS stage_commands (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                show_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                command TEXT NOT NULL,
                mix TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                step_db INTEGER NOT NULL DEFAULT 0,
                muted INTEGER,
                revert_of TEXT NOT NULL DEFAULT '',
                nonce TEXT NOT NULL UNIQUE,
                issued TEXT NOT NULL,
                expires TEXT NOT NULL,
                signature TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued',
                sent_at TEXT NOT NULL DEFAULT '',
                acked_at TEXT NOT NULL DEFAULT '',
                ack TEXT NOT NULL DEFAULT '{}',
                failure TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_scmd_device ON stage_commands(device_id, state, created);
            CREATE INDEX IF NOT EXISTS idx_scmd_show ON stage_commands(show_id, created);
        """)
        # The patch map for a real desk: which mix bus and channel each name on
        # the passport version is. Added after the first schema shipped.
        cols = {r["name"] for r in db.execute("PRAGMA table_info(stage_devices)").fetchall()}
        if "config" not in cols:
            db.execute("ALTER TABLE stage_devices ADD COLUMN config TEXT NOT NULL DEFAULT '{}'")
        # What the daemon says about itself on each heartbeat beyond health:
        # adapter status, console reachability, its last update. Phase 7, for
        # the Stage Rack status surface. Old daemons send none of it and the
        # rack reads "Not reported".
        if "report" not in cols:
            db.execute("ALTER TABLE stage_devices ADD COLUMN report TEXT NOT NULL DEFAULT '{}'")
        # The poll's clock: expire_stale() runs on every desk poll and reads
        # the open commands of one show, so it needs the state in the index.
        db.execute("CREATE INDEX IF NOT EXISTS idx_scmd_show_state "
                   "ON stage_commands(show_id, user_id, state)")


# --- devices -----------------------------------------------------------------

def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register(user_id, show_id, name="", adapter_key="simulator"):
    """Create a device. Returns (device, token). The token is shown once and
    stored only as a hash; the signing key is what the bridge keeps locally
    to verify commands. Only adapters this build has may be named."""
    if adapters.adapter_class(adapter_key) is None:
        raise ValueError("unknown adapter: %s" % adapter_key)
    token = secrets.token_urlsafe(32)
    now = _now()
    dev_id = _uid()
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_devices (id, user_id, show_id, name, adapter_key, token_hash, "
            "signing_key, created, updated) VALUES (?,?,?,?,?,?,?,?,?)",
            (dev_id, user_id, show_id, (name or "Stage Bridge").strip()[:80], adapter_key,
             _hash(token), secrets.token_hex(32), now, now))
    st.emit(show_id, user_id, "bridge.registered", actor="owner",
            detail="%s registered (%s adapter)" % ((name or "Stage Bridge").strip()[:80], adapter_key),
            payload={"device_id": dev_id, "adapter": adapter_key})
    return get_device(dev_id, user_id), token


def get_device(device_id, user_id=None):
    with get_db() as db:
        if user_id is None:
            row = db.execute("SELECT * FROM stage_devices WHERE id = ?", (device_id,)).fetchone()
        else:
            row = db.execute("SELECT * FROM stage_devices WHERE id = ? AND user_id = ?",
                             (device_id, user_id)).fetchone()
    return _row(row)


def device_for_show(show_id, user_id):
    """The newest device that has not been revoked, or None."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM stage_devices WHERE show_id = ? AND user_id = ? AND revoked_at = '' "
            "ORDER BY created DESC LIMIT 1", (show_id, user_id)).fetchone()
    return _row(row)


def authenticate(token):
    """The device's own calls: heartbeat, pull, ack. A revoked device is
    nobody, however good its token."""
    if not token:
        return None
    with get_db() as db:
        row = db.execute("SELECT * FROM stage_devices WHERE token_hash = ? AND revoked_at = ''",
                         (_hash(token),)).fetchone()
    return _row(row)


def _set(device_id, **fields):
    fields["updated"] = _now()
    cols = ", ".join("%s = ?" % k for k in fields)
    with get_db() as db:
        db.execute("UPDATE stage_devices SET %s WHERE id = ?" % cols,
                   list(fields.values()) + [device_id])


def config(device):
    try:
        return json.loads((device or {}).get("config") or "{}")
    except ValueError:
        return {}


def set_config(device_id, user_id, host="", mixes=None, sources=None):
    """The patch map, validated: bus 1-16, channel 1-32, names non-empty.
    Returns (config, refused_names). A name that fails is dropped, never
    guessed - the wrong bus is somebody else's ears."""
    dev = get_device(device_id, user_id)
    if dev is None:
        return None, []
    refused = []
    clean = {"host": (host or "").strip()[:80], "patch": {"mixes": {}, "sources": {}}}
    for name, n in (mixes or {}).items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            refused.append(name); continue
        if name.strip() and 1 <= n <= 16:
            clean["patch"]["mixes"][name.strip()] = n
        else:
            refused.append(name)
    for name, n in (sources or {}).items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            refused.append(name); continue
        if name.strip() and 1 <= n <= 32:
            clean["patch"]["sources"][name.strip()] = n
        else:
            refused.append(name)
    _set(device_id, config=json.dumps(clean))
    adapters.forget(device_id)
    st.emit(dev["show_id"], user_id, "bridge.patched", actor="owner",
            detail="Patch map saved: %d mixes, %d sources"
            % (len(clean["patch"]["mixes"]), len(clean["patch"]["sources"])),
            payload={"device_id": device_id})
    return clean, refused


def rotate(device_id, user_id, actor=""):
    """New token and new signing key, together. Queued commands were signed
    with the old key and can no longer be verified, so they are expired here
    rather than left to fail on the device."""
    dev = get_device(device_id, user_id)
    if dev is None or dev["revoked_at"]:
        return None, None
    token = secrets.token_urlsafe(32)
    _set(device_id, token_hash=_hash(token), signing_key=secrets.token_hex(32),
         rotated_at=_now())
    _close_open_commands(dev, "expired", "Credentials were rotated.", actor)
    st.emit(dev["show_id"], user_id, "bridge.rotated", actor=actor or "owner",
            detail="Credentials rotated", payload={"device_id": device_id})
    return get_device(device_id, user_id), token


def revoke(device_id, user_id, actor=""):
    dev = get_device(device_id, user_id)
    if dev is None or dev["revoked_at"]:
        return None
    _set(device_id, revoked_at=_now(), armed=0)
    _close_open_commands(dev, "rejected", "The device was revoked.", actor)
    adapters.forget(device_id)
    st.emit(dev["show_id"], user_id, "bridge.revoked", actor=actor or "owner",
            detail="Stage Bridge revoked", payload={"device_id": device_id})
    return get_device(device_id, user_id)


def arm(device_id, user_id, actor=""):
    dev = get_device(device_id, user_id)
    if dev is None or dev["revoked_at"] or dev["lockout"]:
        return None
    _set(device_id, armed=1)
    st.emit(dev["show_id"], user_id, "bridge.armed", actor=actor or "owner",
            detail="Show armed for connected control", payload={"device_id": device_id})
    return get_device(device_id, user_id)


def disarm(device_id, user_id, actor="", reason=""):
    dev = get_device(device_id, user_id)
    if dev is None:
        return None
    _set(device_id, armed=0)
    _close_open_commands(dev, "rejected", reason or "The show was disarmed.", actor)
    st.emit(dev["show_id"], user_id, "bridge.disarmed", actor=actor or "owner",
            detail=reason or "Show disarmed - back to Request Mode",
            payload={"device_id": device_id})
    return get_device(device_id, user_id)


def lockout(device_id, user_id, actor="", reason=""):
    """Emergency. Immediate: disarms, refuses everything in flight, and stays
    on until somebody releases it on purpose."""
    dev = get_device(device_id, user_id)
    if dev is None:
        return None
    _set(device_id, lockout=1, armed=0,
         lockout_reason=(reason or "Emergency lockout").strip()[:200])
    _close_open_commands(dev, "rejected", "Emergency lockout.", actor)
    st.emit(dev["show_id"], user_id, "bridge.lockout", actor=actor or "owner",
            detail=reason or "Emergency lockout", payload={"device_id": device_id})
    return get_device(device_id, user_id)


def release_lockout(device_id, user_id, actor=""):
    dev = get_device(device_id, user_id)
    if dev is None:
        return None
    _set(device_id, lockout=0, lockout_reason="")
    st.emit(dev["show_id"], user_id, "bridge.lockout_released", actor=actor or "owner",
            detail="Lockout released; the show stays disarmed until armed again",
            payload={"device_id": device_id})
    return get_device(device_id, user_id)


# The heartbeat fields a daemon may report beyond health. Anything else in the
# body is dropped, and every value is clipped: the device is authenticated but
# it is still input.
REPORT_FIELDS = ("adapter_status", "console_connected", "last_update", "probe")


def clean_report(report):
    out = {}
    for key in REPORT_FIELDS:
        if key not in (report or {}):
            continue
        value = report[key]
        if key == "console_connected":
            out[key] = None if value is None else bool(value)
        elif key == "last_update":
            out[key] = str(value or "")[:40]
        elif isinstance(value, dict):
            out[key] = {str(k)[:40]: (str(v)[:200] if isinstance(v, str) else v)
                        for k, v in list(value.items())[:12]
                        if isinstance(v, (str, int, float, bool)) or v is None}
        else:
            out[key] = str(value)[:200]
    return out


def report(device):
    try:
        return json.loads((device or {}).get("report") or "{}")
    except ValueError:
        return {}


def heartbeat(device, health=None, software_version="", report=None):
    """The device says it is alive and how its console is. Stored as the last
    word; staleness is computed from the timestamp, never from a flag.
    `report` carries the rack fields (REPORT_FIELDS); a daemon that sends
    none keeps the last one it sent."""
    fields = dict(last_heartbeat=_now(),
                  health=json.dumps(health or {"ok": True}),
                  software_version=(software_version or device.get("software_version") or "")[:40])
    if report:
        fields["report"] = json.dumps(clean_report(report))
    _set(device["id"], **fields)
    return get_device(device["id"])


def mode(show_id, user_id, now=None):
    """Request Mode or Connected Control, and why. The desk shows this
    permanently; it is never inferred from a flag somebody set."""
    dev = device_for_show(show_id, user_id)
    ready = safety.device_ready(dev, safety.policy(show_id), now)
    spec = adapters.spec(dev["adapter_key"]) if dev else None
    return {
        "mode": "connected" if ready else "request",
        "code": ready.code, "reason": ready.reason,
        "device": dev, "spec": spec,
        "simulated": bool(spec and spec["simulated"]),
        "verified": bool(spec and spec.get("verified")),
    }


# --- commands ----------------------------------------------------------------

BODY_FIELDS = ("id", "nonce", "device_id", "show_id", "request_id", "command",
               "mix", "source", "step_db", "muted", "revert_of", "issued", "expires")


def canonical(body):
    return json.dumps({k: body.get(k) for k in BODY_FIELDS}, sort_keys=True,
                      separators=(",", ":"))


def sign(body, key):
    return hmac.new(key.encode("utf-8"), canonical(body).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def verify_signature(body, key, signature):
    return hmac.compare_digest(sign(body, key), signature or "")


def get_command(command_id, user_id=None):
    with get_db() as db:
        if user_id is None:
            row = db.execute("SELECT * FROM stage_commands WHERE id = ?", (command_id,)).fetchone()
        else:
            row = db.execute("SELECT * FROM stage_commands WHERE id = ? AND user_id = ?",
                             (command_id, user_id)).fetchone()
    return _row(row)


def commands_for_show(show_id, user_id, limit=50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM stage_commands WHERE show_id = ? AND user_id = ? "
            "ORDER BY created DESC LIMIT ?", (show_id, user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def recent_counts(show_id, performer, mix, source, window_s=60):
    """Commands issued in the last minute, for the rate limits. Refused
    commands are not here - they were never issued."""
    cutoff = datetime.now(timezone.utc).timestamp() - window_s
    out = {"performer": 0, "mix": 0, "source": 0}
    with get_db() as db:
        rows = db.execute(
            "SELECT c.mix, c.source, c.issued, r.performer FROM stage_commands c "
            "JOIN stage_requests r ON r.id = c.request_id "
            "WHERE c.show_id = ? AND c.revert_of = ''", (show_id,)).fetchall()
    for r in rows:
        then = safety.parse(r["issued"])
        if then is None or then.timestamp() < cutoff:
            continue
        if (r["performer"] or "").lower() == (performer or "").lower():
            out["performer"] += 1
        if r["mix"] == mix:
            out["mix"] += 1
        if source and r["source"] == source:
            out["source"] += 1
    return out


def _update_command(command_id, **fields):
    fields["updated"] = _now()
    cols = ", ".join("%s = ?" % k for k in fields)
    with get_db() as db:
        db.execute("UPDATE stage_commands SET %s WHERE id = ?" % cols,
                   list(fields.values()) + [command_id])


def _close_open_commands(dev, state, reason, actor=""):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM stage_commands WHERE device_id = ? AND state IN ('queued','sent')",
            (dev["id"],)).fetchall()
    for c in rows:
        _update_command(c["id"], state=state, failure=reason)
        req_state = "expired" if state == "expired" else "failed"
        st.advance(c["request_id"], dev["user_id"], req_state, actor=actor or "bridge",
                   failure=reason)


def issue(request_id, user_id, actor="", is_revert=False, now=None):
    """Turn an approved request into a signed command for the show's device,
    or refuse and say why. Every refusal is written to the event log with its
    code, so the desk shows it.

    Returns (command, decision). command is None when refused.
    """
    req = st.get(request_id, user_id)
    if req is None:
        return None, safety.Decision(False, "not_found", "No such request.")
    show_id = req["show_id"]
    dev = device_for_show(show_id, user_id)
    snap = adv.snapshot_for(show_id, user_id) or {}
    mixes = [o.get("mix_name") for o in snap.get("outputs") or [] if (o.get("mix_name") or "").strip()]
    sources = [i.get("source") for i in snap.get("inputs") or [] if (i.get("source") or "").strip()]
    pol = safety.policy(show_id)
    recent = recent_counts(show_id, req["performer"], req["mix"], req["source"])

    decision = safety.evaluate(show_id, req, dev, mixes, sources, recent, user_id,
                               pol=pol, is_revert=is_revert, now=now)
    if not decision:
        st.emit(show_id, user_id, "safety.refused", request_id=request_id,
                actor=actor or "safety", detail=decision.reason,
                payload={"code": decision.code, "revert": is_revert})
        return None, decision

    command = adapters.COMMAND_FOR_KIND[req["kind"]]
    step = req["approved_step_db"] if req.get("approved_step_db") is not None else req["step_db"]
    step = int(step)
    if req["kind"] == "less":
        step = -abs(step)
    elif req["kind"] == "more":
        step = abs(step)
    muted = None
    if command == "mute_state":
        muted = 1 if req["kind"] == "mute" else 0
    if is_revert:
        # Put back what the console READ BACK, not what was asked for. The
        # original acknowledgement carries before/after from the desk; the
        # requested +3 may have been clamped at the top of the fader to +1,
        # and reverting by -3 would then jump the level 2 dB below where it
        # started. Only when the ack carries no numbers does the requested
        # step stand in.
        step, muted = _revert_target(req, step, muted)

    issued = datetime.now(timezone.utc) if now is None else now
    body = {
        "id": _uid(), "nonce": secrets.token_urlsafe(18), "device_id": dev["id"],
        "show_id": show_id, "request_id": request_id, "command": command,
        # The source rides on a mute too: a mute is per (mix, source) in the
        # vocabulary ("Mute Lead Vox"), and the X32 adapter addresses
        # /ch/NN/mix/MM/on by channel. Dropping it here (phase 5 did) made
        # every mute address the empty source - phase 7 finding.
        "mix": req["mix"], "source": req["source"] or "",
        "step_db": step if command == "send_level_delta" else 0, "muted": muted,
        "revert_of": req["command_id"] if is_revert else "",
        "issued": issued.isoformat(timespec="seconds"),
        "expires": datetime.fromtimestamp(issued.timestamp() + pol["command_ttl_s"],
                                          timezone.utc).isoformat(timespec="seconds"),
    }
    signature = sign(body, dev["signing_key"])
    ts = _now()
    with get_db() as db:
        db.execute(
            "INSERT INTO stage_commands (id, device_id, show_id, user_id, request_id, command, "
            "mix, source, step_db, muted, revert_of, nonce, issued, expires, signature, state, "
            "created, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'queued',?,?)",
            (body["id"], dev["id"], show_id, user_id, request_id, command, body["mix"],
             body["source"], body["step_db"], muted, body["revert_of"], body["nonce"],
             body["issued"], body["expires"], signature, ts, ts))
    if is_revert:
        st.emit(show_id, user_id, "command.revert_queued", request_id=request_id,
                actor=actor or "engineer", detail="Revert queued for the console",
                payload={"command_id": body["id"], "revert_of": body["revert_of"]})
    else:
        st.advance(request_id, user_id, "queued_for_device", actor=actor,
                   command_id=body["id"])
    return get_command(body["id"], user_id), decision


def _revert_target(req, step, muted):
    """(step_db, muted) that restores the read-back `before` of the applied
    command. Bounded by construction: the measured change can be no larger
    than the bounded step that caused it, and it is rounded to whole dB
    because that is the vocabulary."""
    try:
        ack = json.loads(req.get("device_ack") or "{}")
    except (TypeError, ValueError):
        ack = {}
    before, after = ack.get("before"), ack.get("after")
    if muted is not None:
        if isinstance(before, bool):
            return 0, 1 if before else 0
        return 0, 1 - muted
    if isinstance(before, (int, float)) and isinstance(after, (int, float)) \
            and not isinstance(before, bool) and not isinstance(after, bool):
        measured = int(round(before - after))
        if measured != 0:
            return max(-abs(step), min(abs(step), measured)), None
    return -step, None


def wire(command, signature=True):
    """What the device receives: the signed body, nothing more."""
    body = {k: command.get(k) for k in BODY_FIELDS}
    if signature:
        body["signature"] = command["signature"]
    return body


def pull(device, now=None):
    """The device asks for its queue. Queued commands become sent; expired
    ones are settled as expired instead of handed over."""
    pol = safety.policy(device["show_id"])
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM stage_commands WHERE device_id = ? AND state = 'queued' "
            "ORDER BY created", (device["id"],)).fetchall()
    out = []
    for c in rows:
        c = dict(c)
        alive = safety.command_alive(c, pol, now)
        if not alive:
            _update_command(c["id"], state="expired", failure=alive.reason)
            if not c["revert_of"]:
                st.advance(c["request_id"], device["user_id"], "expired", actor="bridge",
                           failure=alive.reason)
            continue
        _update_command(c["id"], state="sent", sent_at=_now())
        if not c["revert_of"]:
            st.advance(c["request_id"], device["user_id"], "sent", actor="bridge")
        out.append(wire(c))
    return out


def verify_for_device(command, device, now=None):
    """What a bridge checks before touching its console. The in-process
    bridge runs exactly this, so the checks are proven by the tests that
    drive the simulator."""
    if command["device_id"] != device["id"]:
        return safety.Decision(False, "wrong_device", "This command is for another device.")
    if not verify_signature(command, device["signing_key"], command.get("signature")):
        return safety.Decision(False, "bad_signature", "The signature does not verify.")
    if command.get("command") not in adapters.WRITES:
        # The allowlist, checked on the device side too: a signed body that
        # names anything outside the vocabulary is refused before the adapter
        # sees it, however it got signed.
        return safety.Decision(False, "not_allowed", "%r is not a command a bridge may apply."
                               % (command.get("command"),))
    if command["state"] != "sent":
        return safety.Decision(False, "replayed", "This command was already handled.")
    return safety.command_alive(command, safety.policy(device["show_id"]), now)


def acknowledge(device, command_id, nonce, result, now=None):
    """The device reports what happened. `result` is
    {"ok": bool, "before": x, "after": y, "confirmed": bool, "failure": str}.

    Idempotent by nonce: a second acknowledgement for a settled command is
    refused as a replay, which is also what protects against a bridge
    re-posting its local queue after a reconnect.
    """
    cmd = get_command(command_id)
    if cmd is None or cmd["device_id"] != device["id"] or cmd["nonce"] != nonce:
        return None, safety.Decision(False, "unknown_command", "No such command for this device.")
    if cmd["state"] not in ("sent", "queued"):
        return cmd, safety.Decision(False, "replayed", "This command was already settled.")
    alive = safety.command_alive(cmd, safety.policy(cmd["show_id"]), now)
    user_id = cmd["user_id"]
    result = result or {}
    ack = {k: result.get(k) for k in ("ok", "before", "after", "confirmed", "failure", "simulated")}

    if not alive:
        _update_command(command_id, state="expired", failure=alive.reason, ack=json.dumps(ack))
        if not cmd["revert_of"]:
            st.advance(cmd["request_id"], user_id, "expired", actor="bridge", failure=alive.reason)
        return get_command(command_id), alive

    if not result.get("ok"):
        why = (result.get("failure") or "The console refused the command.")[:300]
        _update_command(command_id, state="failed", failure=why, acked_at=_now(),
                        ack=json.dumps(ack))
        if not cmd["revert_of"]:
            st.advance(cmd["request_id"], user_id, "failed", actor="bridge", failure=why)
        else:
            st.emit(cmd["show_id"], user_id, "command.revert_failed", request_id=cmd["request_id"],
                    actor="bridge", detail=why, payload={"command_id": command_id})
        return get_command(command_id), safety.Decision(True, "failed", why)

    confirmed = bool(result.get("confirmed"))
    _update_command(command_id, state="applied" if confirmed else "acked",
                    acked_at=_now(), ack=json.dumps(ack))
    if cmd["revert_of"]:
        if confirmed:
            st.advance(cmd["request_id"], user_id, "reverted", actor="bridge",
                       note="Reverted on the console", device_ack=json.dumps(ack))
        else:
            st.emit(cmd["show_id"], user_id, "command.revert_unconfirmed",
                    request_id=cmd["request_id"], actor="bridge",
                    detail="The console answered but did not confirm the revert",
                    payload={"command_id": command_id})
        return get_command(command_id), safety.Decision(True, "applied" if confirmed else "unconfirmed")

    st.advance(cmd["request_id"], user_id, "device_acknowledged", actor="bridge",
               device_ack=json.dumps(ack))
    if confirmed:
        st.advance(cmd["request_id"], user_id, "applied", actor="bridge",
                   device_ack=json.dumps(ack))
        return get_command(command_id), safety.Decision(True, "applied")
    st.emit(cmd["show_id"], user_id, "command.unconfirmed", request_id=cmd["request_id"],
            actor="bridge", detail="The console answered but did not confirm the change; "
            "it is not shown as done.", payload={"command_id": command_id})
    return get_command(command_id), safety.Decision(True, "unconfirmed")


def reconcile(device, entries):
    """A bridge that lost the internet posts its local audit queue on
    reconnect. Each entry is applied through acknowledge(), which refuses the
    ones already settled - so re-sending is safe and the outcome list says
    what was new."""
    out = []
    for e in entries or []:
        _cmd, decision = acknowledge(device, e.get("command_id", ""), e.get("nonce", ""),
                                     e.get("result") or {})
        out.append({"command_id": e.get("command_id"), "code": decision.code})
    return out


def expire_stale(show_id, user_id, now=None):
    """Commands past their expiry that nobody settled. Called by the desk
    poll so a dead command does not sit at 'sent' forever."""
    pol = safety.policy(show_id)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM stage_commands WHERE show_id = ? AND user_id = ? AND state IN ('queued','sent')",
            (show_id, user_id)).fetchall()
    n = 0
    for c in rows:
        c = dict(c)
        alive = safety.command_alive(c, pol, now)
        if alive:
            continue
        _update_command(c["id"], state="expired", failure=alive.reason)
        if not c["revert_of"]:
            st.advance(c["request_id"], user_id, "expired", actor="bridge", failure=alive.reason)
        n += 1
    return n


# --- the in-process bridge (simulator only) ----------------------------------

def run_local(device_id, user_id, now=None):
    """Be the bridge for one cycle: heartbeat, pull, verify, apply through the
    adapter, acknowledge. Only for a simulated adapter - a real console is
    driven from a real bridge on the venue network, never from here."""
    dev = get_device(device_id, user_id)
    if dev is None or dev["revoked_at"]:
        return {"error": "no such device"}
    spec = adapters.spec(dev["adapter_key"])
    if not spec or not spec["simulated"]:
        return {"error": "run_local drives only the simulator; a real console needs a real bridge"}
    inst = adapters.instance_for(dev["id"], dev["adapter_key"])
    probe = inst.probe()
    dev = heartbeat(dev, inst.health(), software_version="local-" + spec["version"],
                    report={"adapter_status": {"name": spec["key"], "verified": spec["verified"],
                                               "tested_model": spec["tested_model"],
                                               "simulated": spec["simulated"]},
                            "console_connected": probe.get("reachable"),
                            "probe": probe, "last_update": _now()})
    outcomes = []
    for body in pull(dev, now):
        cmd = get_command(body["id"])
        ok = verify_for_device(cmd, dev, now)
        if not ok:
            _cmd, d = acknowledge(dev, cmd["id"], cmd["nonce"],
                                  {"ok": False, "failure": "Bridge refused: " + ok.reason}, now)
            outcomes.append({"command_id": cmd["id"], "code": ok.code})
            continue
        try:
            if cmd["command"] == "send_level_delta":
                result = inst.apply_send_delta(cmd["mix"], cmd["source"], cmd["step_db"])
            else:
                result = inst.set_mute(cmd["mix"], cmd["source"], bool(cmd["muted"]))
            result["ok"] = True
        except adapters.AdapterError as e:
            result = {"ok": False, "failure": str(e)}
        _cmd, d = acknowledge(dev, cmd["id"], cmd["nonce"], result, now)
        outcomes.append({"command_id": cmd["id"], "code": d.code})
    return {"device_id": dev["id"], "outcomes": outcomes, "health": inst.health()}
