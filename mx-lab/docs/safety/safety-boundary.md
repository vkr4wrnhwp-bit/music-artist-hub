# MX LAB — Safety Boundary

Purpose: Define the safety architecture that separates MX LAB from engine control, the phase model that governs any future ECU interaction, and the hard limits on the AI Race Engineer.

Status: Phase 1 — simulation only. This document is normative for all phases.

---

## 1. Core boundary

MX LAB and all associated hardware (MX Node, pit dock, sensors) are **passive**. Nothing in this system controls fueling, ignition, throttle, map slot selection, or any engine behavior — in any phase currently authorized. The motorcycle must run identically whether MX LAB hardware/software is present, absent, powered, unpowered, or failed.

Direct ECU writing is a Phase 4 concept only, and Phase 4 is **DISABLED** until every gate in `docs/vortex/future-direct-integration-plan.md` passes.

## 2. Mandatory write-control label

Every UI control that could ever relate to writing to an ECU (including the disabled `FutureFlashJob` surface) must display, verbatim:

> **DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED**

This label may not be abbreviated, restyled into ambiguity, or hidden behind hover states. It renders wherever the control renders.

## 3. Phase model

| Phase | Name | ECU interaction | Status |
|---|---|---|---|
| 1 | Simulation | None. All data simulated and labeled SIMULATED. | Current |
| 2 | Passive read-only logging | Read/observe only, via verified passive tap. No transmission to ECU. | Future — gated on physical verification |
| 3 | Companion workflow | None by MX LAB. Tuner performs all changes in official Vortex software; MX LAB documents and tracks them (external programming confirmation). | Future |
| 4 | Authorized direct integration | Write, only after all Phase 4 gates pass. | DISABLED |

## 4. Separation of concerns

These four functions are architecturally separate and must never be merged into a single code path or UI surface:

1. **Passive telemetry reading** — ingest and display of logged data. Read-only by construction.
2. **Map-file management** — versioning, review, and approval of map artifacts as documents. Managing a map file confers no ability to apply it.
3. **External programming confirmation** — a human records that a change was applied using official Vortex software. MX LAB records the claim, the actor, and the evidence; it performs nothing.
4. **Future authorized writing** — exists only as a disabled schema (`FutureFlashJob`, status `DISABLED`). No transport, no implementation.

## 5. AI Race Engineer — may-never list

The AI Race Engineer is a rule-based recommender. It may **never**:

- Auto-approve any map, setting, or recommendation.
- Auto-flash, transmit, or trigger any write to any device.
- Invent "safe envelopes," limits, or operating ranges not provided by a verified source.
- Override, modify, or re-rank a tuner's decision.
- Present unvalidated values as safe, verified, or recommended-as-safe.
- Satisfy any readiness or compatibility gate by inference, estimation, or pattern-matching.
- Claim horsepower, performance, or safety outcomes without validated measurement data.

Every AI output is a `Recommendation` object that requires explicit human review before it can influence any workflow state. Recommendations carry provenance and the rule identifiers that produced them.

## 6. Readiness gates

- Gates are satisfied only by recorded evidence: a named human confirmation, a verified inventory record, or validated measurement data.
- **Readiness gates cannot be satisfied by AI inference.** The gate engine rejects any satisfaction event whose actor is not a human principal or a verified data source.
- Gate satisfactions are audited (actor, timestamp, evidence reference) and are never silently overwritten (see conflict policy in `docs/architecture/overview.md`).

## 7. Failure-mode analysis (normative requirement)

Design rule for all phases: **failure of any MX LAB component must have no effect on engine operation.**

| Failing component | Required behavior of the motorcycle |
|---|---|
| MX Node logger (hang, brownout, firmware fault) | No effect. Node input interface is electrically passive with no back-feed path (see `docs/hardware/mx-node-brief.md`). |
| App / PWA (crash, corrupt storage) | No effect. App never connects to the bike while it runs; Phase 1 has no bike connection at all. |
| Cable / harness tap (open, short, chafe) | No effect on ECU operation is the design target: fused, current-limited, isolated tap. Physical verification required per model year before any Phase 2 install. |
| Pit dock | No effect. Dock touches the node only, never the bike. |
| GPS receiver | Logging degrades (sync quality drops); engine unaffected. |
| IMU | Logging degrades; engine unaffected. |
| Any optional sensor (wheel speed, clutch, suspension) | Channel marked Missing/Intermittent; engine unaffected. Sensors are additive instrumentation only, never in series with any OEM control circuit. |
| MX LAB software defect (any layer) | No effect possible in Phases 1–3: no write path exists. Phase 4 remains disabled until gated validation. |

Any design change that could violate this table is a safety regression and is rejected at review.

## 8. Human review requirement

Every recommendation, every map state transition, every gate satisfaction, and every conflict resolution requires a named human actor. The audit log is the enforcement record; an action without a human actor in the audit trail is a defect.
