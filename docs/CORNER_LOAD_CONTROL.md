# Corner-load feed control — BUILT (DEVELOPMENT load estimate)

REDUCE proposals in `load.ts`: within each same-tool, same-feed run
(rapids transparent — a multi-pass pocket is one run), segments whose
replayed removal rate exceeds 2.0× the run median form a spike.
Proposed feed = original × (median/peak), floored so the chip never
thins below the insert's minimum chipload, with hysteresis: stretches
shorter than 0.08" are never proposed, deltas under 12% are chatter and
suppressed. No stock replay → no spike is ever guessed.

CONTROLLED LOAD, NOT MAXIMUM LOAD: reductions carry
estimatedSecondsSaved 0 and the savings total counts RAISE proposals
only — control is not sold as savings. Risk is always REVIEW;
assumptions name the height-field resolution and the unmodelled
lookahead. Protection wins over reduction: a spike inside a protected
region is reported, not touched.
