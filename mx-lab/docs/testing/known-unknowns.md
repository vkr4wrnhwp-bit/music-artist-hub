# MX LAB — Known Unknowns and Physical-Verification Backlog

Purpose: The authoritative list of everything MX LAB does not know and must not assume — each item with its verification path. Nothing here may be treated as resolved without evidence attached to the relevant ECUDefinition or inventory record.

Status: Phase 1 — all items open. This list gates every hardware phase.

---

Verification methods used below:

- **PI** — Physical inspection (on the actual bike/unit, recorded with photos and inspector identity)
- **VDR** — Vortex documentation request (official documentation obtained from Vortex)
- **BT** — Bench test (on the bench fixture, `docs/cnc/bench-fixture-brief.md`)
- **SBI** — Sanctioning-body inquiry (written, recorded per body/series/season)

## 1. Vortex ECU identity and firmware

| # | Unknown | How to verify |
|---|---|---|
| 1.1 | Exact Vortex ECU model fitted to each team bike (per bike, never per fleet) | PI — read unit labels, photograph, record in inventory |
| 1.2 | Firmware version/label per unit, and whether it is externally readable at all | PI + VDR |
| 1.3 | Whether nominally identical units differ (hardware revs, region variants) | PI across all units + VDR |
| 1.4 | Behavior differences across YZ250F vs YZ450F Vortex offerings and across model years | VDR + PI per bike/model year |

## 2. Data output and connectivity

| # | Unknown | How to verify |
|---|---|---|
| 2.1 | Whether a data connector/output exists on the fitted units at all | PI |
| 2.2 | Connector type, location, and pinout (no pinout is assumed, none is documented here) | PI + VDR; BT for pin-by-pin characterization only after PI |
| 2.3 | Whether the output is CAN, a proprietary stream, or something else; electrical characteristics | VDR + BT (listen-only) |
| 2.4 | Whether passive listening is possible without disturbing ECU operation (bus load, termination, error behavior) | VDR + BT fault-injection, then on-bike verification per model year |
| 2.5 | Mating connector identification (no part numbers invented; identified from physical units) | PI + VDR |

## 3. Telemetry channels

| # | Unknown | How to verify |
|---|---|---|
| 3.1 | Which channels the ECU exposes (list), if any | VDR + BT |
| 3.2 | Sample rates, units, scaling, and encoding per channel | VDR + BT characterization |
| 3.3 | Whether channel content differs engine-off (bench) vs engine-running (bike) | BT vs on-bike comparison per model year |
| 3.4 | Whether the handlebar map/trim switch state is visible in any telemetry | VDR + BT + on-bike test |

## 4. Maps, slots, and files

| # | Unknown | How to verify |
|---|---|---|
| 4.1 | Map file format(s) used by official Vortex software; whether files are externally documented or parseable with authorization | VDR (includes the licensing question, Section 7) |
| 4.2 | Map table semantics: axes, resolution, units, trim interaction | VDR; BT round-trip via official software only after documentation |
| 4.3 | Slot/map-selection model: how many slots the fitted units actually have, how switching works, persistence across power cycles | VDR + PI + BT — never assumed from marketing or other Vortex products |
| 4.4 | Checksum/integrity mechanisms in map files and in-ECU storage | VDR + BT |
| 4.5 | What official Vortex software reports about a connected ECU (read-back visibility usable for Phase 3 confirmation records) | PI of the official-software workflow + VDR |

## 5. Physical installation (per bike model AND model year — YZ250F and YZ450F are separate designs)

| # | Unknown | How to verify |
|---|---|---|
| 5.1 | ECU physical location and access on each model year | PI |
| 5.2 | Mount candidate geometry: airbox area, under-seat, steering-stem envelopes and hardpoints | PI — mount survey per `docs/cnc/mount-yz250f.md` / `docs/cnc/mount-yz450f.md`; all dimensions TBD — measure on bike, per model year |
| 5.3 | Heat exposure at candidate locations (peak/sustained) | PI — instrumented ride per model year |
| 5.4 | Mud/water/pressure-wash exposure at candidate locations | PI — post-ride and post-wash inspection |
| 5.5 | Cable routing paths and clearance at full suspension travel / full steering lock | PI per model year |
| 5.6 | Power tap points, if node ever draws bike power: circuit, fusing, load headroom | PI + wiring inspection per model year; BT for tap protection design; node stays self-powered until verified |
| 5.7 | Sensor mounting geometry (wheel-speed target options, fork/shock sensor packaging, GPS sky view) | PI per model year |

## 6. MX Node design inputs

| # | Unknown | How to verify |
|---|---|---|
| 6.1 | Vibration spectrum at candidate mount points (drives isolator selection) | PI — instrumented measurement per model year |
| 6.2 | Realistic session data volume (drives storage sizing) | BT with simulated rates now; revise after 3.2 resolves |
| 6.3 | Between-moto turnaround window available for dock workflow | Team process observation (record as evidence) |
| 6.4 | Node battery runtime under race-day duty cycle | BT once hardware exists |

## 7. Legal and licensing

| # | Unknown | How to verify |
|---|---|---|
| 7.1 | Whether Vortex authorizes third-party reading of ECU data, and under what terms | VDR — written inquiry; legal review of the response |
| 7.2 | Whether any interoperability work (even passive characterization) has licensing or terms-of-use constraints | Legal review + VDR |
| 7.3 | Terms required for any future Phase 4 authorization (see gate 1 in `docs/vortex/future-direct-integration-plan.md`) | VDR — written authorization is the only acceptable evidence |
| 7.4 | Warranty implications of any tap or fixture work on team-owned ECUs | VDR + legal review |

## 8. Competition rules (per sanctioning body, per series, per season)

COMPETITION USE REQUIRES APPROVAL FROM THE APPLICABLE SANCTIONING BODY. SOFTWARE CONFIGURATION DOES NOT ESTABLISH LEGALITY.

| # | Unknown | How to verify |
|---|---|---|
| 8.1 | Whether onboard data logging is permitted in each series entered, and with what constraints | SBI per body/series/season; record per `docs/hardware/competition-mode.md` |
| 8.2 | Which sensors are permitted per series | SBI |
| 8.3 | Whether any radio hardware may be present even when disabled, or must be absent | SBI |
| 8.4 | Whether live pit telemetry is ever authorized, and the authorization process | SBI — written only |
| 8.5 | GPS usage rules per series | SBI |
| 8.6 | Hardware inspection expectations (what officials will want to see) | SBI |
| 8.7 | Rule changes per season (standing re-verification item) | SBI at the start of every season |

## 9. Process rules for this list

- Every resolved item requires: evidence reference, verifier identity, date, and the affected ECUDefinition/inventory/approval record updated. Resolution is audited.
- An item resolved for one ECU unit, bike model, or model year is **not** resolved for any other.
- New unknowns discovered during verification are added here before work proceeds past them.
- No design may be released to fabrication, and no hardware may be installed on a bike, while a blocking item for it remains open.
