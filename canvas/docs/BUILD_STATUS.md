# Build status

Phase 1. Updated at the end of the first implementation pass.

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

## IN PROGRESS

- Feature editing in the workspace (currently read-only; features are created
  through intake proposals and the seed)
- Setup editing (setups render and assess; grip is written by the soft jaw
  generator, not yet directly editable)
- Inspection plan creation UI (plans render; creation is seed-only)

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
