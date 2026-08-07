# Manufacturing safety

This is the document the rest of CANVAS is written to obey. It is not a legal
disclaimer; it is a set of engineering constraints on the software.

## The core problem

A language model produces fluent, plausible, confident output. In most software
that is a feature. In manufacturing it is the failure mode: a plausible wall
thickness, a plausible feed rate, or a plausible material substitution reads
exactly like a correct one, and someone will cut metal from it.

So CANVAS is built to make the difference between *knowledge* and *inference*
visible at every point where a human might act.

## Provenance

Every significant value in the system is wrapped (`src/lib/provenance.ts`):

```ts
interface Provenanced<T> {
  value: T | null
  source: "USER" | "MEASURED" | "MANUFACTURER" | "CALCULATED"
        | "SIMULATION" | "AI_INFERENCE" | "STANDARD" | "DEFAULT"
  confidence: "UNKNOWN" | "LOW" | "MEDIUM" | "HIGH" | "VERIFIED"
  confirmedByUser: boolean
}
```

`isEngineeringGrade()` is the gate. **`AI_INFERENCE` never satisfies it at any
score** unless a human has explicitly confirmed the value. A model that is 99%
confident is still a model.

The UI renders this as a provenance badge beside every value, and the colour
vocabulary is consistent: an AI suggestion is amber, never green.

## Hard rules

1. **An LLM never emits machine motion.** Not G-code, not a feed rate that
   reaches the post, not a coordinate. `src/lib/engines/cam/` contains no model
   calls of any kind, by construction.
2. **The AI layer never invents shop resources.** If a machine, tool, vise or
   material is not recorded, the planner treats it as non-existent. It does not
   assume a "typical" 3-axis mill.
3. **Responsibility is asked, never inferred.** Load bearing, safety critical
   and failure consequence are only ever set by a human through the
   Part Responsibility interview. The intake explicitly writes them back as
   unknown even when the description hints at them.
4. **No process change without responsibility.** The manufacturing method
   advisor returns `INSUFFICIENT_DATA` for casting, forging and additive until
   the responsibility profile is complete. Swapping a fatigue-loaded wrought
   part for a casting is a materials decision, not a cost decision.
5. **Suggestions are proposals.** Model-suggested features land in
   `AIRecommendation` with status `PROPOSED`. They become geometry only when a
   named human accepts them, recorded as `ACCEPT_SUGGESTION` by that person.
6. **Nominal reasoning never rewrites a measurement.** See below.
7. **Nothing exports without a human.** The NC pre-flight gate disables export
   until every required item passes, and operator approval is itself a gate.

## Readiness is not a percentage

`evaluateReadiness()` returns a gate list, and the aggregate is the *worst*
gate, never an average. A percentage invites an operator to feel 87% confident
about a part with no inspection plan at all. Gates are `PASS`, `REVIEW`,
`MISSING`, `FAIL` or `NOT_ATTEMPTED`, and blocking gates block.

## Critical applications

When `loadBearing`, `safetyCritical`, or a `HIGH`/`CRITICAL` failure consequence
is set, CANVAS:

- raises the required input set (loading case, environment, surface finish,
  material condition, inspection requirements all become mandatory),
- shows a persistent critical-application banner,
- adds a non-removable "Critical application review" gate,
- states plainly that CANVAS assists with manufacturing planning and **does not
  certify component safety**.

## Uncertainty is carried, not assumed

Measurement uncertainty comes from the instrument actually used, taken from the
shop's metrology profile. Repeated readings reduce random error but never below
the instrument's own resolution. That uncertainty then propagates into nominal
reasoning confidence — the same reading from calipers and from a bore gauge
produce genuinely different conclusions, and CANVAS says so.

## The workholding model is labelled as a model

`estimateCuttingForce()` is a simplified specific-energy estimate. It is
adequate for ranking setups against each other and is **not** a substitute for
engineering judgement. It returns `null` rather than a partial guess when any
input is missing, because a partially-guessed force looks authoritative. Risk is
reported as `SAFE | LIKELY_SAFE | REVIEW | HIGH_RISK | UNKNOWN` with the factors
and the suggested actions attached — never a bare number.

## Audit

`AuditLog` is append-only and records who changed what, when, from what to what,
and — explicitly, never inferred — whether the actor was `HUMAN`, `AI` or
`SYSTEM`. The whole value of that field is that it is trustworthy, so every
caller sets it deliberately.

## Labelling

Anything not fully implemented says so in the interface: `DEVELOPMENT`,
`SIMULATION ONLY`, `NOT IMPLEMENTED`, `SHELL`. There are no buttons that appear
to perform collision validation and merely play an animation. Where a page has
nothing real to show, it says why rather than filling the space.
