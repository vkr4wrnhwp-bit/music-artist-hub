# Turning cycle optimizer — BUILT (proposals only)

`src/lib/manufacturing/turn/optimize.ts`, surfaced in the Optimizer
proposals panel on `/lathe/[id]/nc-review`. DEVELOPMENT ANALYSIS — all
figures are estimates from the program's own words and the shop's
recorded insert data, never measurements.

## What it proposes — feed and speed words only, never a coordinate

1. **FEED** — contiguous cuts on one tool whose feed/rev sits below the
   insert's recorded window (rubbing). Proposes the window midpoint,
   capped by the preset multiplier (CONSERVATIVE 1.15×, BALANCED 1.35×,
   AGGRESSIVE 1.6× — AGGRESSIVE proposals carry REVIEW risk).
2. **CSS_CONVERSION** — a G97 fixed-RPM region cutting across a ≥1.5×
   diameter range. Proposes G96 at the surface speed the program already
   runs at its LARGEST diameter, so no point cuts faster than today,
   with G50 at the chuck's recorded RPM limit. **Refused when the chuck
   limit is not recorded** — the gap names the missing input instead of
   inventing a clamp value. Always REVIEW risk: interrupted cuts and
   workholding behaviour at higher RPM are not modelled.

## Refused on principle

- G32 thread passes — the feed is the pitch, never optimized.
- Cuts without a tool record, S context, or feed word — UNKNOWN band,
  no proposal; INSUFFICIENT DATA is a verdict.
- Feeds already inside or above the window; SFM already over the insert
  rating is a review, not an optimization target.
- Everything behind a parser refusal — the optimizer sees only what the
  parser understood, and says so in gaps.

## Not built

Program rewrite/emission of the optimized code (proposals are read and
applied by the machinist), spindle-load telemetry, tool-life modelling.

Pinned by 5 tests in `tests/engines/turn.test.ts`, including the
self-test that the optimizer leaves the engine's own post output alone
when its feeds sit inside the insert window.
