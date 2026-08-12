# Lathe NC parser — BUILT (review-only)

`src/lib/manufacturing/turn/nc-parse.ts` + `/lathe/[id]/nc-review` +
`/api/lathe/[id]/nc-analyze`. Analysis only: nothing is rewritten,
exported or certified.

## Understood subset

- Modal motion G0/G1 (G2/G3 flattened to chords with a stated warning)
- G18, G20/G21, G90/G91, G98/G99 (feed per min / per rev)
- G96 CSS / G97 fixed RPM, G50 spindle clamp (bare G50 = preset, warned)
- G32 single-point threading (feed = pitch, never retimed)
- T station calls, S/F words, M3/M4/M5
- X words are diameters — the machinist convention, everywhere

## Refused, never assumed safe (UNSUPPORTED_CONTEXT, by line)

G70–G76 canned/threading cycles, G73, G8x drilling cycles, G41/G42 tool
nose radius comp, G92, G10, M97/M98 subprograms, macros (`#`, GOTO, IF,
WHILE). Each refusal names the line and the reason.

## Analysis (`analyzeLatheNc`)

ESTIMATED cycle with assumptions stated: rapids at an assumed 800 IPM,
CSS segments timed at mean-diameter RPM capped by the G50 clamp (and the
chuck limit when the shop recorded one). Cutting moves with no spindle
context are counted as **untimed** — never guessed.

Findings:

- `MISSING_MAX_RPM_CLAMP` (CONFIDENT) — G96 with no G50 clamp
- `RPM_LIMIT_REVIEW` — G50 above the chuck's rated max RPM
- `CSS_NOT_USED` (REVIEW) — fixed RPM across a >2.5× diameter range
- `UNKNOWN_SPINDLE_CONTEXT` (INSUFFICIENT_DATA) — untimed segments
- `UNSUPPORTED_CONTEXT` — one per refused block

## Self-test

The parser reads the development post's (`turn/post.ts`) own output with
zero refusals, and its cycle estimate agrees with the toolpath engine's —
two engines from opposite directions, pinned in `tests/engines/turn.test.ts`.

Chuck RPM limit comes from the part's own `LatheWorkholding` record,
organisation always from the session.
