# CANVAS GUIDE

A state-aware guidance system: OFF | ASSIST | TEACH, persisted per user
(GuideState). It makes the familiar CAM sequence legible — part, stock,
setup, operations, simulate, verify, deliver — mapped onto
PART → HOLD → CUT → VERIFY → DELIVER.

## Modes
- OFF — no tutoring. Gates, warnings and Next Required Action stay
  active; OFF disables teaching, never safety.
- ASSIST — compact card: the real nextActions() head with SHOW ME and
  an escalation to TEACH. No forced sequence.
- TEACH — one guided decision at a time on the floating Guide Card,
  with coach marks on real controls and blockers taking priority over
  the lesson.

## First-run profile
Six options (new-to-CNC through experienced), mapping to a default mode
only. The profile never restricts functionality and is changeable.

## Identity
Datum mark, precision blue, machinist language. No mascot, no badges,
no amber (amber belongs to manufacturing review states).

## What the Guide can and cannot do
It reads a GuideContext snapshot assembled server-side from the same
package the workspace renders, and writes GuideState only. It can
navigate, highlight and explain. It cannot clear a gate, apply a
mutation, alter provenance or unlock NC export — the engine module has
no write path to any manufacturing table (see GUIDE_SAFETY_RULES.md).
