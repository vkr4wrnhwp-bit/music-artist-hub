# Build status

Updated through Phase 3A. Read /docs/PHASE_3A_SUMMARY.md first — it states
REAL / PARTIAL / SIMULATED / DEVELOPMENT ONLY / SHELL / BLOCKED per feature,
and is the honest answer to "what actually works".

## WORKSPACE DESIGN PASS — PARTIAL

A visual and layout pass over the application shell and the part workspace. It
is **presentation plus two engine corrections**. It built no new manufacturing
capability, and it did not change any feature's status in
/docs/PHASE_3A_SUMMARY.md or /docs/PHASE_3B_SUMMARY.md.

**12 of 13 acceptance criteria met, 1 partial.** `npx tsc --noEmit` clean.
`npx next build` clean — 39 routes emitted, 8/8 static pages, no errors, no
warnings. All 30 routes under `src/app/(app)` return 200 signed in against a
freshly migrated and seeded database, with zero page errors, zero console
errors, and `documentElement.scrollWidth == clientWidth` **and**
`shell-root.scrollWidth == clientWidth` at 1600×1000 and 390×844.

### What changed — REAL

**Token system.** `globals.css` rewritten around one `--canvas-*` palette.
Every existing `--c-*` role name still resolves, so no page file needed
editing. Because `@theme inline` compiles utilities to the raw variable, a
single `.canvas-shell` block re-declares the `--c-*` group and every utility,
opacity modifier, `.tech-label` and inline `stroke="var(--c-blue)"` inside the
dark chrome re-resolves — which is why ~33 pages' `TopBar`, `StatusChip`,
`PartStatusChip`, `DevLabel` and `ProvenanceBadge` are legible on the dark bar
with zero page edits.

Two defects fixed on the way: `--color-white` was unmapped and fell through to
literal `#fff`, making 25 strings invisible on the light ground including every
`SectionHeading` h1; and `accent-[var(--precision)]` in `disagree.tsx` referenced
a variable that does not exist, so both radios rendered as browser defaults.

**Shell.** 72px icon rail + 210px context drawer, both dark, plus a 92px dark
command bar. The drawer is contextual — on `/parts/<id>/…` it lists the twelve
real part sub-routes. Off-canvas behaviour below `lg` is unchanged (close on
route change, Escape, backdrop, body-scroll-lock with restore, all verified
live) and now sets `inert` on the closed panel so ~20 links leave the tab order.
Rail items ship under their real route names. All previously reachable routes
remain reachable.

**Part workspace** rebuilt into three zones: centre work canvas, 356px right
feature panel, footer operation runway. Three horizontal strips left the centre
column — the context rail, view/mode bar and transport bar are now a vertical
edge stack and a floating transport that appears only when a toolpath is on
screen. Measured at 1600×1000: header 101.6px, right panel 356px, footer
144.5px, centre canvas 962×716.

**Dead interaction state wired.** Clicking an operation dispatches
`SET_OPERATION` and selects the feature that operation cuts, so the model and
the panel follow the operation being read. Escape unwinds feature and operation
together. `feature-lens.tsx`'s `capability` prop was dead UI — nothing ever
passed a verdict — and now carries the real `assessCapability` result. A `HOVER`
reducer bug that kept a stale pointer coordinate is fixed.

**Two engine corrections — these are not cosmetic.**

1. `measurementGeometry()` lived in `readiness.ts` and had been re-derived, with
   different rules, in two page files. Moved to
   `engines/inspection-capability.ts` beside `assessCapability()`; both pages now
   call the engine. Before the fix the feature panel printed "NOT CAPABLE" on
   three features the NC-blocking readiness gate counted as one. Panel and gate
   now agree: on the seeded part the bore reads **Not capable**, dowel hole 1
   reads **Marginal — consumes 20% of the band**, and `/readiness` reports "1
   toleranced feature cannot be verified".
2. `part-solid.ts` and the new section sketch both asserted that "the toolpath
   does not produce" chamfers. The deterministic CAM engine emits a real chamfer
   toolpath, visible in the runway on the same screen. Both statements rewritten
   to describe a limit of the drawing, not of the engine.

### Acceptance criteria — 12 of 13

Numbering is the design brief's. Criteria 1, 3, 4 and 5 were verified by pixel
measurement rather than by eye.

| # | Criterion | Status |
|---|---|---|
| 1, 3, 4, 5 | Zone structure, zone dimensions, ground colours, divider weight | **REAL** — rail 72px `#06111C`, drawer 210px `#071A2A`, header `#06111C`, canvas `#FAFAF8`, panel `#F1F3F5`, footer `#EEF0F2`, both dividers `1px solid var(--canvas-border-strong)` |
| 2, 6, 9, 12 | — | **Recorded met.** The screenshot audit did not fault them and this pass changed nothing scoped to them. They were not independently re-measured, and this document does not restate criterion text it cannot verify |
| 7 | Operation runway reads as discrete legible cards | **PARTIAL** — see below |
| 8 | One operation visually dominant at rest | **REAL** — the plan's first operation in sequence order is pre-selected, marked "Plan starts" until the user clicks, then "Selected" |
| 10 | Next required action is prominent, not buried | **REAL** — full-width, 14px/600, untruncated action, two-line reason, severity rule, plus a second home in the project drawer |
| 11 | Datum reference section always present | **REAL** — renders unconditionally; with zero `Datum` rows it states the absence, and on a critical or toleranced feature adds "A toleranced feature with no datum cannot be measured repeatably" |
| 13 | The part fills the work canvas | **REAL** — bounding box 60.9% of the canvas (was 44.7%), 85.0% width, 71.6% height |

**Criterion 7 is the one that is not met.** Cards came down 172→130px, the setup
gutter wraps, tool numbers are mono chips and feature labels wrap to two lines
instead of truncating mid-word, and there is an edge fade with a working
scroll-right chevron. **5 of 9 operations are visible at 1600px, against a
target of 7 or more.** Seven would need ~90px cards, which cannot hold a
readable operation label. Legibility plus a visible continuation affordance was
taken over the count. This is a real miss, not a reinterpretation.

Two checks outside the numbered list were also failing and are now fixed:
monospace is down from 48% to **18.6%** of visible characters — dimensions,
tolerances, T-numbers, cycle times and readout labels stay mono, everything else
is grotesk — and the worst light-surface contrast ratio in the panel or footer
is now **4.98:1**, up from 2.91:1.

### What the new panels are driven from — REAL

`src/components/workspace/panel-data.ts` defines the serialisable shapes the
server hands the client tree. It carries **no `status`, `progress`, `elapsed`,
`confidence` or `pass` field on any type**, because nothing in the schema
produces them and a field that exists is a field a component eventually fills in.

| Surface | Source |
|---|---|
| Capability verdict, required uncertainty, consumed fraction | `assessCapability()` against the shop's real `MetrologyDevice` rows |
| Instrument range, resolution, uncertainty, calibration date | `MetrologyDevice` |
| Recorded reading, uncertainty, repeat count, resolution state, operator, session | `Measurement` + `MeasurementSession` |
| Model dimension | `Feature.parametersJson` |
| Deviation and band | Computed in `dimension.ts`, labelled as computed |
| Section sketch | Stored feature parameters and `stock.z` |
| Operations, tools, sequence, cycle time, move count, placeholder flag, engine errors | The deterministic CAM package |
| Setup risk | Workholding assessment `RISK_LABEL`, carrying its `developmentAnalysis` flag |
| Inspection line counts | `InspectionItem` |
| Material and temper | Part intent, with its provenance badge travelling into the command bar |
| Next required action | `nextActions()` — the full ordered list, not just the head |

The two number systems are kept visually and semantically apart: **⌀1.5748** is
`Feature.parametersJson.diameter`, **1.5744** is `Measurement.measuredValue`.
Different labels, different sizes, different provenance. When no measurement
exists the heading reads "Model dimension — not yet measured", not "Measurement
results".

### Deliberately not rendered — it would have been fabricated

The reference design showed each of these. None is in the build.

| Not rendered | Why | What would make it real |
|---|---|---|
| COMPLETE / ACTIVE / NEXT / PENDING on operations | `Operation` has no status column; `OperationState` still has zero write sites | A shop-floor execution flow that writes operation state |
| Elapsed / remaining time, progress bar | No execution state and no machine connection | The above, plus MTConnect or controller integration |
| `LIVE` on the reading | No gauge or machine connection. Renamed "Last recorded reading" | A connected instrument or controller |
| `PASS` chip on the measurement | `InspectionResult.pass` has no write path, and 1.5744 is outside +0.0005/−0 anyway | An inspection result write path |
| Confidence row on the dimension | `suggestionConfidence` scopes to a standards match, not to the dimension, and is null on both seeded rows | Nothing — this is locked principle 1. A dimension does not get a confidence meter |
| Readiness percentage or score anywhere | Locked principle 1 | Nothing. `PartStatusSummary` renders worst-gate only: "NOT READY · 4 blocking" |
| `SECURED` on workholding | Holding margin is DEVELOPMENT ONLY and returns INDETERMINATE without a recorded clamp force | Validation against physical pull-off testing |
| Heat number, lot, `CERTIFIED` | No material certificate records exist | A material certificate model and an intake path for it |
| Notification count | No notification model | A notification model |
| Measurement points and dimension lines in 3D | `Measurement` stores a scalar, not coordinates | Coordinates on `Measurement`, which means a datum-referenced probing flow |
| Part thumbnail, instrument imagery | No render pipeline, no device photography | An offscreen render job; asset upload for devices |
| "Hold feature" button | Nothing behind it. The panel says so in place of the button | Feature-level workholding constraints, which do not exist |
| Populated Datum Reference | The seed has zero `Datum` rows. The absence is stated, not filled | Accepted `Datum` rows plus `Measurement.datumId` being set by the measurement UI — the column exists and nothing writes it |
| Rail items "Operations", "Shop Floor", "Analytics", "Inspection" | No shop-level routes exist for any of them. Operations are per-part; there is no shop floor page at all; the nearest thing to Analytics is `/intelligence`, which is a **SHELL** | Those routes and the engines behind them |

Honesty carriers were checked and are intact: `/network` and `/intelligence`
still tag **SHELL** in the drawer, `/parts/[id]/nc` now carries a **DEV** tag in
the drawer as well as in its own bar, the NC page still shows "DEVELOPMENT /
SIMULATION POST", "NOT CERTIFIED FOR PRODUCTION" and its gated-export line,
`/reverse-engineer` still shows "IMPORT SCAN — NOT IMPLEMENTED", and the setups
page still carries its five NOT IMPLEMENTED buttons. The workholding tile's
DEVELOPMENT classification was tooltip-only and is now a visible `DevLabel`.
Absent values read "not generated", "not assigned", "not defined", "not
recorded", "no date", "0 results".

The runway header states **"Planned sequence — CANVAS does not track execution
state."** Nothing in the runway is green, because there is no completion data to
make it green. Selection is signalled four ways at once — inset rule, top bar,
blue sequence number, `SELECTED` on the bottom row — specifically so it never
has to displace an operation's own state: op 06 shows `NO ENGINE` and `SELECTED`
at the same time.

### Visual compromises accepted

- **Runway shows 5 of 9 operations at 1600px, not 7.** Criterion 7. Legibility
  over density.
- **The approved light-side palette was darkened to reach AA.** `--canvas-green`
  `#22A06B` measured 3.2:1 on `#FAFAF8`; shipped as `#17754e`. `--canvas-muted`,
  `--canvas-orange` and `--canvas-red` moved for the same reason. Shell variants
  are separately lifted (precision blue is `#4D97FF` on the dark ground, because
  `#0B72FF` is only 4.2:1 there). The shipped palette is therefore not
  byte-identical to the reference.
- **The command bar grows a second row between roughly 1280px and 1460px**
  (102→132px). The alternative was truncating the h1 or hiding the metadata.
  Nothing is hidden; the header gets taller.
- **The work-window colour is duplicated in WebGL.** `scene.tsx` holds
  `WORK_WINDOW = "#FAFAF8"` as a named constant beside a comment saying it must
  equal `--canvas-work-window`, because WebGL cannot read a CSS variable. 35
  hardcoded hexes in that file will not follow a future token change.
- **On part pages the h1 falls back to the route's nav label** — `/parts/<id>`
  reads "Overview", with the part name in the trail above. The slot exists
  (`title`, `chips`, `meta`, `status` on `TopBar`); the part pages do not fill
  it yet.
- **No structural cleanup was done.** `ui.tsx` still has five separate
  Tone→class maps, so a palette change still has five sync points. The 30 pages
  still repeat `<TopBar>` + `<main className="flex-1 overflow-y-auto …">`; no
  `PageShell` hoist. Three pre-existing React-hooks lint errors in the touched
  files were left alone.

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

## PHASE 3B — PARTIAL

See /docs/PHASE_3B_SUMMARY.md. 3 of 9 acceptance criteria.

**Run It Past CANVAS** (`/parts/[id]/review`) is built: a pre-flight review
producing structured findings with severity, location, evidence and method,
from real engines and real toolpath moves. Importing a job package from another
CAM is not built. Make vs Buy, Manufacturing DNA, provenance drilldown and the
tool reality UI are not built.

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

## 2026-08-10 — View environment pass

- View Environment drawer (viewport control stack → Scene → View env):
  8 presets, custom background/floor/grid/selection colours with a
  semantic-colour contrast lock, grid/shadow/reflection/floor controls,
  line-weight and text-size controls, view modes, material-aware
  recommendation, named presets in localStorage (labelled local-only).
  See docs/VIEW_ENVIRONMENT.md.
- Screenshot export is REAL; annotated/setup-sheet/inspection/customer
  exports are DEVELOPMENT-labelled stubs.
- Metrology geometry split: INTERNAL_ROUND vs INTERNAL_FLAT — a bore gauge
  is no longer recommendable for a rectangular pocket. Engine + tests.
- Next-action banner: remaining queue rendered as clickable pills routing
  to each resolution flow.
- NOT done from the brief: operation-table/setup-rail restyle and the
  stronger structural dividers (deferred to the design-phase refactor),
  server-side ViewPreferences persistence, bottom-sheet drawer on mobile
  (the drawer overlays usably but is not a sheet).

## 2026-08-10 — Load-aware NC optimizer: AUDIT ONLY

docs/LOAD_AWARE_NC_OPTIMIZER.md added. Nothing implemented. Key findings:
CANVAS has no NC parser today (verifyNc is a linter); the stock-removal
simulator is the core asset (air-cut proof and engagement estimates come
from replay); no acceleration model exists so savings estimates would
overstate; feed-only optimization in V1 with geometry-word diff as the
invariant; optimized NC exports through the existing mint and gates or not
at all. Phases 4A-4C are implementable on current structure; 4D needs the
chip-thinning/corner math; sequencing rewrite and 3D surfacing are out.

## 2026-08-10 — Cinematic toolpath

Prompt/storyboard generator in the CUT workspace (Scene → Cinematic):
operation selection, 10/15/30s, six styles, include toggles, customer-safe
mode (tested to strip identity/dimensions/tooling), full/short/shot-list/
JSON outputs, copy + download. Deterministic — no model call; cycle-time-
weighted shot timing from real operations. External send is a DEVELOPMENT
stub behind a privacy notice. Technical playback, simulator and all gates
untouched. See docs/CINEMATIC_TOOLPATH.md. 56 tests.

## 2026-08-10 — NC analyzer (optimizer Phases 4A/4B) BUILT

src/lib/nc/: deterministic Fanuc/Haas parser + modal interpreter (G0-G3
with tessellated arcs, G20/21, G90/91, canned cycles expanded, G84 flagged
never-retime, macros/subprograms refuse with line numbers, comp regions
marked) and the analyzer: cycle breakdown per tool, replay-proven air-cut
detection on the stock height field, slow-linking and excessive-retract
findings, verdicts CONFIDENT/REVIEW/INSUFFICIENT_DATA with assumptions
stated. Page at /parts/[id]/nc-analyzer (DEV) with SVG backplot. Analysis
only — no proposals, no modification, no export. Self-test: parses CANVAS
Haas output with zero refusals; parsed cycle time agrees with the engine.
Ten new tests; 66 total. Phases 4C-4F remain per the audit.

## 2026-08-10 — NC optimizer Phase 4D BUILT

src/lib/nc/load.ts: load map and feed proposals, DEVELOPMENT ANALYSIS.
Chipload from programmed F/S + tool record; MRR from per-segment height-
field replay; power = MRR x specific energy. Bands AIR/LIGHT/TARGET/HIGH/
REVIEW colour the backplot. Proposals are feed-only (geometry never
changes, by construction), grouped by contiguous LIGHT runs, capped by
strategy preset — LIGHTS_OUT the most conservative — and never touch taps,
comped regions, or anything lacking tool+material context. Applying
proposals (4E emission, 4F gated export) does not exist and the screen
says so. Self-check: CANVAS's own O1001 bands 486 TARGET / 4 LIGHT —
the generator's feeds sit in the window they were derived from. 72 tests.

## 2026-08-10 — NC optimizer 4E/4F BUILT: the arc is closed

src/lib/nc/emit.ts: feed-word-only application with a masked geometry diff
as the machine-checked invariant (exported and tested directly); modal
ranges refused with reasons, never guessed. /api/parts/[id]/nc-optimize:
accepted proposals are RE-DERIVED server-side and matched exactly — stale
acceptances 409; emitted text must pass the diff, a round-trip parse with
identical segment count, and verifyNc, or nothing is stored. Optimized
programs are NCProgram rows (new columns: origin, sourceProgramId,
optimizationAuditJson; migrations in both dialects) with per-proposal
HUMAN audit rows plus a SYSTEM row for the diff. They render on the NC
page with an OPTIMIZED chip and full audit, behind the same pre-flight,
and export through the same mint — the gates decide, not the optimizer.
Verified end to end on O1001: one proposal applied, geometry identical,
lint clean, export panel armed. 76 tests. Phases 4A-4F all delivered;
remaining per the audit: acceleration model, telemetry, 3D surfacing.

## 2026-08-11 — ADAPTIVE_2D engine BUILT: no placeholders remain

src/lib/engines/cam/engine.ts adaptiveToolpath(): constant-bounded
engagement clearing — 15% radial engagement at full axial depth, chip-
thinning feed compensation (formula stated in the emitted warning, capped
by the machine), helical entry, Archimedean spiral for circular pockets,
morphed boundary spiral for rectangular ones with loop spacing <= ae by
construction. Refusals, not adaptations: wrong feature kind, wrong tool
class, depth beyond flute length, undersized pocket, unfittable corner.
PLACEHOLDER_OPERATIONS is now empty; every operation type has a real
engine. 82 tests.

## 2026-08-11 — STEP recognizer: pocket and slot floors

src/lib/step/recognize.ts: interior horizontal planar faces (all bound
vertices at one Z, strictly between top and bottom) are classified by
exact boundary match — one circle = CIRC_POCKET, two equal end arcs =
SLOT, rectangular hull with optional equal corner arcs = RECT_POCKET.
Anything else is warned about by Z with vertex/arc counts and never
force-fitted. Depth measured from the top face with the milled-from-top
assumption stated in every rationale; all proposals still pass through
human acceptance. Arc center points are excluded from boundary extents
(construction geometry, not boundary). Also fixed: feature lens role
labels drifted from the domain union (COSMETIC_SURFACE vs COSMETIC,
missing FIXTURE_PAD) — both ROLE_LABEL maps now typed against
FunctionalRole so drift fails the build. 86 tests.

## 2026-08-11 — Shop knowledge review queue BUILT: the promotion path is live

/knowledge is now the review queue promised by its own footnote: an OPEN
or EVIDENCE_REQUESTED disagreement can be promoted into scoped shop
knowledge (category, machine/tool/material scope, optional threshold) or
declined with a mandatory reason. Thresholds are all-or-nothing —
parameter, value, unit and direction together or not at all; a number
without its context is a stray value and is rejected. Promotion confidence
follows the evidence: LOW with a comparable job, UNKNOWN without.
Neither outcome touches a gate, and the page says so.

relevantKnowledge() gained its first caller: the machinist approaches
page surfaces knowledge scoped to the machine, tools and material in
play — a filter, not a ranking; other equipment's observations are not
shown. Verified end to end in the browser: disagreement recorded on the
readiness page, promoted at /knowledge with a 0.450" DOC threshold on
the VF-2, surfaced on the machinist page. 86 tests.

## 2026-08-11 — View preferences follow the user

ViewPreference model (userId unique, envJson + savedPresetsJson; paired
sqlite/postgres migrations): the per-user server row is now the source of
truth for viewport settings and saved presets; localStorage stays as the
fast cache so the viewport does not flash defaults while the fetch is in
flight. Server copy wins on load; a browser with local presets and an
empty account list pushes them up rather than losing either. Writes are
debounced fire-and-forget — display preferences are the one category of
data where losing a write is acceptable. User and organisation from the
session, never the request. Drawer footer updated from "this browser
only" to the truth. Verified in the browser: PUT/GET round trip, default
merge, empty-body 400, unauthenticated redirect. 86 tests.

## 2026-08-11 — Machinist tablet view BUILT (spec §3)

/parts/[id]/tablet: a projection of the same manufacturing package — it
hides depth, it does not hold different truth. Five sections in setup
order: SETUP (machine, workholding, jaws, grip/projection/parallels,
clamp force with device-rating fallback labelled as such), TOOLS (T#,
diameter, stickout, with the check-against-the-spindle instruction),
PROBE (expectations derived from the stock record and setup geometry,
and labelled as derived — no invented probing routine), RUN (per-op
card: op#, tool, cycle from the toolpath, the first engine warning),
SIGN-OFF. The checklist IS the audit trail: HUMAN-typed entries, latest
per section wins, who/when shown. Sign-off is testimony recorded via an
APPROVE audit row and only exists while every blocking gate passes —
otherwise the signature line is replaced by the failing-gate list, and
the gate state is re-checked server-side at write time. 48px minimum
touch targets, mono data with units, no percentages. Verified in the
browser: checklist round trip with name and time, sign-off correctly
withheld behind a failing inspection-capability gate. 86 tests.

## 2026-08-11 — Visual datums + VERIFY state in the viewport

The datum reference frame is now drawn on the model: a flag per datum,
anchored to its linked feature (face datums walk the top edge), solid
datum blue when accepted by a human, grey dashed PROPOSED when it is
CANVAS's inference — the viewport draws an inference visibly differently
from a decision. Visibility follows the environment's datum line mode.
Seed now creates the demo frame honestly: A accepted on the top face
(matching the setup note), B proposed off the bore centreline with its
reasoning stored, never auto-accepted.

INSPECTION view mode now colours every toleranced feature's ring by
verification state — computed server-side by the same assessConformance
rule the FAIR generator uses, on the latest INSPECTION-session reading
(RE sessions never verify). Green in tolerance, red out, grey not
measured / cannot determine, with a legend naming exactly those states.
NOT_MEASURED and CANNOT_DETERMINE are distinct states, not absences.
Provenance drilldown already existed in the feature panel (instrument,
datum, session, operator, deviation against band) — noted, not rebuilt.
Verified in the browser. 86 tests.

## 2026-08-11 — NC timing acceleration model BUILT

src/lib/nc/time.ts: trapezoidal velocity profiles at the machine's
recorded axisAccel (new nullable Machine column, paired migrations),
cos-scaled junction velocities, forward/backward feasibility passes.
Closed-form behaviour pinned by tests: long segments pay one accel and
one decel ramp, short segments go triangular and are counted as
acceleration-limited, colinear moves blend at speed while a square
corner stops, dwells break continuity. analyzeNC and the optimizer's
before/after minutes use it when axisAccel is recorded; a machine
without a recorded value keeps distance-over-feed timing and the
assumptions say to record one — the value is never guessed. The model
is labelled DEVELOPMENT ANALYSIS on every output: jerk, per-axis limits
and control look-ahead are not modelled. Verified live: the analyzer
reports the model and the 15 in/s² source on the reference machine.
91 tests.

## 2026-08-11 — CI E2E smoke suite

scripts/e2e-smoke.ts (npm run test:e2e): boots the built app against the
seeded database in a real browser and checks POSTURE, not pixels —
sign-in works, the part workspace renders with no readiness percentage
anywhere, the readiness gates render, the tablet never offers a
signature over a red gate (and explains the withheld one), NC output
stays behind its pre-flight with the not-certified notice, the shop
knowledge page keeps its scoping statement. CI now runs it after the
unit suite and build: playwright install → migrate → seed → smoke. A
failure here is a broken page or a broken gate posture that the 91 unit
tests cannot see.

## 2026-08-11 — Stock definition + STEP-to-plan journey test

Real gap found and closed: nothing let a human define stock after a STEP
import, so every imported part dead-ended before the machinist — each
stage worked alone and the chain still broke. The part page's stock
panel now carries a define-stock form for revisions without stock: the
finished envelope is shown as reference, stock smaller than it is
refused (not shrunk), existing stock is never silently replaced, and the
write audits as HUMAN. The allowance remains the machinist's decision —
no default is offered.

scripts/e2e-journey.ts (npm run test:e2e:journey, in CI): STEP upload →
recognizer proposes hole + pocket → accept → define stock → approve a
machinist approach → operation plan with real toolpaths and cycle time.
Also fixed the smoke suite's CI hang (orphaned server process group) and
updated the STEP import copy to mention pocket/slot recognition.

## 2026-08-11 — DARK CANVAS: the approved design direction lands

The dark-canvas decision (user-approved mockup) is implemented as a
token flip, which is what the design system existed for: shell, page
ground, panels, cards and runway all move to three elevations of the
near-black blue family (#06111c shell / #081522 page / #0a1826 panel /
#0c1c2c card), type and status colours switch to the dark-ground
variants that were already contrast-measured for the shell (blue #4d97ff
at 6.3:1; muted/green/orange/red all clear 4.5:1 at small sizes). No
component was edited — every utility resolves through the role tokens.

The one deliberately light region is the 3D work window: machined
metal, dimensional annotation and blue selection read best on a light
ground, so it keeps its warm-white default and stays user-tunable
through the view-environment presets (Dark Machine Bay exists for an
all-dark screen). --canvas-work-window now belongs to the viewport
alone; the page ground has its own token. The instrument is dark; the
part is lit. Verified by pixel sampling both grounds and by both E2E
suites. 91 tests.

## 2026-08-11 — Design refactor: banner, timeline table, dockable panel

Three refactor-spec SHIP items land on the workspace:

Action banner — the blocking queue promoted to full width under the
header: CRITICAL ACTIONS REQUIRED (n BLOCKING), the actions named, and
FIX NOW routing to the evidence screen for the first gate. Nothing in
the banner clears anything in place; absent entirely when nothing
blocks.

Operation timeline — the horizontal card scroller becomes table rows
grouped by setup with the per-setup risk rail (RiskLevel verbatim from
the workholding engine): Op / Type / Description / Tool / Cycle / Moves.
The only state column is SELECTED (real UI state) and PLAN STARTS (a
property of the sequence) — execution state remains untracked and the
caveat stays in the header, which now also collapses the table.

Dockable feature panel — collapse hands the full width to the viewport
(the ≥75% target); a labelled rail keeps the way back. Both collapse
states persist per browser as pure layout preferences.

Verified in the browser: banner renders with 3 blocking and routes,
10 table rows with setup rail and SELECTED chip, panel collapse and
expand, timeline collapse. Smoke + journey suites pass (a stale local
dev server, not the refactor, caused one false failure). 91 tests.

## 2026-08-11 — Measurement strip: HOLD values docked, ballooned

The refactor-spec measurement strip replaces HOLD's floating value
cards: numbered balloons at the anchors in the scene (the ballooned-
drawing convention AS9102 inspectors already read) matched to a docked
strip at the viewport edge listing the values. One shared ordered list
(hold-measurements.ts) feeds both renderings, so the balloon numbers
and the strip rows cannot disagree — the measurementGeometry lesson,
applied again.

Values never disappear: a row whose value is missing says "not
recorded" / "not calculable — clamp force not recorded" instead of
vanishing. Grip depth no longer displays its drawing fallback as if it
were a recorded number. The holding-margin row carries its verdict tone
and the DEV chip on the row, not in a tooltip. Verified live: six
balloons, six rows, honest gaps. All suites pass. 91 tests.

## 2026-08-11 — Nav consolidation: one rail, one dock

The part page's top strip duplicated five of the part dock's links
(Run it past CANVAS, Machinist, Tooling, Tablet, Full readiness) — two
lists of the same places, learned twice, drifting apart (the dock was
missing Tablet, proving the point). The dock is now the one contextual
navigation and gains Tablet; the top strip keeps only the readiness
gate summary and the one control that is an ACTION with state rather
than a place: NC output, ghost while blocked, primary when the gates
that block export pass. Contextual CTAs inside content panels (e.g.
"define workholding" beside the gap it fixes) are not navigation and
stay. All suites pass. 91 tests.

## 2026-08-11 — Design-phase polish: limits disclosures + permanent contrast audit

LimitsDisclosure lands in ui.tsx: the refactor-spec home for limits
prose that crowded panels as always-open paragraphs. The summary line
names the limit in caps where the user would look; only the explanation
folds. It is an expandable element in the page, never a tooltip — a
limit that changes what an operator would do is never only in a
tooltip. First applied to the NC verification panel (the "Linter, not a
verifier" chip stays visible; the what-it-does-not-catch prose folds).
Statements that ARE the operator's decision input — Not certified for
production, the runway's execution-state caveat, DEV chips,
NOT CONNECTED — stay always-visible by design.

tests/engines/contrast.test.ts makes the contrast audit permanent: it
reads the real tokens out of globals.css and pins primary/dim type at
4.5:1 on every dark ground, muted + all four status colours at 4.5:1 on
the lightest (card) ground, the viewport's locked semantic colours at
the 2.5:1 indicator floor on the default work window, and the
shell < page < panel < card elevation hierarchy. A palette edit that
breaks readability now fails CI instead of shipping. 95 tests.

Design phase complete: dark canvas, action banner, timeline table,
dockable panel, measurement strip, nav consolidation, tablet mode,
limits disclosures, contrast audit.

## 2026-08-11 — Workspace consolidation: the part is the primary interface

Structural pass per the consolidation brief. Context drawer: part
routes grouped under PART/HOLD/CUT/VERIFY/DELIVER (collapsible groups,
current group open; a 15-item flat list became five headings), whole
drawer collapses to a 24px edge tab. View-control stack floats behind
one VIEW button. FOCUS workspace (F): drawer + panel + controls +
drawers + timeline collapse in one keystroke, with a critical-status
chip (blocking count + next action) that never leaves the screen.
Blocking banner compacted: count + worst blocker + FIX, expandable to
per-blocker pills routing to evidence. Timeline minimized state keeps
a one-line selected-operation summary. Shortcuts: F/V/1–5/Esc, never
while typing. Responsive defaults: drawer + timeline collapsed below
1440px, feature panel collapsed everywhere until a feature is
selected. Measured matrix in docs/RESPONSIVE_WORKSPACE.md — 1366×768
default 60% canvas (was 18%), no horizontal scroll anywhere, readiness
and next action visible at every size. No route deleted
(docs/ROUTE_MAPPING.md). All suites pass. 95 tests.

## 2026-08-12 — CANVAS GUIDE: tutor mode, honestly scoped

Guide engine (pure — no write path to manufacturing state, pinned by
test), GuideSession with actual visited-step history, BACK ONE STEP as
a history pop that follows branches as travelled and is disabled at the
first step. Modes OFF/ASSIST/TEACH persisted per user (GuideState,
paired migrations); first-run experience profile mapping to a default
mode only. Floating Guide Card (datum mark, precision blue, machinist
voice, collapsible to a tab; G / Shift+G / Alt+← / Esc, guarded while
typing), coach marks on stable data-guide-target ids, MAKE_A_PART flow
spanning the familiar CAM backbone with state-based completion,
branching, and blockers that take priority over lessons. Training Shop:
Part.training + seeded Basic Plate; the NC export mint refuses training
parts server-side. Verified live: first-run → TEACH, step-of-N with
already-done detection, back disabled at first step, guide progress
coexisting with NOT READY, coach-mark deep link, training NC refusal.
8 new engine tests. 103 tests. Honest gaps in docs/GUIDED_WORKFLOW.md:
no sketching flow (no sketching exists), no turning flows, no analytics
yet, coach marks do not auto-expand collapsed panels.

## 2026-08-12 — TURNING: TURN_2_AXIS lands as a first-class process

Multi-process spine (PROCESS_SUPPORT map as the single truth), four new
tables (LatheMachine, LatheWorkholding, TurningTool, RotationalPart —
paired migrations), rotational X/Z domain with validation, seven
deterministic turning toolpath engines (thread feed = pitch never
retimed; groove/thread/part-off refusals), CSS with G50 clamping, four
hold analyses that refuse to invent inputs (the demo chuck ships with
clamp force deliberately unrecorded → UNKNOWN until a human records
it, audited), worst-gate turning readiness, a development lathe post
that refuses unclamped G96, the 40mm nominal-reasoning demo with
ACCEPT/KEEP/INVESTIGATE (accept = USER-CONFIRMED + audit), and the
/lathe workspace with a real PROFILE X/Z view. CANVAS Demo Shaft
seeded. 13 new engine tests; 116 total. One real bug found by browser
verification: zero-length SHOULDER segments failed validation — fixed
and pinned. Everything absent is labelled DEVELOPMENT or NOT BUILT in
docs/TURNING_MASTER_SUMMARY.md, never mocked.

## Lathe NC parser + backplot (Run It Past CANVAS — lathe)

Refusal-first 2-axis parser (`turn/nc-parse.ts`): modal G0/G1/G32,
G96/G97/G50, G20/G21, G98/G99, X-as-diameter; G7x/G8x cycles, TNR comp,
macros and subprograms refused by line with UNSUPPORTED_CONTEXT — never
silently assumed safe. analyzeLatheNc gives an ESTIMATED cycle with
stated assumptions (800 IPM rapids, CSS at mean diameter capped by G50
and the recorded chuck limit), untimed segments counted not guessed,
findings MISSING_MAX_RPM_CLAMP / RPM_LIMIT_REVIEW / CSS_NOT_USED /
UNKNOWN_SPINDLE_CONTEXT. /lathe/[id]/nc-review page with X/Z backplot
on light paper (blue CSS cut, black fixed-RPM cut, dashed rapids),
linked from the workspace NC panel. SELF-TEST: the parser reads the
development post's own output with zero refusals and the two cycle
estimates agree. 5 new tests; 121 total. Browser-verified live.

## Turning cycle optimizer

optimizeTurnCycle (turn/optimize.ts): per-segment load bands
(LIGHT/TARGET/HIGH/REVIEW/UNKNOWN) from the program's own F/S words
against the shop's recorded insert windows; FEED proposals for rubbing
cuts capped by preset; CSS_CONVERSION proposals for wide-range G97
regions at the SFM the program already accepts at its largest diameter,
clamped by the chuck's recorded RPM limit — refused with a named gap
when that limit is not recorded. Thread passes never touched; no
coordinate word ever proposed. Surfaced as an Optimizer proposals panel
with preset selector on /lathe/[id]/nc-review, DEVELOPMENT ANALYSIS
labelled. 5 new tests; 126 total. Browser-verified live.

## Lathe soft jaw generator

turn/soft-jaws.ts: bore-in-place recipe (grip ⌀ exactly, under preload
on a ring sized from the chuck's recorded jaw stroke — not sized when
the stroke is unrecorded, missing input named; RPM/feed only from the
boring bar's recorded windows; refuses without grip ⌀/length or when
the bar cannot enter). Drawer search with lathe rules: a bored chuck
jaw only ever grows — DIRECT / REBORE (≤0.5" growth or step deepening)
/ BLANK / UNUSABLE-cannot-shrink. /lathe/[id]/soft-jaws page with jaw
cross-section on light paper and audited HUMAN record-bore action
(server refuses shrinking records). boredDiameter/boredDepth columns +
paired migrations; chuck jawStroke seeded. 5 new tests; 131 total.
Browser-verified: blank→recipe→record→DIRECT round trip live.

## Turning reverse engineering

turn/reverse.ts + /lathe/[id]/reverse: guided bench measurement of a
shaft — datum face first, steps front to back with the instrument named
per reading (audited HUMAN, uncertainty from the device record). The
profile assembles with MEASURED provenance; nominal candidates (wear
window open) show deviation + confidence and are ACCEPTED as a USER
ruling or KEPT MEASURED, both audited. Threads recorded as gauged
designations, never mic readings. Stock is a labelled SUGGESTION with
stated basis. reReadingsJson column + paired migrations; empty RE parts
redirect from the workspace to the bench flow. 5 new tests; 136 total.
Browser-verified: create → measure → accept 40 mm nominal → profile →
workspace round trip live.

## Turning cost + make-vs-buy

turn/cost.ts + /lathe/[id]/cost: bar economics derived from the
rotational model — kerf from the recorded parting tool (refused when
unrecorded), remnant from the recorded grip + a stated 1.0" margin,
parts-per-12ft-bar and utilization computed (remnant/drop amortization
only; no kerf double-count), setup hours built from named adders incl.
+0.6 hr when the soft jaw drawer search says the jaws still need
boring. Cycle from generated toolpaths; generic cost engine does the
arithmetic with per-line basis; BUY unevaluated without a real quote.
4 new tests; 140 total. Browser-verified: 23 parts/bar, 97.8% computed
utilization, $46.77 unit cost at qty 5 live.

## 3D lathe view + playback + stock states

turn/sim.ts + components/turn/lathe-3d.tsx in the workspace: the stock
state of a turned part is one curve (radius vs Z, 400 cells); the sim
replays the deterministic toolpaths against it with the same per-rev
timing as the cycle estimates (rapids at a stated 800 IPM). Live
revolved mesh with raw vs machined colouring, tool point riding the
clock, play/scrub/speed transport, and per-operation STOCK STATE jump
buttons. Labelled DEVELOPMENT with its limits printed: not a collision
check, tool drawn as its programmed point, internal ops advance the
clock but never carve the OD (stated, not faked). 4 new tests; 144
total. Browser-verified: playback, scrub, and all 7 stock states live.

## Cinematic turning mappings

cinematic.ts gains process:"TURN" + barStock: lathe-voice shot mappings
for all turning op types (bar spins, tool holds; threads deepen pass by
pass; part-off caught cleanly), turning camera language, bar intro
spoken as ⌀ × length, customer-safe turning nouns. Mill wording pinned
untouched. CINEMATIC button on the turning workspace reuses the shared
drawer with the standing disclaimer. 3 new tests; 147 total.
Browser-verified live.

## Turning NC export mint

mintTurnExport/recordTurnExport: the mill's authorization law applied
to turning — single-use 5-minute tokens, server-side SHA-256, atomic
consume, HUMAN + SYSTEM audit rows, gate re-checked at mint AND record
via the new buildTurnPackage (same assembly the workspace uses).
Refuses training parts, blocking gates, and post refusals; REVIEW
gates do not block (human approval is its own gate). Exported files
keep the NOT FOR PRODUCTION USE header — authorization is not
certification. Shared NcExportPanel parameterized over mint/record.
Browser-verified both ways: withheld while gates fail, PREPARED grant
with digest + TTL once the gates pass.

## TURN_A_SHAFT guide flow

flows.ts gains TURN_A_SHAFT: nine steps in the lathe's voice over the
shared GuideContext — profile, bar stock, lathe, hold-with-evidence
(blockedBy surfaces the chuck-grip gate), turning toolpaths, 3D
playback as a teaching step (labelled: watching leaves no record),
instrument capability, worst-gate clearing, delivery via the turning
export mint. GuideCard parameterized by flowId; session persistence
now merges per-flow instead of replacing the whole map (latent
clobber fixed). Turning context assembled on the lathe workspace from
the same computed state the page renders. CREATE_TURN_SETUP removed
from DEVELOPMENT_FLOWS — it exists now. 3 new tests; 150 total.
Browser-verified: first-run profile picker, truthful "Flow complete"
on the finished Demo Shaft, and mid-flow "Pick the lathe" on the RE
part that has geometry but no machine.

## Resizable workspace panels

use-resizable.ts hook (rAF-throttled pointer drag, localStorage
persistence, double-click reset, clamped ranges) applied to the
context drawer (180–340px) and the feature panel (280–560px) via
canvas-edge handles that light precision blue while dragging. CSS
variable widths keep the mobile layout untouched. Browser-verified
with measured widths: panel 356→478 by drag, 478 after reload, 356
after double-click reset; drawer 210→298.

## Coach mark auto-reveal

A coach mark whose target is absent after ~500ms broadcasts
canvas:reveal-guide-target; the context drawer expands, the workspace
leaves focus mode and expands the feature panel (timeline restored).
Browser-verified: focus mode collapses both surfaces, the reveal event
and a real ?guide= miss both expand them. Remaining partial (recorded):
targets behind inactive panel tabs reveal to panel level only.

## Density modes

COMFORTABLE/COMPACT via a Settings toggle + root data attribute
(DensityApplier in the app layout, localStorage-backed). COMPACT
tightens only the shared primitives through density hook classes
(panel chrome, data rows, table cells) — density is spacing, not a
different design. Browser-verified with measured heights: header
36→24px, row 31→27px, persistent across navigation, clean restore.

## Guide card bottom sheet

Below lg the guide card docks as a bottom sheet: full width, bottom
edge, max 70dvh with internal scroll, and a grab bar that collapses it
to the Guide tab. At lg+ nothing changes — 344px floating card, grab
bar hidden. Browser-verified at 414×896 (full width, docked, collapse
works) and 1600×900 (344px, right-docked, no grab bar).

## Guide analytics events

GuideEvent table (paired migrations) + /api/guide/events (session-
scoped, whitelisted actions, capped payloads) + fire-and-forget
emissions from the card on start/advance/back/skip/reset/mode-change
and a once-guarded FLOW_COMPLETE. /knowledge gains a GUIDE FRICTION
panel: steps most backed out of or skipped, with start/completion
counts — telemetry about the guide, never a gate input. Browser-
verified: a live SKIP on TURN_A_SHAFT appears in the panel; the
finished Demo Shaft records a completion.

## REVERSE_A_PART guide flow

GuideContext gains an optional re snapshot (photos, datums,
measurement counts, pending nominals) assembled on the RE session page
from the same reconstruction plan it renders. Five steps: six-view
photo set, datum frame (human act), measure in constraint order
(blockedBy names the missing datums with counts), rule on nominals,
hand off to the part workspace. DEVELOPMENT_FLOWS is now down to
DRAW_FROM_SCRATCH only — every flow the guide names exists. 3 new
tests; 153 total. Browser-verified on a freshly created RE session.

## Run It Past CANVAS — immutable originals + audit gates

The codebase audit found Phases 4A–4F already real (parser, modal
state, acceleration timing, height-field engagement, banded proposals,
masked-diff emission, gated OPTIMIZED rows). Closed the two structural
gaps: (1) uploads now persist as immutable UPLOADED NCProgram rows
(filename, bytes, server sha256, digest-deduped) and the optimizer
derives from the STORED original with digest verification — client
bytes are never trusted twice — with sourceProgramId lineage; (2) a
worst-gate audit gate group (11 gates, 3 stage summaries) renders atop
the analyzer, with stock alignment REVIEW by construction. 7 new
tests; 160 total. Browser-verified: AUDIT PASS / OPTIMIZATION REVIEW
on a clean program, digest shown, re-analysis dedupes to one row.
Status vs the full brief recorded in docs/RUN_IT_PAST_CANVAS.md.

## Phase 5 — optimizer completion, part 1

Finish-pass protection (protection.ts: rule-based regions from the
part's own critical features; segment-to-center distance — a pass
crossing THROUGH a bore is protected, a live-found hole now pinned;
absolute in V1, shared by analyze + optimize routes), corner-spike
REDUCE proposals (2× run-median MRR spikes, chipload floor, 0.08"
minimum stretch, 12% hysteresis, zero claimed savings — control is not
sold as time), and the ROI/capacity panel (RAISE-only savings, no
dollar figure without a configured shop rate). FeedProposal gains
kind RAISE|REDUCE; savings totals count RAISE only. 9 new tests; 169
total. Browser-verified: the demo program yields 3 RAISE, a suppressed
REDUCE (its spike crosses the protected bearing bore), 1 PROTECTED
region and a live ROI panel — the honest mixed-result story.

## Phase 5 — optimizer completion, part 2

Reference cuts (audited HUMAN records of proven cutting regions with
full machine/tool/material/DOC/WOC/feed/RPM context; SHOP_KNOWLEDGE,
scoped, never a gate input), machine calibration (actual-vs-estimated
cycle records; MEDIAN-ratio factor claimed only from 5+ samples —
outliers cannot poison it, pinned by test; display-only, "never
silently applied"), and telemetry architecture (typed interfaces for
MTConnect/OPC UA/logs/CSV with every source rendered NOT CONNECTED —
the only status that exists). All three on /machines. 3 new tests;
172 total. Browser-verified: insufficient-data chip, a recorded cycle
showing +44s variance, a marked reference cut, five NOT CONNECTED
chips.

## Phase 5 — Show Me + NC block sync + original-vs-proposed

Backplot segments now carry source lines; the immutable original
renders as a read-only block-synced viewer (click plot → scroll code,
click code → frame plot). SHOW ME on every finding/proposal/protected
region frames the scene — bounding box + margin, amber highlight,
context dimmed — never a text modal. Accepted proposals open a source
diff (−/+ per changed block, modal feeds honestly shown as
will-be-unapplied) and a PROPOSED plot mode highlighting accepted feed
regions ("geometry identical by construction"). Fixed a dark-flip
defect: the backplot ground returned to the light work window with
fixed inks. Browser-verified: framing, two-way sync, diff rows,
PROPOSED mode. 172 tests still green.

## Phase 5 — operation classification + seeded optimizer demo

classify.ts: deterministic-only operation groups (DRILL/TAP/FACE/
POCKET/LINKING/UNKNOWN) with narrow rules and honest UNKNOWNs,
rendered with Show Me per group. Seeded demo program
(public/demo/O2507-DEMO.nc + one-click Load demo): deliberate mixed
results — air cutting, excessive retract, rubbing RAISEs, an
engagement-spike REDUCE (F60→30), the protected bearing bore, a
review-only G41 region, G81 drilling classified DRILL. Two engine
refinements from fixture authoring: plunges excluded from spike
analysis (vertical entries are not XY corners), and the protection
engine proved itself by suppressing the demo's REDUCE when the slot
passed 0.125" from a tapped hole — the fixture moved, not the rule.
4 new tests; 176 total. Browser-verified: 6 RAISE + 1 REDUCE + 1
PROTECTED + comped review live.

## Phase 5 — RUN_IT_PAST guide flow + blocker-first Readiness

Mission B closes: RUN_IT_PAST flow (4 steps over db-backed facts —
uploads and optimized revisions; the guide clears nothing) mounted on
the analyzer. Mission A begins: the Readiness page is blocker-first —
the worst gate is the page's one dominant object ("NOT READY — N
BLOCKING" hero with full evidence text and RESOLVE routing), remaining
blockers as compact rows, REVIEW compact, passed gates collapsed
behind "N GATES PASSED — VIEW ALL". The gate engine is untouched:
presentation order only, pinned by the untouched 176-test suite.
Browser-verified: hero, 4 resolve routes, collapse/expand, the flow
card live.

## Phase 5 — NC Output command center + Machinist strategy cards

NC Output redesigned as a program command center: a four-cell status
header (PROGRAM / STATUS / CONTROLLER / POST with DEVELOPMENT — NOT
CERTIFIED beside the post, not buried in prose), a one-line pre-flight
rail with ✓/✕ per item, the FIRST UNRESOLVED item as the dominant card
with SHOW BLOCKER routing to readiness, and the certification
explanation behind WHY. The gate logic (buildPreflight, shared with
generate and the mint) is untouched.

Machinist approaches redesigned around strategy cards: five cards with
the cycle dominant, setups/tools/ops, relative cycle and unit-cost
bars (comparison, not judgement), risk chip, the philosophy's tradeoff
line, and SELECTED state. No overall winner declared — stated in
place. The full comparison table survives behind VIEW TABLE for power
users. Browser-verified: both screens live, screenshots match the
brief's examples.

## Phase 5 — Part Library + Turning landing visual tiles

The part library shows parts, not rows. New `part-thumb.tsx` renders
real geometry server-side on the light work-window ground: mill parts
as a top-view drawing from their own features (stock outline, bores —
blue when critical — holes with crosshairs, pockets, slots), turned
parts as their actual revolved-profile silhouette with the blue chain
centerline. Never a blank placeholder icon; a part with no profile
says "no profile yet".

Tiles carry name, part number · rev · material, TRAINING/status and
TURNED chips, and a concise next action derived from real state (Add
geometry / Define stock / Pick an approach / Measure the profile /
Record clamp force / Review and approve / Open workspace). Turned
parts link straight to the turning workspace.

New `library-view.tsx`: GRID default, TABLE one toggle away for power
users, preference persisted per device (canvas.partsView /
canvas.latheView). Both views are server-rendered; the toggle only
chooses. The Turning landing uses the same tiles with ⌀×length bar
line and APPROVED / REVIEW REQUIRED.

Browser-verified: 4 mill thumbs, 3 turn thumbs, 6 next actions, table
choice persisted across reload, 3 lathe tiles with 2 REVIEW REQUIRED.
Screenshots confirm real geometry rendering on both screens.

## Phase 5 — Turning workspace: view modes, operation runway, feature lens

The turning workspace now leads with the part. PROFILE / 3D / BOTH
view modes (new turn-views.tsx, choice persisted per device): BOTH is
a synchronized split where the one ?op= selection drives the profile
highlight, the toolpath overlay and the 3D playback scope at once.

The operation table is no longer the default interaction. A compact
operation runway ("10 FACE · 20 OD ROUGH · 30 OD FINISH…") selects
ops: the selected op strong blue, refused ops amber, the rest quiet.
The full technical table survives one click away behind VIEW TABLE.

Selecting an op whose target is a profile segment opens a Feature
Lens: the diameter dominant, function / tolerance / surface / datum /
operation / tool in a compact grid, CRITICAL and CONFIRMED-or-REVIEW
chips, mating component when known, and honest actions (Measure,
Verify NC, Cost — only routes that exist). Unstated tolerance and
finish say "not stated"; nothing is invented.

Browser-verified on the demo shaft: 3 view-mode buttons, runway
selection, lens fields for the bearing journal (⌀1.5744, +0.0000 /
−0.0005, 32 Ra, Z 0.750–1.950, T0202), BOTH mode split with 3D
canvas live, mode persisted across reload, table behind VIEW TABLE
with 7 rows.

## Phase 5 — NC Analyzer workspace modes + synchronized load graph

The analyzer is now a mode-based instrument, not a stacked document.
After analysis, one workspace shows at a time: BACKPLOT / PROGRAM /
LOAD / TIME / FINDINGS / COMPARE / VERIFY, with live counts on the
tabs (proposals, findings, accepted changes) and the AUDIT/OPT stage
chips always visible beside them. SHOW ME from any mode — a finding,
a proposal, a protected region, an operation — lands in the BACKPLOT
scene with the selection framed.

New synchronized load graph under the backplot: one bar per motion
segment in program order, height and color from the engagement band
(rapids as thin gray ticks), the target band as a quiet reference
stripe, tool-change boundaries with T labels, and top strips marking
protected finish regions (green), proposed raises (blue) and proposed
reductions (amber). The same selection state drives the graph, the
backplot and the code viewer: click a bar and the code scrolls to the
block; click the plot and the graph lights the span. The DEVELOPMENT
LOAD ESTIMATE label stays on the graph — chipload model, not
telemetry.

COMPARE with nothing accepted says so instead of showing an empty
panel. Browser-verified on the demo program: 7 tabs, 63 graph bars,
bar click → "Framing L…", Show me from FINDINGS returns to BACKPLOT,
accept-then-COMPARE shows the −/+ diff, TIME shows ROI, VERIFY shows
the 11 gates.

## Phase 5 — Readiness SHOW ME

Readiness blockers now carry SHOW ME beside RESOLVE — landing in the
physical scene with a coach mark drawn around the element behind the
gate, not a generic list. Inspection gates land on the inspection
plan (new inspection-plan coach anchor); tool availability, reach and
corner gates land on the tooling assignment panel (new
tool-assignment anchor); stock and machine-envelope gates land on the
workspace's define-stock control; workholding lands on the HOLD
context tab; geometry and material land on the PART context. Gates
whose blocker has no physical scene to show simply omit the link
rather than pointing somewhere vague.

Uses the existing ?guide= coach-mark system (scroll into view,
precision-blue outline, reveal event for collapsed owners) — nothing
new invented. Browser-verified: Show Me on the Bearing Support
inspection gate navigates to /inspection?guide=inspection-plan and
the plan panel renders with the coach-mark outline.

## Phase 5 — Guide consistency: ASSIST references the dominant blocker

When a workspace has blocking gates, the Guide's ASSIST card now
references the page's dominant blocker instead of a generic next
action: "READINESS BLOCKED — N GATES / <gate> is the first failing
gate" with SHOW ME (physical scene + coach mark, via the shared
show-me.ts map the readiness page also uses — one map, no drift),
RESOLVE (the readiness page for mill parts; the on-page gates for
turned parts via the new readinessHref context field) and WHY?
(the gate's own detail, disclosed in place). With no blockers the
card falls back to the next required action as before. The Guide
still never duplicates the page and its buttons still write guide
state only — no path from the card to a gate.

Browser-verified: on a part with failing gates the ASSIST card shows
"READINESS BLOCKED — 9 GATES / Geometry is the first failing gate"
with all three actions, WHY? expanding to "No features are defined
on this part."

## Phase 5 — Real shop beta: WAS CANVAS RIGHT?

BetaRunRecord table (paired migrations) + a recording workflow on
/knowledge: verdict YES/PARTLY/NO typed by the machinist, categories
required when not YES (cycle estimate, tool load, workholding, feed
recommendation, tool selection, inspection, geometry, other), the
full capture list behind a FULL RECORD disclosure (predicted/actual
cycle and load, recommendation under test, measured results, wear,
chatter, scrap, corrective action). Panel shows the verdict tally
and per-category wrong counts; each record is audited (HUMAN).
No engine reads the table — shop-scoped beta evidence only, stated
on the panel. See docs/REAL_SHOP_BETA.md.

Browser-verified: recorded a PARTLY run (est 17.7 → ran 18.4 min,
cycle estimate category), tally and category chips updated, and NO
without a category was rejected with the named error.

## PHASE 5 — FINAL TRUTH AUDIT (brief §50)

1. One product? Largely yes now. Mill workspace, turning workspace,
   turning landing, part library, readiness, NC output, machinist and
   the analyzer share the same object-first pattern, chips, runways,
   disclosures and light work-window grounds.
2. Most like internal engineering software still: the setups page and
   the machines page — dense panels, no dominant object. Honest next
   candidates, not claimed done.
3. NC Analyzer shows what matters: one scene at a time, counts on the
   tabs, worst-stage chips always visible. Yes.
4. SHOW ME physically locates: yes for line-range scenes (backplot
   frames + code + load graph) and for readiness gates (coach mark on
   the real element). NOT built: the §13 special scenes for
   workholding load direction and holder-envelope findings.
5. Block sync works both directions (plot→code, code→plot, graph→both)
   — browser-verified. Viewer lacks §14 search/go-to-block/syntax
   highlighting.
6. Original vs optimized: source diff + PROPOSED plot mode. A true
   OVERLAY/side-by-side backplot (§15) is NOT built.
7. Protected finish op accidentally optimized? No — protection is
   absolute in V1, no override path exists, pinned by tests including
   the through-bore regression.
8. Corner reduction deterministic: yes — run-median MRR, spike ratio,
   chipload floor, plunge exclusion; all tested.
9. Reference cuts carry machine/tool/material/DOC/WOC/feed/RPM/
   coolant/result context. Yes.
10. Calibration from real recorded cycles only, median of ≥5,
    display-only. Yes.
11. Telemetry says NOT CONNECTED everywhere it appears, typed as a
    literal. Yes.
12. ROI is labelled ESTIMATED, RAISE-only, capacity-not-revenue, no
    dollar figure without a configured rate. Yes.
13. Readiness is worst-gate; redesign touched presentation order only.
14. No UX path clears a gate — SHOW ME/RESOLVE/lens/runway are
    navigation and display; disagreement records evidence only.
15. NC Output cannot export while blocked: preview withheld, export
    behind the server-side mint that re-runs the gates.
16. Turning kept every limitation label (development post, kinematic
    replay not collision check, DEVELOPMENT analyses).
17. Part library scans by geometry now — yes, substantially.
18. Approach tradeoffs readable from cards without the table — yes;
    table one click away.
19. Should still not be shown to a real shop: NC export headers say it
    already (NOT FOR PRODUCTION USE); the load model's absolute
    numbers (bands are estimates, no telemetry); the 3D lathe replay
    as anything but a preview.
20. Ready for controlled beta: the analyzer loop (upload → audit →
    findings → proposals → derived program), readiness/approval flow,
    turning planning, WAS CANVAS RIGHT? capture, reference cuts and
    calibration records.

Evidence: 176/176 engine tests, production build clean, zero
horizontal overflow at 1280×800 and 1440×900 across the ten
redesigned routes, and per-feature live browser checks recorded
above.

## Post-Phase 5 — Setups page object-first (truth-audit follow-up)

The truth audit named the setups page the screen most like internal
engineering software. It now leads with the hold itself: a new
hold-scene.tsx side elevation on the light ground — jaws gripping the
stock, grip depth and stock projection dimensioned from their real
recorded values, clamp arrows, and the peak cutting force drawn where
it acts (only when the estimate exists; a missing input renders
"cannot draw the hold — <input> not recorded" instead of a fake
drawing). The holding margin is the dominant number beside it, with
its governing failure mode and the DEVELOPMENT ANALYSIS label. The
full force-balance and cutting-force calculations remain openable via
SHOW CALCULATION exactly as before; no engine changed.

Browser-verified on Bearing Support: 2 hold scenes, 2 margin
headlines (7.70× sliding / 8.56× tipping), 4 dimension callouts,
2 peak-force arrows (221 lbf).

## Post-Phase 5 — Machines page object-first (truth-audit follow-up)

The last screen the truth audit flagged. Each machine card now leads
with its working volume: a new machine-envelope.tsx top view — the
table in ink, the XY travel envelope dashed precision blue, both
dimensioned from the profile values, Z stated as text (no fake
isometric). Beside it, the spindle headline (RPM · hp · rapid) and
the machine's timing truth: the calibration statement with median
variance when calibrated, or INSUFFICIENT CALIBRATION DATA — the
separate calibration panels were merged into the machine card they
describe, with recorded cycles and the record form one disclosure
away. Spec grid, reference cuts and NOT CONNECTED telemetry panels
unchanged.

Browser-verified: envelope renders with table 36″×14″, X 30″ / Y 16″
travel and Z 20″; calibration line reads "One sample is an anecdote,
not a calibration"; recorded-cycles disclosure opens with the est
17.42 / actual 18.16 / +44s row and the form; zero horizontal
overflow.

## Post-Phase 5 — COMPARE becomes the §15 comparison scene

COMPARE now leads with the numbers: ORIGINAL / PROPOSED (ESTIMATED) /
SAVINGS PER PART / GEOMETRY CHANGED: NO (masked diff enforced at
generation) / FINISH PASSES CHANGED: NO (protection absolute), in
mm:ss. Reductions state that they add a little time back and are not
estimated as savings.

Below it, the OVERLAY backplot: since feed-only changes produce
identical toolpaths by construction, drawing two copies of the same
lines would be theater — instead one scene carries the change as
color: accepted raises blue, accepted reductions amber, protected
finish regions green, unchanged cutting neutral ink, rapids dashed.
The Backplot component gained an `overlay` prop; the BACKPLOT mode's
band view is unchanged. The source-level −/+ diff remains below.

Browser-verified on the demo: stat strip reads 2:13 → 2:09, 4 s,
both NOs with their reasons; overlay strokes counted 2 raise-blue,
1 protected-green, 16 neutral.

## Post-Phase 5 — §13 special SHOW ME scenes

Workholding load direction: the hold scene now draws the peak cutting
force the way the force balance says the hold would fail — a lateral
arrow "tries to slide the part in the jaws" when sliding governs, a
corner pry with a rotation arc "tries to roll the part out of the
jaws" when tipping governs, a plain arrow when the mode is unknown.
The readiness workholding SHOW ME now lands on the setups hold scene
(new hold-scene coach anchor) instead of the abstract HOLD tab.

Missing tool/holder data: analyzer LOAD gaps now carry a named fix —
"No tool record for T99" gets an ADD THE TOOL link to the tool crib
(new tool-crib coach anchor on /tools); a missing-stock gap gets
DEFINE STOCK to the workspace control. The gap text itself still
names exactly what is absent; the link only takes you to where it is
entered.

Browser-verified: both force vectors render on Bearing Support's two
setups (sliding on setup 1, tipping on setup 2); an uploaded program
calling T99 produced the gap with the ADD THE TOOL link routed to
/tools?guide=tool-crib.

## Post-Phase 5 — NC viewer power features (§14)

The block-synced viewer gained search and go-to, still strictly
read-only: one field handles all three — text searches the program
(match count shown, Enter/Shift+Enter walk matches through the same
selection the backplot and load graph follow), a bare number goes to
that line, N420 finds the block carrying that N-word. Matches are
jumped to, never filtered — the program always shows whole. Gutter
markers: T<n> at tool-change lines, a red edge + ✕ where
interpretation refused. Both viewer instances (BACKPLOT and PROGRAM
modes) carry the features.

Browser-verified: 3 tool markers on the demo, "G81" → 1 match with
Enter framing the backplot, line-10 goto, and N140 resolving to
source line 7 on an N-worded program.

## Controlled beta — loop closed and dress-rehearsed

"Report this run" now links from NC output into WAS CANVAS RIGHT?
with program, machine, material and predicted cycle pre-filled
(query-param prefill on /knowledge; the verdict and actuals remain
the machinist's to type). With that, the full beta loop was
dress-rehearsed end to end in the browser — analyze → audit →
findings → accept → derived program stored → export correctly
withheld (NOT READY) → run reported with prefill → calibration cycle
recorded → reference cut recorded → turning workspace sanity — all
ten steps passing with measured values recorded in
docs/BETA_RUNBOOK.md, which is the week-one script for a real shop.

## Mobile audit at phone width (390px)

Full pass across 12 screens at 390×844: zero horizontal overflow on
every route, grids collapse to one column, the Guide docks as a
bottom sheet, SVG scenes stay legible. A four-agent visual review of
the screenshots found no broken screens; two cramped items were fixed
— the hold-scene force annotation now anchors inside the drawing
frame (was clipping mid-word at phone width) and the workspace
blocking banner hides its truncating message below sm, leaving
"N blocking — action required" + FIX. Known accepted nits: the
top-bar trail is horizontally scrollable (chips can sit cut at rest),
and page titles appear in both the bar and the heading.

## Mobile polish round two + honest empty thumbnail

The two accepted nits from the mobile audit are now addressed: the
top-bar trail fades out at its right edge (mask only — it still
scrolls) so a chip waiting off-screen reads as "more to the right"
rather than broken; and a mill part with no features no longer draws
an empty stock outline that looks like a finished blank plate — the
tile says "stock only — no geometry yet" (or "no geometry yet" with
no stock), dashed outline, on the same paper ground.

Browser-verified at 390px: no-geometry tile renders with its label,
fade mask computed on the trail, readiness page showing the dominant
blocker with SHOW ME/RESOLVE cleanly at phone width.

## Bug fixes — responsibility profile completion + view background

Engineering-input gate could never be satisfied from the UI: for a
critical part it requires material condition, surface finish and
inspection requirements, but no form wrote those intent fields, and
recorded unknowns counted as outstanding inputs with no way to
resolve them. The responsibility profile now carries all three fields
(written USER-confirmed only when provided — blank stays blank) and
lists open unknowns with explicit per-item resolution checkboxes, all
audited. Verified live: filling the profile on Bearing Support took
Engineering input to PASS, and answering HIGH consequence correctly
escalated the part to CRITICAL APPLICATION with its review gate —
the gate got satisfied by real inputs, not weakened.

View environment background never applied: the scene background was
attached once at canvas construction (<color attach>), so preset and
custom background changes silently did nothing. Replaced with an
imperative SceneBackground that follows the value every change.
Verified live: Dark Machine Bay preset and custom hexes now repaint
the scene immediately.

## Workspace consolidation + visual parity pass

Header condensed to one 64px command row shell-wide (identity + trail
+ metadata + status; inferred headings only on pages without a trail
— duplicate titles gone). Shell now 100dvh. RESET VIEW and RESET
WORKSPACE added to the View environment drawer. Camera reset listener
added to the scene. Verified across the brief's matrix: zero
horizontal and zero page scroll at 1366/1440/1920/1024; part canvas
62% of a 1366×768 screen by default and 66–77% in Focus, with the
critical-status chip (NOT READY · N BLOCKING · next action) retained
in Focus at every size. F/V/1–5 shortcuts confirmed live.

## Workspace consolidation pass 2

Part-route defaults corrected (drawer collapsed, runway minimized at
every width — default canvas share now 67% at 1440×900 and 74% at
1920×1080, inside the brief's 70–75% target without Focus).
Context-aware quick toggles beside VIEW/FOCUS (HOLD→Fixture,
CUT→Toolpath/Tool). Viewport quality AUTO/HIGH/PERFORMANCE persisted;
PERFORMANCE reduces dpr/shadows/reflections only — never geometry,
toolpaths, datums or warnings. All browser-verified.

## Feature Detail — metrology module

The reference design's metrology block, built entirely from engines that
already existed. The Feature Detail panel's "Inspection tool" section is
now METROLOGY and always renders (absence is a finding, as with datums):

- Capability: the best instrument on hand, its range/resolution/
  uncertainty/calibration, and a band-consumption bar. The bar is a
  physical ratio of the instrument's ± to the stated tolerance band —
  not a score, confidence or progress meter. Ticks mark the capability
  target (10%) and the threshold past which a reading cannot verify the
  dimension (12.5%); the printed number is never clamped when the fill
  is, and an uncalibrated instrument's ratio is labelled as arithmetic
  on an untraceable number.
- First-article verdict: CONFORMS / DOES NOT CONFORM / CANNOT DETERMINE
  / NOT MEASURED from assessConformance, with NOMINAL / MEASURED /
  DEVIATION / LIMITS and the departure beyond the violated limit. Every
  number travels from the server inside VerifyInfo.evidence — the exact
  inputs the engine was given — so the verdict and the numbers beside it
  cannot disagree.

Also fixed, found by an adversarial review of the first draft (22
confirmed defects, all from real code paths):

- The workspace judged conformance on raw measuredValue while the FAIR
  report and session page used resolvedValue ?? measuredValue, so one
  reading could verify two ways. One field now.
- The bar's "limit" tick sat at the capability engine's 25% while the
  verdict below failed at the conformance engine's 12.5% — both rules
  are called "4:1" and divide by different things. The tick that governs
  the verdict is the one drawn; the capability limit is stated in words.
- "Limits — none stated" printed for characteristics that DO state a
  tolerance but have no single nominal to anchor it to (any FACE or
  pocket). Now "+0.0020 / −0.0020, unanchored" beside the engine's own
  reason.
- The capability card rates the best instrument on hand; the reading may
  have been taken with another. Where they differ the panel says so
  instead of letting a green bar corroborate a verdict it had no part in.
- Section 2's compare() Deviation and "Against band" rows contradicted
  the engine on the same numbers (a bare inside/outside test that never
  sees measurement uncertainty). Removed; one deviation, from the engine
  that owns the verdict. Its hard-coded "no inspection result has been
  recorded" sentence — printed directly above one — is now conditional.
- The verdict card and the record CTA are gated on the FAIR's own
  characteristic predicate, so neither claims first-article
  accountability for a chamfer nor lands on a page with no form for it.
- Removed the mode-blind measurementSessionId prop chain: nothing could
  use it honestly, and labelling it a reverse-engineering session
  asserted a mode the id does not carry.

Browser-verified across all four verdict states with real instrument
uncertainties, plus the tolerance-without-nominal case and the
not-a-characteristic case. 176/176 engine tests pass.

Known pre-existing defect, NOT fixed here (different subsystem):
features/[fid]/page.tsx stores an accepted fit as
`toleranceMinus = Math.abs(fit.lowerIn)`, which loses the sign for
interference classes where both deviations are positive (k6). The limits
readout inherits it.

## Visual parity audit (brief §30/§45)

Measured on the running production build at 1366×768, 1440×900,
1920×1080 and 1024×768: zero horizontal and zero page scroll at every
size; canvas share 62 / 67 / 74 / 58%; drawer, feature panel and view
environment collapsed/closed and the runway minimized by default;
readiness, blocker count and next action visible in every state.
Viewport ground sampled at rgb(243,243,241) — Studio White as designed.

Differences from the approved reference are recorded in
docs/VISUAL_PARITY_AUDIT.md, split into deliberate (operation execution
status and SEND TO MACHINE do not exist and will not be faked; the
banner shows the top blocker per brief §9; the reference's own FAIL
contradicts its numbers and ours computes the verdict) and real gaps
(part rendering fidelity, grid-vs-gradient ground, header chrome,
bottom action bar placement, next-action card, setup cards, orientation
controls, instrument illustration, analytics route).

## Part rendering fidelity — attempted, reverted, diagnosed

Raising the metals to physical conductor values and adding anisotropy
for tool-mark specular made the viewport worse: top face clipped to
rgb(254,254,254), sides crushed to rgb(0,0,0), measured by sampling the
captured PNG. Rebalancing the direct lights and adding four enclosing
Lightformer panels moved nothing; setting those panels to intensity 20
also moved nothing. The `<Environment>` rig is not reaching the part
material's environment map — which is why the committed low metalness
values work at all. Reverted to the known-good material; the diagnosis
and the next step are recorded in docs/VISUAL_PARITY_AUDIT.md so the
next attempt starts from the real cause rather than from tuning.

## Part rendering fidelity — closed, with a corrected diagnosis

Metals now sit at real conductor values (aluminium 0.62 → 0.9) with the
environment raised to light them. Sampled on the seeded plate: top face
rgb(148,150,153) → rgb(128,131,134), side wall rgb(119,122,125) →
rgb(96,100,102), with a real gradient where there was a near-flat fill.
Cast iron, brass and aluminium verified visually distinct.

The earlier BUILD_STATUS entry claiming the Environment rig "is not
reaching the material" was WRONG and is corrected in
docs/VISUAL_PARITY_AUDIT.md. An in-scene probe showed scene.environment
populated with ACES tone mapping active, and forcing environmentIntensity
0.5 → 3.0 moved every sampled pixel. The environment was arriving; there
was too little of it to light a surface with no diffuse response.

Anisotropy (the tool-mark highlight) remains out, now for an isolated
reason: at anisotropy 0.35 the top face clips to rgb(255,255,255) and the
wall crushes to rgb(0,0,0), because it needs a tangent frame the merged
ExtrudeGeometry does not carry. It returns only after real tangents are
computed.

## Anisotropy — the tool-mark highlight, now rendering

The last piece of the reference's machined look. It failed earlier not
because of the material but because of the geometry: mergeGeometries in
part-solid.ts concatenates position and normal only, dropping the
ExtrudeGeometry UVs, so three had nothing to derive tangents from and the
shader ran on a degenerate frame (top face rgb(255,255,255) over walls at
rgb(0,0,0)).

computeMachiningTangents() now builds the frame directly — one world
direction projected onto each vertex's surface plane, with the standard
fallback where the normal is parallel to it. With anisotropy 0.3 restored:
rgb(134,136,139) top face, rgb(156,159,162) centre, rgb(92,95,98) wall. In
range, no clipping, directional sheen visible across the top face.

It claims one consistent direction, not a per-operation cut direction —
the solid is merged slabs with no per-operation channel, so a tangent
field following each operation's real feed would be invented. Cast iron
and plastic sit at anisotropy 0.

## The ground, and a grid that was never drawing

Parity gap 6 in docs/VISUAL_PARITY_AUDIT.md, closed. The reference has a
graduated ground with no grid; CANVAS drew a flat fill with a grid over it.

`gradientTexture()` in scene.tsx builds a radial gradient on a 2D canvas
from the preset's own background colour and applies it to
`scene.background`. Generated in process rather than fetched — same reason
the environment rig is Lightformers and not a preset HDR: the viewport has
to draw a part on a shop floor with no internet.

The stops had to be set by measurement. The first pass used +18% toward
white at the centre and −11% toward black at the rim, which sampled out at
rgb(247,247,245) down to rgb(235,235,233): twelve levels across the whole
frame, a gradient by construction and a flat wall to look at. ACES tone
mapping runs on the background quad and compresses whatever it is given, so
the stops have to be wider than the result wanted. At +22% / −32% over a
tighter radius the frame measures rgb(247,247,245) at the peak, rgb(217,217,216)
at the top corners and rgb(207,207,206) at the bottom — forty levels.

`backgroundGradient` is a real field with a real control in the drawer's
Surface section. High Contrast sets it false and measures 1 level of
falloff, which is how we know the flag reaches the renderer.

The grid is now off on the default ground — it is decoration, not
reference, and the work offset, datum letters and part size are all drawn
elsewhere. It stays on in Inspection Gray, Blueprint Blue, Dark Machine Bay
and High Contrast.

That change exposed a defect: those presets also draw a floor plane, and
the floor sat 0.003 under the grid, which is nothing across a plane forty
units wide. The depth buffer lost the difference and the floor won, so
every preset that turned the grid on drew no grid. Confirmed by switching
the floor off, at which point the grid appeared. Fixed with a polygon
offset on the floor material rather than a larger gap, because the gap that
works at the near edge is not the gap that works forty units out.

## Orientation, out of the menu

Parity gap 11, half closed. A segmented ISO / TOP / BOTTOM / FRONT / REAR /
LEFT / RIGHT control now sits at the bottom centre of the work window,
driving the same camera positions the VIEW menu always drove. The views
were not missing before; they were four clicks deep, which is three too
many for the thing a machinist does most — look straight down at the face
being cut, then straight at the wall, then back.

The highlight is honest about where the camera actually is. Dragging the
part clears every highlight, because the camera is then in no named view.
OrbitControls fires `start` on the first drag and CameraSync republishes it
as `canvas:orbit`. Entering HOLD reframes to take in the vise, which is not
a named view either, so `setView` takes the label as a separate argument and
that path passes none.

Verified in the running build at 1920x1080, 1440x900, 1366x768 and 1024x768:
control present, no horizontal scroll at any size, ISO lit on arrival, TOP
lit after clicking TOP with the camera genuinely looking down the Z axis,
nothing lit after a drag. Hidden below md, where the view cube covers it.

The reference's bottom-right viewport tool icons are still out. They
duplicate controls that already exist in VIEW rather than adding capability.

## The instrument, drawn

Parity gap 12, closed. instrument-glyph.tsx draws thirteen schematics, one
per deviceType in the capability engine's vocabulary — outside, inside and
depth micrometers, digital caliper, dial bore gauge, telescoping gauge, pin
gauge, height gauge, dial indicator, surface plate, optical comparator, CMM
and spindle probe. They render in the Feature Detail capability card and in
the metrology page's instrument table.

The drawing follows the data: it is selected by the deviceType on the real
MetrologyDevice record assessCapability picked. A micrometer drawn beside a
verdict computed against a CMM would be a picture that lies, which is worse
than a number that lies because nobody thinks to check a picture. An
unrecognised deviceType draws nothing — the same refusal HoldScene and
MillPartThumb already make.

No reading is implied: no needle on a dial, no digits in a display, no
deflection, no annotated gap. There is no probe feed or live instrument
connection in CANVAS and a pointer resting at a graduation would suggest
one. It is also not a meter — no arc fill, no coloured sector, no ring.

Verified by rendering all thirteen. The six device types the demo shop does
not own were seeded temporarily, captured, checked and removed. The first
micrometer was wrong: drawn frame-around-the-gap it read as a closed
capsule, and was redrawn with anvil and spindle sharing one axis and the
frame swinging below it.

## Setup cards: the audit was wrong, and no code was written

Parity gap 10 claimed the reference's SETUP 01 / SAFE cards beside the
viewport were missing. They are not. operation-runway.tsx:286-302 renders
exactly that artifact from assessWorkholding's own vocabulary, and the same
setup-plus-verdict pair renders on three further surfaces.

The difference is placement. Moving it into a left column would cost canvas
share that is already 62.1% at 1366x768 and 57.7% at 1024x768 — both under
the 70-75% target the brief protects — to show a fifth copy of a verdict
already on screen. Recorded rather than quietly dropped.

## Every Add button in the shop now goes somewhere

Five "Add" buttons pointed at routes that did not exist: /tools/new,
/machines/new, /materials/new, /metrology/new and /workholding/new. Nothing
in CANVAS could write any of those records — the only create sites were the
seed scripts — so the shop-setup pages were read-only tables with buttons
that 404'd, in the empty states a new shop sees first.

All five exist now, on a shared ShopForm. Plain form posts, no client
JavaScript: a shop-floor terminal on a slow connection can fill in a record
and it will submit, and validation lives on the server where it has to live
anyway. Tools additionally have an edit route with per-field auditing.

Required means an engine needs it, not that the record should look complete:

  Tool       diameter, corner radius, flutes, chipload, sfm, stickout,
             flute length, max RPM
  Machine    travels, table, spindle limits, changer limits — a machine
             without them cannot fail the envelope gate, so it cannot pass
             it honestly either
  Material   specific cutting energy, because the force model divides by it
             and aluminium to steel is a factor of three
  Instrument uncertainty, because it is the denominator in every
             inspection-capability verdict the shop will see

What stays optional stays optional for a reason. Vise clamp force is
nullable so the holding margin can come back INDETERMINATE naming it as the
missing input, rather than pushing a shop to type a catalogue figure it has
not measured. Axis acceleration is nullable so cycle estimates stay
distance-over-feed and say so. Material yield and tensile strength are
nullable so CANVAS declines to size a load rather than borrowing a figure
from a similar alloy.

One bug found in the form layer itself: step="100" on maximum RPM made the
browser reject 12000 with "the two nearest valid values are 11901 and
12001", blocking the submit before the server saw it. HTML validates against
min + n*step, so step is not a precision hint and is no longer used as one.

Verified in the running build, all five routes: the route resolves, the
server guard holds with native validation disabled and names every missing
field, and a complete record saves and appears in the list.

## Not built: the tool carousel

Tool has a toolNumber and no machine relation; Machine has
toolChangerCapacity as an integer count. Nothing anywhere records that T7 is
in pocket 7 of the VF-2, so there is no carousel to add to — the machines
page prints "20 pockets" as a spec, not as an occupancy.

Adding pocket assignment is a schema change plus both migration sets, which
is fine. What is not a small decision is what it does to the TOOL
AVAILABILITY gate: readiness.ts:107-111 currently passes when the part has
tools assigned from the crib. Once pockets exist, the honest gate asks
whether those tools are loaded in the machine the setup is assigned to —
and parts that pass today would start failing. That is a gate behaviour
change and belongs to the shop, not to an assumption made here.
