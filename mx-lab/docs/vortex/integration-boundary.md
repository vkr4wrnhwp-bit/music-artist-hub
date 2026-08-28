# MX LAB — Vortex Integration Boundary

Purpose: Define how MX LAB relates to Vortex programmable ECUs: Vortex-first in intent, with nothing Vortex-specific hardcoded and nothing assumed without physical verification.

Status: Phase 1 — simulation only. Every Vortex capability referenced here is a target to validate, not an established fact.

---

## 1. Ground rules

- No Vortex capability (data channels, bus type, map formats, connector pinouts, slot counts, protocols, part numbers) is stated as fact anywhere in MX LAB. All such items are **targets to validate** and **require physical verification** (see `docs/testing/known-unknowns.md`).
- ECU identity is **inventoried per bike, never assumed**. Two YZ450Fs on the same team may carry different Vortex units or firmware; the system treats them as distinct until verified otherwise.
- Model-year discipline: YZ250F and YZ450F, and each model year of each, are separate configurations. No capability, harness detail, or mount carries across without its own verification.

## 2. ECUDefinition — capabilities as data

Every bike record references an `ECUDefinition`. The UI and all engines are driven by this data structure; there is no Vortex behavior in code.

```ts
interface ECUDefinition {
  id: string;
  make: "Vortex" | string;          // inventoried, not assumed
  modelLabel: string;                // as read from the physical unit
  firmwareLabel?: string;            // as read; "unknown" until inspected
  bikeModel: "YZ250F" | "YZ450F";
  bikeModelYear: number;
  capabilities: CapabilityRecord[];
  verification: VerificationStatus;  // definition-level floor
  evidence: EvidenceRef[];           // photos, docs, bench logs
}

interface CapabilityRecord {
  kind: "telemetryChannel" | "mapTable" | "globalTrim" | "slotBehavior" | "fileFormat";
  name: string;
  detail: Record<string, unknown>;   // schema varies by kind
  verification: VerificationStatus;  // per-capability
  evidence: EvidenceRef[];
}
```

## 3. Verification statuses

Ordered ladder; a capability holds exactly one status and can only advance with recorded evidence:

| Status | Meaning | Evidence required |
|---|---|---|
| Unverified | Assumed, rumored, or copied from marketing. Default state. | None (this is the floor) |
| Physically Inspected | The unit/connector/label was examined on the actual bike. | Photos, inventory record, inspector identity |
| Documentation Verified | Official Vortex documentation confirms the capability. | Document reference obtained from Vortex |
| Bench Verified | Demonstrated on the bench fixture (`docs/cnc/bench-fixture-brief.md`), engine not running. | Bench log, test procedure, operator |
| Bike Verified | Demonstrated on the actual bike/model year. | On-bike test record |
| Team Approved | A named human (tuner/owner) approves the capability for team use. | Approval record in audit log |

Downgrades are allowed at any time (e.g. firmware change discovered → capability reverts to Unverified) and are audited.

## 4. Capability-driven UI

- A control renders **only** if the corresponding capability exists in the bike's ECUDefinition at the verification level the control requires.
- Anything at `Unverified` renders nothing — not a disabled control, nothing. Disabled-but-visible is reserved for capabilities that are verified but phase-gated (e.g. the Phase 4 write surface, which carries the mandatory label from `docs/safety/safety-boundary.md`).
- The simulator provides a synthetic ECUDefinition whose every capability is marked `Simulated` provenance, so Phase 1 UI is exercised without implying real verification.

## 5. Reading vs writing

These are different risk classes and are never conflated:

| | Reading (observing) | Writing (changing) |
|---|---|---|
| Risk | Data quality risk only, if the tap is passive | Engine behavior risk |
| Earliest phase | Phase 2 (passive read-only logging) | Phase 4 only |
| Precondition | Verified passive tap; failure-mode analysis per model year | Every gate in `docs/vortex/future-direct-integration-plan.md` |
| Current status | Not implemented; simulated only | DISABLED |

Phase 3 involves no MX LAB writing: the tuner performs changes in official Vortex software, and MX LAB documents the change via external programming confirmation.

## 6. What "verified" requires, per capability class

| Capability class | Verification requires (minimum, before Bench Verified can be claimed) |
|---|---|
| Telemetry channel | Physical confirmation the data output exists on this unit; documented meaning, unit, scaling, and rate from Vortex documentation or bench characterization; confirmation the tap is passive (no back-feed, no bus disturbance) |
| Map table | Documented table semantics (axes, units, resolution) from Vortex; confirmation of how the table is represented in exported/managed files; never inferred from file diffs alone |
| Global trim | Documented trim semantics and range; confirmation of how trim state is observable (if at all) — trim-switch visibility in telemetry is an open question, see known-unknowns |
| Slot behavior | Documented slot/map-selection model (count, switching mechanism, persistence) from Vortex documentation plus bench observation; never assumed from other Vortex products |
| File format | Documented or Vortex-confirmed format specification; checksum/integrity behavior understood; round-trip (export → import in official software) demonstrated on the bench without semantic loss |

"Bike Verified" additionally requires demonstration on the specific bike model and model year. "Team Approved" additionally requires a named human approval.

## 7. Open items

All Vortex-specific unknowns, with verification paths, are tracked in `docs/testing/known-unknowns.md`. That list is the authoritative backlog; nothing on it may be treated as resolved without evidence attached to the relevant ECUDefinition.
