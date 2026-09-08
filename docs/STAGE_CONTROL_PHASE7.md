# Stage Control — Phase 7: production hardening

What phase 7 of [STAGE_CONTROL_BRIEF.md](STAGE_CONTROL_BRIEF.md) asked for
— security review, live-audio safety review, performance review,
accessibility review, tests, monitoring, documentation, deployment
validation, operational runbook — and what each produced. The Stage Rack
status surface (the brief's STAGE RACK list) was built in the same phase.
Written on the `stage-hardening` branch, 2026-09-07.

Read with [STAGE_CONTROL_BRIDGE.md](STAGE_CONTROL_BRIDGE.md), which carries
the runbook and the deployment checklist this phase added.

## What was verified

### The acceptance criteria — `tests/test_stage_acceptance.py`

One test per bullet of the brief's ACCEPTANCE CRITERIA, in the brief's
order. Status after this phase:

| Criterion | Status |
| --- | --- |
| A production team can create and publish a versioned Show Passport | pass |
| A show retains its assigned passport version | pass |
| A performer can submit a request from a mobile device | pass (TOUR share link, no account) |
| The request appears in realtime at the Engineer Desk | pass (event cursor; sockets ruled out in phase 1) |
| The engineer can acknowledge, modify, apply manually, reject, or approve it | pass |
| Request states remain accurate | pass (every logged hop is in `TRANSITIONS`) |
| The simulator adapter can process supported bounded commands | pass |
| Unsupported commands are rejected | pass — **fixed**: the command allowlist is now checked on the device side too (see findings) |
| Replayed and expired commands are rejected | pass |
| Stage Bridge can be revoked | pass |
| Emergency lockout immediately prevents connected commands | pass |
| Internet loss does not falsely report successful changes | pass |
| Request Mode remains usable without console integration | pass |
| Tenant isolation and role authorization are tested | pass |
| Existing Street Banker features continue working | pass (smoke: public pages, `/passports/`, `/tours`) |
| Setup, security, deployment, and operating documentation are complete | pass (this file, the runbook, the checklist) |

**Cannot be verified without hardware:** that any real console applies a
bounded command and reads it back. The only console bullet in the brief
names the simulator, which passes; the X32 adapter's bench run is an open
item below, not a failed criterion.

### Security review — `tests/test_stage_security.py`

Held: every `/bridge/*` endpoint is Bearer-only and answers a missing,
wrong or revoked token with the same 401 body; a session cookie opens
nothing there; the HMAC covers the canonical body and a one-byte change in
any field or in the signature is refused on the server and in the daemon;
extra keys do not alter the signature; a nonce cannot be reused (UNIQUE
column, replay refusal, daemon's seen-set); expiry is honoured at pull,
verify, ack, the desk poll and in the daemon; the request rate limit counts
open requests; a guest token is re-checked on all five guest routes for
scope, revocation, expiry and password; no page and no JSON echoes a token,
signing key or HMAC; the diagnostic export is redacted column by column.

CSRF: the app has no CSRF token anywhere (phase 1 audit). Stage Control
matches the app's posture — SameSite=Lax session cookie, login wall,
Bearer-only device door — and the test fails the day a token appears in
`app.py`, so the stage forms get wired to it.

### Live-audio safety review — `tests/test_stage_safety_review.py`

Held: a step is bounded at three layers — the request vocabulary, the
safety engine (on the requested and on the engineer's amount), and the
adapter; a tampered store row and a forged oversized command both fail to
move the simulator; mutes and unmutes exist only for the two kinds that name
them and only on an adapter that declares `mute_state`; a revert restores
the read-back value; lockout refuses everything in flight and releasing does
not re-arm; *stale* is defined once (`stage_safety.heartbeat_state`) and
drops the show to Request Mode at the same second the rack lamp lights.

### Performance — `tests/test_stage_performance.py`

The poll is `seq > ? ORDER BY seq LIMIT ?` on `idx_sevents_show(show_id,
seq)` (the query plan is asserted); `expire_stale`, which runs on every
poll, now has `idx_scmd_show_state`. A show with 5,000 events answers the
desk poll and the guest poll in under 200 ms through the test client, from
the cursor and from zero.

### Accessibility

`tests/test_stage_a11y.py` (phase 6) still holds for the rack panel: it is
built from the shared `sb.lcd` and `sb.lamp` instruments, every lamp
carries its word, the panel sits in a dark `sb-panel` with room ink, and
the design locks (`tests/test_design_system.py`, `test_template_markup.py`)
pass on the new CSS.

### Monitoring — the Stage Rack status surface

`stage_rack.py`, the panel on the bridge page, `GET
/stage/<show>/bridge/diagnostics.json`, the daemon's extended heartbeat and
`--diagnostics` flag. Every field on the brief's STAGE RACK list is exposed
(`tests/test_stage_rack.py`). A value the server has not measured reads
*Not measured*; one the daemon has not reported reads *Not reported*.

## Findings fixed in this phase

1. **The device token travelled in a URL.** Register and Rotate redirected
   to `/stage/<show>/bridge?token=<token>`, so the only credential that
   authenticates a machine able to move a fader landed in browser history
   and any proxy or server log. Now handed to exactly one render through
   the session (`stage_os._CREDS_KEY`); the redirect carries
   `credentials=once` and nothing else. Reloading shows nothing.
2. **The command allowlist was not checked on the device side.** A signed
   body naming any `command` was handed to the adapter, which would have
   raised for an unknown name — but by exception, not by policy.
   `stage_bridge.verify_for_device` and the daemon's `verify` now refuse
   anything outside `stage_adapters.WRITES` as `not_allowed`.
3. **No bound at the adapter layer.** `SimulatorAdapter.apply_send_delta`
   and `X32Adapter.apply_send_delta` applied any delta they were given, so
   the store and the safety engine were the only two bounds on a level
   change. `ConsoleAdapter.bound_step()` is the third; both adapters call it
   first.
4. **A revert used the requested step, not the read-back.** A +3 clamped at
   the top of the fader to +1 was reverted by −3 — a 2 dB jump below where
   the level started. `issue(is_revert=True)` now restores the acknowledged
   `before` from the desk's own before/after (`stage_bridge._revert_target`),
   and a mute revert restores the read-back mute state.
5. **A mute command dropped its source on the wire.** `issue()` blanked
   `source` for `mute_state`, so the simulator muted the empty source and an
   X32 would have refused with "No channel is patched for ''". The source
   now rides on every command.
6. **Two stale facts in STAGE_CONTROL_BRIDGE.md** — that permissions were
   single-owner and that guest access was still the signed-in page — were
   corrected; both shipped before this phase.

## Open items

* **Bench run on real hardware.** `tools/x32_bench.py` has not been run
  against an X32 or M32. Until a person runs it and records the model and
  firmware in `stage_x32.X32Adapter.SPEC`, the adapter is UNTESTED, is not
  in `stage_adapters.ADAPTERS`, and `test_no_real_console_is_claimed` holds
  that the registry has one entry. This is the testing gate the phase 1
  audit set; nothing in this phase lifts it.
* **The Stage Rack hardware.** The status surface exists; the appliance
  does not. Choosing, provisioning and validating a device (power, network
  segmentation, local secure storage for the token and key, watchdog) is a
  separate piece of work. The daemon's `--diagnostics` and the export are
  what that validation will read.
* **CSRF tokens** are a platform-level gap, not a Stage Control one; the
  posture is recorded and tested so the rollout finds these forms.
* **Realtime transport.** Polling stands (phase 1 decision). The
  performance test bounds it; a worker-class change would be the trigger to
  revisit.
* **Manual QA against the deployment checklist** in
  STAGE_CONTROL_BRIDGE.md has not been done on the hosted site by a person;
  the automated half is green.

## Files this phase touched

New: `stage_rack.py`, `docs/STAGE_CONTROL_PHASE7.md`,
`tests/test_stage_acceptance.py`, `tests/test_stage_security.py`,
`tests/test_stage_safety_review.py`, `tests/test_stage_rack.py`,
`tests/test_stage_performance.py`.

Changed: `stage_bridge.py` (report column, `REPORT_FIELDS`, heartbeat
report, device-side allowlist, revert from read-back, source on mutes,
`idx_scmd_show_state`), `stage_safety.py` (`heartbeat_state`,
`offline_after_s`), `stage_adapters.py` (`bound_step`, `probe`),
`stage_x32.py` (`probe`, bound), `stage_store.py` (`events_recent`),
`stage_os.py` (credentials through the session, diagnostics route, rack
context, heartbeat report), `tools/stage_bridge_daemon.py` (`VERSION`,
`ALLOWED_COMMANDS`, `local_status`, extended heartbeat, `--diagnostics`),
`templates/stage/bridge.html`, `static/css/stage-control.css` (`?v=11`),
`static/js/sw.js` (`sb-v213`), the existing stage tests that read the
token from the redirect.
