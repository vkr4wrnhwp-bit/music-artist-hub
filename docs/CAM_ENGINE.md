# CAM engine

## The rule

```
USER INTENT
  → VALIDATED PART MODEL
    → MANUFACTURING PLAN
      → DETERMINISTIC TOOLPATH ENGINE
        → MACHINE CONSTRAINT VALIDATION
          → WORKHOLDING VALIDATION
            → SIMULATION
              → POST PROCESSOR
                → NC VERIFICATION
                  → HUMAN APPROVAL
                    → EXPORT
```

An LLM may only propose an `OperationRequest` — the same structure a human fills
in by hand. Everything downstream of that boundary is arithmetic on the
parametric feature model. `src/lib/engines/cam/` contains no model calls.

This is not a stylistic preference. A toolpath is executable machine motion
against a fixture, in a machine with real travel limits, holding real material.
Sampling from a distribution is the wrong mechanism for producing it.

## What Phase 1 actually implements

| Operation | Status | Notes |
|---|---|---|
| `FACE` | Implemented | Zig-zag with roll-on/roll-off lead, multi-pass by stepdown |
| `POCKET_2D` | Implemented | Offset-inward roughing + finish wall pass; helical entry for circular |
| `DRILL` | Implemented | Single plunge, warns above 4:1 depth:diameter |
| `PECK_DRILL` | Implemented | 0.75×D pecks with full retract |
| `CONTOUR_2D` | Implemented | Cutter-comp applied in-path, tangential lead in/out |
| `CHAMFER` | Implemented | Outside profile pass |
| `ENGRAVE` | Implemented | Single-stroke box per glyph cell — see limits below |
| `SOFT_JAW_POCKET` | Implemented | Shares the pocket engine |
| `ADAPTIVE_2D` | **Interface only** | No engine. Emits no motion; labelled in the UI |
| `BORE` | **Interface only** | No engine |
| `TAP` | **Interface only** | No engine |

Placeholder operations return a `Toolpath` with `isPlaceholder: true`, zero
moves, and an explicit warning. The post writes a comment and skips them. The
readiness and pre-flight screens count them separately so an operator can see
that an operation in the plan has no motion behind it.

## Speeds and feeds

`deriveCuttingParameters()` intersects the tool's rated SFM window with the
material's, derives RPM from `SFM × 12 / (π × D)`, clamps to the lesser of tool
and machine maximum, and derives feed from `RPM × flutes × chipload`. When RPM
clamps at the machine limit the toolpath carries a warning, because that means
surface speed is below the ideal window and the operator should know.

Two refusals guard the derivation. No material window on file refuses
the operation outright — a default window is another material's numbers,
and Inconel at a carbide-in-steel default is a destroyed tool. And for a
milling cutter, a tool window that does not overlap the material's is
refused as "not rated for this material" rather than averaged into a
surface speed belonging to neither; taps and drills are exempt from the
overlap rule because their speed is not set by the material's milling
window, and where the windows do not overlap the tool's own rating wins.

Drills use chipload per revolution, not per tooth.

## Cycle time

Measured from the generated moves — Euclidean distance divided by the actual
feed of each move, plus tool-change time for each distinct tool. It is not an
estimate produced by a model, and it is the number that flows into the cost
engine, so cost and program can never disagree.

## Refusals

The engine refuses rather than approximating:

- **Tool cannot reach depth** → names the tool, the stickout, the depth, and
  suggests longer reach or a second setup.
- **Tool radius exceeds internal corner radius** → the classic un-machinable
  condition. Suggests the largest usable tool diameter or a geometry change.
- **Pocket smaller than the tool** → names the largest tool that fits.
- **Operation not linked to a feature** → refuses; there is nothing to cut.

Errors surface in the Operations panel and block the "No toolpath errors"
pre-flight item.

## Post processors

Modular, registered in `POSTS` (`src/lib/engines/cam/post.ts`):

- Haas NGC, Fanuc, PathPilot (shared Fanuc dialect, per-dialect differences)
- Siemens 840D
- Heidenhain TNC (conversational, structurally different, its own emitter)
- GRBL (no ATC, no G43 — emits a manual tool change stop)

Every post carries `certified: false` and writes
`CANVAS — DEVELOPMENT / SIMULATION POST. NOT CERTIFIED FOR PRODUCTION.` into the
program header alongside part, revision, machine and generation timestamp.

Adding a controller family means adding one `PostDefinition`. Nothing upstream
changes.

## NC verification

`verifyNc()` is a **linter, not a verifier**, and the UI says so. It catches
what is cheap to catch in text:

- coordinates outside the machine's travel envelope
- spindle speed above the machine maximum
- feed above the machine maximum
- cutting motion below Z0 with the spindle off
- missing units word, missing end-of-program

It does **not** verify collisions, stock removal, holder clearance or fixture
interference. Claiming otherwise would be the single most dangerous thing this
product could do.

## Pre-flight

Export is disabled until every required item passes. Items: machine, post,
units, stock, workholding assessment, tools, tool lengths, toolpaths generated,
no toolpath errors, critical dimensions reviewed, simulation run, operator
approval. The screen is deliberately easy to generate from and hard to walk
away from.

## Simulation

Phase 1 renders stock, part, toolpath, cutter, holder and fixture with playback,
scrub and per-element visibility. The `Simulation` record carries
`verifiedStockRemoval: false` and `collisionChecked: false` so no consumer can
mistake a visualisation for a verification.

## Known limits

- No boolean subtraction: features render as translucent removed volume rather
  than a cut solid. Honest, and adequate for reasoning about access and depth.
- Engraving uses a box per glyph cell, not single-line font vectorisation.
- Chamfering holes emits a positioning move rather than a per-hole ring.
- Arc output (`G2`/`G3`) is not emitted; arcs are linearised. Fine for
  development, wasteful of program memory on a real control.
- No rest machining, no adaptive clearing, no 3D surfacing.

Each of these is a bounded piece of work behind the `generateToolpath` seam.
