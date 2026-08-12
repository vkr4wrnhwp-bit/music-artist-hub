# Guide safety rules

1. The engine (`src/lib/guide/engine.ts`) is pure: it can write nothing.
   Back, skip, advance and completion are session arithmetic. Pinned by
   test: the GuideContext is byte-identical after every guide operation.
2. Step completion reads project state. Guide completion therefore
   cannot satisfy readiness — a finished flow leaves blocking gates
   blocking (pinned by test).
3. Blockers take priority over lessons (`blockedBy`), render as gates,
   and survive BACK ONE STEP (pinned by test).
4. Skipping defers a lesson and satisfies nothing (pinned by test).
5. The only table the Guide's API can write is GuideState. Resetting
   guide progress resets tutoring, never manufacturing data.
6. Training parts cannot export production NC — enforced at the mint,
   which is a server action, not at the button.
7. OFF disables tutoring, not safety: gates, warnings and Next Required
   Action are outside the Guide entirely.
8. Analytics (not yet implemented) must never carry part names,
   dimensions, NC text or geometry — flow/step/mode/duration only.
