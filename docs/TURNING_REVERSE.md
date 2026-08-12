# Turning reverse engineering — BUILT

`src/lib/manufacturing/turn/reverse.ts` + `/lathe/[id]/reverse`, started
from "Reverse engineer a shaft" on /lathe.

## The flow

Datum face first, then steps front to back — a diameter and a length per
reading, instrument named so the uncertainty is real. Each reading is an
audited HUMAN act (instrument + uncertainty in the audit reason); the
last reading can be withdrawn (also audited). The engine assembles a
RotationalProfile with MEASURED provenance as readings accumulate; the
growing PROFILE view renders live and the part opens in the full turning
workspace at any point.

## What is never done silently

- No reading is rounded to a nominal. The nominal candidate list (wear
  window open — RE parts are usually worn) shows the top match with its
  deviation and confidence; ACCEPT records the nominal as a USER ruling,
  KEEP MEASURED confirms the reading — both audited with old/new values.
- Threads are recorded as gauged designations ("3/4-16 UNF"), never as a
  micrometer reading over the crests — the guidance says so explicitly.
- Stock is a labelled SUGGESTION (next standard bar over the largest
  measured diameter + 1/16" cleanup, +0.25" length allowance) with its
  basis stated, to be confirmed against the rack.
- A reading recorded without an instrument is flagged: uncertainty
  unknown, nominal matching weaker.

## Storage

`RotationalPart.reReadingsJson` (paired migrations) holds the readings;
the assembled profile is written to `profileJson` so the rest of the
turning stack (toolpaths, analyses, readiness) reads it unchanged. An
RE part with no readings redirects from the workspace to the bench flow.

## Not built

Photo capture for rotational parts, runout/roundness measurement
guidance (V-block + indicator flow), taper measurement (sine bar / two
wires), ID depth mapping beyond a single bore flag.

Pinned by 5 tests in tests/engines/turn.test.ts.
