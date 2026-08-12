# Lathe soft jaws — BUILT

`src/lib/manufacturing/turn/soft-jaws.ts` + `/lathe/[id]/soft-jaws`,
linked from the workspace chuck-grip panel.

## Lathe rules, not mill rules

A mill vise jaw shims DOWN from its cut size. A chuck soft jaw holds
exactly what it was bored at, and can only ever be RE-BORED LARGER. The
drawer search ranks: DIRECT (already at the grip ⌀ — indicate before
trusting), REBORE (below the grip, one cleanup pass up to 0.5" total
growth; also shallow steps needing deepening), BLANK, UNUSABLE (bored
larger than the grip — a chuck jaw cannot shrink, stated plainly).

## The recipe

Bore IN PLACE, UNDER PRELOAD, at the grip diameter (+0.0000/−0.0005),
depth = grip length + 0.05" so the part seats on the step face. The
preload ring is sized at grip + stroke/2 (mid-stroke) — when the
chuck's jaw stroke is unrecorded the ring is NOT sized and the missing
input is named. Boring RPM/feed come from the boring bar's recorded
windows only; no cutting data is invented. The recipe refuses outright
when grip diameter or grip length is missing, or when the boring bar
cannot enter the bore.

No TIR is promised: the final step is "indicate a ground pin and record
what you read" — concentricity is a measurement, not a marketing claim.

## Recording

"Record a completed bore" is a HUMAN act, audited (old ⌀ → new ⌀ ×
depth) onto the LatheWorkholding record (new `boredDiameter`/
`boredDepth` columns, paired migrations). A record smaller than the
current bore is refused server-side — the jaw cannot shrink.

Pinned by 5 tests in tests/engines/turn.test.ts.
