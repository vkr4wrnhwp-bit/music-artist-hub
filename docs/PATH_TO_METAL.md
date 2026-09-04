# PATH TO METAL

What it takes to get from where CANVAS is now to a program a machinist loads
into a machine and runs — and what it takes after that to stand next to
Mastercam or Fusion.

Written against the code as it stands, not against the docs. Every claim below
is anchored to a file. Where a doc and the code disagreed, the code won.

Supersedes the CAM sections of `CANVAS_ROADMAP.md`, which predate the adaptive,
boring, tapping and turning engines.

---

## 1. THE HONEST STATE

**The chain is whole.** Very little is missing structurally. A part goes:

    intake → intent → responsibility → features → process plan →
    setups + operations → deterministic toolpaths → geometric simulation →
    post → NC verification → pre-flight → human approval → minted export

and every one of those stages exists and runs. `src/lib/package.ts` assembles
it, `src/lib/engines/cam/preflight.ts` gates it, `parts/[id]/nc/actions.ts`
mints the bytes behind a single-use 5-minute token that re-runs the gate on
every call. That last file is better than most commercial software manages.

**The trust architecture is the strongest thing here, and it is not close.**
Fourteen gates in `readiness.ts`, aggregated worst-case with no arithmetic.
Provenance on every significant value. `clearableByConfirmation` typed as
`false` so no caller can argue with it. `isEngineeringGrade()` refusing to let
an AI inference clear a required gate. Audit rows with the actor typed
HUMAN | AI | SYSTEM. Cost, holding margin and speeds-and-feeds all returning
null and naming the missing input rather than substituting a default. There is
no CAM package on the market that will tell you it does not know something.

**The fidelity is 2.5D prismatic, and that is the gap.** Not the strategies —
`adaptiveToolpath` does constant radial engagement with proper chip-thinning
compensation and refuses to cut on the shank, which is real work. The gap is
in three specific places:

1. **What comes out of the post is not what the model describes.** Every circle
   is a chorded polygon. There is no cutter compensation the control can see.
   Drilling is long-hand G1 moves rather than canned cycles.
2. **Nothing tells the machinist how to set the job up.** There is no setup
   sheet. The work-offset origin convention exists only as a sentence inside
   the analyzer (`nc/analyze.ts:112`), and never reaches the operator.
3. **The verification verifies the wrong artifact.** `sim/stock-removal.ts` is
   a genuine height-field simulator — but it consumes the internal `Move[]`
   list, not the posted program. A post bug is invisible to it by construction.

**One-sentence verdict.** CANVAS is closer to shipping a trustworthy
manufacturing decision system than it is to shipping a CAM system, and the
remaining distance to runnable NC is mostly a dozen concrete, bounded pieces
of work — none of which requires the geometry kernel that everything past
Tier 2 does.

---

## 2. TIER 0 — MACHINE-READY NC

The bar: a competent machinist takes the posted output, loads it on a real
3-axis VMC, proves it out normally — single block, dry run above the part,
hand on the feed hold — and cuts a correct part. Not "the numbers look
plausible." Correct motion, correct offsets, correct retracts, nothing
surprising at the control.

Nothing in this tier needs a geometry kernel.

### A. The program must describe the part the model describes

**A1 — Arc output. (MEDIUM, do first)**
`Move` has an `ARC` type with `i`/`j`/`cw` fields (`cam/types.ts:93`) and
**no generator ever emits one**. `ringMoves` walks a circle in
`max(24, radius × 60)` straight chords (`cam/engine.ts:607`); `rectMoves`
walks each corner in eight (`:617`).

What the machinist gets: a Ø1.000″ bore comes out as a 30-sided polygon whose
flats sit **0.0027″ inside nominal** — five times the whole band on a ±0.0005″
bearing seat, and a form error, so it cannot be dialled out with an offset. The
part measures round on a two-point mic across the flats and is not round.
Secondary damage: programs are ten to fifty times longer than they need to be,
the control's look-ahead buffer thrashes on short blocks, and the finish shows
every chord.

Build: arc-aware move generation for every circular path, `G2/G3` with `I/J`
in the Fanuc family (`R` is ambiguous over 180°), arc splitting at quadrant
boundaries where a control needs it, helical arc output for helical entry, and
a linearisation fallback with a *stated* chord tolerance for anything genuinely
non-circular.

**A2 — Cutter compensation the control can see. (MEDIUM)**
The contour path is offset in software — `const w = feature.width +
ctx.tool.diameter` (`cam/engine.ts:1147`) — and no `G41/G42/D` word is ever
emitted. `verifyNc` does not look for one, and `nc/parse.ts:156` knows what
comp is only well enough to mark other people's programs as comped.

What the machinist gets: no way to hold size. A cutter 0.0015″ under nominal,
a regrind, a hair of runout, spring on a deep wall — the entire normal recourse
is to nudge the D offset a thou and re-run the finish pass. CANVAS's programs
cannot be adjusted at the control at all. The only fix is to go back to the
computer and re-post, which no shop will do at 11pm.

Build: emit `G41/G42` with a `D` register on finish passes, generate the
lead-in and lead-out geometry the comp rules require (a linear or arc lead at
least one tool radius long, comp on before the first cut, off after the last,
never a comp change in a corner), populate the D register from the tool record,
and add the offset value to the setup sheet. Keep the software-offset path for
roughing where nobody adjusts.

**A3 — Canned cycles. (SMALL)**
`post.ts` special-cases only `TAP` → `G84` (`:88`). Every drill and peck comes
out as long-hand `G1` plunges and retracts.

What the machinist gets: it will cut, but it is not what anyone expects to
read, and it forfeits everything the control does better — `G83` chip-break
timing, dwell at the bottom, retract to R rather than to Z, and single-block
stepping through a cycle instead of forty lines.

Build: `G81` (drill), `G82` (spot/counterbore with dwell), `G83` (peck),
`G73` (chip-break), `G85` (bore/ream, feed out), `G86`, `G76`, with `G80`
cancellation, plus the `R`-plane discipline that goes with them. Structurally
identical to the `G84` case that already exists.

**A4 — A feature with no operation is silently not cut. (SMALL — do this now)**
`preflight.ts` already reasons this way about placeholder toolpaths: "the
program is syntactically complete, runs start to finish, and simply never cuts
those features." The same hole exists one level up. Nothing checks that every
feature is *addressed by an operation*. The workspace knows — "No operation in
the plan cuts this feature" (`components/workspace/feature-actions.ts:75`) —
but it is not a gate.

What the machinist gets: a program that runs to completion and hands back a
part missing its bearing bore. Nobody inspects for the absence of a feature.

Build: a feature-coverage gate in `readiness.ts` and a pre-flight item.
Cheapest high-severity item on this list.

**A5 — The outside contour is a rectangle at the origin. (MEDIUM)**
`contourToolpath` hard-codes `rectMoves(moves, 0, 0, w, l, cr, z, p.feed)`
(`cam/engine.ts:1157`). An `OUTSIDE_CONTOUR` feature carries width, length and
corner radius and nothing else — so every profiled part is a centred rectangle
with equal corners.

Build: a real chained boundary — an ordered list of lines and arcs with an
inside/outside sense — as a feature parameter. This is the first piece of
actual geometry the system needs, and it is worth doing before a kernel because
2D chains cover most of what a job shop profiles.

**A6 — Finish passes are a parameter, not a pass. (MEDIUM)**
`stockToLeave` exists in `CuttingParameters` and is applied as an offset to the
roughing geometry. There is no separate finishing operation with its own tool,
feed, speed, depth of cut and comp state.

What the machinist gets: roughing feeds on the final wall. Finish and
tolerance both suffer, and the ±0.0005″ features the inspection engine reasons
so carefully about were never machined to a finishing strategy.

Build: finish passes as first-class operations — spring pass, separate feed,
comp on, climb-only, full depth in one pass where the tool allows.

### B. The machinist must know how to set the job up

**B1 — There is no setup sheet. (MEDIUM — highest value per hour on this list)**
Grep the source: no setup sheet, no traveller, no job packet. The phrase
appears only in a tool-field hint and in the analyzer's assumption text.

CANVAS *knows* everything a setup sheet contains — stock size and grade, vise
and jaw type, grip depth, parallel height, jaw axis, part orientation, work
offset, the tool list with stickout and holder, the operation order, the
predicted cycle time, the critical dimensions and how each is to be inspected.
It prints none of it. You cannot hand a program to a second-shift machinist
with none of that, which means today the program cannot leave the office.

Build: a printable setup sheet per setup — origin location and how to pick it
up, part orientation with the viewport's own image, stock, workholding, tool
table with pockets/stickout/offsets, operation sequence, cycle time, critical
dimensions, and the gate state at approval. The data is all in
`ManufacturingPackage` already; this is a rendering job, not an engineering one.

**B2 — The work-offset origin is never stated to the operator. (SMALL)**
The convention exists — "Work-offset origin taken as program zero with Z0 at
the stock top" (`nc/analyze.ts:112`), "origin at stock centre"
(`sim/stock-removal.ts:103`) — and appears nowhere in the posted program. The
header carries part, machine, date, tool list and a warning, and not the one
sentence that decides whether the part is cut in the right place.

Build: origin declaration in the post header and on the setup sheet; make it a
property of the Setup rather than a convention held in two comments.

**B3 — A setup has no coordinate frame. (LARGE)**
`Setup` carries `orientation` (a string, "TOP") and `workOffset` ("G54") and no
origin, no transform (`prisma/schema.prisma:759`). Feature coordinates are
assumed to be program coordinates. There is no rotation, no offset, no
part-in-stock placement.

What this forecloses: second-op work. Flip a part and every X, Y and Z in the
second setup is wrong, with nothing in the system aware of it. Multi-part
fixtures, tombstones, anything not centred, and datum transfer between setups
all sit behind the same gap.

Build: a real per-setup transform — origin in stock coordinates, orientation as
a rotation, and a single function every toolpath passes through. Then datum
transfer and its tolerance stack become expressible.

### C. Verification must verify the artifact that is actually run

**C1 — Simulate the posted program, not the pre-post move list. (MEDIUM)**
`sim/stock-removal.ts` takes `Move[]`. So the simulator proves the toolpath
engine's intent, and the post sits downstream of the proof. Every class of post
bug — a dropped retract, a modal feed carried into a rapid, a bad arc, a wrong
offset word — is invisible by construction.

Both halves already exist: `nc/parse.ts` is a real modal G-code interpreter
that refuses honestly what it cannot read, and `stock-removal.ts` is a real
height-field simulator. Wire the parser's output into the simulator and run the
*emitted text*.

**C2 — Prove post output against the toolpath it came from. (SMALL)**
Nothing compares them. Sample the posted program back to points and check them
against the source moves within a tolerance; report any divergence as a
blocking finding. This is the check that lets a post eventually stop being
labelled DEVELOPMENT.

**C3 — Collision checks are optional and say so. (MEDIUM)**
The fixture check runs only when a fixture model is supplied and reports
`fixtureChecked: false` otherwise — honest, and not sufficient to release a
program. Holder and shank contact is inferred from flute length only. There is
no clamp, no parallel, no tombstone, no table, no machine envelope in the
collision model.

Build: required fixture geometry before export, holder solids from the tool
record, rapid-through-material as a blocking finding rather than a note.

### D. The post must be trustworthy for a specific machine

**D1 — Every post is `certified: false`, permanently. (LARGE)**
`PostDefinition.certified` is typed as the literal `false` (`post.ts:32`) — the
same trick as `clearableByConfirmation`, and correct. But there is no path to a
certified post: no record of a post having been validated, against which
machine and control version, by whom, with what evidence.

Build: a post-validation record and gate — cut-air proof, dry run, first
article, signed by a named person against a named machine and control version.
Until that exists the honest label is the only answer, and the honest label
means the program cannot be trusted, which means CANVAS cannot yet do the thing
it exists to do.

**D2 — Control-specific reality. (MEDIUM per control)**
What the current posts do not handle: safe-start block conventions, tool change
position and second home (`G53 G0 Z0` only), work offset schemes beyond a
single `G54` (`G54.1 P`, `G10 L2`), look-ahead and high-speed codes
(`G187`, `G05.1 Q1`, `CYCLE832`), feed modes beyond `G94`, spindle gear ranges,
coolant variants beyond `M8`/`M88`, dwell, subprogram call and repeat, block
numbering, per-control decimal and format rules, maximum program size and drip
feed, operator messages, and probing macros. Heidenhain and Siemens skip
tapping entirely and say so.

Treat each control as its own commissioning project. One control done properly
is worth four done approximately.

**D3 — `verifyNc` reads G-code with regexes. (SMALL)**
`post.ts` checks travel, spindle state and feed words by regex, and bails
honestly on Heidenhain rather than reporting a clean program in a dialect it
cannot read — good judgement. But `nc/parse.ts` is a real interpreter sitting
one directory away. Point the verifier at it.

### E. Gates that must exist for this bar

The gate list is the product. Five are missing for machine-ready NC:

| Gate | Clears on |
|---|---|
| Feature coverage | Every feature is cut by an operation (A4) |
| Post validated | A validation record for this machine + control (D1) |
| Emitted-program verification | Posted text simulated and reconciled (C1, C2) |
| Setup documentation | A setup sheet exists for every setup (B1) |
| Proof-out state | `NEVER RUN` → `PROVEN` on machine, date, operator |

That last one deserves its own paragraph. **The most important property of an
NC program is whether it has ever cut a good part.** Nothing in the schema
records it. A program proven on the VF-2 last Tuesday and the same program
never run are indistinguishable in the system today, and no machinist thinks
about them the same way. This is a small schema change and a large change in
what CANVAS can honestly say.

---

## 3. TIER 1 — A SHOP CAN PUT ITS WORK THROUGH IT

Tier 0 gets one part cut. Tier 1 is the difference between a demonstration and
a shop's Tuesday. Still no kernel required.

- **Chained 2D geometry.** Open and closed chains, islands, multiple pockets,
  slots as real slots, radial and grid patterns, bolt circles. The natural
  extension of A5, and it covers most job-shop profiling.
- **Hole-making as a family.** Spot, drill, peck, chip-break, ream, counterbore,
  countersink, back-spot, with the drill point angle in the depth arithmetic
  (a through hole drilled to nominal depth does not break through).
- **Thread milling.** Today tapping is the only thread strategy. Thread milling
  is how a shop makes one 3/4-10 in 17-4, how it saves a part with a broken tap,
  and how it holds a class-3 fit. The helical arc machinery from A1 is most of it.
- **Rest machining.** Where the big tool could not reach. Needs a record of what
  the previous tool left, which is the first step toward an in-process stock model.
- **Multiple work offsets and fixture offsets.** `G54.1 P`, multi-part fixtures,
  the same program run four up.
- **Tool library that means what it means elsewhere.** Per-material feed and
  speed data rather than one SFM band; tool life in minutes and parts, not a
  0–1 float; presetter data; D and H registers; pocket assignment; sister tools.
- **The job packet.** Setup sheet plus tool list plus traveller plus first-article
  form, printed together, versioned with the program.
- **Program revision control at the machine.** Which revision is loaded, hash
  checked against the approved one (the export already computes a SHA-256),
  DNC or drip feed for programs over the control's memory.
- **Second op properly.** B3's transform plus datum transfer, dowel and soft-jaw
  location, and the tolerance stack across the flip stated as a number.

---

## 4. TIER 2 — 2D AND 3-AXIS PARITY

This is where the geometry kernel decision lands, and it is the fork the whole
system's future hangs on.

**The fork.** Everything below needs a real model of the part — B-rep or mesh —
not a list of parametric features. `step/recognize.ts` is a deliberate 2.5D
spike that names what it cannot read; `domain/features.ts` has fifteen feature
kinds and cannot express a draft, a sculpted surface or a fillet chain. Options
are the same three as before: OpenCascade compiled to WASM, a commercial kernel,
or a constrained in-house B-rep for prismatic solids. It is a build-versus-buy
decision with a decade-long shadow, and it should be made deliberately, once,
with the seam it slots into (`generateToolpath`, `evaluatePart`) already known.

Behind the kernel:

- **In-process stock model.** Stock state carried operation to operation. The
  precondition for rest machining, for honest cycle time, and for a simulation
  that can say a finish pass is cutting air.
- **3D toolpaths.** Parallel/raster, waterline/contour, pencil, scallop, radial,
  spiral, projection, flat-area, and the linking between them.
- **High-speed strategies at production quality.** Full engagement control
  everywhere rather than in adaptive pocketing only, trochoidal slotting, peel
  milling, corner deceleration, arc fitting on the output.
- **Associativity and regeneration.** Change the model, the toolpaths update.
  This is where CANVAS should be *better* than the incumbents rather than equal:
  in Mastercam and Fusion regeneration is a silent recompute, and every
  programmer has been bitten by it. Here it should be a gated event — a diff of
  exactly which moves changed and why, requiring a human to accept it, with the
  approval revoked until they do. The stock-correction machinery built this week
  is the same shape.
- **Machine simulation with kinematics.** Table, column, travels, home, tool
  change position, rapid interference — not just stock removal.
- **Configurable posts.** A post definition a shop can edit without a
  TypeScript build. This is what `.PST` files are for and it is why every shop
  can run every machine.
- **3+2 positioning.** Needs the 4th/5th axis model the machine profile already
  has flags for.

---

## 5. TIER 3 — THE REST OF PARITY

- **Probing.** Part location, in-process, tool setting, on-machine verification.
  Deliberately blocked today because probing routines are executable machine
  motion and the principle holds: a model never emits them. The path is a
  deterministic generator plus a validated post plus the proof-out gate.
- **Full CAD interoperability.** STEP with real B-rep, IGES, Parasolid, native
  formats, assemblies, fixtures modelled as geometry.
- **Feature recognition at production quality.** Automatic, over the kernel,
  with the proposal-and-acceptance flow that already exists so it never becomes
  zero-click geometry.
- **Mill-turn and live tooling.** `docs/MILL_TURN_FUTURE.md` and
  `LIVE_TOOLING_ARCHITECTURE.md` already sketch it; the turning engine
  (`manufacturing/turn/`, seventeen operation types) is further along than most
  people would guess.
- **Full 5-axis.** Probably not. See §7.

---

## 6. HORIZON — WHAT MAKES IT AN OS AND NOT A CAM PACKAGE

These are the reasons to build this at all. Each is listed with the earliest
tier it can start in, and each obeys the same rule: **it may suggest, compare,
question and explain — it may not certify without evidence.**

**H1 — Proof-out as data. (Tier 0)** Every program carries its run history:
which machine, which operator, actual cycle time against predicted, what got
adjusted at the control and by how much. `Job` actuals already exist. This is
the seed corn for everything below.

**H2 — Closed-loop metrology. (Tier 1)** Measured result → offset
recommendation → human applies it → recorded against the tool, the machine and
the material. The measurement model, the capability engine and the audit trail
all exist. What is missing is the loop.

**H3 — Machine telemetry. (Tier 1)** MTConnect or FOCAS: spindle load, feed
override, actual versus programmed. The load-aware NC optimizer
(`nc/load.ts`, `nc/analyze.ts`) already reasons about engagement offline; give
it real load traces and it stops being a model and becomes a measurement.

**H4 — Tool life as evidence. (Tier 1)** Cutting distance per tool per material
is already computed per toolpath. Accumulate it, predict remaining life with a
stated uncertainty, and refuse to certify a ±0.0005″ finish pass on a tool
past the evidence. `lifeRemaining` as a 0–1 float today is exactly the kind of
number the rest of the system would refuse.

**H5 — Chatter and stability. (Tier 2)** Shop-measured tap tests per spindle,
holder and tool; stability lobes; speed selection that avoids the lobe rather
than backing the feed off. Classified DEVELOPMENT ANALYSIS until validated
against coupons, like `holding-margin.ts`.

**H6 — Per-machine correction as shop knowledge. (Tier 1)** "This VF-2 cuts
0.0005″ oversize climbing in 6061 with a 1/2″ three-flute." Scoped to the
machine, the tool and the material, never promoted to a universal fact —
`disagreement.ts` already has the model for exactly this.

**H7 — Machine health in the gates. (Tier 2)** Ballbar and backlash results,
thermal growth, spindle vibration trend. A machine drifting out of calibration
should move a part's gates, not sit in a maintenance spreadsheet.
`MACHINE_CALIBRATION.md` and `calibration.ts` are the start.

**H8 — Program integrity at the control. (Tier 0/1)** The export already
computes a SHA-256 of the program text. Check the program at the machine against
the approved digest. A program edited at the control — which happens on every
job — becomes a recorded, attributable event rather than a mystery six months
later.

**H9 — Quoting from evidence. (Tier 1)** Quantity-aware, machine-aware, with a
stated uncertainty band and a list of the actual jobs it was derived from.
The cost engine already refuses to answer without inputs; give it history.

**H10 — The digital thread. (Tier 2)** Material cert → heat lot → stock → part
revision → program revision → operator → inspection record → shipment, as one
queryable chain. Aerospace and medical customers buy this before they buy CAM.

**H11 — Scheduling that respects gate state. (Tier 2)** A job cannot be
scheduled onto a machine whose gates are not clear. Capacity that knows the
difference between a proven program and a new one.

**H12 — Cross-shop learning without exposure. (Tier 2)** The network model and
its privacy defaults exist. "Shops holding this tolerance in this material use
these five approaches" — anonymous, opt-in, carrying no identifiable geometry.

**H13 — Regeneration diffs.** Covered in Tier 2, listed here because it is a
horizon idea wearing a parity item's clothes. Nobody does this well and it is
squarely in this product's philosophy.

**H14 — AI as interrogator. (any tier)** The model's job is to read the
drawing, the shop's history and the machine, and ask the three questions that
actually decide the job — is this bore a bearing seat, has anyone cut this
material on this machine, does the fatigue life justify the material. It
proposes an `OperationRequest`, the same structure a human fills in. It never
emits motion. That fence is the architecture and it should never move.

**H15 — Physics tiers, each labelled.** Cutting force exists. Deflection,
surface-error prediction and thermal are the next rungs, each classified
DEVELOPMENT ANALYSIS in output and UI until validated against physical tests.

---

## 7. WHAT NOT TO BUILD

Saying no is part of the plan.

- **Full 5-axis.** This is a 3-axis job-shop OS. Five-axis is a different
  product with different customers, and chasing it would starve everything above.
- **A CAD modeller.** Import, recognise, reason. Do not compete with SolidWorks.
- **An AI that writes G-code.** Not a resourcing decision — an architectural
  one. `engines/cam/` contains no model calls and must not acquire any.
- **A generic simulation "confidence" number.** The simulator reports which
  checks ran. It should never average them.
- **Nesting, sheet metal, waterjet paths, additive slicing.** The process
  advisor should keep *recommending* these processes and keep refusing to
  execute them. Recommending a casting is engineering judgement; generating
  the pattern is somebody else's product.

---

## 8. THE ORDER I WOULD ACTUALLY BUILD IT IN

1. **A4** feature coverage gate — hours, prevents a part missing its bore.
2. **B1** setup sheet — the program cannot leave the office without it.
3. **A1** arc output — the largest single fidelity win.
4. **A3** canned cycles — small, and the program starts reading like a program.
5. **C1 + C2** simulate and reconcile the posted text — closes the loop that
   makes every later post change safe.
6. **A2** cutter compensation — the machinist gets their offset back.
7. **B2 + E** origin declaration, proof-out state, the remaining gates.
8. **A5 + A6** chained contours and real finish passes.
9. **D1 + D2** one control commissioned properly, end to end, on real iron.
10. **B3** the setup transform, and second-op work opens up.

Items 1 through 7 are what stands between here and a machinist trusting the
output. Everything after that is scale.
