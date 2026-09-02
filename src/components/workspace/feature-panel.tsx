"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { Feature, FunctionalRole, Stock } from "@/lib/domain/features";
import { featureSummary, fmt, fmtTol } from "@/lib/domain/features";
import { LimitsDisclosure, StatusChip, type Tone } from "@/components/ui";
import { SectionSketch } from "./section-sketch";
import { InstrumentGlyph, hasInstrumentGlyph } from "./instrument-glyph";
import { MeasurementTechnique } from "@/components/measurement-technique";
import type { DatumInfo, FeatureDetail } from "./panel-data";
import {
  compare,
  latestMeasurement,
  primaryDimension,
  RESOLUTION_DETAIL,
  RESOLUTION_LABEL,
  RESOLUTION_TONE,
} from "./dimension";

/**
 * THE FEATURE PANEL
 *
 * A metrology instrument, read top to bottom: what the feature is, what is
 * known about its size, what it looks like in section, what it is measured
 * from, what can measure it, how, and what you can do next.
 *
 * The hierarchy is deliberate. The measurement block is the loudest thing on
 * the panel because it is the thing an inspector is here for; everything below
 * it is the evidence that makes that number mean anything.
 *
 * WHAT THIS PANEL WILL NOT SHOW
 *   - A PASS / FAIL chip derived from arithmetic. `InspectionResult.pass` has
 *     no write path in CANVAS, and `compare()` below is model-dimension
 *     arithmetic, not an inspection result. Neither may colour a verdict.
 *
 *     The METROLOGY block does state a verdict, and it is a different kind of
 *     fact: `detail.verify` is `assessConformance()` — the same engine, the
 *     same reading and the same limits the FAIR report uses — carried whole
 *     from the server with the reading it judged. Its four states are kept
 *     distinct on purpose. NOT_MEASURED is an absence of evidence,
 *     CANNOT_DETERMINE is evidence that cannot decide (the reading sits
 *     within its own uncertainty of a limit, or the instrument cannot
 *     resolve the band at 4:1), and neither is a failure. Collapsing either
 *     into a red chip would invent a result nobody measured.
 *   - A confidence figure. See dimension-card.tsx.
 *   - A datum that has not been accepted by a human, or an instrument the
 *     shop does not own. Neither is ever invented. The datum section is now
 *     rendered even when there are no `Datum` rows, because on a toleranced
 *     feature "no datum has been established" is a FINDING, not a blank —
 *     silently skipping the section was honest about the data and dishonest
 *     about the engineering.
 *   - A "hold feature" action. There is no hold, quarantine or stop-work
 *     state on Feature, Operation, Setup or Job.
 */

// Typed against the domain union so role renames fail the build here too.
const ROLE_LABEL: Record<FunctionalRole, string> = {
  NONE: "",
  BEARING_SEAT: "Bearing seat",
  SEAL_SURFACE: "Seal surface",
  SHAFT_JOURNAL: "Shaft journal",
  LOCATING_SHOULDER: "Locating shoulder",
  PRESS_FIT: "Press fit",
  SLIP_FIT: "Slip fit",
  THREAD: "Thread",
  MOUNTING_HOLE: "Mounting hole",
  DOWEL_HOLE: "Dowel hole",
  DATUM_FACE: "Datum face",
  INSPECTION_SURFACE: "Inspection surface",
  FLUID_PASSAGE: "Fluid passage",
  COSMETIC: "Cosmetic",
  STRUCTURAL_RIB: "Structural rib",
  FIXTURE_PAD: "Fixture pad",
  CLEARANCE: "Clearance",
};

const CAPABILITY_TONE: Record<string, Tone> = {
  CAPABLE: "pass",
  MARGINAL: "review",
  NOT_CAPABLE: "risk",
  NO_INSTRUMENT: "risk",
  NOT_REQUIRED: "neutral",
};

const DATUM_DOF: Record<string, string> = {
  PLANE: "3 degrees of freedom",
  AXIS: "2 degrees of freedom",
  POINT: "1 degree of freedom",
};

/**
 * The four verification states, as a machinist would say them.
 *
 * NOT_MEASURED and CANNOT_DETERMINE are neither pass nor fail and are not
 * tinted as failures. CANNOT_DETERMINE is `unknown` rather than `review`
 * because it is a statement about the evidence, not a caution about the part.
 */
const VERIFY_LABEL: Record<string, string> = {
  CONFORMS: "Conforms",
  NONCONFORMS: "Does not conform",
  NOT_MEASURED: "Not measured",
  CANNOT_DETERMINE: "Cannot determine",
};

const VERIFY_TONE: Record<string, Tone> = {
  CONFORMS: "pass",
  NONCONFORMS: "risk",
  NOT_MEASURED: "neutral",
  CANNOT_DETERMINE: "unknown",
};

/* THE TWO THRESHOLDS ON THE BAND BAR, AND WHY THERE ARE TWO.

   The bar's axis is `consumedFraction` = the instrument's ± half-width over
   the full tolerance band (engines/inspection-capability.ts). Two different
   engines cut that axis in two different places, and both call their rule
   "4:1", because they divide by different things:

     TARGET_RATIO  0.1    capability: at or below this the instrument is
                          CAPABLE (the gauge-maker's 10:1).
     VERIFY_LIMIT  0.125  conformance: engines/fair.ts trips on
                          `uncertainty * 2 > band / 4`, i.e. u/band > 0.125.
                          Past this the reading CANNOT DETERMINE, whatever
                          the capability chip says.
     CAPABILITY_LIMIT 0.25 capability: past this the instrument is
                          NOT_CAPABLE.

   The first version of this bar drew ticks at 0.1 and 0.25 and captioned the
   0.25 one "limit" while the verdict card 60px below failed at 0.125 — so an
   instrument at 20% sat visibly inside the tick labelled "limit", chipped
   MARGINAL and described as "still discriminating", above a CANNOT DETERMINE
   citing the 4:1 rule. The tick that governs the verdict is the one that gets
   drawn and labelled; the capability limit is stated in words instead of
   being drawn as a second, contradictory line.

   If any of these ratios move in their engine they have to move here in the
   same commit. */
const TARGET_RATIO = 0.1;
const VERIFY_LIMIT_RATIO = 0.125;
const CAPABILITY_LIMIT_RATIO = 0.25;

export function FeaturePanel({
  partId,
  features,
  selectedId,
  onSelect,
  stock,
  details,
  datums,
  hasInspectionPlan,
  inspectionSessionId,
}: {
  partId: string;
  features: Feature[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  stock: Stock | null;
  details: Record<string, FeatureDetail>;
  datums: DatumInfo[];
  hasInspectionPlan: boolean;
  /** The OPEN inspection session, or null. Not the same as the latest session. */
  inspectionSessionId: string | null;
}) {
  const feature = features.find((f) => f.id === selectedId) ?? null;

  if (!feature) {
    return <FeatureIndex features={features} onSelect={onSelect} />;
  }

  const detail = details[feature.id];
  const model = primaryDimension(feature);
  const measured = latestMeasurement(detail?.measurements ?? []);
  const comparison = measured ? compare(feature, measured.value) : null;
  const role = ROLE_LABEL[feature.functionalRole] || null;
  const capability = detail?.capability ?? null;
  const instrument = capability?.bestInstrument ?? null;
  // `details[id]` is an index signature and lies about completeness, so every
  // read of it is optional. `evidence` is null on NOT_MEASURED by construction.
  const verify = detail?.verify ?? null;
  const evidence = verify?.evidence ?? null;
  // The FAIR's own definition of a characteristic (engines/fair.ts) and the
  // inspection session page's filter. A feature outside it appears on no
  // AS9102 form and has no record form on the session page, so titling a
  // "first-article verdict" over it claims an accountability that does not
  // exist — and the CTA below would land on a page with nothing to fill in.
  const isCharacteristic = Boolean(feature.tolerance || feature.critical || feature.inspectionMethod);
  const featureDatums = datums.filter((d) => d.featureId === feature.id);
  const shownDatums = featureDatums.length > 0 ? featureDatums : datums;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      {/* 1 — Header */}
      <header className="border-b border-line-strong bg-card px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <span className="instrument-label">Feature detail</span>
          <button
            onClick={() => onSelect(null)}
            className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted transition-colors hover:text-precision-dim"
          >
            All features
          </button>
        </div>
        <h2 className="mt-1.5 text-[16px] leading-tight font-medium text-platinum">{feature.label}</h2>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {feature.critical && <StatusChip tone="review">Critical feature</StatusChip>}
          <StatusChip tone="neutral">{feature.kind.replace(/_/g, " ").toLowerCase()}</StatusChip>
          {/* The functional role is a classification, not a state. It used to
              render blue, which in this system means active / selected / datum
              / measurement — beside a neutral kind chip that made it look
              selectable. It is neutral now and distinguished by its label. */}
          {role && (
            <span className="instrument-label inline-flex items-center gap-1.5 border border-line-strong px-1.5 py-[2px] text-platinum-dim">
              <span className="text-muted">Role</span>
              {role}
            </span>
          )}
        </div>
      </header>

      {/* 2 — The size block. The hero.

          The heading tells the truth about what is under it: on 10 of the 11
          features on the demo part there is no measurement, and "Measurement
          results" over a model dimension is the kind of mislabel an operator
          acts on. */}
      <Section title={measured ? "Measurement results" : "Model dimension — not yet measured"}>
        <div className="border border-line-strong bg-card">
          <div className="px-3.5 py-3">
            <p className="tech-label">Model geometry</p>
            {model ? (
              <p className="mt-1.5 font-mono text-[36px] leading-none tracking-tight text-platinum tabular-nums">
                {model.prefix}
                {model.value.toFixed(4)}
                <span className="ml-2 text-[13px] tracking-normal text-muted">in</span>
              </p>
            ) : (
              <p className="mt-1.5 font-mono text-[15px] text-platinum">{featureSummary(feature)}</p>
            )}
            <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <span className="text-[11.5px] text-muted">{model ? model.name : "Geometry"}</span>
              <span className="font-mono text-[12px] text-platinum-dim tabular-nums">
                {feature.tolerance ? fmtTol(feature.tolerance) : "no tolerance stated"}
              </span>
            </div>
            {model && <p className="mt-1 text-[11px] leading-relaxed text-muted">{featureSummary(feature)}</p>}
          </div>

          {measured ? (
            <div className="border-t border-line-strong bg-panel px-3.5 py-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="tech-label">Recorded reading</p>
                <span
                  className={`text-[9.5px] font-semibold uppercase tracking-[0.12em] ${
                    RESOLUTION_TONE[measured.resolution] === "review" ? "text-review" : "text-platinum-dim"
                  }`}
                  title={RESOLUTION_DETAIL[measured.resolution] ?? ""}
                >
                  {RESOLUTION_LABEL[measured.resolution] ?? measured.resolution}
                </span>
              </div>
              <p className="mt-1.5 font-mono text-[24px] leading-none text-platinum tabular-nums">
                {measured.value.toFixed(4)}
                <span className="ml-2 text-[12px] text-muted">
                  ±{measured.uncertainty.toFixed(4)} · {measured.repeatCount} readings
                </span>
              </p>

              <div className="mt-2.5 space-y-0">
                <Row label="Instrument" value={measured.instrument ?? "not recorded"} />
                <Row label="Measured from" value={measured.datumLetter ? `Datum ${measured.datumLetter}` : "datum not recorded"} muted={!measured.datumLetter} />
                <Row label="Session" value={measured.sessionName} />
                <Row label="Operator" value={measured.operator ?? "not recorded"} muted={!measured.operator} />
                <Row label="Recorded" value={measured.recordedAt} />
                {/* The Deviation and "Against band" rows that used to sit
                    here were `compare()` — model-dimension arithmetic over
                    whichever reading is newest, of any session mode. The
                    METROLOGY block below now states deviation and limits from
                    the conformance engine, on the inspection reading, and the
                    two disagreed by construction: `compare()` does a bare
                    inside/outside test that never sees measurement
                    uncertainty, so it printed an untinted "inside
                    1.5748–1.5753" directly above the engine's "cannot
                    determine" on the same numbers. One deviation, from the
                    engine that owns the verdict. */}
              </div>

              <p className="mt-2.5 border-t border-line pt-2 text-[11px] leading-relaxed text-muted">
                {measured.sessionName ? `Read in ${measured.sessionName}. ` : ""}
                {verify?.state === "NOT_MEASURED"
                  ? "Verification is judged only on inspection-session readings, and none exists for this feature yet — so this reading describes the article it was taken from, not a verified part."
                  : "Whether this reading verifies the part is stated under Metrology below, on the inspection reading the conformance engine judged."}{" "}
                {RESOLUTION_DETAIL[measured.resolution] ?? ""}
              </p>

              {detail && detail.measurements.length > 1 && (
                <p className="mt-1.5 tech-label">
                  {detail.measurements.length} readings recorded · most recent shown
                </p>
              )}
            </div>
          ) : (
            <p className="border-t border-line-strong bg-panel px-3.5 py-3 text-[11.5px] leading-relaxed text-muted">
              No measurement has been recorded against this feature. The dimension above is the model geometry the plan
              will cut, not something anybody has verified.
            </p>
          )}
        </div>
      </Section>

      {/* 3 — Section sketch */}
      <Section title="Section">
        <SectionSketch feature={feature} stock={stock} />
      </Section>

      {/* 4 — Datum reference. Always rendered.

          When there are no `Datum` rows this section states the absence
          instead of disappearing. No datum is invented: the block below says
          only what is already known — that the table is empty, that this
          feature carries a tolerance, and what that combination means. On a
          ±0.0005" bearing bore, "measured from what?" is the one question the
          panel must not answer with silence. */}
      <Section title="Datum reference">
        {shownDatums.length === 0 ? (
          <div className="border border-line bg-card px-3 py-2.5">
            <p className="text-[12px] leading-relaxed text-platinum">
              No datum has been established on this revision.
            </p>
            {(feature.critical || feature.tolerance) && (
              <p className="mt-1.5 border-l-2 border-l-review pl-2 text-[11.5px] leading-relaxed text-review">
                A toleranced feature with no datum cannot be measured repeatably — the dimension above has no reference
                to be taken from.
              </p>
            )}
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              Datums are proposed and accepted in the reverse-engineering flow. CANVAS will not infer one.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {shownDatums.map((d) => (
              <div key={`${d.system}-${d.letter}`} className="border border-line bg-card px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <span className="datum-frame border border-precision px-1.5 py-0.5 font-mono text-[12px] text-precision">
                      {d.letter}
                    </span>
                    <span className="tech-label">{d.system.toLowerCase()} datum</span>
                  </span>
                  <StatusChip tone={d.accepted ? "pass" : "unknown"}>
                    {d.accepted ? "Established" : "Proposed"}
                  </StatusChip>
                </div>
                <p className="mt-1.5 text-[12px] text-platinum">{d.description}</p>
                <p className="tech-label mt-1">
                  {d.geometryType.toLowerCase()} · {DATUM_DOF[d.geometryType] ?? "degrees of freedom not stated"}
                </p>
              </div>
            ))}
            {featureDatums.length === 0 && (
              <p className="text-[11px] leading-relaxed text-muted">
                No datum references this feature directly. The datums above belong to the revision.
              </p>
            )}
          </div>
        )}
      </Section>

      {/* 5 — Metrology. Always rendered.

          Absence is a finding here, the same way it is under Datum reference:
          the case a metrology block most needs to state is the one where the
          shop owns nothing that can make the measurement, and the old
          `{instrument && capability &&}` gate made the section vanish in
          exactly that case. */}
      <Section title="Metrology">
        {capability && capability.verdict === "NOT_REQUIRED" ? (
          <p className="text-[11.5px] leading-relaxed text-muted">
            No tolerance is stated on this feature, so there is nothing for an instrument to be capable of. Capability
            is assessed against a tolerance band, not against a dimension.
          </p>
        ) : !instrument || !capability ? (
          <div className="border border-line bg-card px-3 py-2.5">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[12.5px] leading-snug text-platinum">No instrument can make this measurement.</p>
              <StatusChip tone={CAPABILITY_TONE[capability?.verdict ?? "NO_INSTRUMENT"] ?? "risk"}>
                {capability?.label ?? "No instrument"}
              </StatusChip>
            </div>
            {capability?.requiredUncertainty != null && (
              <div className="mt-2">
                <Row
                  label="Required"
                  tone="risk"
                  value={`±${capability.requiredUncertainty.toFixed(5)} to reach 10:1`}
                />
              </div>
            )}
            <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-muted">
              {capability?.reason ?? "No metrology device on record reaches this geometry and covers this nominal."}
            </p>
          </div>
        ) : (
          <div className="border border-line bg-card px-3 py-2.5">
            <div className="flex items-start justify-between gap-2">
              {/* The instrument, drawn. Selected by the real deviceType off
                  the MetrologyDevice record — an unrecognised type draws
                  nothing and the description stands on its own. */}
              <div className="flex min-w-0 items-start gap-2.5">
                {hasInstrumentGlyph(instrument.deviceType) && (
                  <InstrumentGlyph deviceType={instrument.deviceType} className="mt-[1px] w-[62px] shrink-0" />
                )}
                <p className="min-w-0 text-[12.5px] leading-snug text-platinum">{instrument.description}</p>
              </div>
              <StatusChip tone={CAPABILITY_TONE[capability.verdict] ?? "unknown"}>{capability.label}</StatusChip>
            </div>

            {/* Band consumption. A physical ratio of the instrument's ± to
                the stated band — not a score, not a confidence, not progress.
                The printed number is never clamped even when the fill is.

                What is plotted is the BEST INSTRUMENT THE SHOP OWNS for this
                geometry, which is not necessarily the one that took the
                reading: the inspection session lets an operator pick any
                device in the drawer. Where they differ the verdict card below
                says so rather than letting a green bar corroborate a verdict
                it had no part in. */}
            {capability.toleranceBand != null && capability.consumedFraction != null && (
              <div className="mt-2.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="tech-label">Best on hand consumes</span>
                  <span
                    className={`font-mono text-[11.5px] tabular-nums ${
                      capability.verdict === "CAPABLE" ? "text-platinum" : "text-review"
                    }`}
                  >
                    {(capability.consumedFraction * 100).toFixed(0)}%
                  </span>
                </div>
                <div
                  className="relative mt-1 h-1 bg-line"
                  role="img"
                  aria-label={`The best instrument on hand has an uncertainty of ${(capability.consumedFraction * 100).toFixed(0)} percent of the tolerance band. The capability target is ${TARGET_RATIO * 100} percent and a reading past ${VERIFY_LIMIT_RATIO * 100} percent cannot verify the dimension.`}
                >
                  <div
                    className={`h-1 ${
                      capability.verdict === "CAPABLE"
                        ? "bg-pass/70"
                        : capability.verdict === "MARGINAL"
                          ? "bg-review/70"
                          : "bg-risk/70"
                    }`}
                    style={{ width: `${Math.min(Math.max(capability.consumedFraction, 0), 1) * 100}%` }}
                  />
                  {/* Two ticks, both real: the capability target, and the
                      threshold past which the conformance engine below stops
                      being able to decide. */}
                  <span aria-hidden className="absolute top-[-2px] h-[5px] w-px bg-platinum-dim" style={{ left: `${TARGET_RATIO * 100}%` }} />
                  <span aria-hidden className="absolute top-[-3px] h-[7px] w-px bg-review" style={{ left: `${VERIFY_LIMIT_RATIO * 100}%` }} />
                  {capability.consumedFraction > 1 && (
                    <span aria-hidden className="absolute right-0 top-[-2px] text-[8px] leading-[5px] text-risk">▸</span>
                  )}
                </div>
                <p className="mt-1 text-[10.5px] leading-snug text-muted">
                  ±{instrument.uncertainty.toFixed(4)} of the {capability.toleranceBand.toFixed(4)} band. Ticks at 10%
                  (capability target) and 12.5% — past that a reading cannot verify this dimension whatever the chip
                  above says, because the two rules divide by different things. The capability chip turns NOT CAPABLE
                  at {CAPABILITY_LIMIT_RATIO * 100}%.
                </p>
                {!instrument.calibrated && (
                  <p className="mt-1 text-[10.5px] leading-snug text-risk">
                    This instrument is not calibrated, so the ratio above is arithmetic on an untraceable number, not
                    evidence.
                  </p>
                )}
              </div>
            )}

            <div className="mt-2">
              <Row
                label="Range"
                value={
                  instrument.rangeMin != null && instrument.rangeMax != null
                    ? `${fmt(instrument.rangeMin, 3)}–${fmt(instrument.rangeMax, 3)} in`
                    : "not stated"
                }
                muted={instrument.rangeMin == null || instrument.rangeMax == null}
              />
              <Row label="Resolution" value={instrument.resolution.toFixed(4)} />
              <Row label="Uncertainty" value={`±${instrument.uncertainty.toFixed(4)}`} />
              {/* The "Consumes" row that used to sit here said the same thing
                  as the band bar above, in the same words. One statement. */}
              <Row
                label="Calibration"
                tone={instrument.calibrated ? undefined : "risk"}
                value={
                  instrument.calibrated
                    ? instrument.calibrationDue
                      ? `due ${instrument.calibrationDue.slice(0, 10)}`
                      : "recorded, no date"
                    : "not recorded"
                }
                muted={instrument.calibrated && !instrument.calibrationDue}
              />
            </div>
            <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-muted">{capability.reason}</p>
            {/* How to actually take it. Collapsed — an experienced machinist
                does not need to be told how to rock a bore gauge on every
                feature, and a panel that shouts technique gets ignored
                wholesale. Renders nothing for an instrument with none on
                file. */}
            <MeasurementTechnique
              deviceType={instrument.deviceType}
              geometry={(capability.geometry ?? null) as Parameters<typeof MeasurementTechnique>[0]["geometry"]}
              instrumentLabel={instrument.description}
            />
          </div>
        )}

        {/* The verdict, and the reading it was reached on.

            Every number below travels from the server inside
            `verify.evidence` — the same reading, nominal and limits
            `assessConformance` was handed. Nothing here is recomputed, so
            the status and the numbers beside it cannot disagree. */}
        {verify && isCharacteristic && (
          <div className="mt-2 border border-line-strong bg-card">
            <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
              <span className="tech-label">First-article verdict</span>
              <StatusChip tone={VERIFY_TONE[verify.state] ?? "unknown"}>
                {VERIFY_LABEL[verify.state] ?? verify.state}
              </StatusChip>
            </div>

            {evidence ? (
              <>
                <div className="grid grid-cols-2 gap-px bg-line">
                  {(
                    [
                      [
                        "Nominal",
                        evidence.nominal !== null ? evidence.nominal.toFixed(4) : "none",
                        evidence.nominal !== null ? undefined : "muted",
                      ],
                      [evidence.valueWasResolved ? "Resolved" : "Measured", evidence.value.toFixed(4), undefined],
                      [
                        "Deviation",
                        evidence.nominal !== null
                          ? `${evidence.value - evidence.nominal >= 0 ? "+" : ""}${(evidence.value - evidence.nominal).toFixed(4)}`
                          : "—",
                        evidence.nominal !== null ? undefined : "muted",
                      ],
                      [
                        "Limits",
                        evidence.lo !== null && evidence.hi !== null
                          ? `${evidence.lo.toFixed(4)} – ${evidence.hi.toFixed(4)}`
                          : evidence.tolerancePlus !== null || evidence.toleranceMinus !== null
                            ? // A tolerance IS stated; there is simply no single
                              // nominal for the engine to hang it on. Printing
                              // "none stated" here told the inspector the drawing
                              // carries no tolerance, which is a lie about the
                              // drawing rather than a fact about the engine.
                              `+${(evidence.tolerancePlus ?? 0).toFixed(4)} / −${(evidence.toleranceMinus ?? 0).toFixed(4)}, unanchored`
                            : "none stated",
                        evidence.lo !== null && evidence.hi !== null ? undefined : "muted",
                      ],
                    ] as const
                  ).map(([label, value, mutedFlag]) => (
                    <div key={label} className="bg-card px-3 py-2">
                      <p className="tech-label">{label}</p>
                      <p
                        className={`mt-0.5 font-mono text-[14px] tabular-nums ${
                          mutedFlag === "muted" ? "text-unknown" : "text-platinum"
                        }`}
                      >
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="px-3 py-2">
                  {verify.state === "NONCONFORMS" && verify.departure !== null && (
                    <p className="font-mono text-[11.5px] text-risk tabular-nums">
                      {verify.departure > 0 ? "+" : ""}
                      {verify.departure.toFixed(4)} beyond the limit
                    </p>
                  )}
                  {verify.reason && (
                    <p className="text-[11px] leading-relaxed text-muted">{verify.reason}</p>
                  )}
                  <p className="mt-1 text-[10.5px] leading-relaxed text-muted">
                    ±{evidence.uncertainty.toFixed(4)} · {evidence.instrument ?? "instrument not recorded"} ·{" "}
                    {evidence.sessionName} · {evidence.recordedAt}
                  </p>
                  {/* The card above plots the best instrument on hand. The
                      session lets an operator record with any device in the
                      drawer, so the two are frequently not the same tool —
                      and a green capability bar sitting over a green verdict
                      reads as one corroborated story when it is two. */}
                  {evidence.instrument && instrument && evidence.instrument !== instrument.description && (
                    <p className="mt-1 text-[10.5px] leading-relaxed text-review">
                      This reading was taken with a different instrument than the capability assessment above, which
                      rates the {instrument.description}. The verdict is judged on the reading&apos;s own ±
                      {evidence.uncertainty.toFixed(4)}.
                    </p>
                  )}
                </div>
              </>
            ) : (
              <p className="px-3 py-2.5 text-[11.5px] leading-relaxed text-muted">
                {verify.reason ?? "No inspection-session measurement has been recorded against this feature."}{" "}
                Reverse-engineering readings do not verify a part — they describe the article they were taken from.
              </p>
            )}
          </div>
        )}
      </Section>

      {/* 6 — Inspection method */}
      <Section title="Inspection method">
        {feature.inspectionMethod || detail?.inspectionItem ? (
          <div className="space-y-2">
            {feature.inspectionMethod && (
              <p className="text-[12.5px] leading-relaxed text-platinum">{feature.inspectionMethod}</p>
            )}
            {detail?.inspectionItem && (
              <div className="border border-line bg-card px-3 py-2.5">
                <p className="tech-label">From the inspection plan</p>
                <p className="mt-1 text-[12px] text-platinum">{detail.inspectionItem.label}</p>
                <div className="mt-1.5">
                  <Row
                    label="Nominal"
                    value={`${detail.inspectionItem.nominal.toFixed(4)} ${
                      detail.inspectionItem.plusTol === detail.inspectionItem.minusTol
                        ? `±${detail.inspectionItem.plusTol.toFixed(4)}`
                        : `+${detail.inspectionItem.plusTol.toFixed(4)}/-${detail.inspectionItem.minusTol.toFixed(4)}`
                    }`}
                  />
                  <Row label="Method" value={detail.inspectionItem.method} />
                  {detail.inspectionItem.deviceType && (
                    <Row label="Device class" value={detail.inspectionItem.deviceType.replace(/_/g, " ").toLowerCase()} />
                  )}
                </div>
              </div>
            )}
            <p className="text-[11px] leading-relaxed text-muted">Stored text from the feature and the plan.</p>
          </div>
        ) : (
          <p className="text-[11.5px] leading-relaxed text-muted">
            No inspection method is assigned to this feature.
            {feature.critical
              ? " It is flagged critical, which makes that a gap rather than an omission — a toleranced dimension nobody has a method for is a dimension nobody is going to check."
              : ""}
          </p>
        )}
      </Section>

      {/* 7 — Actions */}
      <Section title="Actions">
        <div className="flex flex-col gap-1.5">
          <PanelAction href={`/parts/${partId}/features/${feature.id}`} primary>
            Function and fit
          </PanelAction>
          {/* Where a first-article reading is actually taken.

              This pointed at `/reverse-engineer/{latestSession}` — a different
              flow with a different meaning. That session id carries no mode
              filter, so it could be a reverse-engineering session, and the RE
              screen records a reading about the article in front of you and
              reasons about nominals. An inspection reading verifies the part
              against its tolerance and is recorded on the inspection session
              page, which requires an instrument and filters
              `mode: "INSPECTION"`.

              With no open inspection session the honest destination is the
              inspection page, which is where the Start session action lives —
              the button says so rather than promising a form. */}
          {/* Only a characteristic has a record form waiting at the other
              end. For anything else the session page renders no form for this
              feature, so the button would be a door into an empty room.

              With no open session the single honest destination is the
              inspection page — and "Inspection plan" already goes there, so
              the two are not both rendered pointing at one URL under two
              names. The label does not claim to start a session, because
              following it does not: the Start session control lives there. */}
          {isCharacteristic &&
            (inspectionSessionId ? (
              <PanelAction href={`/parts/${partId}/inspection/session/${inspectionSessionId}`}>
                Record a measurement
              </PanelAction>
            ) : (
              <PanelAction href={`/parts/${partId}/inspection`}>Inspection — start a session</PanelAction>
            ))}
          {hasInspectionPlan && (!isCharacteristic || inspectionSessionId) && (
            <PanelAction href={`/parts/${partId}/inspection`}>Inspection plan</PanelAction>
          )}
        </div>
      </Section>

      {/* The two standing statements about what CANVAS is. They are true of
          every feature and never change, so they are stated once at the foot
          of the panel rather than repeated as multi-line disclaimers inside
          two sections, where they outweighed the values they qualify.

          Each is now its own named disclosure. "What this panel is not" was a
          heading written for whoever built the panel; a machinist wants to
          know whether there is surface fitting behind a number. The summary
          line names the limit and stays visible — the disclosure hides the
          explanation, never the existence of the limit. Both sentences remain
          verbatim; nothing has been softened. */}
      <footer className="space-y-2 px-4 py-3.5">
        <LimitsDisclosure label="No surface fitting">
          CANVAS does no surface fitting — there is no point cloud and no least-squares routine behind any of this.
        </LimitsDisclosure>
        <LimitsDisclosure label="No hold or quarantine state">
          There is no hold or quarantine state on a feature in CANVAS, so there is no button above that would appear to
          apply one. A concern is recorded as a disagreement, which is evidence and clears nothing.
        </LimitsDisclosure>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The index — what the panel shows when nothing is selected           */
/* ------------------------------------------------------------------ */

function FeatureIndex({ features, onSelect }: { features: Feature[]; onSelect: (id: string | null) => void }) {
  /**
   * The features nobody has said anything about.
   *
   * This line used to read "9 of 11 carry a role or a critical flag", which was
   * wrong three times over.
   *
   * It counted the wrong end. Nine classified features are not the story; the
   * two nobody classified are — the same reason part-status.tsx refuses to say
   * "nine of eleven gates pass".
   *
   * It welded two axes with an OR. A functional role says what a feature is
   * for; `critical` is a severity flag. Their union has no name a machinist
   * would use, and it put the CLEARANCE relief pocket in the same bucket as the
   * ±0.0005"/-0 bearing bore. Criticality is already reported per row by the
   * Crit chip below, where it means something. What the list cannot show is a
   * missing role — ROLE_LABEL maps NONE to "", so an unclassified feature is
   * visually identical to a classified one. That gap is what the header is for.
   *
   * And it hid itself exactly when it mattered: wrapped in `critical.length > 0`,
   * the line vanished on a part where nothing had been classified at all.
   * Inverted, silence now means nothing is outstanding — which is what silence
   * means everywhere else in this workspace.
   *
   * The predicate is role alone, not `!critical && role === "NONE"`, because
   * the hazard keys on role alone: features.ts says CAM and the process advisor
   * may relax geometry that carries no role, whatever its critical flag.
   *
   * NONE is an absence, not a decision. It is a schema default (schema.prisma
   * and the zod schema both), the model is not required to supply the field,
   * and no screen in the product writes it. When this model wants to say
   * "nothing hangs on this" it has CLEARANCE and COSMETIC, and the demo part
   * uses CLEARANCE. So the copy says only that no statement exists — not that
   * the feature is unverified, unapproved or incomplete, none of which the data
   * supports. There is deliberately no affirmative counterpart at zero: a role
   * can arrive from an accepted AI proposal byte-identical to a human's, so
   * "function stated on every feature" would be certifying something nothing
   * here has established.
   */
  const unstated = features.filter((f) => f.functionalRole === "NONE");

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <header className="border-b border-line-strong bg-card px-4 py-3">
        <span className="instrument-label">Feature detail</span>
        <p className="mt-1.5 text-[13px] leading-relaxed text-platinum">No feature selected.</p>
        <p className="mt-1 text-[11.5px] leading-relaxed text-muted">
          Click a feature on the model, choose an operation in the runway below, or pick one from the list.
        </p>
      </header>

      {features.length === 0 ? (
        <div className="p-4">
          <div className="border border-dashed border-line-strong px-3 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-platinum-dim">No features</p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
              A part with no features has no manufacturing plan. Add features, or accept the proposals from the intake.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-3">
          {unstated.length > 0 && (
            <p className="instrument-label mb-1.5">
              {unstated.length} {unstated.length === 1 ? "feature" : "features"} — function not stated
            </p>
          )}
          <ul className="space-y-px">
            {features.map((f) => (
              <li key={f.id}>
                <button
                  onClick={() => onSelect(f.id)}
                  className="w-full border-b border-line border-l-2 border-l-transparent px-2.5 py-2 text-left transition-colors hover:border-l-precision hover:bg-card"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-[12px] text-platinum">{f.label}</span>
                    {f.critical && <StatusChip tone="review">Crit</StatusChip>}
                  </span>
                  <span className="tech-label mt-0.5 block truncate">{featureSummary(f)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Panel primitives                                                    */
/* ------------------------------------------------------------------ */

/**
 * One instrument block.
 *
 * The heading is the grotesk in the dim reading colour with a strong rule
 * under it, so the panel reads as a stack of bounded blocks rather than as one
 * continuous column. It used to be 10px muted monospace — quieter than the
 * body text beneath it, which inverts the hierarchy and is also part of why
 * half the workspace measured as monospace.
 */
function Section({ title, children, last }: { title: string; children: ReactNode; last?: boolean }) {
  return (
    <section className={`px-4 py-3.5 ${last ? "" : "border-b border-line"}`}>
      <h3
        className="instrument-label mb-2 pb-1 text-platinum-dim"
        style={{ borderBottom: "1px solid var(--canvas-border-strong)" }}
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  tone,
  muted,
}: {
  label: string;
  value: string;
  tone?: "review" | "risk";
  muted?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 py-1 last:border-0">
      <span className="tech-label shrink-0">{label}</span>
      <span
        className={`min-w-0 truncate text-right font-mono text-[11.5px] tabular-nums ${
          tone === "risk" ? "text-risk" : tone === "review" ? "text-review" : muted ? "text-unknown" : "text-platinum"
        }`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function PanelAction({ href, children, primary }: { href: string; children: ReactNode; primary?: boolean }) {
  return (
    <Link
      href={href}
      className={`flex items-center justify-between border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] transition-colors ${
        primary
          ? "border-precision bg-precision/10 text-precision-dim hover:bg-precision/20"
          : "border-line-strong bg-card text-platinum-dim hover:border-platinum-dim hover:text-platinum"
      }`}
    >
      <span>{children}</span>
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M2 8 L8 2 M4 2 H8 V6" stroke="currentColor" strokeWidth="1.1" fill="none" />
      </svg>
    </Link>
  );
}
