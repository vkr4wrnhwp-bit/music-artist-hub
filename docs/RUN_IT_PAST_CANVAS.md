# Run It Past CANVAS — status against the master brief

The load-aware NC audit + optimizer. Much of the brief predates this
document as Phases 4A–4F; this records what EXISTS, what was added, and
what honestly remains.

## Exists and verified (mill, 3-axis, Fanuc/Haas-style + generic ISO)

- **Deterministic parser + modal interpreter** (`src/lib/nc/parse.ts`):
  G0/1/2/3 (arcs I/J and R, chord-tessellated), G17 (off-plane arcs
  refused), G20/21, G90/91, G54–G59 (multi-offset downgrades spatial
  findings), G80/81/83 expanded, G84/G74 parsed and NEVER retimed, G4,
  G40/41/42 (comped regions marked, never optimized), G43/49/94/98/99,
  F/S/T/M6, M3/4/5/8/9. Refusals (macros, `#`-vars, IF/GOTO/WHILE,
  M98/M99 subprograms, unresolvable arcs) stop interpretation at the
  named line. `unitsExplicit` exposed; assumed inches is a REVIEW gate.
- **Cycle-time engine** (`analyze.ts` + `time.ts`): cutting / rapid /
  dwell split per tool; trapezoidal acceleration model when the
  machine's axisAccel is recorded, distance-over-feed with the
  assumption stated when not. Findings: AIR_CUTTING (replay-proven
  against bound stock via the height field), EXCESSIVE_RETRACT,
  SLOW_LINKING_MOVE, UNKNOWN_CONTEXT.
- **Engagement + load** (`load.ts`): height-field stock replay, chipload
  banding (AIR/LIGHT/TARGET/HIGH/REVIEW), MRR and spindle-power where
  material specific energy exists, DEVELOPMENT ANALYSIS labelled.
  Feed-only proposals with presets CONSERVATIVE/BALANCED/AGGRESSIVE/
  LIGHTS_OUT (lights-out is the most conservative), per-proposal
  assumptions + required evidence, tapping and comped regions excluded
  by construction.
- **Derived emission** (`emit.ts`): feed words only; masked line diff
  must be byte-clean (the geometry invariant is a check, not a
  promise); round-trip re-parse must match segment for segment.
- **Gated lifecycle**: OPTIMIZED rows carry the full audit JSON (both
  digests, applied/unapplied, before/after minutes, caveats), HUMAN
  audit rows per accepted proposal + SYSTEM row for the mechanical
  diff, and export goes through the same single-use mint as every
  other program.

## Added in this pass

- **Immutable original storage**: analyzing stores the upload as an
  NCProgram row, origin UPLOADED, with sourceFilename, byteLength and
  server-computed sha256 (sourceDigest) — deduplicated by digest, and
  no code path updates an UPLOADED row. The optimize endpoint now
  derives from the STORED original (id + digest named by the client,
  digest verified server-side) — re-sent bytes are never trusted — and
  the OPTIMIZED row records sourceProgramId lineage.
- **Audit gate group** (`audit-gates.ts`): NC FILE INTEGRITY, PARSER
  FIDELITY, UNITS, WORK OFFSET, TOOL MAPPING, MACHINE PROFILE, STOCK /
  PART ALIGNMENT, MATERIAL, ENGAGEMENT MODEL, OPTIMIZATION SCOPE,
  DERIVED NC INTEGRITY. Stage summaries (AUDIT / OPTIMIZATION / EXPORT
  PREREQS) are each the worst required gate — no percentages. Stock
  alignment is REVIEW by construction: CANVAS cannot see the vise.
  Rendered at the top of the analyzer with per-gate evidence text.

## Honest gaps (recorded, not faked)

- Corner-engagement-spike detection and load smoothing (Tier 3) — the
  band model flags HIGH/REVIEW segments but no automatic feed-reduction
  proposal is generated for spikes.
- Finish-pass protection is by exclusion only (comped/tapping); there
  is no feature-role-aware protection of finishing passes yet.
- Reference cuts, machine calibration records, and telemetry
  (MTConnect/OPC UA) — architecture described in the brief, not built.
- Operation classification, block-synchronized code viewer, side-by-
  side original-vs-proposed backplot, Show Me scene changes, ROI panel,
  seeded demo program, and a Run-It-Past guide flow — not built.
- 3D backplot is top-view 2D; drilling cycles beyond G81/83/84 are
  refused, not expanded.

Tests: parser/time/load suites plus 7 audit-gate tests
(tests/engines/audit-gates.test.ts). The worst-gate law, the stored-
original requirement, unmapped-tool refusal, assumed-units downgrade,
and scope exclusions are all pinned.


## Added since the status above

- **Operation classification** (`classify.ts`): deterministic motion
  evidence only — DRILL (≥70% vertical across 2+ positions), TAP
  (drill + tapping flag), FACE (one Z, broad XY), POCKET (descending Z
  levels), LINKING, UNKNOWN ("unlabeled is honest; mislabeled teaches
  the wrong thing"). Every group is method DETERMINISTIC; AI labels,
  when added, arrive separately as AI_INFERRED.
- **Seeded demo program** (`public/demo/O2507-DEMO.nc` + Load demo
  button): deliberate mixed results against the Bearing Support —
  facing with an air pass and a Z2.0 retract, rubbing passes (RAISE),
  an engagement-spike slot (REDUCE F60→30), a rubbing pass over the
  bearing bore (PROTECTED), a G41 region (review-only, never
  optimized), four G81 holes (classified DRILL). During fixture
  authoring the protection engine caught the spike slot passing within
  0.125" of a tapped mounting hole and correctly suppressed the REDUCE
  — the fixture was moved rather than the rule weakened.
- **Plunge exclusion in spike analysis**: vertical entries legitimately
  remove material fast and are not XY engagement spikes; they are now
  excluded from both the median and the spike set, so wall-cut corners
  are compared against wall cuts.
