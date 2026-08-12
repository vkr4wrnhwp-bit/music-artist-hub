# Turning cost + make-vs-buy — BUILT

`src/lib/manufacturing/turn/cost.ts` + `/lathe/[id]/cost` (linked from
the operation-plan panel). The generic cost engine (`engines/cost.ts`)
does the arithmetic; turning changes WHERE the assumptions come from.

## Bar economics — computed, not assumed

- Part-off kerf from the recorded parting tool's groove width. No
  parting tool recorded → parts-per-bar is NOT computed; the missing
  input is named.
- Remnant = recorded grip length + 1.0" spindle-side margin (a stated
  assumption, printed with its basis).
- Parts per 12 ft bar and bar utilization computed from those. The
  utilization factor amortises only the remnant and end drop — the kerf
  is already inside the per-part stock volume, so nothing double-counts.
- Falls back to the visible shop default utilization (named as a
  fallback) when the bar math is refused.

## Setup built from what the setup needs

0.75 hr baseline; +0.60 hr when the recorded soft jaw set is not at
this grip diameter (cross-checked against the soft-jaw drawer search);
+0.15 hr for tailstock engagement. Every adder is a named basis line.

## Unchanged principles

Cycle minutes come from the generated turning toolpaths. BUY stays
unevaluated with no external quote — CANVAS never estimates a supplier
price it has no basis for. Every cost line carries its basis string;
rates/scrap/margin stay visible shop assumptions.

Pinned by 4 tests in tests/engines/turn.test.ts.
