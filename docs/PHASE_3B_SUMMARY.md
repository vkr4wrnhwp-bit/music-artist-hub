# CANVAS — PHASE 3B STATUS

Phase 3B asked for eight things. **One is built.** This document says which,
and what state the other seven are in, so nobody has to find out by clicking.

---

## The eight Phase 3B items

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Run It Past CANVAS | **PARTIAL — built, without import** | The review workflow is real and runs against the package CANVAS holds. Uploading a STEP model, an NC program or a tool list from another CAM is **not built**. |
| 2 | Review package model | **PARTIAL** | Findings are structured objects — severity, setup, operation, feature, point, evidence, method. They are **computed fresh, not persisted**; there are no `ReviewFinding` rows and no resolution tracking. |
| 3 | Cost / Make vs Buy | **NOT BUILT** | The cost engine exists and is connected to real cycle time. The make/buy/alternative-process comparison and the quantity-break UI are not. |
| 4 | Manufacturing DNA | **NOT BUILT** | The `ManufacturingDNA` model exists with **zero write sites**. There is no timeline UI. |
| 5 | Shop knowledge | **PARTIAL — from Phase 2** | Model, scoping and the `/knowledge` page exist. `promoteToShopKnowledge()` still has **no caller**, so the observations list is permanently empty. |
| 6 | I disagree | **BUILT — Phase 2** | Persists, audited, provably does not clear gates. Verified. |
| 7 | Tool reality | **PARTIAL — Phase 2** | Fields exist on `Tool` (condition, actual stickout, runout, helix, regrind count, material history, shop notes) and the cutting model reads condition and helix. **No UI shows or edits them.** |
| 8 | Provenance deep dive | **NOT BUILT** | Provenance badges render; clicking one does not open source, method, operator, instrument, uncertainty or calculation version. |

---

## Acceptance criteria

- [x] Run It Past CANVAS is functional as a review workflow
- [x] Findings are structured
- [ ] Findings appear spatially — **no**; each finding carries a point and a context, and SHOW ME deep-links to the right page, but it does not drive the 3D camera
- [ ] Make vs Buy reacts to quantity — **not built**
- [ ] Manufacturing DNA exists — **not built**
- [x] Shop Knowledge persists (schema and page; nothing writes to it)
- [x] I DISAGREE captures evidence
- [ ] Tool records reflect real shop conditions — **schema yes, UI no**
- [ ] Provenance drilldown works — **not built**

**3 of 9.** Phase 3B is not complete.

---

## What was built

### Run It Past CANVAS — `/parts/[id]/review`

The adoption argument. A shop that trusts its CAM will not abandon it, but it
will run a job past a second opinion before Cycle Start.

Five checks, all from deterministic engines or arithmetic over real toolpath
moves. No model is involved:

| Check | Source |
|---|---|
| Holding margin per setup | Holding model v0.1 (DEVELOPMENT ONLY) |
| Lateral rapids below jaw height | Toolpath move inspection |
| Tool reach at depth | Tool geometry against operation depth |
| Holder clearance | Stickout against depth |
| Spindle power against the machine | Cutting model v0.2 |
| Measurement capability per toleranced feature | Gauge maker's rule |

Each finding carries severity, the setup and operation it belongs to, the
evidence behind it, and the method that produced it — so it can be argued with
rather than only obeyed.

**The page states what it did not check with equal prominence**, because a
clean review is not a safety claim. There is no stock-removal simulation and no
collision engine; a clean result means the checks CANVAS knows how to make
found nothing.

#### One thing worth recording

The first working version of the rapid-clearance check produced **seven HIGH
findings on the demo part, all false**. It flagged every plunge approach — the
rapid straight down over a hole before drilling it, which is below jaw height
by design and entirely normal.

A machinist would have dismissed the whole page in ten seconds, and rightly.
The check now only flags rapids that travel **laterally** while below jaw
height, which is the move that actually takes a vise off. The demo part went
from 7 HIGH + 1 MEDIUM to 1 HIGH + 1 MEDIUM, and both survivors are real.

A check that cries wolf is worse than no check. That is the standard the rest
of this workflow has to meet before more checks are added.

---

## What is still missing, and what it needs

| Item | Blocked on |
|---|---|
| Importing a STEP model | A geometry kernel |
| Importing a posted NC program | Parsing arbitrary dialects back into operations — its own project |
| Findings driving the 3D camera | The interaction model's `cameraTarget` has no consumer yet |
| Persisted findings and resolution tracking | Schema work; findings are currently derived state |
| Manufacturing DNA timeline | Nothing writes `ManufacturingDNA`; the audit log has the raw material for it |
| Provenance drilldown | The data is all recorded — this is UI only |
| Tool reality UI | Fields exist and are read by the force model — this is UI only |

The last two are the cheapest real wins remaining in Phase 3B: both are
presentation over data that already exists and is already correct.
