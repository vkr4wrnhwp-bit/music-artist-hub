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
| The safety engine (`stage_safety.py`) with a per-show policy | — |
| Partner roles for the stage rooms (`stage_review` / `stage_operate` / `stage_configure` / `stage_lockout`) | — |
| The bridge page, the desk in Connected Control, the device endpoints | — |
| QR / guest performer access, as a TOUR share link with scope `stage` | — |

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
| POST | `/bridge/heartbeat` | `{"health": {"ok": true, "detail": "…"}, "software_version": "…"}` plus, optionally, the rack fields `adapter_status`, `console_connected`, `probe`, `last_update` (phase 7; a daemon that omits them is still answered) | armed / lockout / revoked flags, `heartbeat_stale_s` |
| POST | `/bridge/pull` | — | queued commands, now marked sent |
| POST | `/bridge/ack` | `{"command_id", "nonce", "result": {"ok", "before", "after", "confirmed", "failure"}}` | `code`: applied / unconfirmed / failed / expired / replayed |
| POST | `/bridge/reconcile` | `{"entries": [ack bodies…]}` | one code per entry |

A bridge that lost the internet keeps its acknowledgements locally and posts
them to `/bridge/reconcile` when it is back; re-posting is safe.

## Registering a device

Stage Control desk → **Stage Bridge →** → Register. The token is shown once
and stored only as a SHA-256 hash; the signing key is shown with it. Both
are handed to that one page through the session, never through the URL, so
neither lands in a proxy log or a browser history (phase 7 finding). Rotate
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

## The Stage Rack status surface

Phase 7. `stage_rack.status(show, owner)` computes, for the registered
device, every field the brief's STAGE RACK list names: identity (id, name,
and a **fingerprint** - the first eight hex of the stored token hash, never
the token), ownership (TOUR id, owner), network health, console connection,
adapter status, software version, last update, last heartbeat, armed state,
emergency lockout, remote-revocation state. It is drawn on the bridge page
as a panel of LCDs with a lamp lit only for a state a person must act on
(`stage_rack.LAMPS`), and exported by
`GET /stage/<show>/bridge/diagnostics.json` (owner or `stage_configure`)
with the last 50 events and 20 commands, every secret column stripped.

**Network health is defined once**, in the safety engine:
`stage_safety.heartbeat_state()` answers *online* within
`heartbeat_stale_s`, *stale* up to `offline_after_s` (six stale windows,
never under 120 s), *offline* past that, and `None` - shown as *Not
measured* - before any heartbeat. The engine's `device_stale` refusal and
the rack's lamp read the same function, so the panel can never say online
while the engine refuses, or the reverse.

The daemon sends the rack fields on every heartbeat (`adapter_status`,
`console_connected` from the adapter's `probe()`, `software_version` =
`VERSION`, `last_update`) and prints the same status locally with
`--diagnostics`. A daemon that predates these fields is still accepted and
the panel reads *Not reported* for what it did not say.

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

`ConsoleAdapter.bound_step()` is the **third** bound on a level change,
after the request vocabulary and the safety engine: an adapter refuses a
delta beyond its own `limits.max_step_db` even if both layers above it were
bypassed (phase 7). `probe()` is a cheap, read-only reachability check for
the rack panel; the base answers "cannot tell", the simulator answers from
its offline switch, and the X32's is one `/info` query that refuses to run
without `STAGE_BENCH_ADAPTERS=1`.

A **revert** restores what the console read back, not what was asked:
`issue(is_revert=True)` takes the acknowledged `before`/`after` of the
applied command and sends their difference (a +3 clamped at the top of the
fader to +1 is reverted by −1). Only an acknowledgement with no numbers
falls back to the inverse of the requested step.

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

## Who may do what

The account that owns the show's passport attachment holds everything. A
seat at the partner that owns that account (see `partner_store.PERMS`)
opens the rooms with the permission its role carries, and every non-GET
act by a seat is written to `partner_audit` as `stage.<permission>`:

| Permission | Roles | Opens |
| --- | --- | --- |
| `stage_review` | owner, admin, manager, support | the desk, the performer page, acknowledge / modify / approve / done-on-the-desk / reject, locks |
| `stage_operate` | owner, admin, manager | send an approved request to the console, revert a console change |
| `stage_configure` | owner, admin | the Stage Bridge page and every action on it except lockout |
| `stage_lockout` | every role | EMERGENCY LOCKOUT, from the desk or the bridge page |

Anybody without a seat at the owning partner is a 404. A seat without the
permission is a 403. Guest performers use share links (below), which carry
no account at all.

## The TOUR date

A show is a TOUR date. Its page has a **Stage Control** fold inside
Advance: attach a published Show Passport (the version in force at that
moment, stored by id), see when a newer version exists (a notice — the
date keeps what the crew was handed until you attach again on purpose),
detach while the advance is still open, and open the Engineer Desk, the
Stage Bridge and the performer QR from there. The desk links back.

## Performer access by QR

A performer opens their page from a phone with no account. The link is a
**TOUR share link** with scope `stage` — `tour_share_links` already had
opaque, revocable, expiring, show-scoped, optionally passworded tokens, so
there is no second token table and no second admin page. On the tour's
Share page: *What* → Stage Control, pick the date, optional password and
expiry, Create. Every live link shows its QR there
(`/tours/<tour>/share/<link>/qr.svg`); print it for the green room.

The phone opens `/tour-share/<token>` (TOUR's password form first, if
set) and lands on the performer page at `/stage/guest/<token>`, which
posts to `/stage/guest/<token>/ask` and polls `/stage/guest/<token>/events`.
The token is checked on every call: scope, revoked, expired against the
tour's home time zone, password session. Requests are scoped to the tour
owner's account, exactly as they are from the owner's own session.

The desk's *Performer access* panel points at the tour's Share page when
the show is a TOUR date, and says so when it is not.

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

## Quick answers (desk says…)

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

## Operating runbook

Phase 7. Everything below is for the person at front of house, or the one
on the phone with them. The **Stage Rack panel** is the section of the
bridge page headed *Stage Rack · status*; every reading on it is computed
from what the device last said (`stage_rack.status`), and every threshold
it uses is the safety engine's own.

### 1. Install the daemon on a venue laptop

The daemon is `tools/stage_bridge_daemon.py`, standard library only. On the
laptop that sits on the venue's production network:

1. Install Python 3.10 or later. Copy the repository, or just `tools/`,
   `stage_adapters.py` and (for the X32) `stage_x32.py`.
2. Make a folder for the local queue; the default is `instance/` next to
   the repository. It holds acknowledgements the daemon could not deliver.
3. Keep the laptop on the same network segment as the console and on a
   separate path to the internet (a phone hotspot is fine). The daemon calls
   out; nothing calls in, and no port is opened.
4. Put the token and signing key somewhere only that user can read (the
   OS keychain, or a file with owner-only permissions); pass them as
   `--token` and `--key`. They never go in a script somebody will commit.

### 2. Register a device

On the bridge page (`/stage/<show>/bridge`, owner or a seat with
`stage_configure`): name the device, pick the adapter, **Register**. The
page that follows is the only place the token and signing key are ever
shown. Copy both to the laptop, then start the daemon:

```
python tools/stage_bridge_daemon.py --server https://<host> --token <token> --key <key> --adapter simulator
```

Within a few seconds the panel's *Network* LCD reads **online**, *Software*
reads the daemon's version (`daemon-0.2`), and *Console* reads
**connected** if the adapter's probe answered.

Check what the daemon sees on its own side, without a server:

```
python tools/stage_bridge_daemon.py --server x --token x --key x --adapter simulator --diagnostics
```

It prints the same status a heartbeat would carry (health, probe, adapter
declaration, version, queued acknowledgements) and exits. It never prints
the token or key.

### 3. Arm

**Arm the show** on the bridge page. Arming is refused during a lockout.
The desk banner switches to *Connected Control* only when, right now, the
device is registered, not revoked, not locked out, armed, has answered a
heartbeat within `heartbeat_stale_s`, and its last health report was ok.
Anything else is Request Mode with the reason on the banner.

### 4. Emergency lockout

**EMERGENCY LOCKOUT** is on the desk and on the bridge page, and every seat
may press it. It is immediate: the device is disarmed, everything queued or
sent is refused (those requests read *failed*), and the daemon's next pull
returns `lockout: true` with no commands. It stays on until **Release
lockout** is pressed on purpose. Releasing does **not** re-arm; arm again
when it is safe. The console itself is untouched throughout - the engineer
keeps the physical desk.

### 5. Revoke

**Revoke device** when a laptop is lost, a token may have leaked, or the
night is over. Final: the token authenticates nothing, queued commands are
rejected, the daemon stops itself on its next heartbeat, and the show is in
Request Mode. Register a new device to continue.

### 6. Rotate credentials

**Rotate credentials** issues a new token and a new signing key together,
shown once on the page that follows. Anything queued under the old key is
expired, not left to fail on the device. Restart the daemon with the new
pair. Rotate at the start of a run, after any crew change, and whenever a
credential has been on a screen somebody else could see.

### 7. What each lamp on the Rack panel means

A lamp lights only for a state a person must act on. No lamp lit is the
good state; the LCDs carry the readings.

| Lamp | Means | Do |
| --- | --- | --- |
| **Revoked** | The device's credentials were revoked. | Register a new device. |
| **Emergency lockout** | The lockout is on. | Fix what caused it; Release; Arm. |
| **Offline** | No heartbeat for longer than `offline_after_s` (six stale windows, never less than 120 s). | Check the laptop, its power, its internet path; run `--diagnostics` on it. |
| **Heartbeat stale** | No heartbeat within `heartbeat_stale_s`; the show is already in Request Mode. | Same as offline; the panel returns to online on the next heartbeat. |
| **Console unreachable** | The daemon's probe could not reach the desk. | Check the console's network, the host address in the patch map, and that the desk is on the same segment. |
| **Adapter UNTESTED** | The device runs a bench adapter that has not passed on real hardware. | Do not use it with an audience. Run the bench (section 9). |
| **Disarmed** | Registered and answering but not armed. | Arm when the room is ready. |

### 8. When the panel says stale or offline

The show is in Request Mode already; nothing you do here can move audio.
In order:

1. Read the *Last heartbeat* LCD: an age in seconds, or *Not measured* if
   the device has never answered (then it was never started, or it has the
   wrong server or token).
2. On the laptop: is the daemon running? Its log says `offline:` with the
   error when it cannot reach the server, and `revoked or refused` when its
   token is dead.
3. `--diagnostics` on the laptop: does the adapter's probe reach the desk?
4. If the laptop lost the internet mid-show, do nothing to the queue file.
   When the link returns the daemon posts what it owes to
   `/bridge/reconcile`; acknowledgements that arrive after a command's
   expiry settle as *expired*, never as *applied*.
5. The desk keeps working as Request Mode throughout. Apply on the console
   by hand and press **Done on the desk**.

### 9. The X32 bench, and what graduation requires

The X32 adapter is reachable only with `STAGE_BENCH_ADAPTERS=1` in the
environment of the process that uses it (the daemon on the laptop, and the
web process if you want to *register* an X32 device). On a spare channel
and a bus nobody is wearing:

```
STAGE_BENCH_ADAPTERS=1 python tools/x32_bench.py --host <desk ip> --channel 32 --bus 16
```

It reads the level, moves it a bounded step, **reads it back**, puts it
back, mutes and unmutes, and prints PASS/FAIL per step and the desk's
model and firmware. The adapter graduates only when:

1. every step prints PASS and the result line reads **ALL PASSED**;
2. a person writes the printed model and firmware into
   `stage_x32.X32Adapter.SPEC["tested_model"]` / `["tested_firmware"]`,
   sets `"verified": True`, and moves the class into
   `stage_adapters.ADAPTERS`;
3. the commit says who ran the bench, on which desk, on what date;
4. `tests/test_stage_adapters.py::test_no_real_console_is_claimed` is
   updated in the same commit to name the new registry entry.

Until then every screen that names the adapter says UNTESTED, the
*Adapter UNTESTED* lamp is lit, and the adapter's `probe()` refuses to
run without the flag.

## Deployment validation

Run before the first show on a new deployment, and again after any change
to `stage_*.py`, the daemon, or the policy bounds.

- [ ] `python -m pytest tests/test_stage_acceptance.py tests/test_stage_security.py tests/test_stage_safety_review.py tests/test_stage_*.py tests/test_passport*.py tests/test_tour_stage_link.py -q` is green.
- [ ] `tests/test_stage_adapters.py::test_no_real_console_is_claimed` still lists only the adapters that have passed a bench.
- [ ] `STAGE_BENCH_ADAPTERS` is **unset** on the web host unless an X32 device is being registered on purpose.
- [ ] `SESSION_COOKIE_SECURE` is on (it follows `RENDER`), and the site is HTTPS end to end - the device token travels as a Bearer header.
- [ ] Register a simulator device on a throwaway show; the token page shows once; the URL carries no token; reload shows nothing.
- [ ] Arm; press **Pulse**; the desk reads *Connected Control · SIMULATED*; the Rack panel reads online / connected / `local-1.0`.
- [ ] Submit a request from the performer page, approve, send: the request reads *Done* and the command *applied* with a `confirmed: true` acknowledgement.
- [ ] **Take the console offline** on the simulator: the desk falls back to Request Mode with the reason.
- [ ] **EMERGENCY LOCKOUT**: everything in flight reads *failed*; **Release** leaves the show disarmed.
- [ ] **Rotate**: a new token page; the old token is 401 on `/bridge/heartbeat`.
- [ ] **Revoke**: 401 for the device; the bridge page offers registration.
- [ ] `GET /stage/<show>/bridge/diagnostics.json` answers for the owner, 403 for a manager seat, 404 for a stranger, and contains no `signing_key`, `token_hash` or `signature` key.
- [ ] A TOUR share link with scope *stage* opens the performer page on a phone with no session; revoking the link makes every guest route 404.
- [ ] Policy form: `max_step_db` 9 is refused; 2 is stored and the desk refuses a 3 dB send with *delta_out_of_bounds*.
- [ ] The daemon on a real laptop: `--diagnostics` prints, then a normal run shows *online* on the panel within one interval.

## Tests

```
python -m pytest tests/test_stage_acceptance.py tests/test_stage_security.py \
  tests/test_stage_safety_review.py tests/test_stage_*.py \
  tests/test_passport*.py tests/test_tour_stage_link.py -q
```

`test_stage_acceptance.py` is the brief's ACCEPTANCE CRITERIA, one test per
bullet; `test_stage_security.py` and `test_stage_safety_review.py` are the
phase 7 reviews as tests; `test_stage_rack.py` the status surface;
`test_stage_performance.py` the poll's bound. See
[STAGE_CONTROL_PHASE7.md](STAGE_CONTROL_PHASE7.md) for what phase 7 verified
and what is still open.

## Known limitations and what validation is still required

* No *verified* console adapter exists. The X32 adapter is written but
  UNTESTED; it graduates only through the bench run described in the
  runbook above, with `tested_model` and `tested_firmware` filled in from
  that run, not from documentation.
* The Stage Rack appliance does not exist. Its status surface does
  (`stage_rack.py`, the panel on the bridge page, the diagnostic export);
  the hardware is a separate validation.
* The simulator's levels are per web worker. The record is the database.
* There is no CSRF token anywhere in the app; Stage Control's posture is the
  app's (SameSite=Lax session cookie, login wall, Bearer-only device door).
  `tests/test_stage_security.py::test_csrf_posture_matches_the_rest_of_the_app`
  fails the day a token exists so the forms here get wired to it.
* Permissions and guest access, listed as limitations in the first draft of
  this document, have both shipped: see *Who may do what* and *Performer
  access by QR* above.
