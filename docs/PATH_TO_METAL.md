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

**A1 — Arc output. — BUILT**
`Move` carried an `ARC` type with `i`, `j` and `cw` fields and **no generator
ever emitted one**. Four operations walked circles in straight chords: pocket
rings, profile corners, bore helical interpolation, and adaptive's ramp entry.

A Ø1.000″ bore arrived as a thirty-sided polygon whose flats sat **0.0027″
inside nominal** — five times the whole band on a ±0.0005″ bearing seat, and a
form error, so no offset dials it out. The part measures round across the flats
on a two-point mic and is not round.

`cam/arc.ts` now owns the convention in one place: `i` and `j` are the offsets
from the arc's start to its centre, which is the incremental I/J every
Fanuc-family control reads, so the post writes them out with no conversion and
no chance of a sign error in translation. Full circles go out as two 180° arcs
rather than one full-circle block, because a G2 with I/J and no endpoint means
"full circle" on Haas and Fanuc and means something else or nothing elsewhere.

The Fanuc family and GRBL emit native `G2`/`G3` with `I`/`J`, helical included.
Heidenhain gets `CC`/`C`; Siemens gets `G2`/`G3` with `I=`/`J=`. Neither of
those two has its helix syntax implemented, so a helical arc on those posts is
flattened to a stated chord tolerance and **the program says so on the line
where it happens** — a longer program that cuts the right shape beats a guess
at syntax that does not.

Everything downstream that walks the path as segments — the height-field
simulator, the viewport, a post that has to flatten — calls one shared
`flattenArcs`. Three copies of that tessellation would be three chances for the
simulator to disagree with the program about where the tool went.

The one path still walked in chords is adaptive clearing's Archimedean spiral,
and that is not an oversight: its radius grows every revolution, so no `G2`/`G3`
can express it and every CAM system chords it too. Its segment count now comes
from the same chord tolerance as everything else, rather than the fixed 48 per
revolution that got worse as the pocket got bigger.

Measured on the seeded bearing support: **1,685 blocks to 420**, with cycle
time unchanged at 7.9 min — the path is the same path, and an arc measured
along the arc keeps the estimate honest rather than shortening every circular
cut in the program.

`src/lib/engines/cam/arc.ts`, the generators in `cam/engine.ts`, all four posts
in `cam/post.ts`, `sim/stock-removal.ts` and `viewport/scene.tsx`.

**A2 — Cutter compensation the control can see. — BUILT**
The contour path was offset in software — `feature.width + tool.diameter` — and
no `G41`/`G42`/`D` word ever reached the control. That takes away the
machinist's only recourse for holding size. A cutter a thou and a half under
nominal, a regrind, a hair of runout, spring on a deep wall: the answer to every
one of them is to nudge the D offset and re-run the finish pass. A program with
the offset baked in cannot be adjusted at the machine at all, and the only fix
is to walk back to the computer and re-post, which nobody does at 11pm.

The program now carries the **part boundary** and the control offsets it. The
move list still carries the **cutter centre**, because that is what the
simulator sweeps and what every collision check reasons about — the two paths
are built side by side from one generator and zipped, so they cannot drift, and
`Move.program` is where the second one lives.

`G42`, because the contour runs counter-clockwise with the part on the inside,
so the cutter is to the right of travel. With a right-hand tool that is
conventional milling; climbing means reversing to clockwise with `G41`, which
belongs with real finish passes (A6) rather than hidden inside this change.

The lead moves *are* the comp rules: activation on a straight move in free air
at least a tool radius long, cancellation on a straight move away from the part,
never on an arc and never inside a corner. A post also refuses to end a tool
with compensation still open. GRBL has no offset table, so it gets the cutter
centre and a line telling the machinist size is not adjustable there —
reaching for an offset that does not exist is the failure that line prevents.

**A gouge fell out of the rework.** The lead-in used to end on the *left* edge
while the contour started on the *bottom* edge, so the first cutting move was a
straight chord across the bottom-left corner: 0.293 × the corner radius into the
part, nearly a tenth of an inch on an ordinary profile. Nothing in the system
could have caught it — the simulator removes whatever the path sweeps, and there
is no check that the finished shape matches the model. That check needs the
in-process stock model in Tier 2. Meanwhile a test now asserts no cutting move
runs diagonally on a rounded rectangle, which is the signature of a corner being
cut off.

Also gone: four zero-length blocks per pass, where the lead-in and the contour
start were emitted as two separate moves to the same point.

`ProgrammedPoint` in `cam/types.ts`, `contourToolpath` in `cam/engine.ts`, the
comp words in `cam/post.ts`, `programmedPath` in `nc/reconcile.ts`, and the D
register on the setup sheet.

**A3 — Canned cycles. — BUILT**
The post special-cased only `TAP` → `G84`, and derived its Z and R by running
`Math.min` over the move list — pattern-matching a program out of a path, which
gets the wrong answer the day the path changes shape. Every drill and peck came
out as long-hand `G1` plunges and retracts.

Hole-making now carries a `CannedCycle` descriptor built by the engine
*alongside* the move list and from the same numbers: `G81` to drill, `G83` to
peck, `G84` to rigid tap, `G98` so the tool returns to the initial level rather
than to R, and `G80` to close. X and Y go on the cycle block itself rather than
being left to the positioning move, because "drills at the current position" is
true on some controls and not others.

The important part is that the cycle and the moves describe the **same**
motion — the simulator walks the moves and the machine runs the cycle, and two
different paths there is a simulation proving a program that will not run. The
peck retract used to go to `topZ + 0.05` while the rapid came down to
`clearanceZ`: two planes for one operation. Both are now the one `rPlane` the
descriptor carries.

GRBL has no canned cycles at all and faults on them, so it drills as feed moves
and the program says why. Heidenhain (`CYCL DEF 200/203`) and Siemens
(`CYCLE81/83`) are not implemented here and say so too.

One thing fixed in passing: the old special-cased tap branch was the single path
out of this post that ended a tool without an `M5`, leaving the spindle turning.

`CannedCycle` in `cam/types.ts`, the descriptors in `cam/engine.ts`, the cycle
block in `cam/post.ts`.

**A4 — A feature with no operation is silently not cut. — BUILT**
`preflight.ts` already reasoned this way about placeholder toolpaths: "the
program is syntactically complete, runs start to finish, and simply never cuts
those features." The same hole sat one level up. Nothing checked that every
feature was *addressed by an operation*. The workspace knew — "No operation in
the plan cuts this feature" — but it was not a gate, and a program that runs to
completion and hands back a part missing its bearing bore is not something
anybody inspects for. Every inspection method in this system measures something
that is there.

`engines/coverage.ts` now answers it, and both the readiness gate and the export
pre-flight ask that one function — the lesson `preflight.ts` states in its own
header: if the gate logic exists in two places, it does not exist.

The gate has to be clearable on real parts or it gets routed around. A FILLET
has no operation type in the CAM engine at all; a chamfer is broken at the
bench; a bore arrives in the extrusion. So a person may state, in a sentence,
that a feature is not made by this program — recorded with their name and the
time, on the feature's MACHINE tab. It is a manufacturing fact only a person can
know, in the same class as confirming the material, and the gate repeats the
sentence in its detail rather than swallowing it: somebody at the bench still
has to do that work, and the setup sheet (B1) will print it.

Found on three seeded parts the moment it ran, including a bearing support with
six of twelve features that no operation cuts.

`src/lib/engines/coverage.ts`, the `coverage` gate in `readiness.ts`, the
`coverage` item in `cam/preflight.ts`, and
`parts/[id]/features/not-machined-actions.ts`.

**A5 — The outside contour is a rectangle at the origin. — BUILT**
`contourToolpath` hard-coded `rectMoves(moves, 0, 0, w, l, cr, …)`. An
`OUTSIDE_CONTOUR` feature carried width, length and one corner radius and
nothing else, so every profiled part in the system was a centred rectangle with
four equal corners — and a part that is an L, or a D, or a plate with a flat
across one corner was cut as a rectangle **with nothing saying so**.

`cam/chain.ts` holds a closed boundary as an ordered loop of lines and arcs.
The feature may carry one; absent, the rectangle its three numbers describe is
built as a chain, so there is one code path and nothing about an existing part
changes.

The offset is for the CUTTER CENTRE only — the program carries the boundary and
the control offsets it (A2) — and it turns out most of it is free: real profiles
are tangent-continuous, which is what a fillet is *for*, and a tangent joint's
offsets meet by themselves. Two cases need work. A sharp **convex** corner
leaves a gap the tool pivots across, filled with an arc of the tool radius about
the corner. A sharp **concave** corner is **refused**, and that is engineering
rather than laziness: a round tool cannot produce a sharp inside corner, it
leaves a radius, and the drawing has to say so. The message names the corner and
the radius the tool would leave. An inside arc smaller than the cutter is
refused the same way — the rule that already refused a pocket corner tighter
than the tool, generalised to a chain.

A profile that *starts* on an arc is refused too, because compensation cannot be
brought on over one: a control either faults or ramps the offset through the cut.

Two things fixed on the way. Material removed was computed from
`2 × (width + length)` — the bounding box, not the profile — so two parts with
the same envelope and different shapes removed identical material, and that
figure feeds tool wear, cost and the cycle estimate. And the rework itself
briefly carried the cutter offset through the `G40`, leaving the simulated tool
a radius from where the machine actually parks it; the reconciler could not see
it, because the reconciler reads the programmed path and the programmed path was
right.

**Still open:** nothing produces a chain yet. It comes from CAD, and the STEP
recogniser is a 2.5D spike that names what it cannot read. What this removes is
the silent assumption — the geometry can now be *stated*, and where it is, it is
what gets cut.

`src/lib/engines/cam/chain.ts`, `ContourFeature.chain` in `domain/features.ts`,
`contourToolpath` in `cam/engine.ts`.

**A6 — Finish passes are a parameter, not a pass. — BUILT**
`stockToLeave` was the only thing separating a finish pass from a roughing one,
which made it a roughing pass with a different number in it: the same mid-range
chipload, the same stepdown, the same depth ladder. The finishing flag was
derived from the operation TYPE — `CHAMFER || ENGRAVE` — so an operation the
planner labelled "Finish outside profile" cut the final wall at roughing feeds.
On the ±0.0005″ features the inspection engine reasons so carefully about.

`pass: "ROUGH" | "FINISH"` is now a property of the operation, carried from the
planner through the stored row to the engine. A finish pass takes the finishing
chipload, leaves nothing behind, and **runs the full depth in one go** — because
every depth step leaves a witness line: a visible band where the cutter
re-entered, and a place the wall sits proud or shy by however the tool deflected
on that step.

The limit is the flute, not the ambition. Past the flute length the shank is
rubbing the wall, so the pass steps down like a roughing pass and **says so** —
a machinist who ordered a finish pass and got a stepped one has to know which he
has.

And whether a wall gets its own pass no longer depends on the approach. Only
`BEST_FINISH` used to split them, so a toleranced profile planned under any
other heading got roughing feeds on its final wall. The approach decides how
hard to push; whether a toleranced surface is finished is a property of the
feature. All five approaches now split it — and where no tool in the crib can
finish a toleranced wall, the plan says that rather than quietly roughing it.

Absent means ROUGH, so no plan approved before this existed cuts differently.

**Still open:** pocket walls. This covers the contour, which is where comp lives
and where the size a machinist adjusts actually is. A pocket's floor and walls
want separate treatment and separate tools.

`OperationRequest.pass` in `cam/types.ts`, `Operation.pass` in the schema,
`contourToolpath` in `cam/engine.ts`, the profile branch of `machinist.ts`.

**A7 — A hole pattern was one operation, and one hole. — BUILT**
The planner grouped holes by diameter and emitted **one** operation for the
group: `Drill 6 × Ø0.2010`, pointed at `holes[0].id`. The toolpath engine takes
an operation's feature and drills it. Five holes were never produced. No error
was raised, the operation reported real motion, and the pre-flight said every
operation had produced a path — because it had, for one hole. An operator reads
a label promising six holes, runs it, and takes a part with one out of the
machine.

The same shape appeared twice more: spotting counted the holes by running a
regex over the drill operation's own label — the plan reading a number back out
of a sentence it had just written — and `Chamfer top edges` pointed at
`chamfers[0]`, so every other chamfer on the part went uncut.

Found by an independent audit of the engine. No test here caught it, because
every test asked whether the operation produced motion.

Operations are now **one per feature**, which is what everything else in this
system is built on: coverage, inspection method, measurement and tolerance are
all per feature, and a plan that groups is a plan those cannot reason about.
Depth and the peck decision became per-hole with it — the group's depth was
`Math.max` over its members, so a 0.15″ hole beside a 1.2″ one was drilled to
1.2″, through the bottom of the part and into whatever was holding it.

**The program did not get longer.** A control holds a canned cycle modal, so the
post merges consecutive operations that share tool, cycle, depth, R plane, peck,
feed, speed and coolant into one `G98 G81 X Y Z R F` followed by a bare `X Y`
per hole and one `G80` — which is what a real post writes and what a machinist
expects to single-block through. Merging lives in the post rather than the
planner so the two views stay independent, and anything the cycle asserts
differing ends the group: a different depth is a different cycle, and inheriting
one hole's depth for the next is how a program drills through a table.

On the seeded bearing support the plan went from 2 hole operations to 10 (five
spots, five drills), and the posted program is unchanged in shape — two cycles,
two tool changes, ten holes. The reconciler replays the posted text against the
planned path and agrees to 1e-16 on both drills, which is the check that says
the merge is lossless rather than merely shorter.

Three posts had a tool change per operation, invisible while a pattern was one
operation and twenty the moment it was twenty. GRBL's was an `M0` — a program
pause demanding a manual tool change for a tool already in the spindle, twenty
times, which is a program an operator learns to cycle-start through without
reading, and one of those pauses is a real tool change. All three now change on
an actual change.

`planApproach` in `machinist.ts`, `sameCycle` and all four emitters in
`cam/post.ts`.

**A8 — The chamfer was not a chamfer. — BUILT**
`chamferToolpath` ignored `feature.width` and `feature.angle` entirely. It
walked a rectangle around the **STOCK** outline — 6 × 4 on the seeded bearing
support, where the finished profile is 5.875 × 3.875 — at a hard-coded `R0.1`
corner, at whatever Z the plan happened to carry, which was a hard-coded
`−0.03`. A 0.030 × 45° chamfer and a 0.005 × 60° chamfer produced the identical
path, and the path cut air a quarter of an inch outside the part for its entire
length while reporting material removed.

Where the feature applied to **HOLES** it emitted a rapid, a plunge and a
retract at X0 Y0 and nothing else: three moves at the origin, `isPlaceholder`
false, no warning, and the pre-flight counted it as an operation that had
produced motion.

That is exactly the shape locked principle 5 exists for, and worse than a stub,
because a stub says so.

**A chamfer mill is a cone, and the cone decides the angle.** Its flank sits at
half its included angle from the axis, and that flank *is* the chamfer surface —
so depth and offset decide only the width. A 90° chamfer mill cuts 45° chamfers
and cannot cut a 30° chamfer at any depth or any offset; the tool for that is a
120° included one, and CANVAS says so rather than cutting 45° of the right width
and calling it done.

Working in the plane normal to the edge, a chamfer of width W at angle A from
the face runs from (R − W, 0) to (R, −W·tan A). Putting the cone's flank on that
line, with the tip clearing the bottom by `c`:

    Z of the tip  = −(W·tan A + c)
    radial offset = tipRadius + c / tan A

outward on an outside edge, inward on a pocket or a hole, and by symmetry the
same number both ways. Below the chamfer the tool clears the wall by `c / tan A`.
The test does not check that arithmetic against itself — it walks the cone the
tool actually is, from the position this puts it in, and confirms the surface
passes through both ends of the chamfer on the drawing.

**The tool had no point angle**, because nothing in the system recorded one.
`Tool.pointAngle` and `Tool.tipDiameter` are new columns, nullable with no
default, on the form under Geometry. A chamfer mill with no angle recorded is a
cone of unknown angle, and assuming 90° would cut a wrong part for exactly the
shop that owns the 82° one — so the operation is refused and the message names
the field.

The edge is found from the part rather than the stock: `OUTSIDE_TOP` follows the
profile feature's chain, `POCKET` follows the pocket, `HOLES` visits every hole
— interpolating a circle where the hole is big enough and plunging the cone
where it is not, which is how a small hole gets chamfered and what a spotting
drill does. A hole whose diameter is under the tool's tip flat is refused, since
the tool will not enter it.

The planner and the engine ask the **same function** for the depth, so the plan,
the setup sheet and the program carry one number instead of three that can
drift, and a chamfer the crib cannot cut is a concern on the plan rather than an
operation the engine will refuse later. Verified live: clearing the point angle
on the seeded chamfer mill drops the operation from the plan (18 ops to 17) and
puts the reason on the machinist's page; restoring it brings it back.

`src/lib/engines/cam/chamfer.ts`, `chamferToolpath` in `cam/engine.ts`,
`MachiningContext.partFeatures`, `Tool.pointAngle` / `tipDiameter`, the chamfer
branch of `machinist.ts`.

**Still open:** the pass plunges straight to depth at its start point, which is
0.03 of engagement with the flank rather than a ramp or an approach from clear
air. Fine at this depth, wrong the day a chamfer is 0.06.

**A9 — A drill does not make a hole as deep as it goes. — BUILT**
`depthOf` returns `stock.z` for a feature marked `through`, and the operation
went to exactly that Z. A twist drill is ground to a point: the full diameter is
reached a point-length behind the tip, so a Ø0.201″ jobber drill at 118° reaches
full diameter **0.0604″** above where its tip stopped. Every through hole on the
part came off the machine with a cone of material still in the bottom of it —
finished-looking on the plan, on the setup sheet and in the program, and short
on the first article.

Found while fixing A7, which is the second time reading this area for one thing
has turned up another.

The point angle is **required, not assumed**. 118° is the jobber grind and 135°
the split point, and they differ by a quarter of the point length on the same
drill. There is no safe direction to guess in — too shallow leaves the cone, too
deep drills the parallels — so a through hole whose drill has no angle recorded
is a concern on the plan and no operation, with the field named. A hole with a
recorded depth is untouched: that depth is the drawing's, and it is measured to
the shoulder.

The peck decision stayed on the **material** depth rather than the drilled one.
What packs a flute is how much hole the chips have to climb out of; the
point-length overrun is mostly the point leaving the far side. 0.804″ of
material is exactly 4:1 on a Ø0.201 drill and 0.884″ to the tip is 4.4:1, and
pecking the second is a cycle spent on nothing.

**The sheet says what the setup now needs.** A Z of −0.830 on a 0.750″ part
reads as an error to anybody checking the plan against the drawing, and a
machinist who cannot see why will shorten it at the control — or set the part
flat on the parallels and drill them. The operation's rationale states the
material, the point and the break allowance separately, and the setup sheet
carries a CLEARANCE UNDER PART line: the deepest any operation in the setup
finishes below the bottom of the stock, which is exactly the gap the part has to
stand off whatever is under it.

`src/lib/engines/cam/drill-point.ts`, the drill branch of `machinist.ts`,
`buildSetupSheet`.

**Still open:** the same question applies to a contour cut through the stock —
an end mill leaves no cone, but a profile cut to exactly the stock height leaves
the part hanging on a film.

### B. The machinist must know how to set the job up

**B1 — The setup sheet. — BUILT**
Grep the source before this change: no setup sheet, no traveller, no job
packet. CANVAS *knew* everything one contains — stock size and grade, vise and
jaw type, grip depth, parallel height, jaw axis, orientation, work offset, the
tool list with stickout and holder, the operation order, the predicted cycle
time, the critical dimensions and how each is to be inspected — and printed
none of it. You cannot hand a program to a second-shift machinist with none of
that, which meant the program could not leave the office.

`setup-sheet.ts` assembles it and the page prints it: black on white, heavy
rules, program zero boxed at the top, and a print stylesheet that drops the
instrument shell — whose `overflow: hidden` would otherwise have clipped a
four-page sheet to page one with nothing to say the rest existed.

Two things on it are the point.

**Absence is printed, not omitted.** The dangerous setup sheet is the one that
leaves a field blank: a blank grip depth reads as "no grip depth needed", a
missing parallel height reads as "sits on the floor of the vise". Every unknown
becomes a line in a RESOLVE AT THE MACHINE checklist — tools with no pocket,
offsets that CANVAS does not set, toleranced features with no inspection
method, operations that produced no toolpath, features nothing cuts, and grip
numbers that are the plan's intent rather than a measurement. On the seeded
bearing support it printed four, all true.

**The gate state is printed.** A sheet in somebody's hand is not clearance to
cut, so it carries the readiness verdict and every open blocking gate. It also
carries the development-post notice unconditionally, because no package state
turns a development post into a certified one.

`src/lib/setup-sheet.ts`, `src/lib/program-origin.ts`,
`parts/[id]/setups/[sid]/sheet`, and the print block in `globals.css`.

**B2 — The work-offset origin. — BUILT**
The convention lived in two source comments in two different files and reached
the operator in neither. It now lives once, in `program-origin.ts`, and four
surfaces say it in the same words: the setup sheet, the NC analyzer's assumption
list, **and every post header**, in that dialect's own comment syntax.

Putting it in the header exposed two real defects in `verifyNc`, which is a
linter that reads programs and was reading prose. It found the `X0 Y0` inside
the new comment and read the line as a motion block — on its own only noise, but
combined with the feed check it turned a correct program into one reported as
"motion but no feed moves", which is an operator being told a cutting pass runs
at rapid. Any comment mentioning a coordinate outside the travel envelope would
have done the same. Comments are now stripped before anything is read out of a
line.

And it turned out `verifyNc` **could not read Siemens at all** — `X=` addressing
means every coordinate regex misses, so an 840D program came back CLEAN having
seen no motion whatsoever. It already refused Heidenhain by name for exactly
this reason; it now refuses 840D the same way. Verified is what an operator
reads as safe, and a dialect that was not read must never come back verified.

Still to do: the origin should become a property of the Setup — see B3 — rather
than a system-wide default.

**B3 — A setup had no coordinate frame. — BUILT**
`Setup` carried `orientation` — the string "TOP" or "BOTTOM" — and a work
offset, and nothing else. Feature coordinates were program coordinates by
assumption: no origin, no rotation, no statement of how the part sits.

For the first setup on a centred part that assumption is true, which is why it
survived. For the second it is not. Turn a part over and every X on it moves to
the other side of the machine — a hole at X+2.2500 in the model is at X−2.2500
once the part is flipped — and nothing in the system knew. The program was
dimensionally perfect and mirrored, which is the failure mode that measures
correct on every individual feature and scraps the part.

Worse, **"BOTTOM" does not say which way it was turned.** Rolled about X and
pitched about Y both put the bottom face up, and they mirror different
coordinates. The string on its own cannot be acted on at all — so a setup that
says the part is bottom up and does not record the axis is **refused**, and it
produces no motion. That is the one failure worth refusing outright rather than
warning about, because there is nothing downstream that could catch it.

The frame is a turnover, a quarter-turn index and an origin. Rotation is
restricted to quarter turns because that is what a vise does — an angle between
them needs a fixture that locates the part at it, and CANVAS does not model one
— and it keeps every derived box axis-aligned, which is what the simulator's
height field and the collision checks are built on.

Turning the part over is a proper 180° rotation in 3D, but in the XY plane the
machine works in its determinant is −1, so **every arc reverses**: a G3 on the
top face is a G2 on the bottom, and one left as a G3 cuts the other side of the
line. The canned-cycle descriptor is transformed with the moves rather than
derived from them, or a hole pattern would be drilled in one place and simulated
in another.

Applied **once**, in `buildPackage`, where the toolpath is produced — so the
post, the simulator, the reconciler and the sheet all read one frame. Verified
on the seeded bearing support: Setup 2's paths come out with X unchanged, every
Y negated and every arc reversed, and Setup 1 is untouched.

**Z is not transformed, and that is deliberate.** Operations are already
authored in the setup's own Z — the planner emits Setup 2's depths measured from
the face that is up in Setup 2 — so there is nothing to transform from.

The planner states which way it flips and why: rolled front to back about X, so
the face that was against the fixed jaw stays against it and the second setup's
X repeats off the first. Turning it about Y would swap them and hand the datum
to the moving jaw.

And the fact reaches the people it has to. The post header carries one origin
line per work offset — G54 the part as modelled, G55 the same part turned over
about X with every Y mirrored — because an operator picking up an edge under the
wrong reading cuts a mirrored part and nothing in the program is wrong enough
for a gate to catch it. The printed setup sheet carries TURNED as its own line
beside PART UP, since which face is up does not say which way it got there. The
setups page states the refusal beside the control that clears it.

The default is the convention the whole system already ran on: zero at the
centre of the stock, no index, the part the way up it was modelled. A setup that
records nothing means exactly that, so nothing planned before this existed
changes.

`src/lib/engines/cam/setup-frame.ts`, `Setup.flipAxis/quarterTurns/originX/Y`,
`buildPackage`, `PostContext.origins`, `buildSetupSheet`, the setup-geometry
form and the second-setup branch of `machinist.ts`.

**Still open:** a feature whose depth is measured from the opposite face — a
counterbore on the underside — is still not expressible, and datum transfer
between setups and its tolerance stack sit behind that. Multi-part fixtures and
tombstones need an origin per instance, which is this frame repeated rather than
a different idea.

### C. Verification must verify the artifact that is actually run

**C1 + C2 — Verify the artifact that is actually run. — BUILT**
Everything upstream verified the TOOLPATH: workholding, holding margin, the
height-field simulation, collision, cycle time, the gates, the approval. The
post sat downstream of every one of those proofs and nothing read what came out
of it. A dropped retract, a reversed arc, a canned cycle whose R plane does not
match the moves it replaced — each produces a program that looks like the plan
and does not cut like it, and every proof above would still have passed.

`nc/reconcile.ts` reads the emitted program back with the existing NC parser and
proves it traces the same path as the toolpath, to a stated 0.004″. **That is
stronger than simulating the posted text and cheaper.** If the program traces
the moves the simulator already swept, every proof already run against those
moves covers the program too — and there is no second material-removal model to
keep in step with the first. Two simulators that disagree is a worse problem
than the one being solved.

It compares in both directions, because a program that cuts a perfect *subset*
of the plan would pass a one-way check while quietly dropping a finish pass.
It refuses Heidenhain and Siemens **by name** rather than reading them wrongly —
the parser is a Fanuc-family interpreter, and run against a foreign dialect it
produced a page of confident nonsense. It reports UNVERIFIED where the parser
refused, because unread must never come back verified. And it gates: the export
mint runs it against the bytes about to be handed over, not against a stored
verdict.

**It found a real defect on its first run**, in code written an hour earlier:
the drill engine's peck ladder started at the stock top while `G83` measures Q
from the R plane, so every peck depth in the program was one increment off the
move list the simulator had already approved — 13% more cutting distance in the
program than in the plan.

Measured on a real eight-tool part, a freshly posted program traces the plan to
**0.00102″** — the NC parser's own arc tessellation, with everything else below
rounding. The same part's *stored* program, posted before arcs existed, comes
back at 0.0729″ and DOES NOT MATCH, which is the ordinary shop case this catches
every day: the plan moved and the program on the machine did not.

**Still uncovered, stated:** geometry, not machine state. It says nothing about
whether the work offset is set, the length offsets are right, or the spindle
turns the right way — `verifyNc` covers part of that and the setup sheet carries
the rest to the machine.

`src/lib/nc/reconcile.ts`, the mint in `parts/[id]/nc/actions.ts`, the panel on
`parts/[id]/nc`.

**C3 — Collision checks are optional and say so. (MEDIUM)**
The fixture check runs only when a fixture model is supplied and reports
`fixtureChecked: false` otherwise — honest, and not sufficient to release a
program. Holder and shank contact is inferred from flute length only. There is
no clamp, no parallel, no tombstone, no table, no machine envelope in the
collision model.

Build: required fixture geometry before export, holder solids from the tool
record, rapid-through-material as a blocking finding rather than a note.

### D. The post must be trustworthy for a specific machine

**D1 — Every post is `certified: false`, permanently. — BUILT**
`PostDefinition.certified` is typed as the literal `false` — the same trick as
`clearableByConfirmation`, and correct. But there was no path *out*: no record
of a post having been validated, against which machine and which control
software, by whom, with what evidence. Every post was permanently DEVELOPMENT,
which is honest right up until it becomes the label nobody reads.

`certified` stays a literal `false` and always will, because **certification is
not a property of the code**. It is a property of a post having been run on a
specific machine, at a specific control software version, by a named person who
watched what happened. So it lives in a `PostValidation` record beside the
machine, and both the readiness gate and the export pre-flight read that record.
Blocking, on both.

Scoped, and superseded rather than inherited. A post proven on the VF-2 says
nothing about the VF-4 next to it. And a control software update can change how
a canned cycle retracts or how look-ahead handles short blocks — which is
exactly what a post validation is *about* — so the control version is part of
the identity of what was proven, taken from the machine record rather than typed
on the form. A version nobody recorded cannot match a version nobody recorded:
"unknown equals unknown" is the reading that lets a stale proof stand.

Evidence is required and it is prose. "Cut air above the part, single blocked
the whole program, first article to print" is what the next person needs, and
this is the one gate in the system where a click would be least defensible.
Withdrawing a validation revokes it rather than deleting it — a program exported
last month under a proof later withdrawn is something a shop needs to find.

One distinction the build surfaced: **a program CANVAS did not write abstains
rather than failing.** An uploaded program came out of somebody else's CAM, and
proving CANVAS's Haas post says nothing whatever about a file Mastercam wrote. A
gate that claimed otherwise would be asking for evidence about the wrong
artifact — the kind that gets cleared to make it go away.

`src/lib/engines/post-validation.ts`, the `PostValidation` model,
`Machine.controlVersion`, the panel on `/machines`, the `postvalidation`
pre-flight item and the `post-validation` gate.

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

| Gate | Clears on | State |
|---|---|---|
| Feature coverage | Every feature is cut by an operation | **BUILT** (A4) |
| Emitted-program verification | Posted text reconciled to its toolpath | **BUILT** (C1+C2) — gates the mint |
| Proof-out state | A named person, a machine, a date, and a part that came out good | **BUILT** — non-blocking, see below |
| Post validated | A validation record for this machine + control | Open (D1) |
| Setup documentation | A setup sheet exists for every setup | **Dropped** — the sheet is generated from the package, so it cannot be missing. A gate that always passes is worse than no gate. The sheet's own RESOLVE AT THE MACHINE list carries what it does not know. |
| Collision checked | Fixture, holder and rapid interference all actually ran | Partial (C3) |

**The most important property of an NC program is whether it has ever cut a
good part**, and nothing recorded it: a program proven on the VF-2 last Tuesday
and the same program never run were indistinguishable, and no machinist treats
them the same. `nc/proof.ts` now answers NEVER RUN, PROVEN or STALE.

It is deliberately **non-blocking**. A program that has never cut a part is the
normal state of every new program, and a gate that refused to release one would
make first articles impossible — which is to say it would be routed around
inside a week. It makes the distinction visible and attributable, not
impossible.

STALE is the state worth reading twice: a program that *was* proven and has
since been re-posted. The proof stores the SHA-256 of the code it was about, so
a re-post moves it to STALE by itself rather than going on vouching for text
nobody has run — the same construction as the turning side's approval digest,
and for the same reason. An approval that outlives the thing it approved is
worse than none, because somebody relies on it.

Adding the gate also surfaced a mis-routing in SHOW ME: it substring-matched
gate ids **or labels**, so "Proven on the machine" matched the `machine` gate
and sent the operator to stock definition. The id now decides, and it decides
first.

---

## 3. TIER 1 — A SHOP CAN PUT ITS WORK THROUGH IT

Tier 0 gets one part cut. Tier 1 is the difference between a demonstration and
a shop's Tuesday. Still no kernel required.

- **Chained 2D geometry.** Open and closed chains, and general island
  avoidance. The natural extension of A5, and it covers most job-shop
  profiling. ~~Slots as real slots~~, ~~radial and grid patterns, bolt
  circles~~ and ~~the one island case that needs no clipping~~ — BUILT; see T1,
  T4 and T5.
- **Hole-making as a family.** Spot, drill, peck, chip-break, ream, back-spot.
  ~~Counterbore, countersink~~ and ~~the drill point angle in the depth
  arithmetic~~ — BUILT; see A9 and T1 below.

**T1 — Three feature kinds the planner skipped. — BUILT**
SLOT sat in the pocket bucket, so every slot on a part got a `POCKET_2D`
operation and the pocket engine then refused it — *"is a SLOT and cannot be
machined with a 2D pocket operation"*. A plan that reads complete, produces an
operation, and cannot run: the machinist reads the plan, and the refusal only
appears at export. COUNTERBORE and COUNTERSINK sat in **no bucket at all** — no
operation, no concern, total silence on a feature whose whole point is that a
screw head has to sit in it. The add-feature form collected the head diameter,
the head depth and the countersink angle the entire time.

A slot is a centreline and a width, not a rectangle. It cannot be helixed into
— at full width there is no room to swing, and this engine refuses to plunge a
tool nobody recorded as centre-cutting — so it ramps along its own length at 3°,
alternating direction, and the step per pass is whatever that ramp reaches over
the travel the cutter actually has. A slot no longer than the cutter is a
round-ended pocket and is refused rather than fed straight down at one point.
Where the tool is narrower than the slot it takes a finishing lap round the
stadium the boundary offsets to; where it is not, the program says the cutter is
180° engaged, which is the heaviest cut there is.

The planner picks the **biggest cutter that fits**, which is the opposite rule
to a pocket's biggest-that-clears-the-corner, and prefers one that leaves a wall
to finish.

A counterbore is the one plunge in the system that does not need a
centre-cutting mill: the tool is concentric with a hole that already exists, so
its axis is over open air. A ⌀0.400 bore with a ⌀0.375 mill leaves 0.0125" of
radius to move in — no helix fits, and none is needed. It is cut to the
counterbore's own depth, not the operation's `finalZ`: the pilot goes through
the part, and a head cut to the pilot's Z is the part in two pieces.

A countersink is a cone cut by a cone, which is the same arithmetic as the
chamfer in A8 — the tool's included angle IS the angle, and a tool ground at 90°
is refused for an 82° countersink rather than plunged deeper to make the
diameter. The plan carries the depth the engine derives, so the sheet and the
program are one number.

The stage table puts a head after the drill and before the tap: a counterbore
cut after tapping takes the top of the thread off, and a countersink after it
raises a burr into the finished form.

`slotToolpath` and `headToolpath` in `cam/engine.ts`, `classify` and the slot
and head branches of `machinist.ts`, `FEATURE_STAGE`.

**T2 — A tapped hole was never threaded. — BUILT**
The planner had **no thread branch at all**. `tapToolpath` has existed since
Phase 1, the `TAP` operation type has always existed, the seeded crib holds a
1/4-20 spiral point tap — and nothing ever emitted the operation. Four "1/4-20
mounting hole" features on the seeded part came out as four plain Ø0.201 holes,
and the coverage gate passed them, because the feature HAS operations: it was
spotted and it was drilled. A part with no threads in it, and a plan that reads
complete.

Found by reading the planner for something else. It is the worst of the family
so far, because unlike the counterbore there was no gate that caught it: every
check the system runs was satisfied by a hole.

**The match is on the thread, not the diameter.** A 1/4-20 tap and a 1/4-28 tap
are both Ø0.250, and picking one by size puts a 28-pitch tap into a hole drilled
for 20 and snaps it off in the part — the most expensive thing that happens to a
small hole. `Tool.threadDesignation` is a new nullable column and a tap without
one is refused rather than matched on its size, the same rule as the chamfer
mill's point angle. `sameThread` compares the numbers a designation parses to,
so "1/4-20" and "1/4-20 UNC" are one tap and "M6x1.0" and "M6 x 1" are one tap.

**Thread milling** is the other half, and it is the same helical arc machinery
the bore already uses. A full-form mill carries the whole profile on its flutes,
so one 360° turn rising a single pitch cuts the entire thread; the tool circles
at (major − toolDiameter) / 2, because an internal thread's MAJOR diameter is
its root. It runs bottom-up and counter-clockwise, which climb mills a
right-hand thread, and enters and leaves on tangential half-turns of the same
helix rather than diving at the wall radially. A single-point mill needs a pass
per thread and this engine does not implement one — it says so rather than
emitting one turn and calling it a thread. A mill whose form is shorter than the
thread is refused: one turn would cut the top and leave the bottom uncut, which
a plug gauge finds and a tapped hole never would.

All five approaches tap where a tap exists, because that is what a shop does.
`BEST_FINISH` mills it instead, because the size then comes off the D offset —
which is how a class-3 fit is held and how a first article is corrected without
buying a tool.

**And the hole is checked against the thread.** The feature form asks for
"Diameter" on a tapped hole and does not say which of the two diameters it
means. `major − pitch` is the standard tap drill at about 77% engagement, so a
hole recorded at the thread's own major diameter has 0% of the form left to cut
and says so, and one drilled tight enough to put over 85% on the tap says that
too — past about 80% the strength barely moves and tap life falls off a cliff.
This checks a recorded hole; it never replaces one.

Verified on the seeded part: four `G84` holes merged into one cycle at F34.40 =
688 rpm × 0.0500 pitch, no `M3` before it because the cycle owns the spindle,
`verifyNc` clean and the reconciler agreeing to 5e-17.

`src/lib/engines/cam/thread.ts`, `threadMillToolpath` in `cam/engine.ts`,
`Tool.threadDesignation`, the thread branch of `machinist.ts`.

**T3 — The tap's lead chamfer, and the hole under a blind one. — BUILT**
Found while building T2 and fixed straight after it. A tap does not cut a full
thread to the end of its travel: the lead chamfer is still forming when it
stops. A drawing calling 0.500" of thread wants 0.500" of **full form**, and a
tap that stops there leaves the last threads incomplete — which a plug gauge
finds and nothing else does.

Worse, a blind tapped hole was drilled to the thread depth and then tapped to
the same depth. That is how a tap bottoms out and snaps off in the part, and it
was the arithmetic on every blind tapped hole in the system.

`Tool.tapLeadThreads` records the chamfer in threads — taper 7-10, plug 3-5,
bottoming 1-1.5, and it is on the catalogue page. The tap's tip now runs to the
called-out depth plus its lead, and the drill under a **blind** one goes deeper
still: thread, plus lead, plus two threads for the chips to go somewhere.

The two cases are not treated the same, because the cost of a wrong guess is
not the same. In a **through** hole the far side is already open, so running
past costs nothing and a tool with no lead recorded gets a stated five threads
— printed in the operation's own rationale, not hidden in a Z. In a **blind**
hole a lead assumed too short bottoms the tap, so it is refused and the message
names the field.

`tapDepth` in `cam/thread.ts`, the drill and tap branches of `machinist.ts`,
`Tool.tapLeadThreads`.

**T4 — A bolt circle is one line on a drawing and six features on a part. — BUILT**
Every hole in a pattern had to be typed in by hand, one at a time, with its
coordinates worked out off the machine. Six holes on a 3.000" circle is twelve
numbers to compute and twelve to mistype, on the most common thing there is on a
plate — and a hole entered at the wrong angle gets drilled in the wrong place
and measures perfectly on its own diameter.

**It expands rather than staying a pattern**, and that is the design decision
worth stating. Everything downstream of the feature list is per feature:
coverage asks whether each one is cut, inspection assigns each one a method,
measurement records a reading against each one, and A7 made operations per
feature for exactly that reason. A virtual pattern would have to be unfolded at
every one of those points, and the first place it was not unfolded would be a
hole nobody checked. So the drawing's statement is turned into the real features
it describes, and travels with them as provenance so the group stays visible and
editable as a group.

Bolt circle, grid and line. The source feature **becomes** instance 1 rather
than being copied beside it, so the tolerance, the fit and the mating component
already recorded carry across — it is one feature the machinist described,
placed the number of times the drawing says. The **inspection method does not**:
that is a decision about how one feature gets verified, signed by whoever made
it, and copying it would put a person's name on five decisions they did not
make.

A pattern whose centres land off the stock is refused **before any feature
exists**, with the count and the first offender named — a bolt circle bigger
than the plate is a transposed diameter or the wrong datum, and six features
plus one hole in the middle of a rapid is a much more expensive way to find
that out. The whole placement is one transaction, because half a bolt circle is
worse than none: the coverage gate would pass on three holes where the drawing
calls six.

Verified through the UI on the journey plate: a ⌀9.000 circle refused with *"6
of 6 would sit off the 4.250 × 3.250 stock — the first at X4.5000 Y0.0000"*, a
⌀3.000 one placed as six features at exact coordinates, and the planner picking
them up as six spots and six drills — which the post then merges into two
cycles.

`src/lib/domain/pattern.ts`, `patternFeature` in `features/feature-actions.ts`,
`components/pattern-form.tsx`, `Feature.patternId/patternIndex/patternJson`.

**T5 — A pocket machined away anything standing in it. — BUILT**
A pocket toolpath sweeps its whole area. On a 3.000 × 2.000 pocket with a
Ø0.750 locating boss at its centre, **66 of the 188 moves were inside the
boss**, and the helical entry started at the boss's own centre. The boss was
machined away, the operation reported real motion, and nothing said a word.

The coverage gate caught the wrong half of it. A `BOSS` was in no `classify`
bucket at all, so it had no operation and read as "not cut" — and a machinist
looking at a feature they want **left standing** could reasonably record it as
not made by this program, which clears the gate and leaves the program still
cutting it away. The check that existed pointed at the symptom and the cause
went unmentioned.

Machining round an island is island avoidance: offsetting a region bounded by an
outer loop and inner loops, and clipping every ring against every island. That
is a real piece of computational geometry and this engine does not have it — so
a pocket with something standing in it is **refused, by name**, rather than
approximated.

**One case needs none of it.** A round island concentric in a round pocket is an
annulus, and concentric rings between the two radii are exactly right with
nothing to clip — a sealing land, a relief round a spigot, a counterbored face.
That case is cut: the rings start a tool radius clear of the island, the helix
goes in the BAND rather than on the axis (there is material on the axis now), a
band narrower than the tool is refused, and the island gets a finish pass of its
own because it is a wall of the part and the one the boss's size is measured on.
Measured: a Ø0.375 tool in a Ø2.500 pocket round a Ø1.200 spigot cuts between
radius 0.7875 and 1.0625, and nothing enters the spigot.

The planner does not plan a pocket the engine will refuse — the same rule as the
slot — and every boss now says how it is not made, whether it stands in a pocket
or on its own face.

`src/lib/engines/cam/island.ts`, `pocketToolpath` in `cam/engine.ts`, the boss
and pocket branches of `machinist.ts`.

**Still open:** general island avoidance, which is the rest of this Tier 1 item
along with open chains and multiple pockets. What is here refuses honestly and
cuts the one arrangement it can prove.

**T6 — The last kinds nothing looked at. — BUILT**
A sweep of **all fifteen feature kinds** through the planner, asking one
question of each — does this produce an operation, or say why not — found three
still dropped in silence.

A **FILLET** appeared nowhere in any engine. It did not constrain tool
selection, it was not cut, and it raised no concern. `minimumInternalRadius`
read pocket corners, bores and slots and not the one feature whose entire
content is a corner radius — so a drawing calling R0.0625 pocket fillets beside
a pocket whose own corner reads R0.2500 was cut with a Ø0.500 mill and came back
with corners four times too big for whatever had to sit in them. A fillet is not
a cut of its own; it is the drawing stating the smallest cutter that may be
used, and now it says so and constrains it. An OUTSIDE_VERTICAL fillet
constrains nothing, because a cutter of any size goes round an outside corner.

A **STEP** had no toolpath and no plan branch, though it is an ordinary cut: a
facing pass over a strip along one edge. It is not a pocket — it is open on the
side it runs along, so ringing a closed boundary would air-cut the open edge and
bury the cutter at the closed one. It zig-zags across the strip, entering and
leaving past the end of the part where there is no material, which is what lets
it need neither ramp nor helix. The cut lands exactly on the edge and exactly on
the wall: a Ø0.500 tool on a 0.500" step off a 6.000 plate runs its centre from
X−3.250 to X−2.750.

And a **FACE with no face mill in the crib** produced no operation and no
concern — the silence that survived longest, because a shop nearly always owns
one. Datum A is the surface every other dimension on the part is measured from.

The sweep is now a test. Every kind in the vocabulary is planned against a crib
that can make it, and any that produces neither an operation nor a concern
naming it fails the suite — which is the check that would have found SLOT,
COUNTERBORE, COUNTERSINK, BOSS, FILLET, STEP and the unthreaded tapped hole in
one run, months before an audit did.

`stepToolpath` in `cam/engine.ts`, `minimumInternalRadius` in `domain/features.ts`,
the step, fillet and face branches of `machinist.ts`.

**T7 — Tool life was a number nobody updated. — BUILT**
`Tool.lifeRemaining` was a 0-1 float. It was **required** on the tool form and
rendered on the crib page as a colour-coded percentage — green above 40%, review
above 15%, risk below — and **nothing in the system ever changed it**. It was
whatever somebody typed when the tool was added, possibly a year and four
hundred parts ago, presented ever after as a live gauge. A machinist reading
"T2 · 100%" in green concludes that tool has plenty of edge left. That is worse
than showing nothing and worse than a stub, because a stub says so.

What a tool has actually done is now accumulated: when a job is marked COMPLETE,
each tool is charged the cutting time its toolpaths took times the quantity made,
scoped to the shop that ran it, logged with `actorType: "SYSTEM"`. Where a
machinist recorded an actual cycle time that is what is charged, apportioned
across the tools in the ratio of their estimates — there is nothing per tool to
measure against, and a measured-looking figure on a derived share would be the
same lie in miniature.

Three rules the old float broke:

- **No denominator, no percentage.** A tool with no expected life recorded gets
  the minutes and a sentence saying what is missing, never a fraction. Inventing
  a denominator is how the float got there.
- **It is a floor, not a total, and it says so beside the number.** A job run
  without being recorded, or this cutter borrowed for another part, is time
  nothing here saw. A machinist who believes 40% is left and has 5% is the
  person the feature exists to protect.
- **A fresh edge restarts the count.** Minutes never fall on their own, which is
  right until somebody regrinds the cutter or swaps the inserts. Without a
  restart the chip reads PAST_EXPECTED on a brand new edge — wrong in the
  direction of alarm, and ignored exactly as fast as one wrong the other way.
  What went in is required, the cleared count is kept in the audit trail, and a
  regrind counts as one.

Completing a job in the browser found what the tests did not: a spot drill
charged 0.4 min read "0 min over 1 part" and "0% used", which to somebody
glancing down a column is the same sentence as "unused". Short times keep a
decimal and a real charge never rounds to nothing.

`src/lib/engines/tool-life.ts`, the COMPLETE branch of `jobs/actions.ts`,
`freshEdge` in `tools/actions.ts`, the crib and tool-edit pages. `lifeRemaining`
stays in the schema so no shop's data is thrown away, and reaches no screen.

**T8 — The offset registers the program calls for. — BUILT**
`G43 H6` tells the control to apply the length in row 6 of its offset table;
`G41 D6` applies its radius. CANVAS wrote `lengthOffset: t.toolNumber` in three
places. H and D were the tool number, everywhere, with no shop record behind
them — and the program header and the setup sheet printed the result as though
CANVAS knew what was loaded in that control.

It usually IS the tool number, on a Haas or a Fanuc where H and D index the same
row. It is not universal, and a shop running sister tools or keeping diameter
offsets in a separate block so a length can never be typed into a radius had no
way to say so. A wrong H is the single most consequential wrong number in a
program: the tool goes to the wrong Z, which is a crash into the fixture or a
cut in air.

The registers are now recorded on the tool. Where a shop has recorded them the
program calls them; where nobody has, the tool number still stands in — a
program has to call something — but it goes out labelled ASSUMED, in the header,
against each tool, and on the setup sheet, with the tools named rather than
counted. The two live in one engine so the paper in the operator's hand cannot
name a different register from the program.

Two blocks the post could write and must not, both found while wiring this and
neither reachable through today's engine — which is exactly why they were worth
closing:

- `G41 D0`. Not "no offset selected" but compensate by ZERO: the control cuts on
  the programmed boundary and every wall comes back a tool radius oversize. It
  reads like a real block and it runs. The emitter's `D${dOffset ?? 0}` is gone.
- **Compensation on an arc block.** G41/G42 must be commanded in G0 or G1; this
  family alarms on comp in a circular block. The arc branch returned before the
  comp words were ever used, so an arc lead-in would have gone out silently
  uncompensated — the same oversize part with nothing to read. No arc lead-in
  exists today, which is why the trap would have been sprung by whoever added
  one. Both throw rather than emit.

And emitting the seeded crib turned up a third, in the header itself. A
Fanuc-family comment runs from `(` to the FIRST `)`, and T6 is described as
`#7 (0.201") carbide drill` — so the comment ended after 0.201 and the control
read ` carbide drill` as G-code words and alarmed on line 12. Comment text is
now sanitised on the way out: brackets become square ones, and `⌀ ″ ° — · × ±`
go out as the words a machinist would have typed, because a lot of readers in
the field are ASCII and a control that chokes on a byte in a comment is not a
control with a bug.

`src/lib/engines/cam/offsets.ts`, `commentText` and the emitters in `cam/post.ts`,
the tool crib form, `setup-sheet.ts` and the printed sheet.

**T9 — Two setups, one program, no flip. — BUILT**
The worst defect found in the CAM chain so far, and the seeded demo part is the
case that shows it. `CANVAS Bearing Support` has two setups: *Top face and
features* under G54, and *Flip, thickness and profile* under G55. It posted as
one continuous program.

`Toolpath` dropped `setupId` on the way out of the engine — `OperationRequest`
carried it, the toolpath did not. So by the time the post saw the list, every
setup's motion was one undifferentiated stream, and the emitter had no
information to do anything else even if it had wanted to. All eleven motion
blocks called a single work offset taken from a **dropdown on the export form**,
and nothing marked the boundary: no stop, no comment, not a blank line. The
control ran setup 1 and then ran setup 2's motion on a part still clamped the
first way. Setup 2 machines the opposite face. That program drives the tool
through the vise.

And the header had printed `G54 — …` and `G55 — …` since B3, which is exactly
what made it look considered.

- **A setup change is a person doing something with their hands.** The boundary
  now retracts to machine zero, brings the table out, and stops on **M0** — not
  M1, because an optional stop is skipped by a control with optional-stop off,
  which is a setting, and a part coming out of the vise is not. It names the
  setup, says to re-clamp as the sheet shows and set G55, and prints that
  frame's own sentence including the turnover warning. It sits *before* the
  operation heading, so an operator single-blocking does not read it as
  belonging to the next cut, and the tool is re-called afterwards even if it is
  the same cutter — the operator has been at the machine.
- **Motion runs under its own setup's offset.** A setup with no frame recorded
  falls back rather than borrowing the other one's, which would be the same
  failure arrived at from the other direction.
- **The work-offset dropdown is gone.** It was a fourth source of truth for
  something the setups record, and picking it wrong silently overrode them while
  the header printed the setups' own offsets. The page states what the setups
  say instead.
- **The header says how many setups the program holds**, because a machinist
  loading one program has no other way to know it contains two operations until
  they meet the M0 halfway down it.
- **A setup entered twice is refused.** The package builds toolpaths setup by
  setup so they arrive contiguous; if they ever stopped being, this would
  cheerfully ask the operator to flip the part, cut two moves, and flip it back.
  That is motion which is individually correct and collectively a part clamped
  four times to make two cuts.

Every control answers for itself. GRBL runs everything this post writes under
G54, so its boundary says the offset is the operator's to re-zero rather than
emitting a G55 the machine will not honour. The 840D selects the frame itself.
The TNC emits no datum shift, so it says so and names the preset the sheet
calls — and its stop is a numbered block, because a comment is not one and a
stop that is not a block is a stop the control skips.

`setupId` on `Toolpath`, `setupBoundary` / `offsetFor` / `enterSetup` and all
four emitters in `cam/post.ts`, the NC export page.
- ~~**Thread milling.**~~ — BUILT, along with the tapping that was never
  planned at all. See T2.
- **Rest machining.** Where the big tool could not reach. Needs a record of what
  the previous tool left, which is the first step toward an in-process stock model.
- **Multiple work offsets and fixture offsets.** ~~One offset per setup~~ —
  BUILT, see T9. Still open: `G54.1 P`, multi-part fixtures, the same program
  run four up.
- **Tool library that means what it means elsewhere.** Per-material feed and
  speed data rather than one SFM band; presetter data; pocket assignment; sister
  tools. ~~Tool life in minutes and parts, not a 0–1 float~~ — BUILT, see T7.
  ~~D and H registers~~ — BUILT, see T8.
- **The job packet.** Setup sheet plus tool list plus traveller plus first-article
  form, printed together, versioned with the program.
- **Program revision control at the machine.** Which revision is loaded, hash
  checked against the approved one (the export already computes a SHA-256),
  DNC or drip feed for programs over the control's memory.
- **Second op properly.** B3's transform and T9's boundary are in. Still open:
  datum transfer, dowel and soft-jaw location, and the tolerance stack across
  the flip stated as a number.

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

1. ~~**A4** feature coverage gate~~ — BUILT. Found six uncut features on a
   seeded part the first time it ran.
2. ~~**B1** setup sheet~~ — BUILT. The program can leave the office.
3. ~~**A1** arc output~~ — BUILT. 1,685 blocks to 420 on the seeded part, and
   a bore that is round.
4. ~~**A3** canned cycles~~ — BUILT. The program reads like a program.
5. ~~**C1 + C2** simulate and reconcile the posted text~~ — BUILT. It caught a
   peck-depth defect in code written an hour earlier, which is the loop
   working.
6. ~~**A2** cutter compensation~~ — BUILT. The machinist has their offset back,
   and a corner gouge went with it.
7. ~~**B2 + E** origin declaration, proof-out state, the remaining gates~~ —
   BUILT. The origin declaration is now per setup; see B3.
8. ~~**A5 + A6** chained contours and real finish passes~~ — BUILT.
8b. ~~**A7 + A8 + A9** one operation per hole, a chamfer that is one, and a
   through hole that goes through~~ — BUILT. A six-hole bolt circle was one
   hole, a chamfer was a ring round the stock, and every through hole had a
   cone left in the bottom of it. The audit found the first two; the third
   turned up while fixing them. The tests found none of the three.
9. **D1 + D2** one control commissioned properly, end to end, on real iron.
   ~~D1~~ BUILT; D2 needs real iron.
10. ~~**B3** the setup transform~~ — BUILT. A flipped setup was a mirrored
   program that measured correct on every feature, and "BOTTOM" could not say
   which way the part was turned.

Items 1 through 8b are built. What is left in Tier 0 is **D2** — one control
commissioned end to end — and it needs real iron and a machinist, not more
code. Everything after that is scale.
