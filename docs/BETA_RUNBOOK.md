# CONTROLLED BETA — RUNBOOK

What a shop does in week one, what CANVAS records, and what it must
not be trusted for yet. The full loop below was dress-rehearsed end
to end in the browser on 2026-08-13; measured results at the bottom.

## Week zero — before the first program

This section did not exist in the original runbook because none of it was
possible: the shop records were read-only and every "Add" button was a
dead link. They are all editable now, and the loop below assumes this is
done. Budget an hour or two, once.

0. **Smoke the install.** `npm run build && npm run db:seed && npm run
   smoke` — boots the built app, requests every workspace route with a
   real session, and asserts the assemblies assemble (seconds, no
   browser). Then `npm run test:e2e` for the browser walk of sign-in and
   gate posture. A beta morning that starts with a broken page is a beta
   morning lost.

1. **Tool crib.** Every cutter you will use, with real geometry. Corner
   radius decides whether an internal corner is machinable at all;
   stickout decides whether a depth is reachable; chipload and surface
   speed are what the feed calculation reads. A tool that is not in the
   crib does not exist to the planner.
2. **Machines.** Travels, table, spindle and changer limits. A machine
   recorded without travels cannot fail the envelope gate, which means
   it cannot pass it honestly either.
3. **Instruments.** Every gauge, with the uncertainty it actually
   achieves in your conditions — not the catalogue figure and not the
   resolution. This is the denominator in every inspection-capability
   verdict you will see. A caliper entered at ±0.0002 will be called
   capable of a bore it cannot verify.
4. **Workholding.** Jaw width, height, opening, fixture height. Clamp
   force only if you have measured it or read it off a torque chart for
   the torque you actually use — left blank, the holding margin comes
   back INDETERMINATE and names it, which is the correct answer for a
   vise nobody has measured.
5. **Map each machine's carousel.** Machines → Carousel → load each tool
   into its pocket. Until this is done, the TOOLING LOADED gate reads
   NOT_ATTEMPTED — CANVAS will say it cannot tell whether the tooling is
   in the machine, and will not claim it is missing.

Everything above is evidence a person enters. Nothing in it is inferred,
and blanks stay blank rather than becoming plausible defaults.

## The daily loop (per program you run)

1. **Run it past CANVAS first.** Part → NC ANALYZER → upload the
   program you already run today. Read the VERIFY tab: the audit is
   the worst of 11 gates, never a percentage.
2. **Read the findings, not just the savings.** Air cutting and
   retract findings carry verdicts (CONFIDENT is replay-proven,
   REVIEW is a heuristic). SHOW ME frames every one in the scene.
3. **Accept proposals one at a time.** There is deliberately no
   accept-all. Protected finish regions never carry a proposal.
4. **Generate the derived program.** It stores only if the masked
   geometry diff and round-trip parse pass. The original upload is
   immutable — CANVAS cannot alter what you gave it.
5. **Export only through the gate.** NC output stays NOT READY until
   every pre-flight item resolves; the export mint re-runs the gates
   server-side. The header on every exported file says NOT FOR
   PRODUCTION USE — a human owns the decision to run it.
6. **After the run, report it.** The "Ran this program? Report the
   run" link on NC output opens WAS CANVAS RIGHT? with program,
   machine, material and predicted cycle pre-filled. Type the actual
   cycle and your verdict. PARTLY/NO requires naming what was wrong.
7. **Record the cycle on the machine card** (Machines → Recorded
   cycles). Calibration is claimed only from 5+ cycles; until then
   the page says "one sample is an anecdote, not a calibration."
8. **Mark reference cuts** when a region runs clean — machine, tool,
   material, DOC/WOC/feed/RPM. Scoped shop evidence, never
   generalized.

## What the beta measures

- Cycle estimate accuracy (calibration records + beta runs)
- Which recommendation categories are wrong most (WAS CANVAS RIGHT?
  category tallies on /knowledge)
- Guide friction (which steps people back out of)
- Disagreements (WHY/CHANGE/I DISAGREE — reviewed into shop
  knowledge or declined with a reason)

## Hard limits to state to every beta operator

- Load bands are a chipload model, not telemetry. DEVELOPMENT LOAD
  ESTIMATE means exactly that.
- Times are distance-over-feed with recorded-machine adjustments
  only. Expect variance; that variance is the data we want.
- The posts are development posts. Nothing CANVAS exports is
  certified for production; prove-out procedure is unchanged.
- Holding margin is DEVELOPMENT ANALYSIS — not validated against
  physical testing.
- No beta record changes any calculation or clears any gate.
- TOOLING LOADED tells you whether the cutters are in the changer
  according to what somebody recorded — not according to the machine.
  There is no connection to the control. If the map is stale, the gate
  is confidently wrong, and the fix is to keep the map honest when tools
  are swapped.

## What this runbook cannot do on its own

Everything above has been dress-rehearsed in the browser. None of it has
been run against metal, and that is the entire point of the beta, so it
is worth being blunt about the division of labour.

CANVAS can be driven through the whole loop by anybody. What it cannot
do is supply the two things the beta exists to collect:

- **A real machinist's judgement.** Whether a recommendation was right,
  whether a load band matched what the spindle actually did, whether a
  workholding verdict matched what the part actually did in the vise.
  WAS CANVAS RIGHT? is the collection point and it is worthless without
  somebody who was standing at the machine.
- **Actual cycle times off a real control.** Calibration is claimed from
  five samples and refuses to claim anything below that. Those five have
  to come from five real runs.

So the next step is not a build task. It is: pick one shop, one machine,
one part they already run, and work the loop above for a week. Until
that happens the honest status of the beta is *rehearsed, not run*, and
this document should keep saying so.

## Dress rehearsal results (2026-08-13, demo org)

1. Audit: 11 gates listed, stage AUDIT: REVIEW (comped region —
   correct, the demo contains G41).
2. Findings: 4 air-cutting findings visible with verdicts.
3. Proposals: 3 under BALANCED; first accepted individually.
4. Derived program stored: 1 applied, 2.22 → 2.19 min, lint clean.
5. NC output: NOT READY (inspection unresolved) — export correctly
   withheld; report-run link present.
6. Report prefill carried predicted 5.93 min + Haas VF-2.
7. Verdict recorded; tally live on /knowledge.
8. Calibration honesty correct at 3 samples: "claimed from 5. One
   sample is an anecdote, not a calibration."
9. Reference cut recorded (6061-T6, DOC .375, WOC .075, F68, S9200).
10. Turning workspace loads with runway and readiness stated.
