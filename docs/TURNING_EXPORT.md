# Turning NC export mint — BUILT

`src/app/(app)/lathe/[id]/nc/actions.ts` (mintTurnExport /
recordTurnExport) + the shared NcExportPanel (now parameterized over
mint/record actions), embedded under the NC preview on the turning
workspace.

## The law, same as the mill

- The ONLY server surface emitting turning NC bytes is the mint, and it
  re-runs the full turning readiness (worst-gate) via
  `buildTurnPackage` — the same function the workspace renders from, so
  the button and the gate cannot drift ("the rendered button is not the
  gate").
- Refusals: training parts; any blocking (FAIL/NOT_ATTEMPTED) gate;
  NOT_READY_TO_RUN overall; any post refusal (unclamped G96). REVIEW
  gates do not block export — human approval is its own required gate.
- Single-use token, 5-minute TTL, atomic consume; record re-checks the
  turning gate and audits "authorisation lapsed" when it no longer
  holds. HUMAN row for the operator's write, SYSTEM row for the
  read-back digest compare — actor always typed.
- The emitted file KEEPS the development post's NOT FOR PRODUCTION USE
  header: an authorization is permission to take bytes out of CANVAS,
  not a certification of the post processor. The panel's NOT CERTIFIED
  chip stands.

## Refactor

`src/lib/manufacturing/turn/package.ts` — buildTurnPackage assembles
model + toolpaths + hold analyses + worst-gate readiness + dev post in
one place, used by the mint (page refactor to consume it is a pending
cleanup; the mint is the authority either way). NcExportPanel accepts
`mint`/`record` server-action props, defaulting to the mill's.
