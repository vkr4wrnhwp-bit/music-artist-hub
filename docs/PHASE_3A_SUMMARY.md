# CANVAS — PHASE 3A STATUS

Phase 3A asked for eighteen things. **Two are done, several were already
present from earlier phases, and most are not built.** This document says
which is which, item by item, so nobody has to find out by clicking.

Status vocabulary, used strictly:

| Label | Meaning |
|---|---|
| **REAL** | Works against real state, persists, and the logic behind it is genuine |
| **PARTIAL** | Works, but a named part of the requirement is missing |
| **SIMULATED** | Renders and responds, but the thing it depicts is not computed |
| **DEVELOPMENT ONLY** | Real logic, not validated against physical testing |
| **SHELL** | Route exists, no engine behind it |
| **BLOCKED** | Cannot be built without something CANVAS does not have |

---

## The eighteen Phase 3A items

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Home | **PARTIAL** | Exists and is clean, but is not the "what are we making" hero the brief describes. `/parts/new` is closer to it. |
| 2 | Reverse engineer | **PARTIAL** | Photos → datums → measure works. `RECONSTRUCT / FEATURES / REVIEW` are not distinct stages. |
| 3 | Photo intake | **REAL** | Seven-view set with scale reference. Uploads do not survive redeploy on the free plan, and the app says so. |
| 4 | Datum setup | **PARTIAL** | Three datum systems, proposed with reasoning, accepted by a human, persisted. **Not yet drawn on the part** — the brief asks for visual datums. |
| 5 | Guided measurement | **REAL** | Sequential, instrument-aware, persists value/units/instrument/uncertainty/feature/session. Datum linkage exists in schema (`Measurement.datumId`) but the UI does not set it yet. |
| 6 | Feature hover | **REAL** | No click needed. Unrelated geometry recedes; the hovered feature lights up. |
| 7 | Feature lens | **REAL** | Compact, shows size, tolerance, function, criticality and measurability. **No DETAIL/MEASURE/MAKE/VERIFY actions on it yet.** |
| 8 | Feature specimen view | **NOT BUILT** | `specimenMode` exists in the interaction model with no consumer and no caller. It is a field, not a feature. |
| 9 | Nominal reasoning | **REAL** | Suggests, never applies. Accepting writes USER-confirmed provenance and re-runs readiness. |
| 10 | Functional feature classification | **REAL** | Mating component → bearing identified → fit class → tolerance. Bearings only; other families say so. |
| 11 | Hold mode | **PARTIAL** | Vise, jaws and grip render; holding margin is real. Contact patch, clamping direction and cutter clearance are **not** drawn spatially. |
| 12 | Soft jaws | **PARTIAL** | Generates real geometry, writes `Jaw` rows, updates grip depth. **No visual sequence, no MACHINE THESE JAWS button.** |
| 13 | Cut mode | **PARTIAL** | Toolpath and tool render and play back. **No operation timeline, and selecting an operation does not change the scene.** |
| 14 | Operation timeline | **NOT BUILT** | — |
| 15 | Verify mode | **NOT BUILT** | The rail button exists and returns the same scene flags as PART. It is currently inert in 3D. |
| 16 | Readiness | **REAL** | Gate-based, worst-gate, no percentage, blocks NC export. |
| 17 | Next required action | **REAL** | Persistent, ordered by what invalidates what. |
| 18 | Copilot structured mutations | **NOT BUILT** | The copilot cannot change the scene and cannot propose a structured update. On the deterministic provider it matches intent with regexes and deflects most natural phrasings. |

---

## Acceptance criteria

The brief lists twelve. Honestly assessed:

- [x] Part dominates workspace
- [x] Feature hover works
- [x] Feature lens works
- [ ] Specimen view exists — **no**
- [x] Reverse-engineering flow works (photos → datums → measurement)
- [ ] Datums are visual — **no, they are records not geometry**
- [x] Measurement mission exists
- [x] Nominal reasoning works
- [ ] HOLD / CUT / VERIFY are distinct — **HOLD and CUT differ; VERIFY does not**
- [x] Readiness remains strict
- [x] Next required action is persistent
- [ ] Copilot can propose structured changes — **no**

**8 of 12.** Phase 3A is not complete.

---

## What changed in this phase

**Real subtracted part geometry.** The largest single change. The viewport
previously drew a stock block with translucent volumes marking removed
material — a bore was never a hole. The part is now built as a stack of
extruded cross-sections, sliced at every Z where a feature begins or ends. For
2.5D prismatic geometry that is the shape, not an approximation of it.

Chamfers, fillets, countersinks and angled slots are **not** represented and
are reported as such. They need a geometry kernel, and a fake chamfer would
show an edge break the toolpath does not produce.

---

## Standing classifications

| Thing | Status |
|---|---|
| Deterministic CAM engine | **REAL** — no model involvement, refuses on unreachable geometry |
| Cutting force (Kienzle v0.2) | **REAL**, confidence capped at MEDIUM |
| Holding margin v0.1 | **DEVELOPMENT ONLY** — not validated against pull-off testing |
| Inspection capability | **REAL** — cannot be cleared by confirmation |
| Readiness gates | **REAL** |
| NC post | **DEVELOPMENT ONLY** — not certified, header says so |
| "Simulation" gate | **SIMULATED** — passing it means the toolpath was drawn. No stock removal, no collision, no holder check |
| Fixture geometry | **SIMULATED** — parametric approximation of a vise, not the actual model |
| Shop knowledge | **SHELL in practice** — reads real tables, but `promoteToShopKnowledge()` has no caller, so it renders empty |
| `/intelligence`, `/network` | **SHELL** |
| `/jobs`, `/quoting` | **SHELL** — read-only, one seeded row, no creation flow |
| Shop libraries (machines, tools, materials, metrology, workholding) | **PARTIAL** — read-only, no create/edit/delete anywhere |
| Stock removal simulation, collision checking | **BLOCKED** — needs a voxel or B-rep sweep engine |
| Photograph geometry analysis | **BLOCKED** — no vision model configured |
| CAD import (STEP/IGES) | **BLOCKED** — needs a geometry kernel |
| Network matching | **BLOCKED** — needs multi-tenant infrastructure and participants |

---

## Known unfinished edges

- `OperationState` model has **zero write sites**. It was built as architecture
  for the operation timeline and nothing has ever written a row.
- `specimenMode`, `cameraTarget`, `manufacturingState` and `activeOperation` in
  the interaction model have **no consumers**.
- The copilot's intent matching is regex-based. "How should I hold this?" works;
  "Where do I grip it?" falls through to the no-model-configured message.
- No feature or setup editing UI. The holding model's own inputs — jaw surface,
  clamp force, grip depth — cannot be set by hand.
- Two Postgres migrations (`feature_mating`, `datums`) are hand-written and have
  never been executed against a live Postgres.
