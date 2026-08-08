# Build status

Updated through Phase 3A. Read /docs/PHASE_3A_SUMMARY.md first — it states
REAL / PARTIAL / SIMULATED / DEVELOPMENT ONLY / SHELL / BLOCKED per feature,
and is the honest answer to "what actually works".

## DONE

**Foundation**
- Next.js 16 / TypeScript / Tailwind v4 application, deployable, env-driven
- CANVAS design system: graphite palette, precision blue used sparingly, datum
  motif, technical labels, framing corners, restrained motion
- Brand marks (datum coordinate mark, wordmark with axis "A")
- Cookie-session auth, bcrypt, organisation multi-tenancy, roles
- Prisma schema — 40 entities, SQLite dev / PostgreSQL-ready, migrated
- Append-only audit log with explicit HUMAN / AI / SYSTEM actor typing
- Object storage abstraction with upload validation and org-scoped keys
- AI provider abstraction; deterministic default provider + Anthropic provider
- Provenance primitive applied throughout, rendered as badges in the UI

**Intake**
- Home "What are we making?" command bar (describe / photo / drawing / CAD)
- Grammar-based intake parser: dimensions, fractions, materials, thread
  callouts, tolerances, quantities, features — works with no API key
- Part Intent Model with per-field provenance and named unknowns
- Part Responsibility interview gating process advice
- AI feature proposals as reviewable, acceptable/rejectable records

**Workspace**
- Three.js viewport: orthographic views, shaded/wireframe/ghost, feature
  selection, datum display, fixture, toolpath, tool, playback and scrub
- Ten-panel navigator: part, features, stock, setups, workholding, tools,
  operations, inspection, cost, history
- Persistent copilot answering from structured project data, with an explicit
  "needs" list when it cannot answer

**Engines**
- Deterministic 2.5D toolpath engine: face, pocket, drill, peck, contour,
  chamfer, engrave, soft-jaw pocket
- Speeds/feeds from tool + material + machine intersection
- Cycle time measured from generated moves
- Workholding assessment: grip depth, jaw engagement, projection, thin wall,
  holder clearance, datum access, with a specific-energy cutting force estimate
- Soft jaw generator with parametric geometry and machining process
- Nominal dimension reasoning against bearing/thread/dowel/drill/stock tables
- Readiness gate list (worst-of, never averaged)
- Cost engine with full assumption set and quantity breaks
- Make vs buy that refuses to invent a supplier price
- Manufacturing method advisor across 21 processes
- Network fingerprint with disclosure audit

**Output**
- Six modular post processors (Haas, Fanuc, PathPilot, Siemens, Heidenhain, GRBL)
- NC verification linter (envelope, speed, feed, spindle-off cutting, units)
- Pre-flight gate that disables export until every required item passes
- Operator approval as a named human act

**Data**
- Demo shop: Haas VF-2 reference profile, 9 tools, 6" vise, jaw blanks,
  6 materials, 8 metrology instruments
- TEST PART 001 — CANVAS Bearing Support, 11 features, 2 setups, inspection
  plan, a completed job with a `PART_MOVED` outcome, and a 1.5744" measurement
  that exercises the 40 mm nominal-reasoning demo

## PHASE 3A — PARTIAL

See /docs/PHASE_3A_SUMMARY.md for the item-by-item status. 8 of 12
acceptance criteria met; Phase 3A is not complete.

**Real subtracted part geometry.** `components/viewport/part-solid.ts`. The
part is built as a stack of extruded cross-sections sliced at every Z where a
feature begins or ends. Holes are holes. Chamfers, fillets, countersinks and
angled slots are not represented and are reported as unrepresented rather than
approximated — they need a geometry kernel.

Not built in this phase, and named in the brief: feature specimen view, visual
datums on the part, operation timeline, VERIFY mode, soft jaw visual sequence,
copilot structured mutations.

## PHASE 2 — BUILT

**Cutting force model v0.2 (Kienzle).** `engines/cutting-force.ts`. Replaces the
Phase 1 specific-energy approximation. Published material coefficients, average
and peak reported separately, uncertainty band on every result, and a refusal to
return anything when an input is missing. Confidence capped at MEDIUM — it is a
calculation, not a measurement, and must not be able to satisfy a gate alone.

**Holding margin v0.1.** `engines/holding-margin.ts`. Applied load against
resisting load: friction across both jaw faces plus any positive stop, checked
against both sliding and overturning, worst mode governs. Replaces grip depth as
the deciding factor — grip depth is demoted to advice once the force balance is
available. Returns INDETERMINATE when clamping force is unrecorded rather than
assuming one. Classified DEVELOPMENT ANALYSIS.

**Inspection capability.** `engines/inspection-capability.ts`. Gauge maker's rule
— instrument uncertainty against tolerance band, 10% target, 25% limit. Blocking
and not clearable by confirmation. Upgrade suggestions exclude equipment the shop
already owns and equipment that still would not reach the required uncertainty.

**Show your work.** `components/show-calculation.tsx`. Every consequential
calculated number opens to method, inputs, assumptions and uncertainty.

**Next required action.** `engines/next-action.ts`. One instruction, ordered by
what invalidates what rather than by what is easiest.

**Part status everywhere.** Readiness travels with the part on every screen.

**I disagree.** `lib/disagreement.ts`, `/knowledge`. Recorded as evidence,
scoped, never clearing a gate.

**Tool reality.** Condition, actual stickout, measured runout, helix, regrind
count, previous material and shop notes on the tool record. Condition and helix
feed the force model.

**Operation-state geometry.** `OperationState` model — the addressable state and
scalar envelope of the part at a point in the process. The material-removal
solid modelling that would populate it automatically is not built.

## IN PROGRESS

- Feature editing in the workspace (currently read-only; features are created
  through intake proposals and the seed)
- Setup editing (setups render and assess; grip is written by the soft jaw
  generator, not yet directly editable)
- Inspection plan creation UI (plans render; creation is seed-only)

## PHASE 2 — NOT BUILT

These are named in the Phase 2 brief and are deliberately not faked:

- Reverse engineering as the flagship seven-view intake with a reconstruction
  plan and a guided sequential measurement mission
- Datum-first reverse engineering — design, manufacturing and inspection datums
  as distinct coordinate systems, with measurements referencing them
- Nominal reasoning 2.0 — reasoning from the mating component (bearing number,
  shaft, seal) rather than from the measured dimension alone
- Soft jaws 2.0 — jaw geometry as real project geometry driven by
  operation-state, with a MACHINE THESE JAWS path into actual operations
- Manufacturing strategy modes (conservative / balanced / aggressive /
  lights-out) affecting whole strategy rather than feeds and speeds
- Copilot as a control surface proposing structured project mutations
- Shop knowledge review queue — the promotion path from disagreement to
  knowledge exists in the data model but has no UI

## NEXT

1. Direct parametric feature editing with live re-assessment
2. Adaptive clearing, boring and tapping toolpath engines
3. Arc (`G2`/`G3`) output instead of linearised arcs
4. Stock removal simulation and holder/fixture collision detection
5. Measurement dependency solver — the *minimum* set that constrains a model
6. Vision analysis of uploaded photographs
7. STEP/DXF import behind a geometry kernel
8. Job creation and shop-floor execution flow
9. Quote generation from stored cost estimates
10. Revision comparison (Rev A vs Rev B diff)

## BLOCKED

| Item | Blocked on |
|---|---|
| CAD import (STEP/IGES/Parasolid) | A geometry kernel. No honest shortcut exists |
| Collision and stock-removal verification | A voxel or B-rep sweep engine |
| Photograph geometry analysis | A configured vision model |
| Network matching | Multi-tenant network infrastructure and opted-in participants |
| Revenue opportunity engine | The network layer plus a demand corpus |
| Company research | Web tooling; deliberately not wired up |
| FEA / topology optimisation | An external solver. Not faked |
| Live machine status | MTConnect or controller integration |
| Certified post processors | Validation on real machines |
