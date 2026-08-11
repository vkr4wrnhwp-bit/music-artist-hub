# Load-Aware NC Optimizer — Concept Audit & Implementation Plan

Status: **AUDIT — nothing in this document is implemented.** This is the
honest inventory of what the codebase already provides, what must be built,
and what must not be claimed until the math and context exist.

The one-sentence verdict up front: **CANVAS is unusually well positioned for
Phases 4A–4C because the stock-removal simulator already computes the thing
load-awareness needs — material removed per motion segment — but true
load-aware feed optimization is gated on context the user may not supply,
and every finding without that context is REVIEW or INSUFFICIENT DATA, not
a proposal.**

---

## 1. What already supports this (audit of the current codebase)

| Asset | Where | What it gives the optimizer |
|---|---|---|
| `Move[]` / `Toolpath` | `engines/cam/types.ts` | The internal motion representation. Parsed NC lands here and everything downstream — viewport, simulator, cycle time — works unchanged. |
| `StockRemovalSimulator` | `lib/sim/stock-removal.ts` | **The core asset.** Height-field replay already computes removed volume per cut step, collision events, and per-segment timing. Air cutting = segments that remove zero material. Engagement estimate = volume removed ÷ (axial depth × distance). Tested (7 tests). |
| `cycleTime()` / `buildTimeline()` | `cam/engine.ts`, `lib/sim` | Distance-over-feed timing, rapids at machine rate. The baseline for savings estimates. |
| Kienzle cutting-force model | `engines/cutting-force.ts` | Real load math: chipload, engagement, material specific energy → force. This is what turns "engagement estimate" into "load estimate". |
| Tool / Machine / Material models | `domain/shop.ts`, DB | diameter, flutes, stickout, flute length, chipload window, SFM window, maxRPM; machine maxFeed, rapid, travels; material specificEnergy. |
| `verifyNc()` | `cam/post.ts` | A text linter (envelope, spindle state, units). NOT a parser — but its checks apply verbatim to optimized output. |
| STEP importer | `lib/step/` | The parser pattern: dependency-free, deterministic, honest unrecognized-report. The NC parser follows it. |
| Review/finding structures | `machinist-review.ts`, readiness gates | Finding severity vocabulary and the worst-gate aggregation the optimizer's verdicts must reuse, not reinvent. |
| Export mint | `nc/actions.ts` | Server-minted, gate-checked, single-use export authorization. Optimized NC exports through **the same mint**, never a new path. |
| Upload path | `UploadedAsset` + storage | File intake exists. |

## 2. Does CANVAS parse NC today?

**No.** Generation is one-way: `Move[] → post → text`. The only code that
reads NC text is `verifyNc()`, which regexes lines for linting and builds no
motion. There is no interpreter, no modal state machine, no backplot.

## 3. Architecture to add

```
src/lib/nc/
  parse.ts       ISO/Fanuc word parser → NCBlock[] (line-preserving)
  interpret.ts   modal state machine → MotionSegment[] (absolute, inches,
                 arcs tessellated, canned cycles expanded)
  backplot.ts    MotionSegment[] → Move[]  ← everything downstream is free
  analyze.ts     cycle time breakdown, air-cut/retract findings
                 (drives StockRemovalSimulator when stock context exists)
  load.ts        engagement per segment → Kienzle load estimate
  optimize.ts    findings → OptimizationProposal[] (feed-only in V1)
  emit.ts        proposal application → optimized NC text + line-mapped audit
```

Deterministic end to end. No model call anywhere in this pipeline — an LLM
never retimes machine motion (CLAUDE.md principle 6 applies to *modified*
motion exactly as it applies to generated motion).

## 4. V1 G-code subset

| Support | Words |
|---|---|
| Full | G0 G1 G2 G3 (arcs tessellated to the simulator's tolerance), G17, G20/G21, G90/G91, F, S, T, M6, M3/M4/M5, M8/M9, M30, comments, block numbers |
| Single-offset assumption | G54–G59 parsed; a program using **more than one** offset downgrades every spatial finding to REVIEW (fixture-relative geometry unknown) |
| Expand if feasible | G81/G83 drilling cycles (the interpreter expands them to moves; retiming allowed on the plunge feed only) |
| Parse, never retime | **G84/G74 tapping — feed is the thread.** The optimizer refuses to touch a tap block, same rule as the posts. |
| Review-only | G41/G42 cutter comp (comped geometry is machine-side; every finding inside a comped region is REVIEW), G18/G19 planes (flagged, motion not interpreted in V1) |
| Refuse | Macros (#variables, IF/WHILE), subprograms (M98/M97), 4th/5th axis words. A refused program says exactly which line refused it. |

## 5. Data required for true load-awareness

From the models that already exist: tool diameter, flute count, tool class,
stickout, flute length, chipload window (Tool); material + specificEnergy
(Material); stock envelope (PartRevision); machine maxFeed/rapid/travels
(MachineProfile); workholding + holding margin (Setup + holding-margin
engine); spindle speed and feed from the program itself.

Derived by the replay: per-segment DOC/WOC/engagement from the height field;
operation-state geometry (the stock as it is *at that line*, which the
replay gives for free and a static model cannot).

**Honest gaps in the current data model:**
- **Acceleration model: BUILT (2026-08-11), gated on recorded data.**
  `Machine.axisAccel` (in/s², nullable) drives a trapezoidal profile with
  cos-scaled junction velocities and forward/backward feasibility passes
  (`src/lib/nc/time.ts`). Null accel → timing stays distance-over-feed and
  the assumptions say so; the value is never guessed. The model itself is
  DEVELOPMENT ANALYSIS: jerk, per-axis limits and control look-ahead are
  not modelled, and it says that on every analysis.
- **No finished-part model for uploaded NC.** Geometry preservation is
  verified as "same motion, different feeds" (bitwise geometry-word
  identity), not against a part model — which is why V1 changes feeds only.
- **No holder solid.** Holder clearance checks are the flute-length ring
  check the simulator already does; a true holder profile is later.

## 6. Missing data → verdict, not guess

| Context available | Best achievable |
|---|---|
| NC only | Backplot, cycle-time breakdown, retract-height and slow-linking heuristics. Air cutting **cannot be confirmed** without stock — retract-plane findings cap at REVIEW; everything load-shaped is INSUFFICIENT DATA. |
| + stock | Air cutting CONFIDENT (replay proves zero removal). Engagement profile exists but unitless. |
| + tool geometry | Engagement in real units; chip thinning computable; corner-spike detection at REVIEW. |
| + material + machine | Kienzle load estimates; feed proposals become possible: CONFIDENT inside the model's envelope, REVIEW at its edges. |
| + workholding | Load-direction-vs-holding findings (`WORKHOLDING_LOAD_DIRECTION_REVIEW`) using the real holding margin. |

`INSUFFICIENT DATA` is a first-class verdict rendered as such, with the
named missing input — the mating-engine pattern. No default is ever
substituted to make a proposal possible (principle 12).

## 7. UI flow

Lives under **Run it past CANVAS** (the review surface that already exists):

Upload NC (+ optional STEP / tool table / setup binding) → parse report
(what was understood, what refused, line-numbered) → **Backplot** (existing
viewport, existing Move[]) → **Cycle time analysis** (per-op, cut vs rapid
vs dwell, with the no-accel caveat printed on the totals) → **Load map** →
**Proposals** (each with the §10 fields) → operator accepts/rejects each →
**Simulate** (the existing stock-removal simulator runs the *optimized*
motion) → **Original vs optimized** side-by-side → **Export** through the
existing mint, only when its gates pass.

## 8. Structured models (V1 shapes)

`NCBlock` {line, raw, words, comment} · `MotionSegment` {blockRange, kind
RAPID|LINEAR|ARC_CW|ARC_CCW|DRILL_CYCLE, start/end/center, feed, spindle,
tool, offset, modalSnapshot} · `ParsedToolpath` {segments, toolChanges,
refusals, warnings, unitsSource} · `EngagementEstimate` {segmentId, mrr,
radialFraction|null, axialDepth|null, source: "REPLAY", cellSize} ·
`LoadEstimate` {segmentId, force|null, spindlePower|null, method:
"KIENZLE", assumptions[], verdict CONFIDENT|REVIEW|INSUFFICIENT_DATA} ·
`CycleTimeFinding` {kind (§9), blockRange, seconds, verdict, evidence,
missingInputs[]} · `OptimizationProposal` (§10 fields, feed-only) ·
`FeedOverrideSegment` {blockRange, originalF, proposedF} ·
`OptimizedNCProgram` {sourceProgramId, proposalsApplied[], emittedText,
digest, geometryIdentical: boolean (verified by geometry-word diff), audit}
· `OptimizationAuditLog` — one row per accepted/rejected proposal, actor
HUMAN, plus one SYSTEM row for the emission diff.

DB: `NCProgram` gains nothing; uploaded and optimized programs are new rows
with a `sourceProgramId` link and `origin: UPLOADED|GENERATED|OPTIMIZED`.

## 9. Finding kinds

`AIR_CUTTING` (replay-proven; stock required) · `LOW_ENGAGEMENT` ·
`HIGH_ENGAGEMENT` · `CORNER_LOAD_SPIKE` (instantaneous engagement rise; REVIEW
in V1 — cell-resolution noise is real) · `EXCESSIVE_RETRACT` (clearance far
above stock top) · `SLOW_LINKING_MOVE` (feed moves above the material) ·
`TOOL_REACH_REVIEW` (flute-length ring check) ·
`WORKHOLDING_LOAD_DIRECTION_REVIEW` · `SEQUENCING_OPPORTUNITY` (**detect and
report only in V1** — reordering motion is geometry-adjacent and stays out of
the emitter) · `UNKNOWN_CONTEXT` (comped regions, multi-offset, refused
blocks).

## 10. Every proposal shows

original block range and text · original F · proposed F · estimated time
saved (with the accel caveat) · reason (the finding) · risk level · the
assumptions, verbatim · required evidence to raise confidence · **geometry
changes: NO** (V1 invariant, machine-verified by geometry-word diff at
emission — a proposal that would change any coordinate word is a bug, not a
feature).

## 11. Load map

Backplot segments coloured by verdict band: gray = air/no cut · blue =
light engagement · green = target band · orange = high · red =
review/overload. Orange and red here MEAN review and risk — consistent with
the locked semantic colours, not a new palette. Segments without load
context render in a hatched "no data" treatment, never in a band they did
not earn.

## 12. Strategy presets

Presets move the target band and proposal ceilings, never the physics:
**CONSERVATIVE** (narrow band, proposals capped at small feed deltas) ·
**BALANCED** · **AGGRESSIVE** (wider deltas, still inside the chipload
window and machine maxFeed, more REVIEW flags accepted as proposals) ·
**LIGHTS-OUT** (the *most* conservative: unattended running means no
operator to hear a bad cut — lowest load ceiling, REVIEW findings are never
auto-proposed, and the preset says why).

## 13. Production-readiness rules

Optimized NC inherits the existing export architecture unchanged: it is an
`NCProgram` row, it renders behind the same pre-flight, and it leaves only
through the same server-minted single-use authorization. Additional gates
specific to optimized programs: parse had zero refusals · tool + machine +
material context bound · the optimized motion was replayed through the
simulator · every applied proposal individually operator-accepted (bulk
"accept all" does not exist) · geometry-word diff clean. Absent any one:
the program renders, the export does not.

## 14. Implementation plan

- **4A — Parse + backplot.** Parser, interpreter, `Move[]` bridge; parse
  report with refusals. *Fully implementable now.* The viewport, transport
  and cycle-time code run on the result unchanged.
- **4B — Cycle time + air cut.** Timing breakdown per tool/op; air-cut via
  replay when stock is bound; retract/slow-link heuristics otherwise
  (REVIEW). *Fully implementable now* — the simulator does the hard part.
- **4C — Context binding + engagement.** Bind uploaded program to
  part/tools/machine/material (UI + matching by T numbers); engagement per
  segment from replay. *Implementable now; quality scales with context.*
- **4D — Load map + proposals.** Kienzle per segment; findings →
  proposals under a strategy preset. *The math exists; the new work is
  chip-thinning and corner-engagement treatment, and honest banding.*
- **4E — Emit optimized NC.** Feed-word substitution with line mapping,
  geometry-word diff, audit rows. *Small, once 4D is trusted.*
- **4F — Compare + gated export.** Side-by-side, simulate optimized
  motion, export through the existing mint. *Mostly wiring.*

## 15. Brutally honest limits

1. **"Load-aware" is an estimate, not a measurement.** No spindle-load
   telemetry exists (see REFACTOR_SPEC — Bridge agent). Until it does, load
   = height-field engagement × Kienzle, labelled DEVELOPMENT ANALYSIS like
   the holding model, uncertainty stated.
2. **2.5D only.** The height field is exact for top-down 3-axis work and
   wrong for undercuts, 3D surfacing ball work, and anything the STEP spike
   also refuses. A surfacing program parses and backplots; its load map says
   INSUFFICIENT DATA rather than pretending.
3. **Savings estimates overstate without recorded acceleration.** The
   trapezoidal model exists and engages when `Machine.axisAccel` is
   recorded; machines without it keep distance-over-feed timing with the
   overstatement stated on every figure.
4. **Cutter comp and macros gut confidence.** Real shop programs are full of
   both. V1 will refuse or REVIEW a large fraction of real-world files — the
   parse report says so plainly rather than optimizing the fraction it
   understood and staying quiet about the rest.
5. **Sequencing is reported, never rewritten, in V1.** Reordering motion
   safely requires the operation-state geometry guarantees of a CAM kernel
   we deliberately do not have.
6. **No claim of production readiness, ever, from this feature alone.** The
   development-post banner, the pre-flight, and the operator approval carry
   through to optimized output unchanged.
