# Reverse engineering

The flagship workflow, and the one with the most opportunity to mislead.

## The rule

**CANVAS never claims dimensional reconstruction from an uncalibrated
photograph.** Not with a ruler in frame, not with a 1-2-3 block, not with a
gauge block. A scale reference bounds the error; it does not eliminate the
perspective, lens and placement error underneath it.

Photographs organise, locate and communicate *which* feature is being discussed.
Measurements dimension. The interview between the two is where the product's
value is.

## Flow

```
Name the component
  → create part + revision + measurement session
    → upload the photo set (6 orthogonal + iso + details)
      → guided measurement, ordered datum-first
        → nominal reasoning per reading
          → human accepts / keeps / investigates
            → resolved value updates the parametric model
```

## Photo set

Top, bottom, front, back, left, right are requested; isometric and detail are
optional. Views are labelled at upload so guided measurement can show the right
image when it asks for a dimension, rather than making the operator hunt.

A scale reference is recorded per upload (rule, 1-2-3 block, gauge block, known
bearing, known fastener, manual dimension, or none) — stored as metadata for
the human's benefit, not consumed as a measurement input.

## Metrology profile

CANVAS designs instructions around instruments the shop actually owns
(`Shop → Metrology`). Instrument selection is by capability:

| Measuring | Preference order |
|---|---|
| Bore | bore gauge → telescoping gauge → CMM → calipers |
| Shaft | micrometer → CMM → calipers |
| Drilled hole | pin gauges → bore gauge → calipers |
| Thread | micrometer → optical comparator → calipers |
| Thickness | micrometer → height gauge → calipers |

The alternative is always shown, labelled as lower confidence with its actual
uncertainty. When the best available instrument is not good enough for the
feature, CANVAS says so rather than accepting the reading silently.

## Uncertainty

Uncertainty comes from the instrument used, not from an assumption. Repeat
readings reduce random error by √n but are floored at the instrument's
resolution. This number is not decoration — it directly sets how confidently a
reading can be matched to a standard nominal value.

## Nominal dimension reasoning

The feature that demonstrates the product's engineering intelligence, in
`src/lib/engines/nominal.ts`. It is **entirely deterministic** — table lookups
against published standards, no model inference — so a suggestion carries
`STANDARD` provenance and a real, explainable basis.

Tables: metric and inch bearing sizes, metric round bar, inch fractions to
1/64, drill index sizes, UNC/UNF/metric thread major diameters, inch and metric
dowel pins, common plate thicknesses.

The demo case:

```
Measured        1.5744"   (1–2" bore gauge, 3 readings, ±0.0002")
Nominal         1.5748"   = 40 mm
Deviation       -0.4 thou
Confidence      ~97%
Basis           40 mm is a stocked metric bearing size; the measured value
                falls within the expected seat tolerance band.

[ ACCEPT 40 MM ]   [ KEEP MEASURED VALUE ]   [ INVESTIGATE ]
```

Confidence is deviation relative to instrument uncertainty, with a small boost
when a metric candidate lands on an "ugly" inch number — 1.5748 is a far
stronger metric signal than 1.5000. A suggestion is only surfaced above 0.70
confidence *and* when the runner-up is not within 0.03, because two tied
candidates are not a clear signal of engineering intent.

**Nothing is ever applied automatically.** `measuredValue` is what the
instrument said and never changes. `resolution` records what the human decided.
Only an explicit `ACCEPTED_NOMINAL` or `KEPT_MEASURED` writes to the feature
model, and it is audited as a human action with a name on it.

## Functional feature recognition

Geometry and function are separate fields. A 1.5748" bore is geometry;
`BEARING_SEAT` is responsibility. The `FunctionalRole` vocabulary — bearing
seat, seal surface, shaft journal, locating shoulder, press fit, slip fit,
thread, mounting hole, dowel hole, datum face, inspection surface, fluid
passage, cosmetic, structural rib, fixture pad — is what stops CAM and the
process advisor relaxing a dimension that carries a role.

## Not implemented in Phase 1

- Vision analysis of photographs. `analyzePartImage()` returns observations
  empty and states plainly that no vision model is configured, rather than
  describing geometry it has not analysed.
- Scan import (STL/point cloud) and mesh-to-parametric fitting.
- Automatic feature detection from images.
- Full measurement dependency-graph solving. The `dependsOn` field and the
  ordering exist; the solver that computes the *minimum* set of measurements to
  mathematically constrain a model does not.
