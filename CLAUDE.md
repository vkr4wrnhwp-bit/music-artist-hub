@AGENTS.md

# CANVAS — LOCKED PRODUCT PRINCIPLES

CANVAS is an AI Manufacturing Operating System, initially for 3-axis CNC job
shops. It is not an AI G-code toy, a CAD clone, a CAM clone, or a chatbot
parked beside manufacturing software.

Its purpose is to answer: **I need this made. Figure everything else out.**

1. CAN I MAKE IT?
2. SHOULD I MAKE IT?
3. WHO SHOULD MAKE IT?
4. HOW SHOULD IT BE MADE?
5. HOW DO WE KNOW IT IS READY TO RUN?

The principles below are locked. Do not remove or weaken them without an
explicit instruction to do so.

## 1. Readiness is gate-based

Manufacturing readiness is not a percentage, average, score, confidence meter
or progress bar. It is a list of gates, and the aggregate state is **the worst
unresolved required gate**. Never average a FAIL away. A part with nine passing
gates and one failure is not 90% ready; it is not ready.

Implemented in `src/lib/engines/readiness.ts`. The aggregation function is
worst-case by construction — if you find yourself adding arithmetic to it, stop.

## 2. Gates are satisfied by evidence, not clicks

A human clicking "confirm" must not validate an engineering condition that
requires evidence. A ±0.0005" bore cannot pass inspection capability because
somebody acknowledged a warning; the underlying evidence has to change.

`inspection-capability.ts` is the canonical example: the verdict is a property
of the instruments the shop owns, and `clearableByConfirmation` is typed as
`false` rather than as a boolean, so no caller can set it.

## 3. AI inference never satisfies a required gate

The model may suggest, identify patterns, recommend, question, compare and
explain. It may not silently certify. An AI inference stays inferred until
supported by acceptable evidence.

`provenance.ts` → `isEngineeringGrade()` returns false for `AI_INFERENCE`
unless a human has explicitly confirmed it. This is the one place that rule
lives; do not reimplement it elsewhere.

## 4. Provenance is first-class data

Significant values carry `{value, source, confidence, confirmedByUser}` and,
where relevant, timestamp, instrument, method and uncertainty. Sources are
`USER | MEASURED | MANUFACTURER | CALCULATED | SIMULATION | AI_INFERENCE |
STANDARD | DEFAULT`.

## 5. Do not fake capabilities

Unimplemented systems stay visibly labelled: SHELL, DEVELOPMENT, SIMULATION
ONLY, BETA, NOT CONNECTED. Never fill an unimplemented feature with
plausible-looking fake results. A button that appears to optimise and does not
is a lie the operator would act on.

## 6. NC export stays gated

Executable NC must not be available while required gates fail. The architecture
is INTENT → VALIDATED GEOMETRY → PROCESS PLAN → DETERMINISTIC TOOLPATH →
WORKHOLDING ANALYSIS → MACHINE VALIDATION → SIMULATION → POST → NC
VERIFICATION → HUMAN APPROVAL → EXPORT.

**An LLM is never the sole generator or validator of executable machine
motion.** The CAM engine (`engines/cam/`) contains no model calls and must not
acquire any.

## 7. CANVAS must be willing to disagree

It is not a people-pleasing assistant. It should be able to say "I would not run
this setup yet", "I would not machine this from billet at that quantity", and
"your measurement method cannot verify the requested tolerance".

## 8. Do not assume CNC is the answer

Process recommendation eventually spans machining, turning, casting, forging,
forming, stamping, fabrication, laser, waterjet, EDM, moulding, additive,
off-the-shelf components and outsourcing.

## 9. Function before process

Understand what the part does — load bearing, load types, fatigue, pressure,
temperature, environment, failure consequence, service life, regulatory
requirements, quantity — before recommending substantial manufacturing changes.
Never recommend a cheaper process merely because the geometry looks compatible.

## 10. The experienced machinist test

For every feature: would an experienced machinist learn something useful from
CANVAS before pressing Cycle Start? If not, reconsider the feature.

## 11. Human override records evidence, and clears nothing

Every significant recommendation supports WHY / CHANGE / I DISAGREE.
Disagreement is captured as shop knowledge — reasoning, whether a comparable
job has been run, which job. It does **not** clear a safety gate.

Shop knowledge is not universal knowledge. It is scoped to the shop, machine,
tool and material it was observed on, and is never promoted into a published
engineering fact. See `src/lib/disagreement.ts`.

## 12. Never invent engineering values

Do not invent a safe load, a tolerance, a material substitution, a process or a
force. Deterministic engines calculate; where an input is missing they return
null and say what is missing rather than substituting a default. A
partially-guessed number is worse than no number, because it looks
authoritative.

Calculated values that are consequential must be openable — method, inputs,
assumptions, uncertainty. See `components/show-calculation.tsx`.

Models not validated against physical testing are classified DEVELOPMENT
ANALYSIS in their output and in the UI. `holding-margin.ts` carries a
non-optional `developmentAnalysis: true` field for exactly this reason.

## 13. Security and tenancy

- Never expose AI API keys client-side.
- Organisation id always comes from the session, never from a request
  parameter. One shop's proprietary geometry must never be reachable from
  another shop's session.
- Network sharing defaults to PRIVATE. Broader participation is opt-in, company
  identity is never exposed without consent, and anonymous network matching
  carries no identifiable proprietary information.
- Audit entries type the actor explicitly as HUMAN | AI | SYSTEM. It is never
  inferred.

## Communication style

Write like an experienced machinist, manufacturing engineer or metrology
technician. Not a marketing chatbot.

Prefer `WORKHOLDING — REVIEW` over "your setup confidence is 72%". Prefer "I
need two measurements before I can resolve this bearing interface" over "your
part is 84% complete". No emoji in manufacturing UI.

## Visual language

**Studio White**, approved 2026-09-04. Warm white workspace, graphite type,
restrained precision blue. The instrument is paper; the part is the brightest
thing on it and the main interface. Blue means active state, selected geometry,
datum, measurement, toolpath, coordinate origin — used sparingly.

Four steps of one warm neutral, in this order by luminance: chrome, page,
panel, card. `contrast.test.ts` enforces both the ordering and the WCAG floors
by reading the tokens straight out of `globals.css` — change a hex and CI
measures it.

No grid background. No sketch-style placeholder UI: where a part has geometry,
render it. Aerospace metrology and precision instrumentation, not generic SaaS:
no oversized rounded cards, no gradients, no gaming aesthetics, no AI robot
icons. Clean separators and considered spacing do the work that borders and
shadows do elsewhere.

This section is style, not one of the locked principles above — but the flip
away from the previous dark-canvas direction was an explicit instruction, so do
not revert it on the strength of an older screenshot.
