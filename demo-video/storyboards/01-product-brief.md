# Product brief — TRACE demo film

Written from the running application, not from marketing copy. Every claim
below was checked against a screen in `public/recordings/`.

## What the product is

TRACE is a telemetry and tuning platform for motocross race teams. A rider
reports how the bike felt; TRACE ties that report to a specific corner and lap,
correlates it against the session's measured channels, proposes ranked causes
with a computed confidence, and keeps the decision — including the decision to
reject a change — as a permanent, attributable record.

## Who the film is for

The **tuner** — the person who decides whether a map change ships. They are the
persona the capture rig signs in as (`u-tuner`, Jules Ortiz). Secondary
audience: the team owner asking why this is worth buying.

## The single question the film answers

> A rider says it hit too hard on the exit. Then what?

Everything in the film is an answer to that question, in order.

## What makes it different (and defensible)

1. **Feel is anchored to data.** The rider's marker carries a lap, a time
   offset, a corner and the channel values at that instant.
2. **The engineer shows its work.** Ranked causes, measured evidence, explicit
   alternatives, and a confidence number that is *capped* when a channel is
   degraded. It never reports certainty it does not have.
3. **It recommends; it never decides.** Approval is role-gated.
4. **There is no ECU write path.** TRACE emits a change sheet a person performs
   in the manufacturer's own software. This is a designed boundary, and the
   application says so on the screen in red.
5. **The comparison is honest.** A/B compare reports what changed, what
   happened, and what probably caused it — including uncontrolled variables it
   could not hold constant.

## The honest climax

The seeded A/B in the product is not a success story, and the film does not
pretend otherwise. Revision R07 produced:

| Metric | Change |
|---|---|
| Best lap | **+1.79 s** (99.18 → 100.97) |
| Mean lap | **+2.59 s** (100.04 → 102.63) |
| Lap consistency (σ) | **+0.28 s** (worse) |
| Peak slip (p95) | 0 % |
| Mean coolant | +0.1 °C |
| **Rider confidence** | **+3** (better) |

The rider liked the change. The change was slower. TRACE also flags that map
slot moved 3 → 4 as an **uncontrolled** variable.

This is the most persuasive thing the product does, so it is the climax. A film
that invented a win here would be both dishonest and less compelling.

## Non-negotiable disclosures

Carried on the closing card of every deliverable:

> Phase 1 runs on simulated telemetry, labeled on every screen. No ECU write
> path exists in this build.

The captures themselves also carry the application's own `SIMULATED
DEMONSTRATION DATA` banner and per-session `SIMULATED` pills. These were left
in frame deliberately — they are the product being honest, and cropping them
out would misrepresent it.

## What the film does not claim

- No performance claim ("makes you faster"). The seeded evidence does not
  support one.
- No claim of two-person approval in the change-sheet scene: the seeded record
  shows the same tuner as author and approver, so the copy describes the change
  sheet instead.
- No integration is shown as live. The Vortex boundary is shown as disabled,
  which is what the build does.
