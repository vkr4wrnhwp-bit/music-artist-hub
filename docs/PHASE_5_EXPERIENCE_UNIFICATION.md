# PHASE 5 — EXPERIENCE UNIFICATION

Mission A of the Phase 5 brief: bring Turning, NC Analyzer, Readiness,
NC Output, Machinist Approaches and the Part Library up to the Bearing
Support workspace's standard. Object-first, blocker-first, technical
depth on demand. Every engine underneath is untouched — this phase
changed presentation and interaction, not one calculation.

## The core rule applied everywhere

Each screen has ONE dominant object, ONE primary action, contextual
support, and depth behind WHY / VIEW TABLE / details. Tables survive
for power users, one persisted toggle or disclosure away, never as the
default interaction.

## Screen by screen

### Part Library (`/parts`)
Visual grid by default: real-geometry thumbnails (`part-thumb.tsx`) —
mill parts as a top-view drawing from their own features (critical
bores in blue, holes with crosshairs), turned parts as their revolved
profile silhouette with the blue chain centerline. Tiles carry status
chips and a state-derived next action. `library-view.tsx` persists
GRID/TABLE per device (`canvas.partsView`). The full revision table is
the TABLE view, unchanged.

### Turning landing (`/lathe`)
Rotational parts as profile-silhouette tiles with ⌀×length,
APPROVED / REVIEW REQUIRED and a next action; list view one toggle
away (`canvas.latheView`). Machines, workholding and tooling panels
remain compact secondary sections.

### Turning workspace (`/lathe/[id]`)
PROFILE / 3D / BOTH view modes (`turn-views.tsx`, persisted in
`canvas.turnView`); BOTH is a synchronized split — one `?op=`
selection drives the profile highlight, the toolpath overlay and the
3D playback scope. The operation table gave way to a compact runway
(selected op strong blue, refused ops amber; VIEW TABLE keeps the
full table). Selecting an op with a target segment opens the Feature
Lens: diameter dominant, function / tolerance / surface / datum /
operation / tool, CRITICAL and CONFIRMED-or-REVIEW chips, honest
actions only. Unstated values say "not stated".

### NC Analyzer (`/parts/[id]/nc-analyzer`)
Mode-based instrument: BACKPLOT / PROGRAM / LOAD / TIME / FINDINGS /
COMPARE / VERIFY, one scene at a time, live counts on the tabs, stage
chips always visible. SHOW ME from any mode lands in the BACKPLOT
scene with the selection framed. Synchronized load graph under the
backplot (see NC_ANALYZER_UX.md).

### Readiness (`/parts/[id]/readiness`)
Blocker-first: the worst gate is the page's dominant object with
RESOLVE and SHOW ME (physical scene + coach mark via the shared
`lib/guide/show-me.ts` map); other blockers as compact rows; REVIEW
items in their own panel; passed gates collapsed behind "N gates
passed — view all". The worst-gate engine is untouched.

### NC Output (`/parts/[id]/nc`)
Program command center: four-cell status header (PROGRAM / STATUS /
CONTROLLER / POST with DEVELOPMENT — NOT CERTIFIED beside the post),
one-line pre-flight rail with ✓/—/✕ per item, the FIRST UNRESOLVED
item as the dominant card with SHOW BLOCKER, certification depth
behind WHY. Gate logic (`buildPreflight`) unchanged; export stays
mint-gated.

### Machinist Approaches (`/parts/[id]/machinist`)
Strategy cards: cycle dominant, setups/tools/ops, relative cycle and
unit-cost comparison bars, risk chip, the philosophy's tradeoff line,
SELECTED state. No overall winner is declared — stated in place. Full
comparison table behind VIEW TABLE.

### Guide
ASSIST references the page's dominant blocker ("READINESS BLOCKED —
N GATES / <gate> is the first failing gate") with SHOW ME / RESOLVE /
WHY?, falling back to the next required action when nothing blocks.
The card still writes guide state only.

## Verification

Every redesigned screen was browser-verified live (Playwright against
the production build) before push, with measured values recorded in
BUILD_STATUS.md. Responsive check at 1280×800 and 1440×900 across the
ten redesigned routes: zero horizontal overflow. 176 engine tests
pass; production build clean.

## What presentation was NOT allowed to do

- No percentage or average appeared anywhere readiness is shown.
- No UX path clears a gate: SHOW ME, RESOLVE, runway chips, lenses
  and cards are navigation and display only.
- DEVELOPMENT / ESTIMATED / NOT CONNECTED labels moved with their
  features into the new layouts, never dropped for cleanliness.
