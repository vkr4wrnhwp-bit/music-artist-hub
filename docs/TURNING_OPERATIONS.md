# Turning operations

Types in `turn/operations.ts` (17 named; 8 have engines, the rest
refuse by name). Every op carries feed/rev, CSS or fixed RPM, DOC,
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
