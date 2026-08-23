# Turning operations

Types in `turn/operations.ts` (17 named; 16 have engines — every
implementable type. CUSTOM refuses by definition: an operation CANVAS
cannot characterise is not one it generates motion for). Every op carries feed/rev, CSS or fixed RPM, DOC,
finish allowance, spring passes, coolant. Engines are pure arithmetic;
refusals are typed results with reasons ("groove narrower than the
insert"). Thread passes: constant-area infeed, feed = pitch, G97 —
the same never-retime law as the mill's G84. Cycle time is ESTIMATED
and states assumptions per op: no acceleration model, CSS at mean pass
diameter, no dwell/spin-up.

## Chamfers and radius blends

These two are where the insert's nose radius stops being ignorable.

A straight OD or a face gets away with ignoring it: the nose touches the
work at the programmed X (or Z), so the imaginary tool tip the control
positions cuts the size you asked for. **A taper or an arc does not.** The
contact point walks around the nose as the cut angle changes, and an
uncompensated path leaves the profile off by an amount that scales with the
nose radius — on a 1/32" insert that is over ten thou, always in the same
direction. This is the entire reason lathe controls have G41/G42.

So both operations:

- **Refuse without a recorded nose radius.** `TurningTool.noseRadius` was a
  column used by nothing before this.
- **State what the uncompensated path costs**, with the number, as a warning
  on the toolpath — not buried in a comment.

### What is deliberately not built

**Automatic nose radius compensation.** The post emits `G40` and CANVAS does
not compute a compensated path. Emitting a corrected profile would be a
number with nothing behind it, and emitting `G41/G42` *as well as* a
compensated path would double-compensate — a real hazard. The bound is
stated and the machinist decides: turn comp on at the control, or prove the
chamfer on the first piece.

### Blends are chorded, and say so

The post has no arc output — `TurnMove` is `RAPID | CUT | THREAD_PASS`, which
maps to `G0 / G1 / G32`. A blend is therefore chorded into linear moves at a
stated **0.0005" chord tolerance**, and the assumption says so rather than
describing the result as an arc.

The points are stepped along the **true arc**. The first implementation
interpolated the chord and pushed each point out by a parabola; it claimed
0.0005" and delivered 0.0027" — five times worse, stated with a confidence
it had not earned. That is pinned by a test that recovers the arc centre
from the endpoints and checks every point against it.

### Concave is not the same question as internal

`ProfileSegment.internal` says whether a feature is a bore or an OD.
`ProfileSegment.concave` — added for this — says which way a blend curves:
a fillet cut **into** the material (the stress-relief radius at the base of
a shoulder) or a round **on** it (a broken corner).

An OD shoulder carries a concave fillet every day, so the two are
independent. Confusing them puts the arc on the wrong side of its own
endpoints: a visibly wrong profile, cut confidently. A blend whose segment
does not record concavity is refused rather than assigned a side.

Concavity also decides the nose fit: a **concave** blend cannot be cut by a
nose bigger than itself — the same impossibility the milling engine refuses
for a corner radius against an end mill. A convex blend has no such limit,
because a large nose simply rolls around the outside of it.

## Tap and ream

Both are centreline operations with hard rules rather than parameters.

**Tap.** The feed is not chosen — it IS the thread. In G99 feed-per-rev the
tap's feed word is the pitch exactly, so `params.feedPerRev` is overridden
rather than trusted, and the override is stated as a warning. The spindle is
capped at 600 RPM (the engine's cap travels to the post as
`spindleRpmOverride`, because a cap the post cannot see is not a cap).
Refusals: no pitch, no drilled hole, CSS enabled.

The reversal at the bottom cannot be expressed as moves — `TurnMove` has no
spindle state — so the toolpath carries `rigidTapCycle: true` and the post
emits `M29 S… / G84 … F(pitch) / G80`, which owns the spindle: no `M3`
before it, no stand-in `G1` moves leaked into the program. A post without
the cycle must refuse the operation. (The lathe NC *parser* refuses `G84`
by the same honesty — it cannot expand a control-dependent cycle, so
analysis of a program containing one stops at that line by name.)

**Ream.** A reamer follows a hole, it does not make one. Removal on diameter
is bounded on both sides — below 0.003" it burnishes and the hole comes out
glassy and undersize; above 0.015" it is being used as a drill and cuts
oversize or bell-mouthed. Both refusals name the bound. The reamer feeds in
AND OUT at cutting feed: a rapid out of a reamed hole drags a spiral scratch
down the finish the reamer exists to produce, and a reamer is never
reversed.

## ID grooving and threading

Boring's law applies to everything inside a bore: **clear is inward.** An OD
groove retracts to a bigger X; an ID groove retracting to a bigger X is
parked in the groove it just cut.

Before any of it, the tool has to fit the hole. `TurningTool.minBoreDiameter`
is the tool record's own answer — a column previously used by nothing — and
an unrecorded value is a refusal, not an assumption.

**ID groove.** Plunges outward from the bore surface to the groove root
(`endDiameter > startDiameter` — an internal groove is *bigger* than its
bore, the mirror of the OD case, and the inverted form is refused as
removing nothing). Between plunges the tool comes fully off the root before
any Z move: the test requires **both endpoints** of every Z-changing move to
sit at or inside the clear diameter, because a diagonal rapid from the root
ends clear and sweeps through the shoulder on the way.

**ID thread.** Passes open outward from the minor diameter (the bore) with
constant-area infeed, feed = pitch on `G32`, G97 fixed RPM — the OD thread's
law plus boring's. Form depth is **0.5413 × pitch**, not the external
0.6134: the internal crest is truncated (5/8H, the standard nut form).
Cutting an internal thread to the external depth over-cuts the major and
guts the thread engagement. Between passes the tool comes off the flank
inward and leaves the bore along the clear diameter, never dragged back
across the thread it just cut.
