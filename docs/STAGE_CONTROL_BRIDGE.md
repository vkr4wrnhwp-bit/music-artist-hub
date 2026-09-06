# Stage Control — Stage Bridge, console adapters, and the safety engine

Phases 5 and 6 of [STAGE_CONTROL_BRIEF.md](STAGE_CONTROL_BRIEF.md), and the
operating notes phase 7 asks for. Read the
[phase 1 audit](STAGE_CONTROL_PHASE1_AUDIT.md) first for the two decisions
that shape everything here: there is no realtime infrastructure (the event
cursor is the realtime), and the console the owner tours with has no
authentication of its own, so **every bound is ours**.

## What ships, and what does not

| Ships | Does not ship |
| --- | --- |
| The adapter contract (`stage_adapters.py`) | A *verified* adapter for any real console |
| A simulator adapter, labelled simulated everywhere it speaks | A Stage Rack appliance |
| The server side of the Stage Bridge protocol (`stage_bridge.py`) and the daemon (`tools/stage_bridge_daemon.py`) | — |
| An X32 adapter (`stage_x32.py`) as a **bench adapter**: UNTESTED, behind `STAGE_BENCH_ADAPTERS=1`, never in the default registry | The bench test that would let it graduate (`tools/x32_bench.py` — a person runs it) |
| The safety engine (`stage_safety.py`) with a per-show policy | Partner-tenant roles for stage permissions (single-owner for now) |
| The bridge page, the desk in Connected Control, the device endpoints | QR / guest performer access (belongs with `tour_share_links`) |

**Nothing claims X32 support.** The owner has lifted the brief's rule against
reverse-engineered protocols (audit amendment, 2026-09-04), so an X32
adapter has been written — see *The X32 adapter* below — but it may not
report the console as supported until it has moved a fader on a named model
and firmware and read the value back. `tested_model`, `tested_firmware` and
`verified` are fields on the contract for exactly that reason, and every
screen that names the adapter says UNTESTED until they are filled in.

## Architecture

```
performer phone ──ask──▶ stage_store (requests, TRANSITIONS, event cursor)
                                   │ approve
engineer desk ──send──▶ stage_bridge.issue() ──▶ stage_safety.evaluate()
                                   │ allowed                  │ refused → safety.refused event
                                   ▼
                        stage_commands (signed body, nonce UNIQUE, expiry)
                                   │ pull (Bearer token)
                        Stage Bridge on the venue network
                                   │ verify signature / expiry / replay
                                   ▼
                        console adapter ──▶ desk ──▶ read-back
                                   │ ack {ok, before, after, confirmed}
                                   ▼
                        stage_bridge.acknowledge() → request state
```

The request state machine is unchanged from phase 4. The bridge only ever
calls `stage_store.advance()`, so the whitelist still governs: a request
reaches `applied` **only** through `queued_for_device → sent →
device_acknowledged → applied`, and the last step happens only when the
acknowledgement says `confirmed: true`.

## The wire format

A command is the canonical JSON of these fields, signed with HMAC-SHA256
using the device's signing key:

```
id, nonce, device_id, show_id, request_id, command, mix, source,
step_db, muted, revert_of, issued, expires
```

`command` is one of `send_level_delta` (with `step_db`, bounded) or
`mute_state` (with `muted`). Nothing else exists. `expires` is `issued +
command_ttl_s` from the show's policy (default 20 s).

A bridge that receives a command must, in this order:

1. verify the signature with its signing key (`stage_bridge.sign`);
2. refuse it if `expires` has passed;
3. refuse it if it has seen the nonce before;
4. apply it through its adapter;
5. acknowledge it once.

The server enforces the same three from its side: the nonce column is
`UNIQUE`, a second acknowledgement for a settled command is refused as
`replayed`, and an acknowledgement that arrives after expiry settles the
request as `expired`, never `applied` — internet loss cannot report a change
that may not have happened.

## Device endpoints

All under `/bridge/`, outside the login wall, `Authorization: Bearer <token>`
required; anything else is 401.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/bridge/heartbeat` | `{"health": {"ok": true, "detail": "…"}, "software_version": "…"}` | armed / lockout / revoked flags |
| POST | `/bridge/pull` | — | queued commands, now marked sent |
| POST | `/bridge/ack` | `{"command_id", "nonce", "result": {"ok", "before", "after", "confirmed", "failure"}}` | `code`: applied / unconfirmed / failed / expired / replayed |
| POST | `/bridge/reconcile` | `{"entries": [ack bodies…]}` | one code per entry |

A bridge that lost the internet keeps its acknowledgements locally and posts
them to `/bridge/reconcile` when it is back; re-posting is safe.

## Registering a device

Stage Control desk → **Stage Bridge →** → Register. The token is shown once
and stored only as a SHA-256 hash; the signing key is shown with it. Rotate
replaces both and expires anything queued under the old key. Revoke is
final: the token is nobody's, queued commands are rejected, and the show
returns to Request Mode.

One device per show at a time. A second registration is refused until the
first is revoked.

## Modes, and why they are computed

`stage_bridge.mode()` answers *connected* only when, right now, a device is
registered, not revoked, not locked out, armed, has answered a heartbeat
within `heartbeat_stale_s`, and its last health report was ok. Anything else
is Request Mode with the reason. The desk banner, the bridge page and the
events poll all call this; nothing stores "connected" as a flag, so the
product cannot drift into Connected Control silently.

## Emergency lockout

Immediate. Disarms the device, settles every queued or sent command as
rejected (their requests read *failed*), and stays on until released on
purpose. Releasing does **not** re-arm. Arming during a lockout is refused.

## The safety engine

`stage_safety.evaluate()` runs every check the brief lists, broadest first,
and returns the first refusal with a code the desk shows in words:

`no_device · device_revoked · lockout · disarmed · device_stale ·
adapter_unhealthy · not_authorised · wrong_show · locked · not_a_command ·
no_adapter · unsupported · no_revert · mix_unknown · source_unknown ·
delta_out_of_bounds · rate_performer · rate_mix · rate_source ·
not_approved / not_applied`

Every refusal is written to the show's event log as `safety.refused` with
its code.

### Policy

Per show, editable on the bridge page, storable only inside these bounds:

| Key | Default | Bounds |
| --- | --- | --- |
| `max_step_db` | 3 | 1–3 |
| `per_performer_per_min` | 6 | 1–30 |
| `per_mix_per_min` | 10 | 1–60 |
| `per_source_per_min` | 10 | 1–60 |
| `command_ttl_s` | 20 | 5–120 |
| `heartbeat_stale_s` | 20 | 5–300 |

The delta ceiling is the **tighter** of the policy and the adapter's own
`limits.max_step_db`, and it can never be raised above the request
vocabulary's three decibels.

### What can never be a command

Preamp gain, phantom power, patching, routing, clocking, firmware, network
settings, output protection, system processing, the master output. They are
listed in `stage_adapters.NEVER` so a test can hold them out, and they have
no name in the command vocabulary, so nothing can ask for them.

## The adapter contract

`stage_adapters.ConsoleAdapter`. A subclass declares a `SPEC` with every
field the brief asks for and implements only what it can do; anything it
cannot do raises `AdapterError` rather than pretending.

```
key, manufacturer, product_family, tested_model, tested_firmware, protocol,
version, commands, acknowledges, can_revert, connection, limits
({max_step_db, min_level_db, max_level_db}), known_limitations, simulated
```

`acknowledges` means the adapter can **confirm a write by reading the value
back**. The X32 can; not every desk can. An adapter that cannot confirm
leaves requests at `device_acknowledged` — the performer reads "console
answered", never "done".

## The simulator

`SimulatorAdapter`: one send level per (mix, source), moved by a bounded
delta, clamped to the console's range, read back after every write. Three
switches on the bridge page rehearse the failures the desk must survive:
take the console offline (mode falls back to Request), refuse the next
write (the request reads *failed* with the reason), and stop confirming
writes (the request stops at *device acknowledged*).

There is no daemon for the simulator; the web process is its bridge for one
cycle whenever the desk sends or the page's **Pulse** button is pressed
(`stage_bridge.run_local`). `run_local` refuses any adapter whose spec is
not `simulated` — a real console is driven from a real bridge on the venue
network, never from the web process. Levels live in one worker's memory;
the acknowledgements in `stage_commands` are the durable record.

## The X32 adapter — UNTESTED, bench only

`stage_x32.py` speaks the community-documented OSC remote protocol (UDP
10023): `/ch/NN/mix/MM/level` in the desk's own fader law and
`/ch/NN/mix/MM/on`, nothing else. It reads every write back, which is what
lets a change be *confirmed* on this desk. It is **not** in
`stage_adapters.ADAPTERS`. It is a bench adapter: reachable only with
`STAGE_BENCH_ADAPTERS=1` on the machine running it, labelled UNTESTED on
every screen that names it, and it graduates only when:

1. `STAGE_BENCH_ADAPTERS=1 python tools/x32_bench.py --host <desk ip>
   --channel 32 --bus 16` prints **ALL PASSED** on a spare channel and bus;
2. a person writes the model and firmware it printed into
   `X32Adapter.SPEC.tested_model` / `tested_firmware`, sets `verified` to
   True, and moves the class into `ADAPTERS` — in a commit that says who ran
   the bench and when.

The patch map (mix bus and channel per passport name, plus the desk's IP)
is set on the bridge page and stored on the device; the daemon reads it
from the same JSON.

## Running the bridge daemon

```
python tools/stage_bridge_daemon.py --server https://street-banker.onrender.com \
    --token <device token> --key <signing key> --adapter simulator

STAGE_BENCH_ADAPTERS=1 python tools/stage_bridge_daemon.py ... \
    --adapter x32 --host 192.168.1.10 --patch patch.json
```

Standard library only. Heartbeat → reconcile what is owed → pull → verify
(signature, expiry, nonce) → apply → ack, every `--interval` seconds.
Acknowledgements it cannot deliver wait in `instance/stage-bridge-queue.json`
and go out through `/bridge/reconcile` when the link returns. A `revoked`
answer stops it; a `lockout` answer applies nothing.

## Writing a bridge (for a real console, later)

A bridge is a small daemon that:

1. holds its token and signing key in local secure storage;
2. every few seconds POSTs `/bridge/heartbeat` with its adapter's health;
3. POSTs `/bridge/pull`, verifies each command (signature, expiry, nonce),
   applies it through the adapter, reads the value back, and POSTs
   `/bridge/ack` with `confirmed` set honestly;
4. keeps acknowledgements it could not deliver and POSTs `/bridge/reconcile`
   when the link returns;
5. treats `lockout: true` or `revoked: true` in any response as a stop;
6. never exposes the console to anything but itself.

The Stage Rack appliance the brief describes is this daemon on dedicated
hardware. It does not exist yet and nothing here says it does.

## Runbook

* **The desk says Request Mode with a reason** — read the reason: revoked,
  lockout, disarmed, stale heartbeat, adapter fault. Fix that; the mode
  recomputes on the next poll.
* **A request sits at *sent*** — the desk poll expires it after
  `command_ttl_s`; it reads *timed out* to the performer.
* **A request reads *console answered* and never *done*** — the adapter did
  not confirm the write. That is the truth; apply on the desk if needed.
* **Feedback on stage** — EMERGENCY LOCKOUT on the bridge page. Everything in
  flight is refused. Release, then arm, when it is safe.
* **A device is lost or compromised** — Revoke. Register a new one.
* **Audit** — every issue, refusal, send, acknowledgement, lockout, rotation
  and revocation is in `stage_events`, in order, with the cursor.

## Tests

```
python -m pytest tests/test_stage_adapters.py tests/test_stage_safety.py \
  tests/test_stage_bridge.py tests/test_stage_bridge_routes.py
```

## Known limitations and what validation is still required

* No real console adapter exists. Writing one (X32 first, per the owner) is
  the next milestone; it must ship with `tested_model` and
  `tested_firmware` filled in from a real bench test, not from documentation.
* Permissions are single-owner: the account that owns the passport
  attachment is the engineer. The brief's role list (operate connected
  control, configure bridge, arm, lock, emergency lockout) maps onto partner
  roles later, through `partner_os.require()`.
* The simulator's levels are per web worker. The record is the database.
* Guest / QR access for performers is still the signed-in page.
