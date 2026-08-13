# NC ANALYZER — WORKSPACE UX

The analyzer is a technical analysis instrument, not an information
document. This file describes the interaction model; the engines are
documented in LOAD_AWARE_NC_OPTIMIZER.md and RUN_IT_PAST_CANVAS.md.

## Workspace modes

After analysis, exactly one scene shows at a time:

- **BACKPLOT** (default) — load-map backplot + block-synced code
  viewer + synchronized load graph. ORIGINAL/PROPOSED plot modes.
- **PROGRAM** — operation groups (deterministic classification) and
  the immutable original, read-only.
- **LOAD** — feed proposals (RAISE and REDUCE) with individual
  acceptance, protected finish regions, generate-optimized.
- **TIME** — cycle breakdown per tool + ROI/capacity panel.
- **FINDINGS** — air cutting, excessive retract, slow linking, each
  with verdict and assumptions.
- **COMPARE** — source-level −/+ diff of accepted changes; explains
  itself when nothing is accepted yet.
- **VERIFY** — the 11 audit gates, worst-of stage summaries.

Tabs carry live counts (proposals, findings, accepted). The AUDIT and
OPT stage chips stay visible beside the tabs in every mode.

## One selection, three instruments

`sel: [fromLine, toLine]` drives everything:

- Backplot: frames the selection (bbox + margin), highlights hits
  amber, dims the rest; click a segment → selects its source line.
- Code viewer: scrolls to and highlights the block; click a line →
  selects it. Original is read-only, always.
- Load graph: one bar per motion segment in program order, height and
  color from the engagement band; selection lights the span; click a
  bar → selects its source line.

Esc clears. SHOW ME on any finding, proposal, protected region or
operation sets the selection AND switches to BACKPLOT — it changes
the scene, never just tints a row.

## Load graph anatomy

Rapids draw as thin gray ticks (they carry no engagement); the TARGET
band is a quiet green reference stripe; tool-change boundaries are
dashed verticals labelled T<n>. Top strips: green = protected finish
region (no proposal in either direction), blue = proposed raise,
amber = proposed reduction. The DEVELOPMENT LOAD ESTIMATE label is
permanent — bands come from the chipload replay model, not telemetry.

## Honesty rules carried by the UX

- The original program is immutable; the viewer says so in its header
  and offers no edit affordance.
- PROPOSED plot mode states "geometry identical by construction
  (masked diff)" — because the emitter enforces exactly that.
- COMPARE previews the F-word swap client-side and says the
  authoritative diff happens server-side at generation.
- Findings inside comped regions stay REVIEW; unsupported code stays
  refused at parse, and analysis stops at the refusal line.
