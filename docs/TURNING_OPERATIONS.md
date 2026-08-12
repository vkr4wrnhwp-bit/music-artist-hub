# Turning operations

Types in `turn/operations.ts` (17 named; 8 have engines, the rest
refuse by name). Every op carries feed/rev, CSS or fixed RPM, DOC,
finish allowance, spring passes, coolant. Engines are pure arithmetic;
refusals are typed results with reasons ("groove narrower than the
insert"). Thread passes: constant-area infeed, feed = pitch, G97 —
the same never-retime law as the mill's G84. Cycle time is ESTIMATED
and states assumptions per op: no acceleration model, CSS at mean pass
diameter, no dwell/spin-up.
