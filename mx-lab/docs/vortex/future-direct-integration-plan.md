# MX LAB — Future Direct Integration Plan (Phase 4)

Purpose: Specify the gate checklist, recovery requirements, bench validation outline, and the disabled `FutureFlashJob` schema for the only phase in which MX LAB could ever write to a Vortex ECU.

Status: Phase 4 — DISABLED. Nothing in this document is implemented. This is a specification of preconditions, not a commitment to build.

---

## 1. Standing state

Direct ECU integration is **DISABLED**. All related UI carries, verbatim:

> **DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED**

Phase 4 work may not begin, and the disabled state may not be lifted, until **every** gate below passes, with evidence recorded in the audit log. Gates are conjunctive — all must pass; there is no override.

## 2. Phase 4 gate checklist

| # | Gate | Pass criteria | Evidence |
|---|---|---|---|
| 1 | Written authorization | Written authorization from Vortex (and any other rights holder) covering the specific integration | Signed document on file |
| 2 | Verified protocol documentation | Official, versioned protocol documentation for the exact ECU model + firmware, obtained from Vortex — not reverse-engineered, not inferred | Document reference in ECUDefinition evidence |
| 3 | Bench validation | Full bench protocol (Section 4) passed on the bench fixture for the exact ECU model + firmware | Bench logs, operator, procedure version |
| 4 | Recovery strategy | Demonstrated recovery path from a failed/interrupted write (Section 3) | Recovery drill records |
| 5 | Checksum validation | Integrity/checksum scheme for map data understood, implemented, and verified against official Vortex software output | Comparison records |
| 6 | Power-loss testing | Write interrupted by power loss at multiple points; ECU recoverable in every case using the documented recovery strategy | Test matrix results |
| 7 | Read-back verification | Every write followed by full read-back and byte-level comparison; mismatch aborts and flags | Implementation + bench proof |
| 8 | Legal review | Counsel review of the integration (licensing, liability, warranty implications) completed | Review record |
| 9 | Competition-rule review | Per-sanctioning-body review for every series the team enters | Records per body (see `docs/hardware/competition-mode.md`) |

Gate status is tracked per ECUDefinition (model + firmware + bike model year). Passing gates for one configuration authorizes nothing for any other configuration.

## 3. Recovery strategy requirements

Before any write capability is enabled, the following must exist and be drilled:

- A documented, Vortex-supported procedure to restore a known-good state after a failed or interrupted write (target to validate: whether official Vortex software provides such a path — requires verification with Vortex).
- A verified known-good baseline captured and stored (with checksum and provenance) before every write session.
- Confirmation of what happens to the ECU mid-write (target to validate: bootloader behavior, brick risk) — from Vortex documentation, never assumed.
- A spare, verified ECU available at the bench during all validation work.
- An abort path at every step that leaves the ECU in a defined state, or a documented recovery from any undefined state.

## 4. Bench validation protocol (outline)

Executed on the bench fixture (`docs/cnc/bench-fixture-brief.md`), never first on a bike, never with a running engine:

1. Inventory: record ECU model label, firmware label, harness configuration; photograph.
2. Baseline capture: read full state (per documented protocol), checksum, store with provenance.
3. Read-path validation: repeated reads are byte-identical; documented channels match documented meanings.
4. Write-path validation on expendable/spare unit only: write documented test payloads; read back; compare.
5. Fault injection: power loss at staged points during write; connector disturbance; verify recovery per Section 3.
6. Round-trip with official Vortex software: changes made by MX LAB are readable and correct in official software, and vice versa.
7. Regression: repeat after any firmware or tooling change. Bench results bind to exact model + firmware labels only.

## 5. FutureFlashJob design

The schema exists in Phase 1 so the workflow, audit, and UI seams are real — the capability is not.

```ts
interface FutureFlashJob {
  id: string;
  status: "DISABLED";               // literal type: no other value exists in Phase 1–3
  message: "AUTHORIZED DIRECT ECU INTEGRATION HAS NOT BEEN IMPLEMENTED";
  // Fields below are schema-only placeholders; nothing populates or executes them.
  targetEcuDefinitionId?: string;
  approvedMapId?: string;           // would require Team Approved map + all Section 2 gates
  gateChecklistRef?: string;        // reference to the Phase 4 gate evidence bundle
  createdBy?: string;               // human actor only; AI can never create a flash job
  auditRef?: string;
}
```

Rules:

- `status` is the literal `"DISABLED"`; there is no state machine and no transition function in Phases 1–3.
- No transport layer, driver, or protocol code may exist in the repository while Phase 4 is disabled.
- Any UI that surfaces a `FutureFlashJob` displays the Section 1 label and the `message` string verbatim.
- The AI Race Engineer has no permission to reference, create, or recommend flash jobs (see may-never list in `docs/safety/safety-boundary.md`).
