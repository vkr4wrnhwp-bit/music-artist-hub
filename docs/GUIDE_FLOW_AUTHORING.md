# Authoring Guide flows

Flows live in `src/lib/guide/flows.ts` as typed `GuideFlowDef` objects —
one authored place, no per-page hardcoding. A step:

- `done(ctx)` — completion is a property of PROJECT STATE, never a
  click. A user who did the work manually reads as done.
- `applies(ctx)` — branching. A step that does not apply in the current
  context does not exist in it (e.g. the proposals step only exists
  while proposals are pending; deliver never applies to training parts).
- `blockedBy(ctx)` — a real gate that takes priority over the lesson.
  Returning one renders the blocker card; only real evidence clears it.
- `href(ctx)` + `uiTarget` — where the work happens and which
  `data-guide-target` the coach mark outlines there.
- `why` / `camHint` / `recommended` — the teaching content. CAM hints
  render only when the terminology preference is on.

Active flows: MAKE_A_PART. Not authored because the capability does not
exist (listed in DEVELOPMENT_FLOWS, never faked): DRAW_FROM_SCRATCH
(no sketching), CREATE_TURN_SETUP (no turning), REVERSE_ENGINEER_GUIDE
(sessions exist; the guided flow is future work).
