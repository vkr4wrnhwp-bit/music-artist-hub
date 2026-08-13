# REAL SHOP BETA — evidence architecture

## What exists

`BetaRunRecord` (paired sqlite/postgres migrations): one row per real
run a machinist chose to report. Fields cover the brief's capture
list — machine, material, tool/holder, workholding, predicted vs
actual cycle, predicted vs observed load notes, the CANVAS
recommendation under test, measured part results, tool wear, chatter,
scrap/failure, corrective action — plus the verdict.

## WAS CANVAS RIGHT?

The verdict is YES / PARTLY / NO, typed by the machinist, never
inferred. PARTLY and NO require at least one category:

CYCLE_ESTIMATE · TOOL_LOAD · WORKHOLDING · FEED_RECOMMENDATION ·
TOOL_SELECTION · INSPECTION · GEOMETRY · OTHER

The form lives on /knowledge beside shop knowledge and guide
friction; the panel shows the verdict tally and a per-category wrong
count so "CANVAS keeps missing cycle estimates on this machine" is
visible at a glance. Recording writes an audit row (actor HUMAN).

## What this is not

- No engine reads BetaRunRecord. It changes no calculation, no gate,
  no proposal. It is evidence for the shop and for development.
- It is not universal truth: rows are organization-scoped, like all
  shop knowledge, and are never promoted into engineering facts.
- Live telemetry stays NOT CONNECTED (see
  TELEMETRY_ARCHITECTURE.md); actual spindle load here is a typed
  observation, labelled as such.

## Not built (honest)

- Pre-filling predicted cycle/load from a specific NC analysis run
  (the partRevisionId / ncProgramId columns exist for that wiring).
- Any aggregation beyond the on-page tallies. Calibration remains a
  separate, defensible path (MACHINE_CALIBRATION.md, median of ≥5).
