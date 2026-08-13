# CONTROLLED BETA — RUNBOOK

What a shop does in week one, what CANVAS records, and what it must
not be trusted for yet. The full loop below was dress-rehearsed end
to end in the browser on 2026-08-13; measured results at the bottom.

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
