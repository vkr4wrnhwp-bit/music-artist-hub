# CANVAS roadmap

## Where Phase 1 landed

A working manufacturing platform: intake → intent → responsibility → geometry →
setups → workholding → tooling → operations → deterministic toolpaths →
simulation → development post → readiness → cost → make vs buy, with an audit
trail and a privacy model underneath it.

The engines are real. Where a capability is not implemented, the interface says
so rather than animating something plausible.

## Phase 2 — geometry and CAM depth

**Geometry kernel.** The single largest unlock. Phase 1's parametric 2.5D model
is honest and adequate for prismatic work, but STEP import, boolean subtraction,
true stock-removal simulation and profile-following soft jaws all wait behind a
kernel. Options: OpenCascade via WASM, a commercial kernel, or a constrained
in-house B-rep for prismatic solids. This is a build-vs-buy decision with a long
shadow — see `docs/ARCHITECTURE.md` for the seam it slots into
(`generateToolpath`, `evaluatePart`).

**CAM depth.** Adaptive clearing, boring, tapping and thread milling engines.
Arc output. Rest machining. Per-hole chamfer passes. Single-line font
vectorisation for engraving.

**Verification.** Voxel stock removal, holder and fixture collision detection,
machine travel simulation, tool reach checking against actual geometry. Until
this exists, `Simulation.verifiedStockRemoval` stays `false` and the UI keeps
saying so.

## Phase 3 — reverse engineering depth

**Measurement dependency solver.** The stated objective: ask for the *minimum*
set of measurements that mathematically constrains the model. The dependency
graph fields exist; the solver does not.

**Vision.** Feature enumeration and view registration from photographs — still
never dimensional reconstruction.

**Scan import.** STL and point cloud, with mesh-to-parametric fitting and a
deviation map against the fitted model.

**Broken Part Mode** and **Obsolete Part Mode**, including a revision-controlled
digital spare-parts library.

## Phase 4 — shop floor

Job creation and scheduling. Capacity modelling that makes make-vs-buy's
opportunity-cost caveat go away. First-article inspection capture against the
plan. Tool life tracking from actual cut minutes. Machine connectivity
(MTConnect) for real status on the home dashboard. Estimate-versus-actual
feedback so the cost model learns from the shop it runs in.

## Phase 5 — network

Multi-tenant fingerprint index. Supplier matching with consent-gated
introductions. The revenue-opportunity engine. Collective intelligence over
opted-in outcomes — successful and failed workholding strategies, chatter,
tool breakage, scrap events, warping, tolerance misses.

Every part of this is gated behind the privacy model already shipped. It does
not get relaxed to make matching easier.

## Phase 6 — process breadth

Turning and mill-turn. Sheet metal and fabrication. Additive as a first-class
process chain including DfAM, build orientation, support strategy and the hybrid
print-then-finish workflow. External FEA and topology optimisation integration —
connected properly, never simulated.

## Decisions taken, and why

**SQLite in development.** The application runs with zero external services.
The schema is Postgres-ready; the adapter is the only thing that changes.

**Strings instead of Prisma enums.** One source of truth for the vocabulary, in
`lib/domain`, rather than splitting it between the schema and TypeScript unions.

**A deterministic default AI provider.** CANVAS is fully usable with no API key
and no network. The intake parser is a real grammar, not a stub. This also
proves the architectural point: the model is an enhancement to the intake layer,
not the thing the product is made of.

**JSON for the Part Intent Model.** Every field is a
`{value, source, confidence, confirmedByUser}` tuple. Shredding that into
columns would either quadruple the column count or lose the provenance pairing,
and the provenance pairing is the point.

**One `buildPackage()` composition point.** Readiness depends on workholding,
which depends on the roughing operation, whose cycle time drives cost. Computing
those separately is how a UI shows a cost that does not match the program beside
it.

**No percentage on readiness.** A gate list whose aggregate is the worst gate.
Averaging lets a part with no inspection plan read as 90% ready.
