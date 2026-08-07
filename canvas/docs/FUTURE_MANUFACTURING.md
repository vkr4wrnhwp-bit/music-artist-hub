# Future manufacturing

CANVAS treats CNC as one process among many from day one. The process
vocabulary in `src/lib/engines/process-advisor.ts` is not a CNC system with
alternatives bolted on — machining is one entry in a list.

## Process vocabulary

Subtractive: 3-axis billet, turning, wire EDM, sinker EDM.
Sheet and forming: laser, waterjet, plasma, stamping, forming, hydroforming.
Near-net: casting, forging, extrusion.
Polymer: injection molding, polymer additive.
Metal additive: powder-bed fusion, binder jetting, directed energy deposition.
Hybrid: additive + CNC finishing.
Non-manufacturing: purchase off the shelf — often the correct answer, and the
one a CAM vendor will never suggest.

## What the advisor considers

Function, material, load, fatigue, geometry, tolerance, surface finish,
quantity, tooling cost, lead time, safety criticality, certification.

It is rule-based and volume-driven, and it is **gated on responsibility**.
Casting, forging and additive return `INSUFFICIENT_DATA` until the Part
Responsibility interview is complete. Substituting a wrought billet part for a
casting without knowing the loading case is the kind of advice that gets someone
hurt, and the cost saving is exactly what makes it tempting.

CANVAS is permitted to say *"you should not machine this"* — and does, at
volume, for flat through-profiles, and where a standard part likely exists.

## Volume crossovers

- **1–50** — billet machining. No tooling amortisation can beat it.
- **~500/yr** — near-net blank plus finish machining becomes attractive.
- **~2,000/yr** — casting plus finish machining should be quoted.
- **~20,000/yr** — dedicated tooling and a production cell change everything.

These are starting points for investigation, not conclusions. CANVAS does not
claim exact economics without underlying cost data and says so.

## Additive, honestly

Metal powder-bed parts still need datum creation, stress relief, support
removal and CNC finishing on every functional surface. The advisor says this
rather than presenting additive as a finished part. For safety-critical
components it blocks entirely: qualified powder, process controls and NDT are
not things CANVAS models.

The hybrid chain CANVAS is designed to eventually treat as one workflow:

```
design → DfAM → build orientation → support strategy → material selection
  → print → heat treat → HIP → support removal → datum creation
  → CNC finishing → inspection
```

## Design optimisation (placeholders only)

Weight reduction, machining simplification, tool-access improvement, setup
reduction, topology optimisation, load-path optimisation.

**No FEA is connected.** CANVAS does not promise structural simulation it
cannot perform, and Broken Part Mode's "improve it" path is explicitly gated on
this. Interfaces exist for external FEA, topology optimisation, thermal, flow
and fatigue solvers.

## Future workflow shells

- **Broken Part Mode** — "I broke this." Exact replacement is reverse
  engineering. *Improving* it requires structural analysis that is not
  connected, so the path is gated rather than faked.
- **Obsolete Part Mode** — "I can't buy this anymore." Reverse engineering into
  a revision-controlled digital spare-parts library with supplier matching.
- **Company research** — analysing a company's public information for product
  families and make/buy opportunities. Deliberately not wired up: uncontrolled
  scraping is not something to add quietly.

## The north star

```
"I need 250 of these."
```

Reason about what it is, what it does, how critical it is, what material it
needs, how it should be manufactured, which process is cheapest at that volume,
how it should be held, which tools, which machine, how long, how to inspect it,
what it costs, whether to make or buy, whether someone in the network already
makes something similar, and what historical jobs teach — then coordinate
execution.

Every decision in Phase 1 is made so that nothing above is foreclosed.
